"""Gmail email scanner for detecting job rejection emails."""

import json
import base64
import time
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from anthropic import Anthropic


REJECTION_QUERY = (
    '(subject:"unfortunately" OR subject:"regret to inform" OR subject:"other candidates" '
    'OR subject:"moved forward with" OR subject:"position has been filled" '
    'OR subject:"not selected" OR subject:"decided not to proceed" '
    'OR subject:"will not be moving forward" OR subject:"not be able to offer" '
    'OR "we will not be moving forward" OR "decided to move forward with other" '
    'OR "not a match" OR "after careful consideration")'
)


def _build_gmail_service(credentials_json):
    """Build a Gmail API service from stored credentials JSON."""
    creds_data = json.loads(credentials_json)
    creds = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
        scopes=creds_data.get("scopes", ["https://www.googleapis.com/auth/gmail.readonly"]),
    )
    return build("gmail", "v1", credentials=creds)


def _epoch_from_date(date_str):
    """Convert a date string (YYYY-MM-DD) or datetime object to epoch seconds."""
    if not date_str:
        return None
    try:
        # Handle datetime/date objects directly (e.g. from PostgreSQL)
        if hasattr(date_str, "timestamp"):
            return int(date_str.timestamp())
        if hasattr(date_str, "strftime"):
            date_str = date_str.strftime("%Y-%m-%d")
        # Handle "YYYY-MM-DD HH:MM:SS" string format
        date_str = str(date_str).split(" ")[0]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def _extract_email_info(msg):
    """Extract subject, sender, and snippet from a Gmail message."""
    headers = msg.get("payload", {}).get("headers", [])
    subject = ""
    sender = ""
    for h in headers:
        name = h.get("name", "").lower()
        if name == "subject":
            subject = h.get("value", "")
        elif name == "from":
            sender = h.get("value", "")
    snippet = msg.get("snippet", "")
    return {"subject": subject, "sender": sender, "snippet": snippet}


def _classify_with_claude(emails_batch, companies):
    """Use Claude Haiku to classify emails as rejections and extract company names."""
    if not emails_batch:
        return []

    client = Anthropic()
    companies_list = ", ".join(set(c for c in companies if c))

    prompt = f"""You are analyzing emails to identify job application rejections.

Here are the companies the user has applied to: {companies_list}

For each email below, determine:
1. Is this a job rejection email? (true/false)
2. If yes, which company from the list above sent it? Match by company name or sender domain.

Return a JSON array with one object per email:
[{{"index": 0, "is_rejection": true/false, "company": "matched company name or empty string"}}]

Return ONLY the JSON array, no other text.

Emails:
"""
    for i, email in enumerate(emails_batch):
        prompt += f"\n--- Email {i} ---\nFrom: {email['sender']}\nSubject: {email['subject']}\nSnippet: {email['snippet']}\n"

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text.strip()
        # Handle markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        return json.loads(response_text)
    except Exception as e:
        print(f"Claude classification error: {e}")
        return []


def _match_to_job(company_name, jobs):
    """Match a company name to a job in the list using fuzzy matching."""
    if not company_name:
        return None
    company_lower = company_name.lower().strip()
    for job in jobs:
        job_company = (job.get("company") or "").lower().strip()
        if not job_company:
            continue
        # Exact match
        if company_lower == job_company:
            return job
        # Substring match (either direction)
        if company_lower in job_company or job_company in company_lower:
            return job
    return None


def scan_for_rejections(credentials_json, jobs, since_date):
    """
    Scan Gmail for rejection emails and match them to tracked jobs.

    Args:
        credentials_json: JSON string of Gmail OAuth credentials
        jobs: List of job dicts (with 'company', 'id', etc.)
        since_date: Date string (YYYY-MM-DD) to scan from

    Returns:
        dict with keys: emails_checked, rejections_found, details (list)
    """
    service = _build_gmail_service(credentials_json)

    # Build query with date filter
    epoch = _epoch_from_date(since_date)
    query = REJECTION_QUERY
    if epoch:
        query = f"after:{epoch} {query}"

    # Search Gmail with pagination
    messages = []
    page_token = None
    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 100}
        if page_token:
            kwargs["pageToken"] = page_token
        results = service.users().messages().list(**kwargs).execute()
        messages.extend(results.get("messages", []))
        page_token = results.get("nextPageToken")
        if not page_token or len(messages) >= 500:
            break

    if not messages:
        return {"emails_checked": 0, "rejections_found": 0, "details": []}

    # Fetch message details
    emails = []
    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="metadata",
            metadataHeaders=["Subject", "From"]
        ).execute()
        email_info = _extract_email_info(msg)
        email_info["msg_id"] = msg_ref["id"]
        emails.append(email_info)

    # Extract company names from jobs for matching
    companies = [j.get("company", "") for j in jobs]

    # Classify with Claude in batches of 20 to avoid context limits
    BATCH_SIZE = 20
    classifications = []
    for batch_start in range(0, len(emails), BATCH_SIZE):
        batch = emails[batch_start:batch_start + BATCH_SIZE]
        batch_results = _classify_with_claude(batch, companies)
        # Adjust indices to be global
        for result in batch_results:
            result["index"] = result.get("index", -1) + batch_start
        classifications.extend(batch_results)

    # Match rejections to jobs
    details = []
    for classification in classifications:
        if not classification.get("is_rejection"):
            continue
        idx = classification.get("index", -1)
        if idx < 0 or idx >= len(emails):
            continue
        email = emails[idx]
        company = classification.get("company", "")
        matched_job = _match_to_job(company, jobs)
        if matched_job:
            details.append({
                "job_id": matched_job["id"],
                "job_company": matched_job.get("company", ""),
                "job_role": matched_job.get("role", ""),
                "email_subject": email["subject"],
                "sender": email["sender"],
            })

    return {
        "emails_checked": len(emails),
        "rejections_found": len(details),
        "details": details,
    }
