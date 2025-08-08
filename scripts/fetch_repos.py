#!/usr/bin/env python3
import os
import requests
import json
import base64
import datetime
from pathlib import Path

DATA_DIR = Path("data")
DOCS_DIR = Path("docs")
SNAPSHOT_FILE = DATA_DIR / "latest_snapshot.json"
TODAY = datetime.datetime.utcnow().date().isoformat()
TODAY_FILE = DATA_DIR / f"{TODAY}.json"
DOCS_LATEST = DOCS_DIR / "latest.json"

TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    print("ERROR: No GITHUB_TOKEN provided in env. Exiting.")
    exit(1)

HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

friends_env = os.getenv("FRIENDS")
if not friends_env:
    print("ERROR: FRIENDS env variable not set. Exiting.")
    exit(1)

friends = [f.strip() for f in friends_env.split(",") if f.strip()]

print("Checking public repos for:", friends)

def fetch_public_repos(user):
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{user}/repos?per_page=100&page={page}&type=public&sort=created"
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            print(f"Warning: failed to fetch repos for {user}: {r.status_code}")
            break
        page_data = r.json()
        if not page_data:
            break
        repos.extend(page_data)
        page += 1
    return repos

current = {}
for u in friends:
    repos = fetch_public_repos(u)
    for r in repos:
        full = r.get("full_name")
        current[full] = {
            "name": r.get("name"),
            "full_name": full,
            "owner": r.get("owner", {}).get("login"),
            "html_url": r.get("html_url"),
            "description": r.get("description"),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        }

if SNAPSHOT_FILE.exists():
    prev = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
else:
    prev = {}

new_full_names = [fn for fn in current.keys() if fn not in prev.keys()]
print(f"New public repos found: {len(new_full_names)}")

def fetch_readme_snippet(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return None
    j = r.json()
    content_b64 = j.get("content", "")
    try:
        decoded = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
    except Exception:
        return None
    lines = decoded.splitlines()
    snippet_lines = lines[:5]
    snippet = "\n".join(snippet_lines).strip()
    if len(snippet) > 400:
        snippet = snippet[:400].rsplit("\n", 1)[0] + "..."
    return snippet

new_items = []
for full in new_full_names:
    meta = current[full]
    snippet = fetch_readme_snippet(meta["owner"], meta["name"])
    new_items.append({
        "full_name": full,
        "name": meta["name"],
        "owner": meta["owner"],
        "html_url": meta["html_url"],
        "description": meta["description"],
        "created_at": meta["created_at"],
        "readme_snippet": snippet
    })

DATA_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

TODAY_FILE.write_text(json.dumps(new_items, ensure_ascii=False, indent=2), encoding="utf-8")
SNAPSHOT_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
DOCS_LATEST.write_text(json.dumps(new_items, ensure_ascii=False, indent=2), encoding="utf-8")

dates_file = DOCS_DIR / "dates.json"
if dates_file.exists():
    dates_list = json.loads(dates_file.read_text(encoding="utf-8"))
else:
    dates_list = []
if TODAY not in dates_list:
    dates_list.append(TODAY)
    dates_list.sort(reverse=True)
dates_file.write_text(json.dumps(dates_list, ensure_ascii=False, indent=2), encoding="utf-8")

print("Wrote:", TODAY_FILE, "and updated latest/dates.")
if not new_items:
    print("No new public repos today.")
else:
    print(f"{len(new_items)} new public repos saved.")
