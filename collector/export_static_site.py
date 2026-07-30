#!/usr/bin/env python3
"""
Exports the collector's SQLite database into a self-contained tree of static
JSON files under docs/site_data/, for GitHub Pages hosting -- the static-site
counterpart of web/app.py's read-only JSON API.

Every value here is produced with the exact same analytics/ functions and SQL
that web/app.py's routes use, so the static site and the live Flask app never
diverge in what a figure means -- only in *when* it's computed (export time vs.
request time). Re-run this after any data or extraction change and the static
site picks it up on the next commit+push, same as the live site does today.

Usage:
    python export_static_site.py
"""
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "cse_documents.db"
OUT_DIR = PROJECT_ROOT / "docs" / "site_data"
COMPANIES_DIR = OUT_DIR / "companies"

sys.path.insert(0, str(PROJECT_ROOT))
from analytics.metrics import fundamental_ratios, valuation_multiples
from analytics.report_diff import diff_periods


def _financials_rows(db, symbol, period_type=None, basis=None):
    query = "SELECT * FROM financial_statements WHERE symbol = ?"
    params = [symbol]
    if period_type:
        query += " AND period_type = ?"
        params.append(period_type)
    if basis:
        query += " AND basis = ?"
        params.append(basis)
    query += " ORDER BY period_end_date"
    return [dict(r) for r in db.execute(query, params).fetchall()]


def _preferred_annual_rows(db, symbol):
    rows = _financials_rows(db, symbol, period_type="ANNUAL")
    by_period = {}
    for r in rows:
        existing = by_period.get(r["period_end_date"])
        if existing is None or (r["basis"] == "GROUP" and existing["basis"] != "GROUP"):
            by_period[r["period_end_date"]] = r
    return [by_period[k] for k in sorted(by_period)]


def _to_frontend_shape(fs_row):
    return {
        "period": fs_row["period_label"],
        "period_end_date": fs_row["period_end_date"],
        "basis": fs_row["basis"],
        "revenue": fs_row["revenue"],
        "operating_income": fs_row["operating_profit"],
        "pbt": fs_row["profit_before_tax"],
        "pat": fs_row["profit_after_tax"],
        "eps": fs_row["eps_basic"],
        "currency": fs_row["currency"],
        "source_doc_id": fs_row["source_doc_id"],
        "source_page": fs_row["income_statement_page"] or fs_row["balance_sheet_page"] or fs_row["cashflow_page"],
    }


def _market_data_with_valuation(db, symbol):
    """Mirrors /api/market_data's response shape exactly (valuation nested inside)."""
    row = db.execute("SELECT * FROM market_data_latest WHERE symbol = ?", (symbol,)).fetchone()
    if not row:
        return None
    result = dict(row)
    latest_fs = _financials_rows(db, symbol, period_type="ANNUAL", basis="GROUP")
    if not latest_fs:
        latest_fs = _financials_rows(db, symbol, period_type="ANNUAL")
    latest_dps_row = db.execute(
        "SELECT dps FROM dividends WHERE symbol = ? ORDER BY period DESC LIMIT 1", (symbol,)
    ).fetchone()
    latest_dps = latest_dps_row["dps"] if latest_dps_row else None
    result["valuation"] = valuation_multiples(latest_fs[-1], result, latest_dps) if latest_fs else None
    return result


def _thesis(db, symbol):
    row = db.execute("SELECT * FROM thesis WHERE symbol = ?", (symbol,)).fetchone()
    if not row:
        return None
    result = dict(row)
    result["pillar_scores"] = json.loads(result.pop("pillar_scores_json"))
    result["weights_used"] = json.loads(result.pop("weights_used_json"))
    result["key_reasons"] = json.loads(result.pop("key_reasons_json") or "[]")
    result["watch_factors"] = json.loads(result.pop("watch_factors_json") or "[]")
    result["horizon_notes"] = json.loads(result.pop("horizon_notes_json") or "{}")
    return result


