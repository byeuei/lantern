#!/usr/bin/env python3
"""
CSE Documents Collector -- V0.1

What this does, honestly:
- Polls CSE's confirmed-real endpoints (getFinancialAnnouncement, circularAnnouncement)
- These endpoints return only the latest ~8 items MARKET-WIDE, regardless of company.
- This script filters those items down to YOUR coverage universe (the symbols you care about)
  and saves anything new into a local database + folder of PDFs.
- Run this repeatedly over time (daily is enough) and it will accumulate real history for
  your covered companies -- exactly the same way CSEPal built theirs. There is no way to
  retroactively pull 5 years of history through this endpoint; that is a separate, one-time
  task (see BACKFILL section at the bottom of this file).

Usage:
    python cse_documents_collector.py

Requires: pip install requests
"""
import re
import sqlite3
import hashlib
import os
import time
import requests
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG -- the full CSE-listed coverage universe. Base symbol matching
# (matches_universe) already collapses voting/non-voting share classes to the
# same base (e.g. "TKYO.N0000" and "TKYO.X0000" both resolve to "TKYO").
# Sourced from cse.lk's tradeSummary endpoint (the full name<->symbol master
# list), which is also how build_symbol_lookup() resolves free-text company
# names below -- keep this list in sync with the `coverage_universe` DB table.
# ---------------------------------------------------------------------------
COVERAGE_UNIVERSE = [
    "AAF", "AAIC", "ABAN", "ABL", "ACL", "ACME", "AEL", "AFS",
    "AFSL", "AGAL", "AGPL", "AGST", "AHPL", "AHUN", "AINS", "ALLI",
    "ALUM", "AMF", "AMSL", "APLA", "ASCO", "ASHO", "ASIR", "ASIY",
    "ASPH", "ATL", "ATLL", "AUTO", "BALA", "BERU", "BFL", "BFN",
    "BIL", "BOGA", "BOPL", "BPPL", "BREW", "BRR", "BRWN", "BUKI",
    "CABO", "CALC", "CALF", "CALH", "CALI", "CALT", "CALU", "CARE",
    "CARG", "CARS", "CBNK", "CCS", "CDB", "CERA", "CFI", "CFIN",
    "CFLB", "CFVF", "CHL", "CHMX", "CHOT", "CIC", "CIND", "CINS",
    "CINV", "CIT", "CITH", "CITW", "CLND", "COCO", "COCR", "COLO",
    "COMB", "COMD", "CONN", "COOP", "CPRT", "CRL", "CSD", "CSLK",
    "CTBL", "CTC", "CTEA", "CTHR", "CTLD", "CWL", "CWM", "DFCC",
    "DIAL", "DIMO", "DIPD", "DIST", "DOCK", "DPL", "EAST", "EBCR",
    "ECL", "EDEN", "ELPL", "EMER", "EML", "ETWO", "EXT", "FCT",
    "GEST", "GHLL", "GLAS", "GRAN", "GREG", "GUAR", "HARI", "HASU",
    "HAYC", "HAYL", "HBS", "HDFC", "HEXP", "HHL", "HNB", "HNBF",
    "HOPL", "HPFL", "HPL", "HPWR", "HSIG", "HUNA", "HVA", "INME",
    "JAT", "JETS", "JFP", "JINS", "JKH", "JKL", "JXG", "KAHA",
    "KCAB", "KFP", "KGAL", "KHC", "KHL", "KOTA", "KPHL", "KVAL",
    "KZOO", "LALU", "LAMB", "LCBF", "LCEY", "LDEV", "LFIN", "LGIL",
    "LGL", "LHCL", "LHL", "LIOC", "LION", "LITE", "LLUB", "LMF",
    "LOFC", "LOLC", "LPL", "LPRT", "LUMX", "LVEF", "LWL", "MADU",
    "MARA", "MASK", "MBSL", "MCPL", "MDL", "MEL", "MELS", "MERC",
    "MFPE", "MGT", "MHDL", "MRH", "MSL", "MULL", "NAMU", "NDB",
    "NEH", "NHL", "NTB", "ODEL", "OFEQ", "ONAL", "OSEA", "PABC",
    "PACK", "PALM", "PAP", "PARQ", "PEG", "PHAR", "PINS", "PKME",
    "PLC", "PLR", "PMB", "RAL", "RCH", "RCL", "REEF", "RENU",
    "REXP", "RHL", "RHTL", "RICH", "RIL", "RWSL", "SAMP", "SCAP",
    "SDB", "SDF", "SEMB", "SERV", "SEYB", "SFCL", "SFIN", "SHAW",
    "SHL", "SHOT", "SIGV", "SIL", "SINH", "SINS", "SIRA", "SLND",
    "SLTL", "SMOT", "SOY", "SPEN", "STAF", "SUN", "TAFL", "TAJ",
    "TAP", "TESS", "TILE", "TJL", "TKYO", "TPL", "TRAN", "TSML",
    "TYRE", "UAL", "UBC", "UBF", "UCAR", "UDPL", "UML", "VFIN",
    "VLL", "VONE", "VPEL", "WAPO", "WATA", "WIND", "WLTH", "YORK",
]

