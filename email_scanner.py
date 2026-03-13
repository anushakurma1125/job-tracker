"""Gmail email scanner for detecting job rejection emails."""

import json
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from anthropic import Anthropic


# Broad rejection keyword phrases for Gmail search
REJECTION_KEYWORDS = [
    # Direct rejection phrases
    '"unfortunately"',
    '"regret to inform"',
    '"other candidates"',
    '"moved forward with"',
    '"position has been filled"',
    '"not selected"',
    '"decided not to proceed"',
    '"will not be moving forward"',
    '"not be able to offer"',
    '"decided to move forward with other"',
    '"not a match"',
    '"after careful consideration"',
    # Common rejection phrases often missed
    '"thank you for your interest"',
    '"we will not be proceeding"',
    '"no longer under consideration"',
    '"has been closed"',
    '"we have decided to pursue"',
    '"not moving forward"',
    '"did not select"',
    '"unable to offer"',
    '"chosen not to move forward"',
    '"we went with another"',
    '"appreciate your interest"',
    # Application status update subjects
    'subject:"application update"',
    'subject:"application status"',
    'subject:"regarding your application"',
    'subject:"your application"',
    'subject:"update on your"',
    'subject:"hiring update"',
]

# Maximum emails to process per scan to stay within Render's request timeout.
# Each email requires a Gmail API call + Claude classification time.
# Budget: ~50 emails = ~15s Gmail fetch (batch) + ~10s Claude = ~25s total.
MAX_EMAILS_PER_SCAN = 100


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


def _batch_fetch_messages(service, message_refs):
    """
    Fetch message details in batches using Gmail batch API.
    Much faster than fetching one-by-one (100 messages in ~2s vs ~30s).
    """
    emails = []
    BATCH_SIZE = 50  # Gmail batch API limit is 100, use 50 for safety

    for batch_start in range(0, len(message_refs), BATCH_SIZE):
        batch_refs = message_refs[batch_start:batch_start + BATCH_SIZE]
        batch_results = {}

        def make_callback(msg_id):
            def callback(request_id, response, exception):
                if exception is not None:
                    print(f"[Email Scan] Batch fetch error for {msg_id}: {exception}")
                    return
                batch_results[msg_id] = response
            return callback

        batch = service.new_batch_http_request()
        for ref in batch_refs:
            msg_id = ref["id"]
            batch.add(
                service.users().messages().get(
                    userId="me", id=msg_id, format="metadata",
                    metadataHeaders=["Subject", "From"]
                ),
                callback=make_callback(msg_id),
            )
        batch.execute()

        # Collect results in order
        for ref in batch_refs:
            msg_id = ref["id"]
            if msg_id in batch_results:
                email_info = _extract_email_info(batch_results[msg_id])
                email_info["msg_id"] = msg_id
                emails.append(email_info)

    return emails


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
            max_tokens=2048,
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


def _paginated_search(service, query, max_results=500):
    """Fetch all message IDs matching a Gmail query, with pagination."""
    messages = []
    page_token = None
    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": min(200, max_results)}
        if page_token:
            kwargs["pageToken"] = page_token
        try:
            results = service.users().messages().list(**kwargs).execute()
        except Exception as e:
            print(f"[Email Scan] Gmail search error: {e}")
            break
        messages.extend(results.get("messages", []))
        page_token = results.get("nextPageToken")
        if not page_token or len(messages) >= max_results:
            break
    return messages[:max_results]


