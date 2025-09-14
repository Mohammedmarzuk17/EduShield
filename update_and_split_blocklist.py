import os
import re
import json
import csv
import requests
from urllib.parse import urlparse
from datetime import datetime
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
from io import BytesIO
import math

# ---------------------------
# Helpers
# ---------------------------

def toASCII(input_str):
    """Normalize string to ASCII-like format."""
    try:
        return input_str.strip().lower().encode("ascii", "ignore").decode("ascii")
    except Exception:
        return input_str.strip().lower()

def extract_domain(url_or_text):
    """Extract and normalize domains from messy input or institution names."""
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
            return toASCII(domain) if domain else None
        except Exception:
            return None

    # If plain domain
    domain_pattern = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")
    if domain_pattern.match(candidate):
        return toASCII(candidate)

    # Otherwise treat as a "name" entry (colleges/universities etc.)
    return toASCII(candidate)

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

def fetch_and_parse_pdf(url):
    entries = []
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            reader = PdfReader(BytesIO(r.content))
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    for line in text.splitlines():
                        cleaned = line.strip()
                        if cleaned and len(cleaned) > 3:
                            entries.append(cleaned)
    except Exception as e:
        print(f"[!] Failed to fetch/parse PDF {url}: {e}")
    return entries

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
        "phishtank": "http://data.phishtank.com/data/online-valid.csv",
        "phishing_army": "https://phishing.army/download/phishing_army_blocklist_extended.txt",
        "threatfox": "https://threatfox.abuse.ch/downloads/hostfile/",
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

    # ---- Remote UGC/AICTE PDFs ----
    pdf_feeds = {
        "ugc": "https://www.ugc.ac.in/pdfnews/fake-universities-list.pdf",
        "aicte": "https://www.aicte-india.org/downloads/fake_institutions_list.pdf"
    }

    for source, url in pdf_feeds.items():
        entries = fetch_and_parse_pdf(url)
        for entry in entries:
            domain = extract_domain(entry)
            if domain:
                if domain not in domain_map:
                    domain_map[domain] = {"domain": domain, "sources": [source]}
                elif source not in domain_map[domain]["sources"]:
                    domain_map[domain]["sources"].append(source)

    # ---- Local manual JSON files ----
    manual_files = {
        "ugc": "manual/manual_ugc.json",
        "aicte": "manual/manual_aicte.json",
    }

    for source, path in manual_files.items():
        items = parse_json_feed(path)
        for item in items:
            domain = extract_domain(item)
            if domain:
                if domain not in domain_map:
                    domain_map[domain] = {"domain": domain, "sources": [source]}
                elif source not in domain_map[domain]["sources"]:
                    domain_map[domain]["sources"].append(source)

    # ---- Local user uploads ----
    user_files = {
        "local_csv": "user_feed.csv",
        "local_json": "user_feed.json",
        "local_html": "user_feed.html",
        "local_pdf": "user_feed.pdf",
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
                        domain_map[domain] = {"domain": domain, "sources": [source]}
                    elif source not in domain_map[domain]["sources"]:
                        domain_map[domain]["sources"].append(source)
        except FileNotFoundError:
            continue

    # ---- Final blocklist ----
    merged_list = sorted(domain_map.values(), key=lambda x: x["domain"])
    print(f"[+] Total domains to store: {len(merged_list)}")

    # ---- Chunked export ----
    CHUNK_SIZE = 3000
    os.makedirs("blocklists_chunks", exist_ok=True)
    total_chunks = math.ceil(len(merged_list) / CHUNK_SIZE)
    chunk_files = []

    for i in range(total_chunks):
        chunk = merged_list[i*CHUNK_SIZE:(i+1)*CHUNK_SIZE]
        chunk_file = f"blocklists_chunks/blocklist_chunk_{i+1}.json"
        with open(chunk_file, "w", encoding="utf-8") as f:
            json.dump({"domains": chunk}, f, indent=2, ensure_ascii=False)
        chunk_files.append(chunk_file)
        print(f"✅ Saved chunk {i+1}/{total_chunks} -> {chunk_file}")

    # ---- Full blocklist (optional) ----
    with open("blocklist.json", "w", encoding="utf-8") as f:
        json.dump({"last_updated": datetime.utcnow().isoformat(), "domains": merged_list}, f, indent=2, ensure_ascii=False)

    print(f"[+] Full blocklist.json saved with {len(merged_list)} domains.")
    return merged_list

# ---------------------------
# Split blocklist into per-source JSON & manifest
# ---------------------------

def split_blocklist():
    os.makedirs("blocklists", exist_ok=True)

    with open("blocklist.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    domains = data.get("domains", [])
    grouped = {}

    for entry in domains:
        sources = entry.get("sources") or ["unknown"]
        for src in sources:
            key = src.lower()
            grouped.setdefault(key, []).append(entry)

    sources_list = ["urlhaus", "openphish", "ugc", "aicte", "custom", "phishtank", "phishing_army", "threatfox"]
    for s in sources_list:
        grouped.setdefault(s.lower(), [])

    for src, items in grouped.items():
        out_file = f"blocklists/{src}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({"domains": items}, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved {len(items)} entries to {out_file}")

    files = [{"file": f"{s.lower()}.json", "source": s} for s in sources_list]
    with open("blocklists/manifest.json", "w", encoding="utf-8") as mf:
        json.dump({"files": files}, mf, indent=2, ensure_ascii=False)
    print("✅ Generated blocklists/manifest.json with all sources")

# ---------------------------
# Run all
# ---------------------------

if __name__ == "__main__":
    merged = update_blocklist()
    split_blocklist()
