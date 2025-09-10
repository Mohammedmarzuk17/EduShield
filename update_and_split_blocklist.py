# update_and_split_blocklist.py
import os
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from PyPDF2 import PdfReader

# ================================
# 1️⃣ Update main blocklist
# ================================
# Placeholder logic for updating blocklist
# Replace with your actual update logic from previous update_blocklist.py
def update_blocklist():
    print("Updating main blocklist...")
    # Example: fetch remote blocklists, parse PDFs/HTML, merge etc.
    # Save updated blocklist to blocklist.json
    blocklist = {"domains": [
        {"domain": "example-fake-college.edu", "sources": ["ugc"], "severity": "red"},
        {"domain": "scamsite.test", "sources": ["urlhaus"], "severity": "red"}
    ]}
    with open("blocklist.json", "w", encoding="utf-8") as f:
        json.dump(blocklist, f, indent=2, ensure_ascii=False)
    print("✅ blocklist.json updated with", len(blocklist["domains"]), "entries")

# ================================
# 2️⃣ Split blocklist by source + manifest
# ================================
def split_blocklist():
    print("Splitting blocklist by source...")
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

    # Force include all expected sources
    sources_list = ["urlhaus", "openphish", "ugc", "aicte", "custom"]
    for s in sources_list:
        key = s.lower()
        grouped.setdefault(key, [])

    # Write grouped JSON files
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

# ================================
# 3️⃣ Run all
# ================================
if __name__ == "__main__":
    update_blocklist()
    split_blocklist()
