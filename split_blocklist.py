# split_blocklist.py
import os
import json

# Ensure blocklists folder exists
os.makedirs("blocklists", exist_ok=True)

# Load main blocklist.json
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

# Write each grouped source to its own JSON file
for src, items in grouped.items():
    out_file = f"blocklists/{src}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"domains": items}, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved {len(items)} entries to {out_file}")

# Generate manifest.json including all sources
files = [{"file": f"{s.lower()}.json", "source": s} for s in sources_list]
with open("blocklists/manifest.json", "w", encoding="utf-8") as mf:
    json.dump({"files": files}, mf, indent=2, ensure_ascii=False)
print("✅ Generated blocklists/manifest.json with all sources")