# Resolved from this file's location, not cwd -- any script that imports these
# (financials_entry.py, manual_backfill.py, etc.) is correct regardless of where
# it's run from. This closes a recurring bug: relative paths silently wrote to
# whatever directory the script happened to be launched from.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = str(DATA_DIR / "cse_documents.db")
STORAGE_ROOT = str(DATA_DIR / "documents")
BASE = "https://www.cse.lk/api/"
HEADERS = {"User-Agent": "cse-collector-prototype/0.1 (personal research use)"}


# ---------------------------------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            source_id       TEXT PRIMARY KEY,   -- CSE's own numeric id for the item
            symbol          TEXT NOT NULL,
            company_name    TEXT,
            doc_type        TEXT NOT NULL,       -- ANNUAL_REPORT | INTERIM_REPORT | CIRCULAR | UNCLASSIFIED
            source_category TEXT,                -- verbatim fileText from CSE, never discarded
            uploaded_date   TEXT,
            source_path     TEXT,
            sha256          TEXT,
            local_path      TEXT,
            discovered_at   TEXT NOT NULL,
            source_type     TEXT NOT NULL DEFAULT 'automated'  -- automated (this script) | manual (backfill)
        )
    """)
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
    if "source_type" not in existing_cols:
        conn.execute("ALTER TABLE documents ADD COLUMN source_type TEXT NOT NULL DEFAULT 'automated'")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            symbol                   TEXT PRIMARY KEY,
            company_name             TEXT,
            generated_at             TEXT NOT NULL,
            summary_text             TEXT NOT NULL,
            earnings_comparison_json TEXT NOT NULL,
            gaps_note                TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dividends (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol        TEXT NOT NULL,
            company_name  TEXT,
            period        TEXT NOT NULL,     -- fiscal year label, e.g. "FY2025"
            dps           REAL,              -- NULL when a nil/no-dividend year, distinguished from "not sourced yet"
            currency      TEXT NOT NULL DEFAULT 'LKR',
            source_doc_id TEXT,
            source_page   INTEGER,
            notes         TEXT,
            UNIQUE(symbol, period)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS coverage_universe (
            symbol       TEXT PRIMARY KEY,
            company_name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS financial_statements (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol                   TEXT NOT NULL,
            company_name             TEXT,
            period_type              TEXT NOT NULL,               -- ANNUAL | INTERIM
            period_label             TEXT NOT NULL,
            period_end_date          TEXT NOT NULL,                -- YYYY-MM-DD
            basis                    TEXT NOT NULL DEFAULT 'GROUP', -- GROUP | COMPANY
            currency                 TEXT NOT NULL DEFAULT 'LKR',
            unit_scale               TEXT NOT NULL DEFAULT '000',    -- 1 | 000 | 000000, as disclosed

            -- income statement
            revenue                     REAL,
            cost_of_sales               REAL,
            gross_profit                REAL,
            operating_profit            REAL,
            depreciation_amortization   REAL,
            finance_costs               REAL,
            finance_income              REAL,
            profit_before_tax           REAL,
            tax_expense                 REAL,
            profit_after_tax            REAL,
            minority_interest           REAL,
            eps_basic                   REAL,
            eps_diluted                 REAL,

            -- balance sheet (period-end position)
            total_assets                REAL,
            current_assets              REAL,
            inventory                   REAL,
            trade_receivables           REAL,
            cash_and_equivalents        REAL,
            total_liabilities           REAL,
            current_liabilities         REAL,
            trade_payables              REAL,
            short_term_borrowings       REAL,
            long_term_borrowings        REAL,
            total_equity                REAL,
            shares_in_issue             REAL,

            -- cash flow statement
            cash_from_operations        REAL,
            capex                       REAL,
            cash_from_investing         REAL,
            cash_from_financing         REAL,

            -- citation: per-statement (how figures actually appear across pages), plus a
            -- free-text escape hatch for exceptions -- same discipline as dividends.notes
            source_doc_id               TEXT NOT NULL,
            income_statement_page       INTEGER,
            balance_sheet_page          INTEGER,
            cashflow_page                INTEGER,
            notes                       TEXT,

            UNIQUE(symbol, period_end_date, period_type, basis)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fs_symbol ON financial_statements(symbol)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data (
            symbol              TEXT NOT NULL,
            as_of               TEXT NOT NULL,      -- trading date this snapshot reflects, YYYY-MM-DD
            collected_at        TEXT NOT NULL,       -- ISO timestamp the collector actually ran
            price               REAL,
            previous_close      REAL,
            closing_price       REAL,
            open                REAL,
            high                REAL,
            low                 REAL,
            turnover            REAL,
            share_volume        REAL,
            market_cap          REAL,
            shares_outstanding  REAL,     -- derived = market_cap / closing_price; NULL if no trade
            source              TEXT NOT NULL DEFAULT 'tradeSummary',
            PRIMARY KEY (symbol, as_of)
        )
    """)
    conn.execute("""
        CREATE VIEW IF NOT EXISTS market_data_latest AS
        SELECT m.* FROM market_data m
        JOIN (SELECT symbol, MAX(as_of) AS as_of FROM market_data GROUP BY symbol) latest
          ON m.symbol = latest.symbol AND m.as_of = latest.as_of
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS thesis (
            symbol                     TEXT PRIMARY KEY,
            company_name               TEXT,
            generated_at               TEXT NOT NULL,
            recommendation             TEXT NOT NULL,   -- BUY | ACCUMULATE | HOLD | REDUCE | SELL | UNRATED
            composite_score            REAL,              -- 0-100, NULL if UNRATED
            confidence                 REAL,               -- 0-100, data-completeness based
            pillar_scores_json         TEXT NOT NULL,       -- {pillar: {score, weight_used, rationale, citations[]}}
            weights_used_json          TEXT NOT NULL,        -- renormalized weights actually applied
            macro_pillar_available     INTEGER NOT NULL DEFAULT 0,  -- always 0 in Phase 1
            key_reasons_json           TEXT,                          -- top reasons supporting the call
            watch_factors_json         TEXT,                           -- what could change the view
            horizon_notes_json         TEXT,                            -- {6m,1y,3y,5y}: short cited notes
            thesis_text                TEXT,
            gaps_note                  TEXT,
            source_financials_asof     TEXT,                             -- staleness marker
            source_market_data_asof    TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interim_updates (
            symbol           TEXT NOT NULL,
            company_name     TEXT,
            period_label     TEXT NOT NULL,   -- e.g. "Q2 2026 (quarter ended 30 June 2026)"
            period_end_date  TEXT NOT NULL,
            generated_at     TEXT NOT NULL,
            note_text        TEXT NOT NULL,    -- what drove the result + other notable details, cited
            qoq_json         TEXT,              -- [{metric,label,prior_period,prior_value,new_period,new_value,pct_change}]
            yoy_json         TEXT,               -- same shape, vs the same quarter a year earlier
            source_doc_id    TEXT NOT NULL,
            source_page      INTEGER,
            gaps_note        TEXT,
            PRIMARY KEY (symbol, period_end_date)
        )
    """)
    conn.commit()
    return conn


