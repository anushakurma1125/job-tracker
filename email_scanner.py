"""Gmail email scanner for detecting job rejection emails.

Three-stage classification pipeline:
  Stage 1 (Gmail search): High-recall keyword/company search — casts a wide net.
  Stage 2 (Rule-based):   Deterministic phrase matching on full email body — handles
                          the ~80% of rejections that use boilerplate language. Zero cost.
  Stage 3 (LLM):          Claude classifies only ambiguous emails that Stage 2 couldn't
                          confidently decide. Must cite the exact rejection sentence.
"""

import base64
import json
import re
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from anthropic import Anthropic


# ── Stage 1: Gmail keyword search (high recall) ──

REJECTION_KEYWORDS = [
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
    'subject:"application update"',
    'subject:"application status"',
    'subject:"regarding your application"',
    'subject:"your application"',
    'subject:"update on your"',
    'subject:"hiring update"',
]

# First scan: no keyword filters, scan ALL emails for maximum recall.
MAX_EMAILS_FIRST_SCAN = 5000
MAX_EMAILS_INCREMENTAL = 100


# ── Stage 2: Deterministic phrase matching (high precision) ──

# Phrases that are STRONG rejection signals — if found in the email body,
# classify as rejection without needing the LLM.
STRONG_REJECTION_PHRASES = [
    "we have decided to move forward with other candidates",
    "we have decided to pursue other candidates",
    "we will not be moving forward with your",
    "we are not moving forward with your",
    "we've decided to move forward with other",
    "we've decided to pursue other candidates",
    "decided not to move forward with your",
    "decided not to proceed with your",
    "not selected for",
    "will not be proceeding with your application",
    "will not be moving forward with your application",
    "we regret to inform you",
    "we are unable to offer you",
    "position has been filled",
    "role has been filled",
    "we will not be extending an offer",
    "we won't be moving forward",
    "unfortunately, we have chosen",
    "unfortunately, we will not",
    "unfortunately we will not",
    "unfortunately, after careful",
    "after careful consideration, we have decided",
    "after careful review, we have decided",
    "we have decided not to move forward",
    "your application was not selected",
    "your application has not been selected",
    "we chose not to move forward",
    "we are not able to offer you",
    "we have filled the position",
    "the position has been closed",
    "we have selected another candidate",
    "we went with another candidate",
    "chosen to move forward with another",
    "no longer being considered",
    "no longer under consideration",
    "your candidacy for .{0,50} has not been",
    "not be advancing your application",
]

# Phrases that indicate the email is NOT a rejection — even if it contains
# some matching keywords. These are whitelist overrides.
NON_REJECTION_PHRASES = [
    "we'd like to schedule",
    "we would like to schedule",
    "we'd like to invite you",
    "we would like to invite you",
    "please find your offer",
    "we are pleased to offer",
    "congratulations",
    "we're excited to extend",
    "next steps in the process",
    "moving you forward",
    "we'd like to move forward with you",
    "would like to move you to the next",
    "invite you to interview",
    "looking forward to speaking",
]

# Compile patterns once for performance
_STRONG_PATTERNS = [re.compile(p, re.IGNORECASE) for p in STRONG_REJECTION_PHRASES]
_NON_REJECTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in NON_REJECTION_PHRASES]


def _stage2_classify(body_text):
    """
    Rule-based classification on email body text.

    Returns:
      "rejection"  — confident this is a rejection (strong phrases found)
      "not_rejection" — confident this is NOT a rejection (whitelist phrases found)
      "uncertain"  — can't decide, needs LLM (Stage 3)
    """
    if not body_text:
        return "uncertain"

    # Check non-rejection phrases first (higher priority)
    for pattern in _NON_REJECTION_PATTERNS:
        if pattern.search(body_text):
            return "not_rejection"

    # Check strong rejection phrases
    for pattern in _STRONG_PATTERNS:
        if pattern.search(body_text):
            return "rejection"

    return "uncertain"


# ── Email body extraction ──

