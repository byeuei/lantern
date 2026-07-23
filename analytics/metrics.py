"""
Fundamental ratios and valuation multiples -- pure functions over already-cited
raw figures from `financial_statements` / `market_data_latest` / `dividends` rows.

Nothing here ever guesses a missing input. Every function returns a `_gaps` list
naming which outputs couldn't be computed and why, alongside whatever it could
compute -- same "absence of evidence is a finding, not silently skipped" discipline
as the rest of this project. Ratios are computed on read, never stored: they're
pure derivations of raw figures that already carry citations, and re-deriving them
is free at this project's scale (a few dozen companies).

Callers pass in plain dict-like rows (sqlite3.Row or dict) -- this module never
opens its own DB connection, so it works identically inside Flask's request-scoped
connection and inside the write-side extraction scripts.
"""
from __future__ import annotations


def _get(row, key):
    """None-safe field access that works for sqlite3.Row or dict."""
    if row is None:
        return None
    try:
        val = row[key]
    except (KeyError, IndexError):
        return None
    return val


def _div(numerator, denominator):
    """Safe division: None if either input is missing or denominator is ~0."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def fundamental_ratios(fs: dict) -> dict:
    """fs: one financial_statements row (ANNUAL or INTERIM). Returns a flat dict of
    ratio_name -> float|None, plus `_gaps`: list of ratio names that couldn't be
    computed and a short reason why."""
    gaps = []
    flagged = set()

    def g(key, note):
        gaps.append(f"{key}: {note}")
        flagged.add(key)

    revenue = _get(fs, "revenue")
    cost_of_sales = _get(fs, "cost_of_sales")
    gross_profit = _get(fs, "gross_profit")
    if gross_profit is None and revenue is not None and cost_of_sales is not None:
        gross_profit = revenue - cost_of_sales

    operating_profit = _get(fs, "operating_profit")
    dep_amort = _get(fs, "depreciation_amortization")
    ebitda = None
    if operating_profit is not None and dep_amort is not None:
        ebitda = operating_profit + dep_amort
    elif operating_profit is not None:
        ebitda = operating_profit  # conservative: no D&A add-back disclosed
        g("ebitda", "depreciation_amortization not disclosed; EBITDA understated (= operating profit only)")
    else:
        g("ebitda", "operating_profit not available")

    pat = _get(fs, "profit_after_tax")
    pbt = _get(fs, "profit_before_tax")
    tax = _get(fs, "tax_expense")

    total_assets = _get(fs, "total_assets")
    current_assets = _get(fs, "current_assets")
    current_liabilities = _get(fs, "current_liabilities")
    inventory = _get(fs, "inventory")
    receivables = _get(fs, "trade_receivables")
    total_liabilities = _get(fs, "total_liabilities")
    total_equity = _get(fs, "total_equity")
    cash = _get(fs, "cash_and_equivalents")
    st_debt = _get(fs, "short_term_borrowings")
    lt_debt = _get(fs, "long_term_borrowings")
    total_debt = None
    if st_debt is not None or lt_debt is not None:
        total_debt = (st_debt or 0) + (lt_debt or 0)
    else:
        g("total_debt", "short/long term borrowings not disclosed")

    finance_costs = _get(fs, "finance_costs")
    cfo = _get(fs, "cash_from_operations")
    capex = _get(fs, "capex")

    result = {
        "gross_profit": gross_profit,
        "gross_margin": _div(gross_profit, revenue),
        "operating_margin": _div(operating_profit, revenue),
        "ebitda": ebitda,
        "ebitda_margin": _div(ebitda, revenue),
        "net_margin": _div(pat, revenue),
        "roe": _div(pat, total_equity),
        "roa": _div(pat, total_assets),
        "roce": _div(operating_profit, (total_assets - current_liabilities)
                      if total_assets is not None and current_liabilities is not None else None),
        "current_ratio": _div(current_assets, current_liabilities),
        "quick_ratio": _div(
            (current_assets - inventory) if current_assets is not None and inventory is not None else None,
            current_liabilities,
        ),
        "debt_to_equity": _div(total_debt, total_equity),
        "net_debt_to_ebitda": _div(
            (total_debt - cash) if total_debt is not None and cash is not None else None, ebitda
        ),
        "interest_coverage": _div(operating_profit, finance_costs),
        "asset_turnover": _div(revenue, total_assets),
        "receivables_turnover": _div(revenue, receivables),
        "working_capital": (current_assets - current_liabilities)
                            if current_assets is not None and current_liabilities is not None else None,
        "free_cash_flow": (cfo - capex) if cfo is not None and capex is not None else None,
    }

    # ROIC: NOPAT / invested capital. NOPAT = operating_profit * (1 - effective tax
    # rate) when PBT/tax are both disclosed; else fall back to pre-tax and flag it
    # explicitly rather than silently mixing pre-/post-tax figures.
    invested_capital = None
    if total_debt is not None and total_equity is not None:
        invested_capital = total_debt + total_equity
    if operating_profit is not None and invested_capital:
        if pbt and tax is not None and pbt != 0:
            effective_tax_rate = tax / pbt
            nopat = operating_profit * (1 - effective_tax_rate)
            result["roic"] = nopat / invested_capital
            result["roic_basis"] = "post-tax"
        else:
            result["roic"] = operating_profit / invested_capital
            result["roic_basis"] = "pre-tax (tax rate not derivable)"
            g("roic", "profit_before_tax/tax_expense not both disclosed; using pre-tax operating profit instead of NOPAT")
    else:
        result["roic"] = None
        result["roic_basis"] = None
        g("roic", "operating_profit or invested capital (debt+equity) not available")

    for key, val in list(result.items()):
        if val is None and not key.endswith("_basis") and key not in flagged:
            g(key, "one or more required inputs not disclosed for this period")

    result["_gaps"] = gaps
    return result


def valuation_multiples(fs: dict, market: dict, latest_dps: float | None = None) -> dict:
    """fs: latest ANNUAL row for the symbol (fall back to COMPANY basis if GROUP
    absent -- caller's responsibility to pick the right row). market: a
    market_data_latest row. latest_dps: most recent per-share dividend from the
    `dividends` table, if any. Returns valuation_name -> float|None plus `_gaps`."""
    gaps = []

    # financial_statements figures are stored in whatever unit the source filing
    # used (unit_scale: '1', '000', or '000000') -- market_cap from tradeSummary is
    # always absolute currency. Scale every fs figure up to absolute units before
    # comparing the two, or P/B and EV/EBITDA come out ~1000x too high whenever a
    # filing is stated in Rs'000 (the common case).
    scale_map = {"1": 1, "000": 1_000, "000000": 1_000_000}
    unit_scale = _get(fs, "unit_scale") or "1"
    scale = scale_map.get(unit_scale, 1)

    price = _get(market, "closing_price") or _get(market, "price")
    market_cap = _get(market, "market_cap")
    eps = _get(fs, "eps_basic")  # per-share figures are always stated in absolute currency, never scaled
    total_equity = _get(fs, "total_equity")
    if total_equity is not None:
        total_equity = total_equity * scale
    pat = _get(fs, "profit_after_tax")

    operating_profit = _get(fs, "operating_profit")
    dep_amort = _get(fs, "depreciation_amortization")
    ebitda = (operating_profit + dep_amort) if operating_profit is not None and dep_amort is not None else operating_profit
    if ebitda is not None:
        ebitda = ebitda * scale

    st_debt = _get(fs, "short_term_borrowings")
    lt_debt = _get(fs, "long_term_borrowings")
    total_debt = (st_debt or 0) + (lt_debt or 0) if (st_debt is not None or lt_debt is not None) else None
    if total_debt is not None:
        total_debt = total_debt * scale
    cash = _get(fs, "cash_and_equivalents")
    if cash is not None:
        cash = cash * scale

    enterprise_value = None
    if market_cap is not None and total_debt is not None and cash is not None:
        enterprise_value = market_cap + total_debt - cash

    pe_ratio = _div(price, eps)
    pb_ratio = _div(market_cap, total_equity)
    ev_ebitda = _div(enterprise_value, ebitda)
    dividend_yield = _div(latest_dps, price)
    payout_ratio = _div(latest_dps, eps)

    if price is None:
        gaps.append("pe_ratio/pb_ratio/dividend_yield: no current market price available")
    if eps is None:
        gaps.append("pe_ratio/payout_ratio: eps_basic not available in latest annual financials")
    if total_debt is None or cash is None:
        gaps.append("ev_ebitda: total debt or cash not disclosed -- enterprise value not computable")
    if latest_dps is None:
        gaps.append("dividend_yield/payout_ratio: no dividend on file for this symbol")

    return {
        "price": price,
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "pe_ratio": pe_ratio,
        "pb_ratio": pb_ratio,
        "ev_ebitda": ev_ebitda,
        "dividend_yield": dividend_yield,
        "payout_ratio": payout_ratio,
        "_gaps": gaps,
    }


def cagr(series: list[tuple[str, float]], years: int) -> float | None:
    """series: [(period_end_date, value), ...] ascending by date. Returns the CAGR
    over approximately `years` using the earliest and latest points available,
    or None if there's insufficient history or the start value isn't positive
    (CAGR is undefined/misleading for a loss-making or zero base year)."""
    clean = [(d, v) for d, v in series if v is not None]
    if len(clean) < 2:
        return None
    clean.sort(key=lambda x: x[0])
    start_date, start_val = clean[0]
    end_date, end_val = clean[-1]
    if start_val is None or start_val <= 0:
        return None
    try:
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
    except (ValueError, TypeError):
        return None
    span = end_year - start_year
    if span <= 0:
        return None
    return (end_val / start_val) ** (1 / span) - 1
