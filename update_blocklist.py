# update_blocklist.py
import requests
import pandas as pd
from bs4 import BeautifulSoup
import json
import re
from PyPDF2 import PdfReader
import os

# -------------------------
# Helper Functions
# -------------------------

def extract_entries(file_path_or_url, file_type='auto', is_url=True):
    """Extract entries from CSV, JSON, PDF, HTML, TXT"""
    data = []
    try:
        if file_type == 'pdf' or file_path_or_url.endswith('.pdf'):
            r = requests.get(file_path_or_url) if is_url else None
            if r: open('temp.pdf','wb').write(r.content)
            reader = PdfReader('temp.pdf' if is_url else file_path_or_url)
            for page in reader.pages:
                data.extend(page.extract_text().splitlines())
        elif file_type == 'csv' or file_path_or_url.endswith('.csv'):
            df = pd.read_csv(file_path_or_url if not is_url else file_path_or_url)
            for col in df.columns:
                data.extend([str(val) for val in df[col] if pd.notna(val)])
        elif file_type == 'json' or file_path_or_url.endswith('.json'):
            j = json.loads(open(file_path_or_url).read())
            if isinstance(j, dict):
                for v in j.values(): data.append(str(v))
            elif isinstance(j, list):
                data.extend([str(i) for i in j])
        elif file_type == 'html' or file_path_or_url.endswith('.html'):
            r = requests.get(file_path_or_url) if is_url else None
            html_content = r.text if is_url else open(file_path_or_url).read()
            soup = BeautifulSoup(html_content,'html.parser')
            for td in soup.find_all(['td','li','p']):
                data.append(td.get_text(strip=True))
        else:  # fallback plain text
            r = requests.get(file_path_or_url) if is_url else None
            text = r.text if is_url else open(file_path_or_url).read()
            data.extend(text.splitlines())
    except Exception as e:
        print(f"Extraction failed for {file_path_or_url}: {e}")
    return data

def classify_entry(entry):
    """Detect if entry is URL or Name"""
    url_pattern = r'^(https?:\/\/)?([\w\-]+\.)+[\w\-]+(\/[\w\-._~:/?#[\]@!$&\'()*+,;%=]*)?$'
    return 'url' if re.match(url_pattern, entry.strip()) else 'name'

def name_to_domain(name):
    """Convert institution name to possible domain"""
    try:
        domain_guess = re.sub(r'[^a-z0-9]', '', name.lower())
        domain_guess += ".edu.in"  # heuristic
        return domain_guess
    except:
        return None

def ai_detect_feed(page_url):
    """AI-assisted detection of feed if user link fails"""
    try:
        r = requests.get(page_url)
        soup = BeautifulSoup(r.text,'html.parser')
        links = soup.find_all('a')
        candidates = [link.get('href') for link in links if link.get('href') and ('.csv' in link.get('href') or 'download' in link.text.lower() or 'recent' in link.text.lower())]
        return candidates[0] if candidates else None
    except Exception as e:
        print("AI feed detection failed:", e)
        return None

def safe_extract_entries(link, file_type='auto', is_url=True):
    """Try user link first, fallback to AI, return entries safely"""
    try:
        entries = extract_entries(link, file_type, is_url)
        if not entries:
            print(f"User link {link} failed, attempting AI detection")
            try:
                ai_link = ai_detect_feed(link)
                if ai_link:
                    print(f"AI detected feed: {ai_link}")
                    entries = extract_entries(ai_link)
                else:
                    print("AI could not detect a valid feed either.")
                    entries = []
            except Exception as e:
                print(f"AI detection failed: {e}")
                entries = []
        return entries
    except Exception as e:
        print(f"Extraction failed for {link}: {e}")
        return []

# -------------------------
# User Feeds (Links or Local Files)
# -------------------------
user_feeds = [
    "http://data.phishtank.com/data/online-valid.csv",
    "https://urlhaus.abuse.ch/downloads/csv_recent/",
    "https://www.ugc.ac.in/fakeuniversities",
    "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt"
]

# Optional local custom files
local_files = []
custom_folder = "custom_feeds"
if os.path.exists(custom_folder):
    local_files = [os.path.join(custom_folder, f) for f in os.listdir(custom_folder)]

# -------------------------
# Collect All Entries
# -------------------------
all_entries = []

for feed in user_feeds:
    all_entries.extend(safe_extract_entries(feed, is_url=True))

for file in local_files:
    all_entries.extend(safe_extract_entries(file, is_url=False))

# -------------------------
# Classify and Map
# -------------------------
urls, names = [], []

for e in all_entries:
    try:
        if classify_entry(e) == 'url':
            urls.append(e)
        else:
            names.append(e)
    except:
        continue

mapped_domains = []
for n in names:
    try:
        domain = name_to_domain(n)
        if domain:
            mapped_domains.append(domain)
    except:
        continue

# -------------------------
# Merge and Save
# -------------------------
try:
    blocklist = list(set(urls + mapped_domains))
    with open("blocklist.json","w") as f:
        json.dump(blocklist, f, indent=2)
    print(f"Blocklist updated successfully with {len(blocklist)} entries")
except Exception as e:
    print(f"Failed to save blocklist: {e}")