def populate_coverage_universe(conn):
    """Fill coverage_universe with every ticker in COVERAGE_UNIVERSE, resolving the
    real company name from tradeSummary where possible (falls back to the bare
    symbol if a ticker isn't currently trading/found -- e.g. a wrong/stale code in
    the list) so the web search bar has something to show for every ticker even
    before any documents exist for it."""
    data = fetch("tradeSummary")
    items = data.get("reqTradeSummery", [])
    name_by_base = {}
    for item in items:
        symbol = item.get("symbol", "")
        base = symbol.upper().split(".")[0]
        name = item.get("name", "")
        if base and name:
            name_by_base[base] = name

    rows = [(base, name_by_base.get(base, base)) for base in COVERAGE_UNIVERSE]
    conn.executemany(
        "INSERT INTO coverage_universe (symbol, company_name) VALUES (?, ?) "
        "ON CONFLICT(symbol) DO UPDATE SET company_name=excluded.company_name",
        rows,
    )
    conn.commit()
    return rows


def classify(file_text: str) -> str:
    t = file_text.lower()
    if "annual report" in t:
        return "ANNUAL_REPORT"
    if "interim" in t:
        return "INTERIM_REPORT"
    return "UNCLASSIFIED"


def pdf_url(path: str) -> str:
    if path.startswith("cmt/"):
        return "https://cdn.cse.lk/" + path
    return "https://cdn.cse.lk/cmt/" + path