def _interim_updates(db, symbol):
    rows = db.execute(
        "SELECT * FROM interim_updates WHERE symbol = ? ORDER BY period_end_date DESC", (symbol,)
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["qoq"] = json.loads(d.pop("qoq_json") or "[]")
        d["yoy"] = json.loads(d.pop("yoy_json") or "[]")
        d["operational_highlights"] = json.loads(d.pop("operational_highlights_json") or "[]")
        d["key_drivers"] = json.loads(d.pop("key_drivers_json") or "[]")
        result.append(d)
    return result


def _shareholder_info(db, symbol):
    row = db.execute(
        "SELECT * FROM shareholder_info_latest WHERE symbol = ?", (symbol,)
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["top_shareholders"] = json.loads(d.pop("top_shareholders_json") or "[]")
    return d


def _price_history(db, symbol, days=90):
    rows = db.execute(
        """
        SELECT as_of, price, closing_price FROM market_data
        WHERE symbol = ? ORDER BY as_of DESC LIMIT ?
        """,
        (symbol, days),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def _compare_snapshot(db, symbol, company_name):
    """Mirrors app.py's _company_snapshot() exactly (valuation as a sibling key,
    not nested in market_data) -- the compare-mode shape the frontend expects."""
    summary_row = db.execute(
        "SELECT summary_text, gaps_note FROM summaries WHERE symbol = ?", (symbol,)
    ).fetchone()
    earnings = [_to_frontend_shape(r) for r in _preferred_annual_rows(db, symbol)]
    interim_rows = _financials_rows(db, symbol, period_type="INTERIM")
    quarters = [_to_frontend_shape(r) for r in interim_rows]
    market_row = db.execute("SELECT * FROM market_data_latest WHERE symbol = ?", (symbol,)).fetchone()
    market = dict(market_row) if market_row else None
    latest_dps_row = db.execute(
        "SELECT dps FROM dividends WHERE symbol = ? ORDER BY period DESC LIMIT 1", (symbol,)
    ).fetchone()
    latest_dps = latest_dps_row["dps"] if latest_dps_row else None
    annual_rows = _preferred_annual_rows(db, symbol)
    valuation = valuation_multiples(annual_rows[-1], market, latest_dps) if (annual_rows and market) else None
    thesis_row = db.execute(
        "SELECT recommendation, composite_score, thesis_text FROM thesis WHERE symbol = ?", (symbol,)
    ).fetchone()

    # Ratios and YoY growth -- absolute Revenue/PAT/EPS aren't comparable across
    # companies of different sizes, so the compare view needs scale-independent
    # metrics instead: margins, returns, leverage, and growth rates.
    ratios_annual = fundamental_ratios(annual_rows[-1]) if annual_rows else None
    ratios_quarterly = fundamental_ratios(interim_rows[-1]) if interim_rows else None

    revenue_growth_yoy = None
    pat_growth_yoy = None
    if len(annual_rows) >= 2:
        prev, latest = annual_rows[-2], annual_rows[-1]
        prev_rev, latest_rev = prev["revenue"], latest["revenue"]
        if prev_rev not in (None, 0) and latest_rev is not None:
            revenue_growth_yoy = (latest_rev - prev_rev) / abs(prev_rev)
        prev_pat, latest_pat = prev["profit_after_tax"], latest["profit_after_tax"]
        if prev_pat not in (None, 0) and latest_pat is not None:
            pat_growth_yoy = (latest_pat - prev_pat) / abs(prev_pat)

    return {
        "symbol": symbol,
        "company_name": company_name,
        "summary_text": summary_row["summary_text"] if summary_row else None,
        "gaps_note": summary_row["gaps_note"] if summary_row else None,
        "annual": earnings,
        "quarterly": quarters,
        "market_data": market,
        "valuation": valuation,
        "ratios_annual": ratios_annual,
        "ratios_quarterly": ratios_quarterly,
        "revenue_growth_yoy": revenue_growth_yoy,
        "pat_growth_yoy": pat_growth_yoy,
        "thesis": dict(thesis_row) if thesis_row else None,
    }


def build_company_bundle(db, symbol, company_name):
    documents = [dict(r) for r in db.execute("""
        SELECT symbol, company_name, doc_type, source_category,
               uploaded_date, source_path, discovered_at, source_type
        FROM documents WHERE symbol = ? ORDER BY uploaded_date DESC
    """, (symbol,)).fetchall()]

    summary_row = db.execute("""
        SELECT symbol, company_name, generated_at, summary_text, gaps_note,
               income_statement_analysis, balance_sheet_analysis, cash_flow_analysis,
               equity_statement_analysis, other_statements_analysis
        FROM summaries WHERE symbol = ?
    """, (symbol,)).fetchone()
    summary = None
    if summary_row:
        summary = dict(summary_row)
        summary["earnings_comparison"] = [_to_frontend_shape(r) for r in _preferred_annual_rows(db, symbol)]

    financials_annual = _financials_rows(db, symbol, period_type="ANNUAL")

    # Ratios + report_diff precomputed for every basis actually present, so the
    # frontend's basis toggle is an instant in-memory switch instead of a fetch.
    bases_present = sorted({r["basis"] for r in financials_annual}) or ["GROUP"]
    ratios, report_diff = {}, {}
    for basis in bases_present:
        rows = _financials_rows(db, symbol, period_type="ANNUAL", basis=basis)
        ratios[basis] = [
            {**{"period_label": r["period_label"], "period_end_date": r["period_end_date"]}, **fundamental_ratios(r)}
            for r in rows
        ]
        report_diff[basis] = diff_periods(db, symbol, "ANNUAL", basis, limit=20)

    return {
        "documents": documents,
        "summary": summary,
        "financials_interim": _financials_rows(db, symbol, period_type="INTERIM"),
        "financials_annual": financials_annual,
        "market_data": _market_data_with_valuation(db, symbol),
        "thesis": _thesis(db, symbol),
        "ratios": ratios,
        "report_diff": report_diff,
        "interim_updates": _interim_updates(db, symbol),
        "shareholder_info": _shareholder_info(db, symbol),
        "price_history": _price_history(db, symbol),
        "compare_snapshot": _compare_snapshot(db, symbol, company_name),
    }


def main():
    if not DB_PATH.exists():
        print(f"[!] {DB_PATH} not found -- nothing to export.")
        sys.exit(1)

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    universe_rows = [dict(r) for r in db.execute("""
        SELECT symbol, company_name, doc_count FROM (
            SELECT cu.symbol AS symbol, cu.company_name AS company_name,
                   COALESCE((SELECT COUNT(*) FROM documents d WHERE d.symbol = cu.symbol), 0) AS doc_count
            FROM coverage_universe cu
            UNION
            SELECT d.symbol AS symbol, MAX(d.company_name) AS company_name, COUNT(*) AS doc_count
            FROM documents d
            WHERE d.symbol NOT IN (SELECT symbol FROM coverage_universe)
            GROUP BY d.symbol
        )
        ORDER BY symbol
    """).fetchall()]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    COMPANIES_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUT_DIR / "coverage_universe.json", "w", encoding="utf-8") as f:
        json.dump(universe_rows, f, ensure_ascii=False)

    for row in universe_rows:
        symbol = row["symbol"]
        bundle = build_company_bundle(db, symbol, row["company_name"])
        with open(COMPANIES_DIR / f"{symbol}.json", "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=False)

    db.close()
    print(f"Exported {len(universe_rows)} companies to {OUT_DIR}")


if __name__ == "__main__":
    main()