def _extract_body_text(payload):
    """Recursively extract plain text body from a Gmail message payload."""
    body_text = ""

    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        try:
            body_text += base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        except Exception:
            pass
    elif mime_type == "text/html" and body_data and not body_text:
        # Fallback: strip HTML tags for a rough text extraction
        try:
            html = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
            body_text += re.sub(r"<[^>]+>", " ", html)
            body_text = re.sub(r"\s+", " ", body_text).strip()
        except Exception:
            pass

    # Recurse into parts (multipart emails)
    for part in payload.get("parts", []):
        part_text = _extract_body_text(part)
        if part_text:
            body_text += "\n" + part_text

    return body_text.strip()


def _extract_email_info_full(msg):
    """Extract subject, sender, snippet, and full body from a Gmail message."""
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

    # Extract full body text
    body = _extract_body_text(msg.get("payload", {}))
    # Truncate to ~3000 chars to keep LLM costs reasonable
    if len(body) > 3000:
        body = body[:3000]

    return {"subject": subject, "sender": sender, "snippet": snippet, "body": body}


# ── Gmail helpers ──

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
        if hasattr(date_str, "timestamp"):
            return int(date_str.timestamp())
        if hasattr(date_str, "strftime"):
            date_str = date_str.strftime("%Y-%m-%d")
        date_str = str(date_str).split(" ")[0]
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def _batch_fetch_messages(service, message_refs, fetch_body=True):
    """
    Fetch message details in batches using Gmail batch API.

    If fetch_body=True, fetches full message (for body extraction).
    Otherwise fetches metadata only (subject + sender + snippet).
    """
    emails = []
    BATCH_SIZE = 50

    fmt = "full" if fetch_body else "metadata"

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
            if fetch_body:
                batch.add(
                    service.users().messages().get(userId="me", id=msg_id, format=fmt),
                    callback=make_callback(msg_id),
                )
            else:
                batch.add(
                    service.users().messages().get(
                        userId="me", id=msg_id, format=fmt,
                        metadataHeaders=["Subject", "From"]
                    ),
                    callback=make_callback(msg_id),
                )
        batch.execute()

        for ref in batch_refs:
            msg_id = ref["id"]
            if msg_id in batch_results:
                email_info = _extract_email_info_full(batch_results[msg_id])
                email_info["msg_id"] = msg_id
                email_info["internal_date"] = int(batch_results[msg_id].get("internalDate", 0))
                emails.append(email_info)

    return emails


# ── Stage 3: LLM classification for ambiguous emails ──

def _classify_with_claude(emails_batch, companies):
    """
    Stage 3: Use Claude to classify ONLY ambiguous emails.
    Requires the model to cite the exact rejection sentence from the email body.
    Returns classifications with confidence scores.
    """
    if not emails_batch:
        return []

    client = Anthropic()
    companies_list = ", ".join(set(c for c in companies if c))

    prompt = f"""You are a precise email classifier. Your ONLY job is to determine if an email is a job application rejection.

Companies the user has applied to: {companies_list}

RULES:
- An email is a rejection ONLY if it explicitly states the application is unsuccessful, the candidate was not selected, or the company chose someone else.
- Vague "updates", status notifications, or acknowledgements are NOT rejections.
- "Thank you for your interest" alone is NOT a rejection — it must be combined with explicit rejection language.
- If in doubt, classify as NOT a rejection. False positives are worse than false negatives.

For each email, return:
- is_rejection: true only if you found explicit rejection language
- confidence: 0.0 to 1.0 (only mark true if confidence >= 0.9)
- company: matched company name from the list, or empty string
- evidence: the EXACT sentence from the email body that indicates rejection (empty if not a rejection)

Return a JSON array:
[{{"index": 0, "is_rejection": true/false, "confidence": 0.95, "company": "Company Name", "evidence": "exact quote from email"}}]

Return ONLY the JSON array.

Emails:
"""
    for i, email in enumerate(emails_batch):
        body_preview = email.get("body", email.get("snippet", ""))
        prompt += f"\n--- Email {i} ---\nFrom: {email['sender']}\nSubject: {email['subject']}\nBody:\n{body_preview}\n"

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        results = json.loads(response_text)
        # Filter: only accept high-confidence rejections
        for r in results:
            if r.get("is_rejection") and r.get("confidence", 0) < 0.9:
                r["is_rejection"] = False
        return results
    except Exception as e:
        print(f"Claude classification error: {e}")
        return []


