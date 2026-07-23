#!/usr/bin/env python3
"""
Manual financial-statement entry -- mirrors manual_backfill.py's convention for a
different table. Claude reads an actual annual/interim report PDF, transcribes the
disclosed figures, and calls insert_financial_statements() with one dict per period.
There is no OCR/structured-extraction pipeline here by design -- every figure passes
through a human/AI reading step before it reaches the database.

Validation enforces this project's citation discipline: a period with no page
reference at all is rejected outright (every figure must be traceable to a source
document), and a source_doc_id that doesn't belong to the stated symbol is rejected
(catches copy-paste mistakes against the wrong company's report). Unit-scale drift
and basic accounting-identity checks (assets = liabilities + equity, PBT - tax = PAT)
are warned but not blocked, since real filings do have minor rounding/NCI noise that
shouldn't stop a legitimate entry.

Usage: import and call insert_financial_statements() with a list of entries.
"""
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.cse_documents_collector import DB_PATH, init_db
from analytics.report_diff import diff_periods

REQUIRED_FIELDS = ("symbol", "period_type", "period_label", "period_end_date", "source_doc_id")
PAGE_FIELDS = ("income_statement_page", "balance_sheet_page", "cashflow_page")
VALID_PERIOD_TYPES = {"ANNUAL", "INTERIM"}
VALID_BASES = {"GROUP", "COMPANY"}

FINANCIAL_FIELDS = (
    "revenue", "cost_of_sales", "gross_profit", "operating_profit",
    "depreciation_amortization", "finance_costs", "finance_income",
    "profit_before_tax", "tax_expense", "profit_after_tax", "minority_interest",
    "eps_basic", "eps_diluted",
    "total_assets", "current_assets", "inventory", "trade_receivables",
    "cash_and_equivalents", "total_liabilities", "current_liabilities",
    "trade_payables", "short_term_borrowings", "long_term_borrowings",
    "total_equity", "shares_in_issue",
    "cash_from_operations", "capex", "cash_from_investing", "cash_from_financing",
)


class ValidationError(ValueError):
    pass


def _validate_hard(entry: dict, conn) -> None:
    for field in REQUIRED_FIELDS:
        if not entry.get(field):
            raise ValidationError(f"{entry.get('symbol', '?')}: missing required field '{field}'")

    try:
        datetime.strptime(entry["period_end_date"], "%Y-%m-%d")
    except ValueError:
        raise ValidationError(f"{entry['symbol']}: period_end_date '{entry['period_end_date']}' is not YYYY-MM-DD")

    if entry["period_type"] not in VALID_PERIOD_TYPES:
        raise ValidationError(f"{entry['symbol']}: period_type must be one of {VALID_PERIOD_TYPES}, got '{entry['period_type']}'")

    basis = entry.get("basis", "GROUP")
    if basis not in VALID_BASES:
        raise ValidationError(f"{entry['symbol']}: basis must be one of {VALID_BASES}, got '{basis}'")

    if not any(entry.get(f) for f in PAGE_FIELDS):
        raise ValidationError(
            f"{entry['symbol']} {entry['period_label']}: no page citation given "
            f"(at least one of {PAGE_FIELDS} is required) -- every figure must be traceable"
        )

    doc_row = conn.execute(
        "SELECT symbol FROM documents WHERE source_id = ?", (entry["source_doc_id"],)
    ).fetchone()
    if doc_row is None:
        raise ValidationError(f"{entry['symbol']}: source_doc_id '{entry['source_doc_id']}' not found in documents table")
    if doc_row[0] != entry["symbol"]:
        raise ValidationError(
            f"{entry['symbol']}: source_doc_id '{entry['source_doc_id']}' belongs to symbol "
            f"'{doc_row[0]}', not '{entry['symbol']}' -- likely a copy-paste citation error"
        )


