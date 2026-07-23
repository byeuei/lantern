# Lantern — Sri Lankan Equity Research Platform

Personal research platform for the Colombo Stock Exchange. Goal: cut company research
time from hours to under 5 minutes, backed by a real, verified, growing document and
data archive — not by an AI guessing at numbers.

**Read this whole file before changing anything.** It's the handoff from a long design
conversation, and it explains what's real, what's a prototype, and what's deliberately
not built yet.

## Project status (as of this handoff)

| Piece | Status |
|---|---|
| PRD, research methodology, Collector architecture | Designed, in `docs/` |
| CSE data source | Reverse-engineered, confirmed working, unofficial (see "What's confirmed" below) |
| Documents collector (`collector/cse_documents_collector.py`) | Working V0.1 — polls live, saves to SQLite + local PDFs. Has NOT been run repeatedly over time yet, so its database is likely empty or near-empty at handoff. |
| Web UI (`web/documents_module.html`) | Static prototype with hand-embedded sample data, NOT wired to the real SQLite database yet. Visual direction only. |
| Historical backfill (past 5 years) | Not started. Deliberately out of scope for the collector script — see below. |

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

1. **Finalize the real coverage universe list** (~60 tickers) and put it in
   `collector/cse_documents_collector.py`'s `COVERAGE_UNIVERSE` — it currently has a
   starter guess, not the real list.
2. **Get the collector running on a schedule** (daily is enough) so it starts
   accumulating real history for covered names going forward. On Windows this can be
   Task Scheduler; a cron job if this ends up on a server/Linux box eventually.
3. **Wire `web/documents_module.html` to the real SQLite database** instead of its
   current hand-embedded sample data — this is a mechanical change (read from
   `data/cse_documents.db` instead of the hardcoded `DOCS` array), but needs a small
   local server or a build step since a static HTML file can't read a SQLite file
   directly from the browser.
4. **Do the one-time historical backfill** for the top-priority names in the coverage
   universe (see "What's NOT solved" above).
5. **Re-read `docs/Data_Collector_Design.md` section 0** before doing much more —
   it has the phased build plan (Phase 0 → Phase 3) and explicitly recommends NOT
   over-building resilience infrastructure (Postgres, alerting, backups) before the
   basics above are proven out with real, accumulating data.

## Folder structure

```
cse-research-platform/
├── README.md              (this file)
├── docs/
│   ├── PRD.md                    — product requirements, V1/V2 scope, user journeys
│   ├── Research_Framework.md      — the analytical methodology every AI output should follow
│   └── Data_Collector_Design.md   — full collector architecture, schema, and design decisions
├── collector/
│   └── cse_documents_collector.py — working V0.1 documents collector (see status above)
├── web/
│   └── documents_module.html      — static UI prototype, sample data only
└── data/                          — collector's database and downloaded PDFs land here
                                      (empty at handoff; .gitkeep placeholder)
```

## A note on how this project has been worked so far

This was built through a long back-and-forth: PRD → research methodology → collector
design → live API testing (including inspecting a real competitor, csepal.lk, via
browser network tab) → the working V0.1 script above. The style has been: challenge
assumptions before building, test claims against real data rather than trust
documentation, and be explicit about what's confirmed vs. what's still a guess. Worth
continuing that habit rather than treating anything above as gospel — re-verify
against the live API if behavior seems to have changed.
