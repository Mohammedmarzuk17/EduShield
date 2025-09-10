import os
import re
import json
import csv
import requests
from urllib.parse import urlparse
from datetime import datetime
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

# ---------------------------
# Helpers
# ---------------------------

def extract_domain(url_or_text):
    """Extract and normalize domains from messy input or names."""
    if not url_or_text:
        return None

    candidate = str(url_or_text).strip().strip('"').strip("'")

    # If URL
    if candidate.startswith(("http://", "https://")):
        try:
            parsed = urlparse(candidate)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain if domain else None
        except Exception:
            return None

    # If plain domain
    domain_pattern = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")
    if domain_pattern.match(candidate):
        return candidate.lower()

    # Otherwise treat as a "name" and convert to lowercase
    return candidate.lower()

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
        print(f"[!] CSV parse error in {path}: {e}")
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
        print(f"[!] JSON parse error in {path}: {e}")
    return []

def parse_html_feed(path):
    domains = []
    try:
        with open(path, encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            for link in soup.find_all("a", href=True):
                domains.append(link["href"])
    except Exception as e:
        print(f"[!] HTML parse error in {path}: {e}")
    return domains

def parse_pdf_feed(path):
    domains = []
    try:
        with open(path, "rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    domains.extend(text.split())
    except Exception as e:
        print(f"[!] PDF parse error in {path}: {e}")
    return domains

# ---------------------------
# Main Update Logic
# ---------------------------

def update_blocklist():
    domain_map = {}

    # ---- Remote feeds ----
    feeds = {
        "urlhaus": "https://urlhaus.abuse.ch/downloads/text/",
        "openphish": "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt",
        "custom": "https://raw.githubusercontent.com/Mohammedmarzuk17/EduShield/main/custom_feed.json",
    }

    for source, url in feeds.items():
        lines = fetch_text_feed(url)
        for item in lines:
            domain = extract_domain(item)
            if domain:
                if domain not in domain_map:
                    domain_map[domain] = {"domain": domain, "sources": [source]}
                elif source not in domain_map[domain]["sources"]:
                    domain_map[domain]["sources"].append(source)

    # ---- Local user uploads ----
    user_files = {
        "ugc_csv": "user_feed.csv",
        "ugc_json": "user_feed.json",
        "ugc_html": "user_feed.html",
        "ugc_pdf": "user_feed.pdf",
    }

    for source, path in user_files.items():
        try:
            if path.endswith(".csv"):
                items = parse_csv_feed(path)
            elif path.endswith(".json"):
                items = parse_json_feed(path)
            elif path.endswith(".html"):
                items = parse_html_feed(path)
            elif path.endswith(".pdf"):
                items = parse_pdf_feed(path)
            else:
                items = []

            for item in items:
                domain = extract_domain(item)
                if domain:
                    if domain not in domain_map:
                        domain_map[domain] = {"domain": domain, "sources": ["ugc"]}
                    elif "ugc" not in domain_map[domain]["sources"]:
                        domain_map[domain]["sources"].append("ugc")
        except FileNotFoundError:
            continue

    # ---- Final blocklist ----
    blocklist = {
        "last_updated": datetime.utcnow().isoformat(),
        "domains": sorted(domain_map.values(), key=lambda x: x["domain"]),
    }

    with open("blocklist.json", "w", encoding="utf-8") as f:
        json.dump(blocklist, f, indent=2, ensure_ascii=False)

    print(f"[+] Blocklist updated with {len(domain_map)} unique domains.")

# ---------------------------
# Split and generate per-source files
# ---------------------------

def split_blocklist():
    os.makedirs("blocklists", exist_ok=True)

    with open("blocklist.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    domains = data.get("domains", [])
    grouped = {}

    # Group domains by source
    for entry in domains:
        if isinstance(entry, dict):
            sources = entry.get("sources") or ["unknown"]
            for src in sources:
                key = src.lower()
                grouped.setdefault(key, []).append(entry)
        else:
            grouped.setdefault("unknown", []).append({"domain": str(entry), "sources": ["unknown"]})

    # Force all sources
    sources_list = ["urlhaus", "openphish", "ugc", "aicte", "custom"]
    for s in sources_list:
        key = s.lower()
        grouped.setdefault(key, [])

    # Write grouped files
    for src, items in grouped.items():
        out_file = f"blocklists/{src}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({"domains": items}, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved {len(items)} entries to {out_file}")

    # Generate manifest.json
    files = [{"file": f"{s.lower()}.json", "source": s} for s in sources_list]
    with open("blocklists/manifest.json", "w", encoding="utf-8") as mf:
        json.dump({"files": files}, mf, indent=2, ensure_ascii=False)
    print("✅ Generated blocklists/manifest.json with all sources")

# ---------------------------
# Run all
# ---------------------------

if __name__ == "__main__":
    update_blocklist()
    split_blocklist()