def _validate_soft(entry: dict, conn) -> list[str]:
    warnings = []
    symbol = entry["symbol"]
    unit_scale = entry.get("unit_scale", "000")

    prior = conn.execute(
        "SELECT unit_scale FROM financial_statements WHERE symbol = ? ORDER BY period_end_date DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    if prior and prior[0] != unit_scale:
        warnings.append(
            f"unit_scale '{unit_scale}' differs from this symbol's most recent stored row "
            f"('{prior[0]}') -- double check this isn't a Rs vs Rs'000 mistake"
        )

    ta, tl, te = entry.get("total_assets"), entry.get("total_liabilities"), entry.get("total_equity")
    if ta is not None and tl is not None and te is not None and ta != 0:
        diff_pct = abs(ta - (tl + te)) / abs(ta)
        if diff_pct > 0.01:
            warnings.append(f"total_assets ({ta}) != total_liabilities+total_equity ({tl + te}) by {diff_pct:.1%}")

    pbt, tax, pat = entry.get("profit_before_tax"), entry.get("tax_expense"), entry.get("profit_after_tax")
    if pbt is not None and tax is not None and pat is not None and pbt != 0:
        expected_pat = pbt - tax
        diff_pct = abs(pat - expected_pat) / abs(pbt)
        if diff_pct > 0.01:
            warnings.append(f"profit_before_tax - tax_expense ({expected_pat}) != profit_after_tax ({pat}) by {diff_pct:.1%}")

    return warnings


def insert_financial_statements(entries: list[dict]) -> int:
    """entries: list of dicts. Required: symbol, period_type, period_label,
    period_end_date, source_doc_id, plus at least one of income_statement_page/
    balance_sheet_page/cashflow_page. Optional: basis (default GROUP), currency
    (default LKR), unit_scale (default '000'), company_name, notes, and any subset
    of FINANCIAL_FIELDS. Upserts on (symbol, period_end_date, period_type, basis) --
    re-running to fix a mistake is idempotent."""
    conn = init_db()
    conn.row_factory = sqlite3.Row
    inserted = 0

    for entry in entries:
        _validate_hard(entry, conn)
        warnings = _validate_soft(entry, conn)
        for w in warnings:
            print(f"  [warn] {entry['symbol']} {entry['period_label']}: {w}")

        basis = entry.get("basis", "GROUP")
        currency = entry.get("currency", "LKR")
        unit_scale = entry.get("unit_scale", "000")

        columns = ["symbol", "company_name", "period_type", "period_label", "period_end_date",
                   "basis", "currency", "unit_scale", "source_doc_id",
                   "income_statement_page", "balance_sheet_page", "cashflow_page", "notes"]
        values = [entry["symbol"], entry.get("company_name"), entry["period_type"],
                  entry["period_label"], entry["period_end_date"], basis, currency, unit_scale,
                  entry["source_doc_id"], entry.get("income_statement_page"),
                  entry.get("balance_sheet_page"), entry.get("cashflow_page"), entry.get("notes")]

        for field in FINANCIAL_FIELDS:
            if field in entry:
                columns.append(field)
                values.append(entry[field])

        placeholders = ", ".join("?" for _ in columns)
        update_clause = ", ".join(f"{c}=excluded.{c}" for c in columns if c not in
                                   ("symbol", "period_end_date", "period_type", "basis"))

        conn.execute(
            f"""
            INSERT INTO financial_statements ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(symbol, period_end_date, period_type, basis)
            DO UPDATE SET {update_clause}
            """,
            values,
        )
        conn.commit()
        print(f"  -> {entry['symbol']} {entry['period_label']} ({basis}): stored")
        inserted += 1

        diffs = diff_periods(conn, entry["symbol"], entry["period_type"], basis, limit=5)
        if diffs:
            print(f"     top changes vs prior period:")
            for d in diffs:
                if d["pct_change"] is not None:
                    print(f"       {d['label']}: {d['prior_value']:,.2f} -> {d['new_value']:,.2f} ({d['pct_change']*100:+.1f}%)")
                else:
                    print(f"       {d['label']}: {d['direction']}")

    conn.close()
    print(f"\nInserted/updated {inserted} financial_statements row(s).")
    return inserted


if __name__ == "__main__":
    print("Import insert_financial_statements() and call it with a list of sourced entries.")
