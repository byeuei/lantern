#!/usr/bin/env python3
"""
Manual backfill -- inserts documents sourced by hand (company IR pages, web search,
older cdn.cse.lk links no longer in the live feed) into the same `documents` table
cse_documents_collector.py writes to, tagged source_type='manual' so downstream
consumers can always tell how a row got there.

This is the mechanism the README's BACKFILL section described but never built --
CSE's live feed only ever shows ~8 recent items market-wide, so multi-year depth has
no automated source; it has to be sourced once, by hand, per company.

Usage: import and call backfill_documents() with a list of entries, or run this file
directly against ENTRIES below.
"""
import hashlib
import os
from datetime import datetime

from cse_documents_collector import DB_PATH, STORAGE_ROOT, HEADERS, init_db, classify
import requests


def download_pdf(url: str, dest_path: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        if r.status_code != 200:
            print(f"  [!] Download failed ({r.status_code}): {url}")
            return None
        h = hashlib.sha256()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                h.update(chunk)
                f.write(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"  [!] Download error: {e}")
        return None


def backfill_documents(entries: list[dict]):
    """entries: [{symbol, company_name, doc_type (optional, inferred from title if
    absent), title, uploaded_date, source_path (a real, fetchable URL), source_id
    (optional, a stable unique string -- defaults to a hash of source_path)}]"""
    conn = init_db()
    inserted = 0
    for e in entries:
        source_id = e.get("source_id") or ("manual_" + hashlib.sha256(e["source_path"].encode()).hexdigest()[:16])
        existing = conn.execute("SELECT 1 FROM documents WHERE source_id = ?", (source_id,)).fetchone()
        if existing:
            print(f"  already have: {e['symbol']} | {e['title']}")
            continue

        doc_type = e.get("doc_type") or classify(e["title"])
        safe_symbol = e["symbol"].replace(".", "_")
        filename = source_id + "_" + e["source_path"].split("/")[-1].split("?")[0]
        local_path = os.path.join(STORAGE_ROOT, safe_symbol, doc_type, filename)

        print(f"  -> BACKFILL: {e['symbol']} | {e['title']}")
        sha = download_pdf(e["source_path"], local_path)
        if not sha:
            print(f"     skipped (download failed): {e['source_path']}")
            continue

        conn.execute("""
            INSERT INTO documents (source_id, symbol, company_name, doc_type,
                source_category, uploaded_date, source_path, sha256, local_path,
                discovered_at, source_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')
        """, (source_id, e["symbol"], e["company_name"], doc_type, e["title"],
              e["uploaded_date"], e["source_path"], sha, local_path,
              datetime.now().isoformat()))
        conn.commit()
        inserted += 1

    print(f"\nBackfilled {inserted} new document(s).")
    conn.close()
    return inserted


if __name__ == "__main__":
    print("Import backfill_documents() and call it with a list of sourced entries.")