def matches_universe(symbol: str) -> bool:
    base = symbol.upper().split(".")[0]
    return base in COVERAGE_UNIVERSE


def normalize_name(text: str) -> str:
    text = text.upper()
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_symbol_lookup() -> dict:
    """Map normalized company name -> (symbol, company_name) for coverage-universe
    companies, using cse.lk's tradeSummary (the only endpoint that returns a full
    name<->symbol master list). Needed because circularAnnouncement (and similarly
    shaped feeds) carry no `symbol` field at all -- the company name only ever
    appears embedded inside free-text `fileText`."""
    data = fetch("tradeSummary")
    items = data.get("reqTradeSummery", [])
    lookup = {}
    for item in items:
        symbol = item.get("symbol", "")
        if not matches_universe(symbol):
            continue
        name = item.get("name", "")
        if not name:
            continue
        # Store the bare base symbol (e.g. "NTB", not "NTB.N0000") -- this must match
        # the form getFinancialAnnouncement's own `symbol` field already uses, or the
        # same company ends up split across two different symbol strings in the
        # documents table (and two separate entries in the web UI's company list).
        base_symbol = symbol.upper().split(".")[0]
        lookup[normalize_name(name)] = (base_symbol, name)
    return lookup


def resolve_from_text(text: str, lookup: dict):
    """Scan free text for a coverage-universe company name. Returns (symbol,
    company_name) or (None, None)."""
    norm_text = normalize_name(text)
    for norm_name, (symbol, name) in lookup.items():
        if norm_name and norm_name in norm_text:
            return symbol, name
    return None, None


# ---------------------------------------------------------------------------
# FETCHING
# ---------------------------------------------------------------------------
def fetch(endpoint: str) -> dict:
    try:
        r = requests.post(BASE + endpoint, data={}, headers=HEADERS, timeout=15)
        return r.json()
    except Exception as e:
        print(f"  [!] {endpoint} failed: {e}")
        return {}


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


# ---------------------------------------------------------------------------
# MAIN COLLECTION RUN
# ---------------------------------------------------------------------------
def collect(conn, endpoint: str, response_key: str, label: str, lookup: dict):
    print(f"\nChecking {label} ({endpoint}) ...")
    data = fetch(endpoint)
    items = data.get(response_key, [])
    print(f"  {len(items)} item(s) in this feed right now (market-wide).")

    new_count = 0
    for item in items:
        symbol = item.get("symbol", "")
        name = item.get("name", "")
        if not symbol:
            # This feed doesn't expose a symbol field (confirmed true for
            # circularAnnouncement) -- the company name only shows up embedded in
            # fileText, so resolve it against the coverage-universe lookup instead
            # of silently dropping every item.
            symbol, name = resolve_from_text(item.get("fileText", ""), lookup)
        if not symbol or not matches_universe(symbol):
            continue  # not one of our covered companies -- skip

        source_id = str(item.get("id"))
        existing = conn.execute(
            "SELECT 1 FROM documents WHERE source_id = ?", (source_id,)
        ).fetchone()
        if existing:
            continue  # already have this one

        file_text = item.get("fileText", "")
        doc_type = classify(file_text) if label == "financial reports" else "CIRCULAR"
        if doc_type not in ("ANNUAL_REPORT", "INTERIM_REPORT"):
            # Scope is deliberately narrowed to annual + interim reports only for now
            # (disclosures/circulars and unclassified items are skipped, not stored).
            continue
        path = item.get("path", "")
        url = pdf_url(path)
        name = name or symbol

        safe_symbol = symbol.replace(".", "_")
        filename = f"{source_id}_{path.split('/')[-1]}"
        local_path = os.path.join(STORAGE_ROOT, safe_symbol, doc_type, filename)

        print(f"  -> NEW: {symbol} | {file_text}")
        sha = download_pdf(url, local_path)

        conn.execute("""
            INSERT INTO documents (source_id, symbol, company_name, doc_type,
                source_category, uploaded_date, source_path, sha256, local_path, discovered_at, source_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'automated')
        """, (source_id, symbol, name, doc_type, file_text,
              item.get("uploadedDate", ""), url, sha, local_path if sha else None,
              datetime.now().isoformat()))
        conn.commit()
        new_count += 1
        time.sleep(1)  # be polite between downloads

    print(f"  Saved {new_count} new document(s) for your coverage universe.")


