#!/usr/bin/env python3
"""
Lantern web server -- V0.1

Serves web/documents_module.html and exposes the collector's SQLite database
(../data/cse_documents.db) as read-only JSON. No writes, no interpretation of the
data beyond what the collector already stored -- same "store first, interpret never"
principle as the collector itself.

Usage:
    python app.py
"""
import hashlib
import hmac
import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path

from flask import Flask, Response, g, jsonify, request, send_from_directory

WEB_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WEB_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "cse_documents.db"

sys.path.insert(0, str(PROJECT_ROOT))
from analytics.metrics import fundamental_ratios, valuation_multiples
from analytics.report_diff import diff_periods

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Basic HTTP auth -- this app has no user accounts and, once hosted, gets a
# public URL. Set LANTERN_USERNAME/LANTERN_PASSWORD as real environment
# variables wherever this runs (do NOT rely on the fallback defaults below in
# any hosted deployment -- they exist only so local development doesn't
# require extra setup).
# ---------------------------------------------------------------------------
LANTERN_USERNAME = os.environ.get("LANTERN_USERNAME", "lantern")
LANTERN_PASSWORD = os.environ.get("LANTERN_PASSWORD", "changeme")


@app.before_request
def _require_auth():
    # The GitHub deploy webhook can't send Basic Auth -- it's protected
    # separately by its own HMAC signature check instead (see deploy_hook()).
    if request.path == "/deploy-hook":
        return
    auth = request.authorization
    if not auth or auth.username != LANTERN_USERNAME or auth.password != LANTERN_PASSWORD:
        return Response(
            "Authentication required.", 401,
            {"WWW-Authenticate": 'Basic realm="Lantern"'},
        )


# ---------------------------------------------------------------------------
# GitHub auto-deploy webhook -- on every push to the repo, GitHub POSTs here.
# We verify the payload really came from GitHub (HMAC signature against a
# shared secret), pull the latest code, then ask PythonAnywhere's API to
# reload the web app so the change actually takes effect.
# ---------------------------------------------------------------------------
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
PYTHONANYWHERE_API_TOKEN = os.environ.get("PYTHONANYWHERE_API_TOKEN", "")
PYTHONANYWHERE_USERNAME = os.environ.get("PYTHONANYWHERE_USERNAME", "")
PYTHONANYWHERE_DOMAIN = os.environ.get("PYTHONANYWHERE_DOMAIN", "")


def _do_pull_and_reload():
    """Runs in a background thread -- git pull + the PythonAnywhere reload API
    call together can take longer than the platform's request timeout, which
    was causing the webhook request itself to be killed (502) before Flask
    ever got to respond. Firing this in the background lets deploy_hook()
    answer GitHub immediately instead."""
    log_path = PROJECT_ROOT / "deploy-hook.log"
    with open(log_path, "a") as log:
        pull = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
        )
        log.write(f"\n--- {datetime_now_iso()} ---\n")
        log.write(f"git pull: rc={pull.returncode}\n{pull.stdout}\n{pull.stderr}\n")
        if pull.returncode != 0:
            return

        if PYTHONANYWHERE_API_TOKEN and PYTHONANYWHERE_USERNAME and PYTHONANYWHERE_DOMAIN:
            import requests
            reload_url = (
                f"https://www.pythonanywhere.com/api/v0/user/"
                f"{PYTHONANYWHERE_USERNAME}/webapps/{PYTHONANYWHERE_DOMAIN}/reload/"
            )
            try:
                r = requests.post(
                    reload_url,
                    headers={"Authorization": f"Token {PYTHONANYWHERE_API_TOKEN}"},
                    timeout=30,
                )
                log.write(f"reload: {r.status_code} {r.text}\n")
            except Exception as e:
                log.write(f"reload failed: {e}\n")


def datetime_now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@app.route("/deploy-hook", methods=["POST"])
def deploy_hook():
    if not GITHUB_WEBHOOK_SECRET:
        return "webhook not configured", 503

    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), request.get_data(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return "invalid signature", 403

    import threading
    threading.Thread(target=_do_pull_and_reload, daemon=True).start()
    return "accepted, deploying in background", 202


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "documents_module.html")