# ── Job matching ──

def _match_to_job(company_name, jobs):
    """Match a company name to a job in the list using fuzzy matching."""
    if not company_name:
        return None
    company_lower = company_name.lower().strip()
    for job in jobs:
        job_company = (job.get("company") or "").lower().strip()
        if not job_company:
            continue
        if company_lower == job_company:
            return job
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


# ── Main scan function ──

def scan_for_rejections(credentials_json, jobs, since_date, is_first_scan=False, before_epoch=None, progress_callback=None):
    """
    Scan Gmail for rejection emails using a 3-stage pipeline:
      Stage 1: Gmail keyword search (high recall)
      Stage 2: Rule-based phrase matching on full body (high precision, zero cost)
      Stage 3: LLM classification for uncertain emails only (high precision)
    """
    def _progress(msg):
        print(f"[Email Scan] {msg}")
        if progress_callback:
            progress_callback(msg)

    service = _build_gmail_service(credentials_json)

    # Build date filter
    epoch = _epoch_from_date(since_date)
    date_filter = f"after:{epoch}" if epoch else ""

    max_emails = MAX_EMAILS_FIRST_SCAN if is_first_scan else MAX_EMAILS_INCREMENTAL

    _progress(f"Starting {'FIRST' if is_first_scan else 'incremental'} scan...")
    print(f"[Email Scan] since_date={since_date}, epoch={epoch}, date_filter={date_filter}")
    print(f"[Email Scan] Active jobs: {len(jobs)}, max_emails={max_emails}")

    # ── Stage 1: Gmail search ──
    all_messages = []

    if is_first_scan:
        query = date_filter.strip() if date_filter else "after:2024/01/01"
        _progress("Stage 1: Searching Gmail for all emails in date range...")
        all_messages = _paginated_search(service, query, max_results=max_emails)
        _progress(f"Stage 1: Found {len(all_messages)} emails")
    else:
        mid = len(REJECTION_KEYWORDS) // 2
        kw_batch1 = REJECTION_KEYWORDS[:mid]
        kw_batch2 = REJECTION_KEYWORDS[mid:]

        keyword_msgs = []
        for kw_batch in [kw_batch1, kw_batch2]:
            query = f"{date_filter} ({' OR '.join(kw_batch)})".strip()
            msgs = _paginated_search(service, query, max_results=150)
            keyword_msgs.extend(msgs)

        companies = list(set(
            j.get("company", "").strip()
            for j in jobs
            if j.get("company", "").strip()
        ))

        company_msgs = []
        if companies:
            COMPANY_BATCH = 10
            for i in range(0, len(companies), COMPANY_BATCH):
                batch = companies[i:i + COMPANY_BATCH]
                parts = []
                for c in batch:
                    parts.append(f'from:"{c}"')
                    parts.append(f'subject:"{c}"')
                company_query = f"{date_filter} ({' OR '.join(parts)})".strip()
                batch_msgs = _paginated_search(service, company_query, max_results=100)
                company_msgs.extend(batch_msgs)

        seen_ids = set()
        for msg in keyword_msgs + company_msgs:
            if msg["id"] not in seen_ids:
                seen_ids.add(msg["id"])
                all_messages.append(msg)

        print(f"[Email Scan] Stage 1: keyword={len(keyword_msgs)}, company={len(company_msgs)}, unique={len(all_messages)}")

    if not all_messages:
        return {"emails_checked": 0, "rejections_found": 0, "details": []}

    if len(all_messages) > max_emails:
        _progress(f"Capping from {len(all_messages)} to {max_emails} emails")
        all_messages = all_messages[:max_emails]

    # Fetch full email details (with body) using batch API
    _progress(f"Fetching full email content for {len(all_messages)} emails...")
    emails = _batch_fetch_messages(service, all_messages, fetch_body=True)

    if not emails:
        return {"emails_checked": 0, "rejections_found": 0, "details": []}

    # ── Stage 2: Rule-based classification ──
    _progress(f"Stage 2: Rule-based classification on {len(emails)} emails...")

    confirmed_rejections = []  # Emails confidently classified as rejections
    uncertain_emails = []      # Emails that need LLM (Stage 3)

    for email in emails:
        # Classify using body text (prefer body, fall back to snippet)
        text = email.get("body") or email.get("snippet", "")
        result = _stage2_classify(text)

        if result == "rejection":
            confirmed_rejections.append(email)
        elif result == "uncertain":
            uncertain_emails.append(email)
        # "not_rejection" — skip entirely

    print(f"[Email Scan] Stage 2: {len(confirmed_rejections)} confirmed rejections, "
          f"{len(uncertain_emails)} uncertain, "
          f"{len(emails) - len(confirmed_rejections) - len(uncertain_emails)} ruled out")
    _progress(f"Stage 2: {len(confirmed_rejections)} confirmed, {len(uncertain_emails)} need AI review")

    # ── Stage 3: LLM classification for uncertain emails only ──
    llm_rejections = []
    if uncertain_emails:
        company_names = [j.get("company", "") for j in jobs]
        BATCH_SIZE = 25
        _progress(f"Stage 3: AI classifying {len(uncertain_emails)} ambiguous emails...")

        for batch_start in range(0, len(uncertain_emails), BATCH_SIZE):
            batch = uncertain_emails[batch_start:batch_start + BATCH_SIZE]
            _progress(f"Stage 3: AI review... ({min(batch_start + BATCH_SIZE, len(uncertain_emails))}/{len(uncertain_emails)})")
            batch_results = _classify_with_claude(batch, company_names)
            for r in batch_results:
                idx = r.get("index", -1)
                if r.get("is_rejection") and 0 <= idx < len(batch):
                    llm_rejections.append(batch[idx])

        print(f"[Email Scan] Stage 3: {len(llm_rejections)} additional rejections from LLM")

    # ── Match all rejections to jobs ──
    all_rejections = confirmed_rejections + llm_rejections
    company_names = [j.get("company", "") for j in jobs]

    # For confirmed rejections (Stage 2), we need to figure out the company.
    # Try sender domain matching first, then fall back to LLM for company extraction.
    details = []
    matched_job_ids = set()

    # Helper: try to match email to a job by sender domain or subject
    def _match_email_to_job(email):
        sender = email.get("sender", "").lower()
        subject = email.get("subject", "").lower()
        body = email.get("body", "").lower()
        for job in jobs:
            company = (job.get("company") or "").strip()
            if not company:
                continue
            c_lower = company.lower()
            # Check sender contains company name or domain
            if c_lower in sender:
                return job
            # Check subject
            if c_lower in subject:
                return job
            # Check body for company name near rejection language
            if c_lower in body:
                return job
        return None

    for email in all_rejections:
        matched_job = _match_email_to_job(email)
        if matched_job and matched_job["id"] not in matched_job_ids:
            matched_job_ids.add(matched_job["id"])
            details.append({
                "job_id": matched_job["id"],
                "job_company": matched_job.get("company", ""),
                "job_role": matched_job.get("role", ""),
                "email_subject": email["subject"],
                "sender": email["sender"],
            })

    _progress(f"Done! Checked {len(emails)} emails, found {len(details)} rejections "
              f"(Stage 2: {len(confirmed_rejections)}, Stage 3: {len(llm_rejections)})")

    return {
        "emails_checked": len(emails),
        "rejections_found": len(details),
        "details": details,
    }