def collect_market_data(conn):
    """Pulls tradeSummary once and writes one market_data row per symbol in
    coverage_universe (all ~264, not just symbols with documents on file -- this
    part is free/automated, unlike deep financial-statement extraction). Idempotent
    per (symbol, as_of=today): re-running the same day updates that day's snapshot
    rather than creating duplicates."""
    data = fetch("tradeSummary")
    items = data.get("reqTradeSummery", [])
    by_base = {}
    for item in items:
        symbol = item.get("symbol", "")
        base = symbol.upper().split(".")[0]
        if not matches_universe(base):
            continue
        # If a company has multiple share classes (voting/non-voting), keep the
        # one with the larger market cap as the representative row for the base
        # symbol -- consistent with how documents/dividends already collapse to
        # one base symbol per company.
        existing = by_base.get(base)
        if existing is None or (item.get("marketCap") or 0) > (existing.get("marketCap") or 0):
            by_base[base] = item

    as_of = datetime.now().strftime("%Y-%m-%d")
    collected_at = datetime.now().isoformat()
    written = 0
    for base, item in by_base.items():
        closing_price = item.get("closingPrice")
        market_cap = item.get("marketCap")
        shares_outstanding = (market_cap / closing_price) if closing_price else None
        conn.execute(
            """
            INSERT INTO market_data (
                symbol, as_of, collected_at, price, previous_close, closing_price,
                open, high, low, turnover, share_volume, market_cap,
                shares_outstanding, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'tradeSummary')
            ON CONFLICT(symbol, as_of) DO UPDATE SET
                collected_at=excluded.collected_at, price=excluded.price,
                previous_close=excluded.previous_close, closing_price=excluded.closing_price,
                open=excluded.open, high=excluded.high, low=excluded.low,
                turnover=excluded.turnover, share_volume=excluded.share_volume,
                market_cap=excluded.market_cap, shares_outstanding=excluded.shares_outstanding
            """,
            (base, as_of, collected_at, item.get("price"), item.get("previousClose"),
             closing_price, item.get("open"), item.get("high"), item.get("low"),
             item.get("turnover"), item.get("sharevolume"), market_cap, shares_outstanding),
        )
        written += 1
    conn.commit()
    print(f"  Market data: {written} symbol(s) updated for {as_of}.")
    return written


def main():
    conn = init_db()
    print(f"Coverage universe: {len(COVERAGE_UNIVERSE)} symbols")
    lookup = build_symbol_lookup()
    print(f"Name->symbol lookup built: {len(lookup)} coverage-universe compan(ies) resolvable from free text")
    collect(conn, "getFinancialAnnouncement", "reqFinancialAnnouncemnets", "financial reports", lookup)
    # Circulars/other disclosures collection is deliberately disabled for now --
    # scope is narrowed to annual + interim reports only. Re-enable by uncommenting
    # the line below if disclosures coverage is wanted again later.
    # collect(conn, "circularAnnouncement", "reqCircularAnnouncement", "circulars/other disclosures", lookup)

    print("\nCollecting live market data (price/market cap) for the full coverage universe...")
    collect_market_data(conn)

    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    print(f"\nTotal documents stored so far (all-time, this database): {total}")
    print("Run this script again periodically (e.g. daily) to keep accumulating new filings.")
    conn.close()

    print("\nSyncing database to the live hosted site...")
    try:
        from sync_to_pythonanywhere import sync as sync_to_pythonanywhere
        sync_to_pythonanywhere()
    except ImportError:
        print("  [!] sync_to_pythonanywhere.py not found alongside this script -- skipping.")


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# BACKFILL (the past 5 years) -- NOT solved by this script, by design.
# ---------------------------------------------------------------------------
# This feed only ever shows recent activity. To get 2020-2025 history, the honest
# path -- proven by CSEPal's own data -- is a one-time, per-company sourcing pass:
#   1. Search "<Company Name> Annual Report <Year> PDF" per company/year
#   2. Check the company's own Investor Relations page
#   3. Check if older cdn.cse.lk links are still resolvable even though delisted
#      from the live feed (many are)
# This is bounded, one-time work -- not a recurring engineering problem. Once done,
# those files can be inserted into this same `documents` table with source_type='manual'
# so the database treats them identically to what this script collects going forward.
