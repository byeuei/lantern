# Lantern — Sri Lankan Equity Research Platform

Personal research platform for the Colombo Stock Exchange. Goal: cut company research
time from hours to under 5 minutes, backed by a real, verified, growing document and
data archive — not by an AI guessing at numbers.

**Read this whole file before changing anything.** It started as the handoff from a
long design conversation; the status table below has since been updated (2026-07-30)
to match what's actually running, not the original prototype snapshot.

## Project status (as of 2026-07-30)

| Piece | Status |
|---|---|
| PRD, research methodology, Collector architecture | Designed, in `docs/` |
| CSE data source | Reverse-engineered, confirmed working, unofficial (see "What's confirmed" below) |
| Documents collector (`collector/cse_documents_collector.py`) | Running daily via `collector/run_daily_collector.ps1` (Windows Task Scheduler). DB has real accumulated data: 693 documents, 439 dividends, 85 financial statement periods, 3,632 market data points, across the full 264-company coverage universe. |
| Manual entry tools (`collector/financials_entry.py`, `collector/manual_backfill.py`) | Working — used to hand-enter interim/annual figures (with page-citation validation) and backfill older documents the live feed can't surface. Precedent: CCS financial statements, KZOO interim updates. |
| Web UI — live (`web/app.py`) | Working Flask app, reads real SQLite DB via `analytics/metrics.py` and `analytics/report_diff.py`, Basic Auth protected, GitHub webhook auto-deploy at `/deploy-hook`. |
| Web UI — static (`docs/index.html` + `docs/site_data/`) | Working — `collector/export_static_site.py` exports the DB + analytics into per-company JSON (264 files) for GitHub Pages hosting. Automated commits ("Update site data") keep it current. |
| Analytics (`analytics/thesis_engine.py`) | Working — generates written thesis/summary entries per company (6 so far). |
| Historical backfill (past 5 years) | Ongoing, one company at a time via manual_backfill.py / financials_entry.py — not automatable, see below. |

## What's confirmed true about the data source (don't re-derive this, it cost real effort)

- CSE exposes an **unofficial, undocumented REST API** at `https://www.cse.lk/api/`,
  POST requests, form-encoded, no auth. Community-documented, actively used by others
  (there's a public GitHub doc and even a third-party MCP server wrapping it).
- Key endpoints tested live and working:
  - `getFinancialAnnouncement` → annual/interim report listings
  - `circularAnnouncement` → circulars/other disclosures
  - `companyInfoSummery` (symbol param genuinely filters — this one works per-company)
- **Critical limitation, confirmed by direct testing (not assumed):** `getFinancialAnnouncement`
  and `circularAnnouncement` IGNORE the `symbol` parameter. They always return the
  latest ~8 items **market-wide**, regardless of what you ask for. This was proven by
  requesting `JKH.N0000` and `COMB.N0000` back to back and getting byte-identical
  responses. Do not waste time trying other symbol values to "fix" this — it's a
  structural fact about the endpoint, not a parameter bug.
- PDFs are hosted on a plain static CDN: `cdn.cse.lk/cmt/upload_report_file/{id}_{ts}.pdf`.
  Direct download, no auth, no rendering needed.
- Comparable product `csepal.lk` was inspected live (network tab): it runs its OWN
  backend (`csepal.lk/api/...`, Node/Express behind Nginx) with genuine multi-year
  per-company history (verified back to 2016/2017 for one test company). This
  **confirms there is no API shortcut for historical depth** — they built it by
  collecting consistently over years, the same plan this project follows.

## What's NOT solved, on purpose

**5+ years of historical annual/interim reports per company.** The live CSE feed
structurally cannot provide this (see above). The only real path:
1. Company investor-relations pages (most hold their own multi-year archives)
2. Web search per company/year for older filings, many still resolve on `cdn.cse.lk`
   even though the live feed no longer lists them
3. This is bounded, one-time work per company — not a recurring engineering problem.
   Do this for the real ~60-company coverage universe once it's finalized, and insert
   results into the same `documents` table with `source` = `'manual'`.

## Immediate next steps, roughly in order

The original bootstrapping steps (finalize coverage universe, get the collector on a
schedule, wire the UI to the real DB) are all done — see status table above. Current
active work:

1. **Historical backfill and interim-report entry, per company, as new filings land.**
   The recurring workflow: when a company releases a new interim/annual report, use
   `collector/financials_entry.py` to hand-transcribe the figures (with page
   citations) into `financial_statements`, and `collector/manual_backfill.py` for the
   underlying document if the live feed didn't catch it. CCS and KZOO are worked
   examples.
2. **Expand thesis/summary coverage** beyond the current 6 companies via
   `analytics/thesis_engine.py`.
3. **Re-read `docs/Data_Collector_Design.md` section 0`** before adding new
   infrastructure — it explicitly recommends not over-building resilience (Postgres,
   alerting, backups) ahead of need.

## Folder structure

```
cse-research-platform/
├── README.md              (this file)
├── docs/
│   ├── PRD.md                       — product requirements, V1/V2 scope, user journeys
│   ├── Research_Framework.md        — the analytical methodology every AI output should follow
│   ├── Data_Collector_Design.md     — full collector architecture, schema, and design decisions
│   ├── index.html                   — static frontend (GitHub Pages), reads docs/site_data/
│   └── site_data/                   — per-company JSON export (264 companies) + coverage_universe.json
├── collector/
│   ├── cse_documents_collector.py   — daily poller, writes documents to SQLite + local PDFs
│   ├── financials_entry.py          — manual financial-statement entry with citation validation
│   ├── manual_backfill.py           — manual document backfill (IR pages, older cdn.cse.lk links)
│   ├── export_static_site.py        — exports DB + analytics into docs/site_data/
│   ├── publish_static_site.py       — commits/pushes the static export
│   ├── sync_to_pythonanywhere.py    — syncs the live Flask deployment
│   └── run_daily_collector.ps1      — Windows Task Scheduler entry point
├── analytics/
│   ├── metrics.py                   — fundamental ratios, valuation multiples
│   ├── report_diff.py               — period-over-period diffs (YoY/QoQ)
│   └── thesis_engine.py             — per-company written thesis/summary generation
├── web/
│   ├── app.py                       — live Flask API (Basic Auth, GitHub deploy webhook)
│   └── documents_module.html        — UI served by app.py
└── data/                            — cse_documents.db (SQLite) and downloaded PDFs
```

## A note on how this project has been worked so far

This was built through a long back-and-forth: PRD → research methodology → collector
design → live API testing (including inspecting a real competitor, csepal.lk, via
browser network tab) → the working V0.1 script above. The style has been: challenge
assumptions before building, test claims against real data rather than trust
documentation, and be explicit about what's confirmed vs. what's still a guess. Worth
continuing that habit rather than treating anything above as gospel — re-verify
against the live API if behavior seems to have changed.
