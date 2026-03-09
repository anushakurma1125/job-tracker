import os
import json
import requests
from bs4 import BeautifulSoup
from anthropic import Anthropic

def _get_client():
    return Anthropic()

EXTRACTION_PROMPT = """You are a job posting data extractor. Given the text content of a job posting webpage, extract the following fields and return them as a JSON object:

{
  "company": "The company name",
  "role": "The job title/role",
  "posted_on": "The date the job was posted (if available, otherwise empty string)",
  "job_description": "A concise summary of the job description (max 500 words covering key responsibilities, requirements, and qualifications)"
}

Rules:
- Return ONLY valid JSON, no other text
- If a field cannot be determined, use an empty string
- For job_description, provide a clean, readable summary — not raw HTML
- For posted_on, use YYYY-MM-DD format if possible

Here is the webpage content:
"""


def fetch_page_text(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove script and style elements
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # Truncate to avoid token limits
    return text[:8000]


def extract_job_details(url):
    page_text = fetch_page_text(url)

    client = _get_client()
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT + page_text,
                }
            ],
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        if hasattr(e, 'response'):
            print(f"Response body: {e.response.text}")
        raise

    response_text = message.content[0].text.strip()

    # Handle cases where Claude wraps JSON in markdown code blocks
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    data = json.loads(response_text)
    data["link"] = url
    return data
