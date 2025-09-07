import os
import requests
import csv
import json
from io import StringIO
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
import hashlib
import re

# -----------------------------
# Configuration
# -----------------------------

# GitHub repo folder for custom feeds
CUSTOM_FEEDS_DIR = "custom_feeds"

# Feed URLs
feed_urls = [
    "https://data.phishtank.com/data/online-valid.csv",
    "https://urlhaus.abuse.ch/downloads/csv_recent/",
    "https://urlhaus.abuse.ch/downloads/csv/",
    "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt"
]

# Output blocklist file
BLOCKLIST_FILE = "blocklist.json"

# -----------------------------
# Utility Functions
# -----------------------------

def sha256_hash(text):
    """Return SHA-256 hash of a string."""
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def normalize_domain(domain):
    """Lowercase, remove protocol and www."""
    domain = domain.lower()
    domain = re.sub(r'^https?:\/\/', '', domain)
    domain = re.sub(r'^www\.', '', domain)
    domain = domain.split('/')[0]
    return domain

def fetch_feed(url):
    """Fetch feed content safely."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[WARN] Failed to fetch {url}: {e}")
        return ""

def parse_csv(content):
    """Parse CSV content into list of domains."""
    domains = set()
    try:
        reader = csv.reader(StringIO(content))
        for row in reader:
            for item in row:
                item = item.strip()
                if item and not item.startswith("#"):
                    domains.add(normalize_domain(item))
    except Exception as e:
        print(f"[WARN] Failed to parse CSV: {e}")
    return domains

def parse_txt(content):
    """Parse TXT content into list of domains."""
    domains = set()
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            domains.add(normalize_domain(line))
    return domains

def parse_html_file(filepath):
    """Extract names from HTML and convert to possible URLs."""
    domains = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            text_entries = soup.get_text(separator="\n").splitlines()
            for entry in text_entries:
                entry = entry.strip()
                if entry:
                    # Convert name → possible domain
                    dom = entry.lower().replace(" ", "") + ".edu"
                    domains.add(dom)
    except Exception as e:
        print(f"[WARN] Failed to parse HTML file {filepath}: {e}")
    return domains

def parse_pdf_file(filepath):
    """Extract text from PDF and convert to possible URLs."""
    domains = set()
    try:
        reader = PdfReader(filepath)
        for page in reader.pages:
            text = page.extract_text()
            for line in text.splitlines():
                line = line.strip()
                if line:
                    dom = line.lower().replace(" ", "") + ".edu"
                    domains.add(dom)
    except Exception as e:
        print(f"[WARN] Failed to parse PDF {filepath}: {e}")
    return domains

def parse_json_file(filepath):
    """Parse JSON file into domains."""
    domains = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if isinstance(item, str):
                    domains.add(normalize_domain(item))
    except Exception as e:
        print(f"[WARN] Failed to parse JSON file {filepath}: {e}")
    return domains

# -----------------------------
# Main Blocklist Collection
# -----------------------------

all_domains = set()

# 1️⃣ Fetch online feeds
for url in feed_urls:
    content = fetch_feed(url)
    if url.endswith(".csv"):
        all_domains.update(parse_csv(content))
    elif url.endswith(".txt"):
        all_domains.update(parse_txt(content))
    else:
        # fallback for unknown format
        all_domains.update(parse_txt(content))

# 2️⃣ Parse custom feed folder
if os.path.exists(CUSTOM_FEEDS_DIR):
    for filename in os.listdir(CUSTOM_FEEDS_DIR):
        filepath = os.path.join(CUSTOM_FEEDS_DIR, filename)
        if filename.endswith(".csv"):
            with open(filepath, 'r', encoding='utf-8') as f:
                all_domains.update(parse_csv(f.read()))
        elif filename.endswith(".txt"):
            with open(filepath, 'r', encoding='utf-8') as f:
                all_domains.update(parse_txt(f.read()))
        elif filename.endswith(".html"):
            all_domains.update(parse_html_file(filepath))
        elif filename.endswith(".pdf"):
            all_domains.update(parse_pdf_file(filepath))
        elif filename.endswith(".json"):
            all_domains.update(parse_json_file(filepath))

# -----------------------------
# Save Blocklist
# -----------------------------

try:
    blocklist_data = {"domains": list(all_domains)}
    with open(BLOCKLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(blocklist_data, f, indent=2)
    print(f"[INFO] Blocklist updated successfully with {len(all_domains)} entries")
except Exception as e:
    print(f"[ERROR] Failed to save blocklist: {e}")
