#!/usr/bin/env python3
"""
Pushes the local database to the live PythonAnywhere-hosted site and reloads
it -- the "data" half of the deploy pipeline (the "code" half is the GitHub
webhook set up separately; see web/app.py's /deploy-hook).

Deliberately NOT part of git: the database is data, not code, and changes far
too often/is far too large to bundle into every commit. This script is the
lighter-weight sync path for exactly that reason.

Credentials are read from environment variables, never hardcoded:
    PYTHONANYWHERE_API_TOKEN, PYTHONANYWHERE_USERNAME, PYTHONANYWHERE_DOMAIN

Usage:
    python sync_to_pythonanywhere.py
"""
import os
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "cse_documents.db"

API_TOKEN = os.environ.get("PYTHONANYWHERE_API_TOKEN", "")
USERNAME = os.environ.get("PYTHONANYWHERE_USERNAME", "")
DOMAIN = os.environ.get("PYTHONANYWHERE_DOMAIN", "")

REMOTE_DB_PATH = f"/home/{USERNAME}/lantern/data/cse_documents.db"


def sync() -> bool:
    if not (API_TOKEN and USERNAME and DOMAIN):
        print("  [!] PYTHONANYWHERE_API_TOKEN/USERNAME/DOMAIN not set -- skipping data sync.")
        print("      (Set these as environment variables to enable it; see collector/README notes.)")
        return False

    if not DB_PATH.exists():
        print(f"  [!] {DB_PATH} not found -- nothing to sync.")
        return False

    headers = {"Authorization": f"Token {API_TOKEN}"}
    upload_url = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}/files/path{REMOTE_DB_PATH}/"

    print(f"  Uploading {DB_PATH.name} ({DB_PATH.stat().st_size / 1024:.0f} KB) to PythonAnywhere...")
    with open(DB_PATH, "rb") as f:
        r = requests.post(upload_url, headers=headers, files={"content": f}, timeout=120)

    # PythonAnywhere's Files API returns 200 on update, 201 on first create.
    if r.status_code not in (200, 201):
        print(f"  [!] Upload failed: {r.status_code} {r.text}")
        return False
    print(f"  Upload OK ({r.status_code}).")

    reload_url = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}/webapps/{DOMAIN}/reload/"
    r = requests.post(reload_url, headers=headers, timeout=30)
    if r.status_code != 200:
        print(f"  [!] Upload succeeded but reload failed: {r.status_code} {r.text}")
        return False
    print("  Reload OK -- live site now has the latest data.")
    return True


if __name__ == "__main__":
    ok = sync()
    sys.exit(0 if ok else 1)
