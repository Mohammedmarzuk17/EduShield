import re
import json
import csv
import requests
from urllib.parse import urlparse
from datetime import datetime
from bs4 import BeautifulSoup  # for HTML parsing
import PyPDF2                  # for PDF parsing

# ---------------------------
# Helpers
# ---------------------------

def extract_domain(url_or_text):
    """
    Extracts and normalizes domains from messy input.
    Accepts URLs, raw domains, CSV fragments, timestamps etc.
    Returns None if no valid domain.
    """
    if not url_or_text:
        return None

    # Strip quotes/whitespace
    candidate = str(url_or_text).strip().strip('"').strip("'")

    # If it looks like a URL
    if candidate.startswith(("http://", "https://")):
        try:
            parsed = urlparse(candidate)
            domain = parsed.netloc.lower()
            return domain if domain else None
        except Exception:
            return None

    # If it looks like a domain (regex match)
    domain_pattern = re.compile(
        r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
    )
    if domain_pattern.match(candidate):
        return candidate.lower()

    return None


def fetch_text_feed(url):
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            return r.text.splitlines()
    except Exception as e:
        print(f"[!] Failed to fetch {url}: {e}")
    return []


def parse_csv_feed(path):
    domains = []
    try:
        with open(path, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                for item in row:
                    domains.append(item)
    except Exception as e:
        print(f"[!] CSV parse error: {e}")
    return domains


def parse_json_feed(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "domains" in data:
                return data["domains"]
            elif isinstance(data, list):
                return data
    except Exception as e:
        print(f"[!] JSON parse error: {e}")
    return []


def parse_html_feed(path):
    domains = []
    try:
        with open(path, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            for link in soup.find_all("a", href=True):
                domains.append(link["href"])
    except Exception as e:
        print(f"[!] HTML parse error: {e}")
    return domains


def parse_pdf_feed(path):
    domains = []
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    domains.extend(text.split())
    except Exception as e:
        print(f"[!] PDF parse error: {e}")
    return domains


# ---------------------------
# Main Update Logic
# ---------------------------

def update_blocklist():
    all_candidates = []

    # ---- Remote feeds ----
    sources = [
        # Example official feeds
        "https://urlhaus.abuse.ch/downloads/text/",
        "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt",
        # You can add your own repo-hosted feeds
        "https://raw.githubusercontent.com/<your-repo>/blocklist.json"
    ]

    for src in sources:
        lines = fetch_text_feed(src)
        all_candidates.extend(lines)

    # ---- Local user uploads (optional) ----
    # Change paths to wherever you store them
    user_files = [
        "user_feed.csv",
        "user_feed.json",
        "user_feed.html",
        "user_feed.pdf",
    ]
    for path in user_files:
        if path.endswith(".csv"):
            all_candidates.extend(parse_csv_feed(path))
        elif path.endswith(".json"):
            all_candidates.extend(parse_json_feed(path))
        elif path.endswith(".html"):
            all_candidates.extend(parse_html_feed(path))
        elif path.endswith(".pdf"):
            all_candidates.extend(parse_pdf_feed(path))

    # ---- Normalize ----
    cleaned = set()
    for item in all_candidates:
        domain = extract_domain(item)
        if domain:
            cleaned.add(domain)

    blocklist = {"last_updated": datetime.utcnow().isoformat(), "domains": sorted(cleaned)}

    # ---- Write ----
    with open("blocklist.json", "w", encoding="utf-8") as f:
        json.dump(blocklist, f, indent=2)

    print(f"[+] Blocklist updated with {len(cleaned)} domains.")


if __name__ == "__main__":
    update_blocklist()