def scan_for_rejections(credentials_json, jobs, since_date):
    """
    Scan Gmail for rejection emails and match them to tracked jobs.

    Uses two search strategies:
    1. Broad rejection keyword search (catches emails with common rejection phrases)
    2. Company-specific search (catches ALL emails from companies the user applied to)

    Results are combined, deduplicated, and classified by Claude.
    Uses Gmail batch API for fast message fetching.
    """
    service = _build_gmail_service(credentials_json)

    # Build date filter
    epoch = _epoch_from_date(since_date)
    date_filter = f"after:{epoch}" if epoch else ""

    print(f"[Email Scan] Starting scan. since_date={since_date}, epoch={epoch}, date_filter={date_filter}")
    print(f"[Email Scan] Active jobs: {len(jobs)}")

    # ── Strategy 1: Rejection keyword search ──
    # Split keywords into two smaller queries to avoid Gmail query length limits
    mid = len(REJECTION_KEYWORDS) // 2
    kw_batch1 = REJECTION_KEYWORDS[:mid]
    kw_batch2 = REJECTION_KEYWORDS[mid:]

    keyword_msgs = []
    for kw_batch in [kw_batch1, kw_batch2]:
        query = f"{date_filter} ({' OR '.join(kw_batch)})".strip()
        print(f"[Email Scan] Keyword query ({len(query)} chars): {query[:120]}...")
        msgs = _paginated_search(service, query, max_results=150)
        keyword_msgs.extend(msgs)

    # ── Strategy 2: Company-specific search ──
    # Search for emails from/about each company the user applied to
    companies = list(set(
        j.get("company", "").strip()
        for j in jobs
        if j.get("company", "").strip()
    ))

    company_msgs = []
    if companies:
        # Build company query in batches to avoid too-long query strings
        COMPANY_BATCH = 10
        for i in range(0, len(companies), COMPANY_BATCH):
            batch = companies[i:i + COMPANY_BATCH]
            parts = []
            for c in batch:
                # Search from: and subject: for each company
                parts.append(f'from:"{c}"')
                parts.append(f'subject:"{c}"')
            company_query = f"{date_filter} ({' OR '.join(parts)})".strip()
            batch_msgs = _paginated_search(service, company_query, max_results=100)
            company_msgs.extend(batch_msgs)

    # ── Combine & deduplicate ──
    seen_ids = set()
    all_messages = []
    for msg in keyword_msgs + company_msgs:
        if msg["id"] not in seen_ids:
            seen_ids.add(msg["id"])
            all_messages.append(msg)

    print(f"[Email Scan] keyword_hits={len(keyword_msgs)}, company_hits={len(company_msgs)}, combined_unique={len(all_messages)}")

    if not all_messages:
        return {"emails_checked": 0, "rejections_found": 0, "details": []}

    # Cap to prevent timeout — process most recent emails first
    if len(all_messages) > MAX_EMAILS_PER_SCAN:
        print(f"[Email Scan] Capping from {len(all_messages)} to {MAX_EMAILS_PER_SCAN} emails")
        all_messages = all_messages[:MAX_EMAILS_PER_SCAN]

    # Fetch message details using batch API (much faster than one-by-one)
    print(f"[Email Scan] Batch-fetching {len(all_messages)} message details...")
    emails = _batch_fetch_messages(service, all_messages)
    print(f"[Email Scan] Fetched {len(emails)} email details")

    if not emails:
        return {"emails_checked": 0, "rejections_found": 0, "details": []}

    # Extract company names from jobs for matching
    company_names = [j.get("company", "") for j in jobs]

    # Classify with Claude in batches of 25
    BATCH_SIZE = 25
    classifications = []
    for batch_start in range(0, len(emails), BATCH_SIZE):
        batch = emails[batch_start:batch_start + BATCH_SIZE]
        print(f"[Email Scan] Classifying batch {batch_start // BATCH_SIZE + 1} ({len(batch)} emails)...")
        batch_results = _classify_with_claude(batch, company_names)
        # Adjust indices to be global
        for result in batch_results:
            result["index"] = result.get("index", -1) + batch_start
        classifications.extend(batch_results)

    # Match rejections to jobs
    details = []
    matched_job_ids = set()  # Avoid duplicate rejections for same job
    for classification in classifications:
        if not classification.get("is_rejection"):
            continue
        idx = classification.get("index", -1)
        if idx < 0 or idx >= len(emails):
            continue
        email = emails[idx]
        company = classification.get("company", "")
        matched_job = _match_to_job(company, jobs)
        if matched_job and matched_job["id"] not in matched_job_ids:
            matched_job_ids.add(matched_job["id"])
            details.append({
                "job_id": matched_job["id"],
                "job_company": matched_job.get("company", ""),
                "job_role": matched_job.get("role", ""),
                "email_subject": email["subject"],
                "sender": email["sender"],
            })

    print(f"[Email Scan] Done. Checked {len(emails)}, found {len(details)} rejections.")

    return {
        "emails_checked": len(emails),
        "rejections_found": len(details),
        "details": details,
    }