@app.route("/api/companies")
def companies():
    db = get_db()
    rows = db.execute("""
        SELECT symbol, company_name, COUNT(*) AS doc_count
        FROM documents
        GROUP BY symbol
        ORDER BY symbol
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/coverage_universe")
def coverage_universe():
    db = get_db()
    # Union coverage_universe (the ~93-ticker target list) with any symbol that
    # already has real documents/summaries but isn't (yet, or anymore) in that
    # list -- e.g. tickers collected before the list was finalized -- so nothing
    # with real data on file becomes unfindable in search.
    rows = db.execute("""
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
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/documents")
def documents():
    db = get_db()
    symbol = request.args.get("symbol")
    if symbol:
        rows = db.execute("""
            SELECT symbol, company_name, doc_type, source_category,
                   uploaded_date, source_path, discovered_at, source_type
            FROM documents
            WHERE symbol = ?
            ORDER BY uploaded_date DESC
        """, (symbol,)).fetchall()
    else:
        rows = db.execute("""
            SELECT symbol, company_name, doc_type, source_category,
                   uploaded_date, source_path, discovered_at, source_type
            FROM documents
            ORDER BY uploaded_date DESC
        """).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/summary")
def summary():
    db = get_db()
    symbol = request.args.get("symbol", "")
    row = db.execute("""
        SELECT symbol, company_name, generated_at, summary_text, gaps_note
        FROM summaries WHERE symbol = ?
    """, (symbol,)).fetchone()
    if not row:
        return jsonify(None), 404
    result = dict(row)
    result["earnings_comparison"] = [_to_frontend_shape(r) for r in _preferred_annual_rows(db, symbol)]
    return jsonify(result)


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
    """One row per period_end_date: GROUP basis preferred, COMPANY as fallback --
    matches how the frontend expects a single earnings-comparison series per period."""
    rows = _financials_rows(db, symbol, period_type="ANNUAL")
    by_period = {}
    for r in rows:
        existing = by_period.get(r["period_end_date"])
        if existing is None or (r["basis"] == "GROUP" and existing["basis"] != "GROUP"):
            by_period[r["period_end_date"]] = r
    return [by_period[k] for k in sorted(by_period)]


def _to_frontend_shape(fs_row):
    """Maps financial_statements columns to the field names the frontend's
    renderSummary()/renderCompareTable() already expect."""
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


@app.route("/api/financials")
def financials():
    db = get_db()
    symbol = request.args.get("symbol", "")
    period_type = request.args.get("period_type")
    basis = request.args.get("basis")
    rows = _financials_rows(db, symbol, period_type, basis)
    return jsonify(rows)


@app.route("/api/market_data")
def market_data():
    db = get_db()
    symbol = request.args.get("symbol", "")
    row = db.execute("SELECT * FROM market_data_latest WHERE symbol = ?", (symbol,)).fetchone()
    if not row:
        return jsonify(None), 404
    result = dict(row)
    latest_fs = _financials_rows(db, symbol, period_type="ANNUAL", basis="GROUP")
    if not latest_fs:
        latest_fs = _financials_rows(db, symbol, period_type="ANNUAL")
    latest_dps_row = db.execute(
        "SELECT dps FROM dividends WHERE symbol = ? ORDER BY period DESC LIMIT 1", (symbol,)
    ).fetchone()
    latest_dps = latest_dps_row["dps"] if latest_dps_row else None
    if latest_fs:
        result["valuation"] = valuation_multiples(latest_fs[-1], result, latest_dps)
    else:
        result["valuation"] = None
    return jsonify(result)


@app.route("/api/ratios")
def ratios():
    db = get_db()
    symbol = request.args.get("symbol", "")
    period_type = request.args.get("period_type", "ANNUAL")
    basis = request.args.get("basis", "GROUP")
    rows = _financials_rows(db, symbol, period_type, basis)
    if not rows:
        rows = _financials_rows(db, symbol, period_type)
    return jsonify([{**{"period_label": r["period_label"], "period_end_date": r["period_end_date"]},
                      **fundamental_ratios(r)} for r in rows])


@app.route("/api/thesis")
def thesis():
    db = get_db()
    symbol = request.args.get("symbol", "")
    row = db.execute("SELECT * FROM thesis WHERE symbol = ?", (symbol,)).fetchone()
    if not row:
        return jsonify(None), 404
    result = dict(row)
    result["pillar_scores"] = json.loads(result.pop("pillar_scores_json"))
    result["weights_used"] = json.loads(result.pop("weights_used_json"))
    result["key_reasons"] = json.loads(result.pop("key_reasons_json") or "[]")
    result["watch_factors"] = json.loads(result.pop("watch_factors_json") or "[]")
    result["horizon_notes"] = json.loads(result.pop("horizon_notes_json") or "{}")
    return jsonify(result)


@app.route("/api/report_diff")
def report_diff():
    db = get_db()
    symbol = request.args.get("symbol", "")
    period_type = request.args.get("period_type", "ANNUAL")
    basis = request.args.get("basis", "GROUP")
    changes = diff_periods(db, symbol, period_type, basis, limit=20)
    return jsonify(changes)


@app.route("/api/interim_updates")
def interim_updates():
    """Latest-interim QoQ/YoY note(s) for a symbol -- a distinct section from the
    AI Summary card, populated on demand whenever a new interim is flagged (see
    collector/financials_entry.py + the interim-note generation process), not
    auto-generated for every company."""
    db = get_db()
    symbol = request.args.get("symbol", "")
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
    return jsonify(result)


@app.route("/api/shareholder_info")
def shareholder_info():
    db = get_db()
    symbol = request.args.get("symbol", "")
    row = db.execute("SELECT * FROM shareholder_info_latest WHERE symbol = ?", (symbol,)).fetchone()
    if not row:
        return jsonify(None), 404
    result = dict(row)
    result["top_shareholders"] = json.loads(result.pop("top_shareholders_json") or "[]")
    return jsonify(result)


@app.route("/api/price_history")
def price_history():
    db = get_db()
    symbol = request.args.get("symbol", "")
    rows = db.execute(
        "SELECT as_of, price, closing_price FROM market_data WHERE symbol = ? ORDER BY as_of DESC LIMIT 90",
        (symbol,),
    ).fetchall()
    return jsonify([dict(r) for r in reversed(rows)])


def _company_snapshot(db, symbol):
    """Everything needed to render one column of the compare view."""
    name_row = db.execute(
        "SELECT company_name FROM coverage_universe WHERE symbol = ?", (symbol,)
    ).fetchone()
    company_name = name_row["company_name"] if name_row else symbol

    summary_row = db.execute("""
        SELECT summary_text, gaps_note
        FROM summaries WHERE symbol = ?
    """, (symbol,)).fetchone()

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

    thesis_row = db.execute("SELECT recommendation, composite_score, thesis_text FROM thesis WHERE symbol = ?", (symbol,)).fetchone()

    return {
        "symbol": symbol,
        "company_name": company_name,
        "summary_text": summary_row["summary_text"] if summary_row else None,
        "gaps_note": summary_row["gaps_note"] if summary_row else None,
        "annual": earnings,
        "quarterly": quarters,
        "market_data": market,
        "valuation": valuation,
        "thesis": dict(thesis_row) if thesis_row else None,
    }


@app.route("/api/compare")
def compare():
    db = get_db()
    symbols_param = request.args.get("symbols", "")
    symbols = [s.strip().upper() for s in symbols_param.split(",") if s.strip()]
    if not symbols:
        return jsonify({"error": "provide ?symbols=A,B,C"}), 400
    if len(symbols) > 6:
        return jsonify({"error": "compare at most 6 companies at a time"}), 400
    return jsonify([_company_snapshot(db, s) for s in symbols])


if __name__ == "__main__":
    app.run(debug=True, port=5000)
