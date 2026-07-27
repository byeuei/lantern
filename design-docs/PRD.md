# Product Requirements Document
## AI-Powered Sri Lankan Equity Research Platform ("Lantern" — working name)

| | |
|---|---|
| **Document version** | 1.0 (Draft for engineering review) |
| **Date** | 6 July 2026 |
| **Author** | Product Owner (Principal User) with AI PM/Analyst support |
| **Status** | For review |
| **Audience** | Software engineering team, future contributors |

---

## 1. Executive Summary

Lantern is a single-user (initially) equity research platform for the Colombo Stock Exchange (CSE). Its core promise: **compress the time to reach an informed, evidence-backed view on any listed CSE company from several hours to under five minutes**, without sacrificing the accuracy standards of institutional research.

The product is deliberately **not** a trading terminal, a charting package, or a portfolio manager in Version 1. It is a **research data engine plus an AI analyst layer**: it continuously ingests everything the CSE publishes (interim financials, annual reports, corporate disclosures, prices), converts unstructured PDFs into a clean, structured, point-in-time financial database, and lets the user interrogate that database in natural language — with every number traceable to its source page.

The single most important strategic insight in this document: **the AI is not the hard part; the data layer is.** Sri Lanka has no Compustat, no consolidated fundamentals feed, and Bloomberg/Refinitiv coverage of CSE counters is shallow and expensive. The durable asset Lantern builds is a verified, structured, historical fundamentals database for CSE-listed companies. The AI layer is a fast-moving commodity that sits on top of it. Engineering effort should be allocated accordingly (roughly 70% data pipeline, 30% AI/UX in V1).

---

## 2. Problem Statement

### 2.1 The problem

Researching a CSE-listed company today is a slow, manual, error-prone assembly job:

1. Prices and market data live on cse.lk, a JavaScript-rendered site with no usable public API and no export.
2. Financial statements are published as **unstructured PDFs** (quarterly interims and annual reports), each with company-specific layouts. Banks, insurers, and non-financial corporates use fundamentally different statement formats.
3. Corporate actions, dividends, rights issues, related-party transactions, and director dealings arrive as free-text PDF disclosures scattered across a chronological feed.
4. There is no consolidated historical fundamentals database. Building a 5-year trend for a single company means opening ~20 PDFs and re-keying figures by hand.
5. Shareholder movement analysis (top-20 lists) requires manual comparison of tables across two annual reports or interim filings.
6. Institutional-quality tools (Bloomberg, AlphaSense, Capital IQ) either do not cover the CSE meaningfully or cost more than the entire research budget of a frontier-market desk.

The result: an experienced analyst spends **2–6 hours** producing a basic company review, most of it on data collection and re-keying rather than analysis and judgement.

### 2.2 What "solved" looks like

The user types a company name and, within five minutes, has:

- A current snapshot (price, valuation multiples, liquidity, shareholding structure).
- A multi-year and multi-quarter financial history in structured, comparable form.
- The latest results analysed against the prior comparable period, with margins and drivers.
- All material recent disclosures, summarised.
- The ability to ask arbitrary follow-up questions ("what did management say about the hotel segment?", "how has the NIM trended since 2022?") and get answers **with page-level citations**.

Time is then spent on judgement, not assembly.

### 2.3 What this product is explicitly NOT (V1)

- Not a trading or order-management system.
- Not a real-time market data terminal (see §6.2 — this assumption is challenged).
- Not a portfolio accounting system.
- Not a distribution platform for third parties (regulatory implications; see §13).

---

## 3. Target Users

### 3.1 Primary user (V1)

**The Owner-Analyst.** A single professional working in or around Sri Lankan capital markets (brokerage/research context), who:

- Reviews CSE companies regularly for internal analysis and client communication.
- Already produces daily/weekly market wraps and shareholder movement analyses.
- Is fluent in financial statements and does not need concepts explained — needs **assembly automated**.
- Is technically capable of running/administering a small self-hosted or cloud-hosted system.
- Has a low tolerance for wrong numbers. A tool that silently mis-extracts one figure is worse than no tool.

### 3.2 Future users (V2+)

- **Sell-side analysts** at Colombo brokerages: need coverage-universe monitoring, comparable tables, note drafting.
- **Buy-side analysts / fund managers** (local unit trusts, EPF-adjacent funds, frontier-market foreign funds): need screening, watchlist alerts, and audit trails for investment committee memos.
- **High-net-worth self-directed investors**: simplified views, possibly a paid tier.

Expansion to these users introduces multi-tenancy, permissions, data-redistribution licensing, and reliability obligations that are **explicitly out of scope for V1** and materially shape the V2 architecture conversation.

---

## 4. User Pain Points (Ranked)

| # | Pain point | Frequency | Severity | V1 addresses? |
|---|---|---|---|---|
| P1 | Financial data trapped in PDFs; re-keying required for any trend analysis | Every task | Critical | Yes — core |
| P2 | No historical structured fundamentals database for CSE | Every task | Critical | Yes — core |
| P3 | Quarterly results comparison (QoQ, YoY) is fully manual | Weekly+ | High | Yes |
| P4 | Disclosure feed is noisy, unsummarised, and easy to miss items in | Daily | High | Yes |
| P5 | Shareholder list movement analysis is manual spreadsheet work | Quarterly per company | High | Yes (import existing workflow) |
| P6 | Peer/sector comparison requires assembling data for 5–10 companies | Weekly | High | Yes |
| P7 | Sector-specific metrics (bank NIMs, insurer combined ratios, plantation NSAs) never pre-computed | Weekly | Medium | Partially (bank pack first) |
| P8 | No alerting on new filings for followed companies | Daily | Medium | Minimal (feed, not push alerts) |
| P9 | Charting / technical analysis is scattered | Occasional | Low | No — deferred (V2) |
| P10 | Broker research from other houses is scattered across email/PDF | Occasional | Low | No — deferred (V2, licensing issues) |

---

## 5. Core Objectives

1. **O1 — Time compression:** Reduce time-to-first-informed-view on any covered company to ≤5 minutes, and time-to-full-quarterly-review to ≤20 minutes.
2. **O2 — Trustworthy data:** Every structured figure is traceable to a source document and page; extraction accuracy is measured, not assumed.
3. **O3 — Durable data asset:** Build a growing, versioned, point-in-time historical fundamentals database for the CSE that appreciates in value every quarter.
4. **O4 — Coverage completeness within scope:** For the defined coverage universe, nothing material published by the CSE is missed for more than one business day.
5. **O5 — Foundation for expansion:** Architecture decisions in V1 must not preclude multi-user V2, but must not pay for it prematurely.

---

## 6. Assumptions — Stated and Challenged

The brief contains several implicit assumptions. Some are wrong or need reframing. Per your instruction, they are challenged here explicitly, because they change the build.

### 6.1 CHALLENGED: "Research any listed company in under five minutes"

There are ~285 listed entities on the CSE, but the tail is illiquid, rarely traded, and reports in inconsistent, sometimes scanned-image PDFs. Building and QA-ing extraction templates for all 285 in V1 would consume the entire budget for marginal value — the bottom 150 counters are researched perhaps once a year.

**Reframed requirement:** V1 defines a **coverage universe of ~60 companies** (S&P SL20 + the most liquid/most-researched names across banks, diversified holdings, consumer, telco, insurance, healthcare, manufacturing, hotels, plantations). These get full structured extraction and QA. Every other company gets **degraded-but-useful coverage**: document ingestion + RAG Q&A with citations + EOD prices, without guaranteed structured fundamentals. The five-minute promise applies to the coverage universe; "ten minutes, with the AI reading the raw PDFs live" applies to the tail. Universe expands over time as templates harden.

### 6.2 CHALLENGED: "My personal Bloomberg Terminal" (real-time data)

Bloomberg's identity is real-time everything. For **research**, real-time ticks add almost nothing: valuation work is done on closing prices, and intraday moves matter for trading, not for forming views. Meanwhile, real-time CSE data is a licensed product; scraping it continuously invites both technical fragility and licensing exposure.

**Reframed requirement:** V1 uses **end-of-day prices** (plus an on-demand "refresh this company's current quote" action when the user is actively looking at a name). Real-time streaming is deferred indefinitely, and possibly forever — it is a different product. This single decision removes an enormous amount of infrastructure.

### 6.3 CHALLENGED: "AI-powered" as the centre of the product

LLMs are unreliable at reading numbers out of complex financial tables at the accuracy level this user requires (O2). An LLM that is 97% accurate per figure will corrupt essentially every multi-line statement it extracts.

**Reframed requirement:** Extraction is a **deterministic-first pipeline** (PDF table parsing, layout templates per company/statement type) with the LLM used for (a) classification and mapping of line items to a canonical chart of accounts, (b) handling layout drift, and (c) narrative sections. Every extracted statement passes **arithmetic validation** (totals foot, balance sheets balance, EPS recomputes from NPAT/share count within tolerance) before entering the database; failures are queued for human review. The AI's user-facing role is retrieval, synthesis, and Q&A over verified data — it must **never invent or "recall" a figure**: answers must quote the database or the document, with citations.

### 6.4 CHALLENGED: One extraction pipeline covers all companies

Bank financial statements (interest income, NIM, impairment stages, CASA) share almost nothing with a plantation company's statements (NSA per kilo, crop volumes) or an insurer's (GWP, combined ratio). A generic P&L schema will produce mush.

**Reframed requirement:** A **canonical core schema** (revenue → gross profit → operating profit → NPAT, balance sheet, cash flow, per-share data) applies to all, plus **sector extension packs**. V1 ships the core schema for the full coverage universe and **one sector pack: banks/NBFIs** (the most-researched sector on the CSE). Insurance, plantations, and telco packs follow in V1.x/V2.

### 6.5 Assumptions accepted (and recorded)

- **A1:** cse.lk remains the authoritative, free, public source for filings and EOD data; personal-use automated retrieval at respectful rates is acceptable risk for a single-user tool (revisit before any multi-user distribution — see Risks).
- **A2:** Filings are predominantly English-language PDFs. (True for the coverage universe.)
- **A3:** The user can perform occasional human-in-the-loop review of flagged extractions (~15–30 min/week). This is a feature, not a failure: it is how the database earns trust.
- **A4:** Single user, single tenant, modest hardware/cloud budget in V1.
- **A5:** LLM API access (e.g., Anthropic API) is available and its per-document cost is acceptable given filing volumes (~60 companies × 4 interims + 1 annual report/year ≈ 300 core documents/year, plus disclosures).
- **A6:** No redistribution of data to third parties in V1, which keeps the tool inside personal/internal-use territory.

---

## 7. Success Metrics

| Metric | Target (V1, by end of first full quarter of operation) |
|---|---|
| **M1. Time-to-brief:** company search → complete snapshot read | ≤ 5 min for coverage universe (measured via session timestamps) |
| **M2. Extraction accuracy:** sampled audit of structured figures vs source PDFs (min. 20 statements/quarter sampled) | ≥ 99.5% per line item; 100% on headline items (revenue, NPAT, EPS, NAV) |
| **M3. Validation pass rate:** statements passing arithmetic checks without human touch | ≥ 85% (rising over time as templates harden) |
| **M4. Ingestion latency:** new filing on cse.lk → available in platform | ≤ 24 hours (same evening for coverage universe) |
| **M5. Citation integrity:** AI answers containing figures that carry a resolvable source citation | 100% (hard requirement — uncited figures are a bug) |
| **M6. Coverage:** companies with full structured history (≥ 12 quarters + 5 annual reports) | ≥ 60 by end of V1 backfill |
| **M7. Usage displacement:** % of the user's real research tasks completed inside the platform without falling back to manual cse.lk workflow | ≥ 80% self-reported |
| **M8. Trust incidents:** materially wrong figures surfaced to the user without a validation flag | 0 tolerated; each one triggers a pipeline post-mortem |

---

## 8. Functional Requirements (V1)

Requirements are numbered FR-x and tagged **[MUST]** / **[SHOULD]** / **[COULD]** (MoSCoW).

### 8.1 Data Ingestion & Pipeline

- **FR-1 [MUST]** Automated daily retrieval of the CSE corporate disclosure feed; classification of each disclosure by type (interim financials, annual report, dividend, rights/capital action, AGM/EGM, director dealing, related-party, other) and by company.
- **FR-2 [MUST]** Automated retrieval of EOD market data for all listed equities: close, change, volume, turnover, VWAP where available, plus ASPI and S&P SL20 index levels.
- **FR-3 [MUST]** Document store: every retrieved PDF archived immutably with metadata (company, type, period, filing date, source URL, checksum). Originals are never modified; the platform must be able to re-run extraction against stored originals.
- **FR-4 [MUST]** Structured extraction pipeline for interim financial statements and annual report financials of coverage-universe companies into the canonical schema: income statement, statement of financial position, cash flow statement, per-share data (EPS, NAV/share, DPS), share count. Both **company** and **group/consolidated** columns captured; group is the default for analytics.
- **FR-5 [MUST]** Arithmetic and consistency validation on every extracted statement (footing, balancing, EPS recomputation, period-over-period sanity bands). Failures enter a **review queue** with a side-by-side PDF/extracted-values UI for one-click human correction; corrections feed back into template improvement.
- **FR-6 [MUST]** Point-in-time integrity: restatements and corrections are versioned, never overwritten; each figure records "as reported on date X in document Y, page Z".
- **FR-7 [MUST]** Historical backfill tooling: batch-ingest past interims (target: 12+ quarters) and annual reports (target: 5 years) for the coverage universe.
- **FR-8 [SHOULD]** Bank/NBFI sector extension pack: net interest income, NIM, fee income, impairment charge and stage coverage, gross/net NPL (Stage 3) ratio, CASA, loan book, deposits, CAR/Tier 1.
- **FR-9 [SHOULD]** Shareholder register extraction: top-20 shareholder tables from filings, with the existing shareholder-movement comparison workflow (new entrants, exits, buyers, sellers) automated between any two periods.
- **FR-10 [COULD]** Dividend history table per company assembled from disclosures (announcement, XD, payment dates, amount).

### 8.2 Company Research Surface

- **FR-11 [MUST]** Global search by company name or ticker (e.g., JKH, COMB.N0000) with instant navigation.
- **FR-12 [MUST]** **Company Snapshot ("5-Minute Brief")** — the flagship screen, auto-assembled, containing: header (price, day/period change, market cap, free float if known, 12-month range, liquidity stats); valuation strip (trailing PER, PBV, dividend yield, and EV/EBITDA for non-financials); latest-quarter results vs comparable period with margin bridge; 5-year / 12-quarter mini financial trends; recent disclosures summarised; AI-generated narrative summary (≤300 words) of "what's happened here lately", fully cited.
- **FR-13 [MUST]** Financials explorer: full statement views by period, quarterly and annual toggles, YoY/QoQ deltas, TTM computation, CSV/XLSX export of any table.
- **FR-14 [MUST]** Document library per company: chronological filings list, in-app PDF viewer with search.
- **FR-15 [MUST]** Peer comparison table: user selects 2–10 companies (or a predefined sector set) → side-by-side valuation and fundamentals table, exportable.
- **FR-16 [SHOULD]** Watchlists: user-defined lists with a consolidated view (prices, upcoming/recent filings, latest results status).
- **FR-17 [SHOULD]** Simple price chart per company (EOD line/candles, 1M–5Y, index overlay). *Deliberately basic; charting depth is V2.*

### 8.3 AI Analyst Layer

- **FR-18 [MUST]** Conversational Q&A scoped to a company or the whole platform, answering from (a) the structured database and (b) RAG over the document store. **Every quantitative claim carries a citation** resolving to a database record or a document page; the UI renders citations as clickable links opening the source at the cited location.
- **FR-19 [MUST]** Refusal behaviour: when the answer is not in the data, the AI says so and offers the nearest available document — it never estimates or recalls figures from model memory.
- **FR-20 [MUST]** One-click **quarterly results review**: on ingestion of a new interim, generate a structured review note (revenue/profit vs YoY and QoQ, margins, segment commentary if disclosed, balance-sheet flags, one-paragraph takeaway) in the user's established wrap/note style; editable and exportable.
- **FR-21 [SHOULD]** Disclosure summarisation: each non-financial disclosure gets a 1–3 sentence machine summary in the feed, with materiality tagging (dividend, capital action, RPT, board change, other).
- **FR-22 [COULD]** Cross-company questions over the structured DB ("which coverage banks grew NII fastest YoY?") answered via safe, read-only structured queries generated by the AI, with the query shown for auditability.

### 8.4 Feeds & Monitoring

- **FR-23 [MUST]** Unified "Today" feed: new filings (all companies, coverage universe pinned/highlighted), market summary (indices, turnover, top movers by turnover), and items awaiting human review.
- **FR-24 [SHOULD]** Daily digest generation compatible with the user's existing market-wrap formats (header stats + top turnover counters), assembled from ingested EOD data for editing and sending. *(Sending itself remains manual — the platform drafts, the user distributes.)*

---

## 9. Non-Functional Requirements

| ID | Requirement |
|---|---|
| **NFR-1 Accuracy** | Zero uncited figures in AI output; extraction accuracy per §7 M2. Accuracy beats availability everywhere in this product: a stale correct number outranks a fresh wrong one. |
| **NFR-2 Auditability** | Every figure, summary, and AI answer must be reconstructible: which document, which page, which extraction/model version, when. Retain full lineage indefinitely. |
| **NFR-3 Availability** | Single-user tool: 99% availability during Colombo business hours (Mon–Fri, 08:00–18:00 IST+0:30) is sufficient. No pager, no HA cluster. |
| **NFR-4 Performance** | Company snapshot renders ≤ 3s (pre-computed, not assembled on request). Search results ≤ 500ms. AI answers may stream; first token ≤ 5s. |
| **NFR-5 Freshness** | EOD data and new filings same evening; disclosure feed refresh at least 3×/business day. |
| **NFR-6 Politeness/robustness of retrieval** | Source retrieval must be rate-limited, cached, resumable, and identifiable; a source-site outage or layout change must degrade gracefully (queue and retry) and alert the user, never silently drop filings. |
| **NFR-7 Cost ceiling** | Total run cost (hosting + LLM API) targeted ≤ USD 150/month in V1. Extraction design must batch and cache accordingly. |
| **NFR-8 Data durability** | Nightly automated backups of database and document store; documented restore procedure; the fundamentals DB is the crown jewel — losing it means losing months of accumulated QA. |
| **NFR-9 Security** | Single-user authentication still required (the notes and watchlists reveal professional positioning); secrets managed properly; no third-party access. |
| **NFR-10 Extensibility** | Adding a company to the coverage universe, or a new line item to a sector pack, must be configuration + template work, not a code change. |
| **NFR-11 Portability** | No hard dependency on one LLM vendor for extraction/Q&A; model calls behind an internal interface with evaluation harness to compare/upgrade models. |

---

## 10. Version 1 vs Version 2 — Scope Decisions and Rationale

### 10.1 In V1 (essential)

1. Ingestion + document archive (FR-1..3) — everything depends on it.
2. Structured extraction, validation, review queue, point-in-time DB (FR-4..7) — the durable asset.
3. Company snapshot, financials explorer, peers, documents, search (FR-11..15).
4. AI Q&A with hard citation guarantee (FR-18..19) and quarterly review generator (FR-20).
5. Today feed + EOD market data (FR-2, FR-23).
6. Bank sector pack (FR-8) and shareholder movement automation (FR-9) — highest-frequency real workflows of the primary user.

### 10.2 Deferred to V2 (with reasons — per your instruction, each deferral is justified)

| Feature | Why not V1 |
|---|---|
| **Real-time / intraday prices, streaming watchlist** | Research runs on EOD data. Real-time adds licensing exposure, infra complexity, and near-zero research value (§6.2). |
| **Push alerts (email/WhatsApp/Telegram) on filings & price moves** | Valuable, but the Today feed covers a single daily-routine user. Alerting done properly needs dedup, quiet hours, and delivery infrastructure — cheap to add once ingestion is trustworthy, wasteful before. |
| **Automated valuation models (DCF, dividend discount, residual income)** | Dangerous automation: garbage-in DCFs create false confidence. Requires forecast inputs the platform doesn't yet have. V2 candidate as *user-driven templates pre-populated with verified historicals* — never auto-generated "target prices". |
| **Insurance / plantation / telco / hotel sector packs** | Each pack is real template + QA work. Banks first (most researched); others sequenced by actual usage data from V1. |
| **Full 285-company structured coverage** | §6.1. Tail counters get documents + RAG, not guaranteed structured data. Expansion is a rolling operational task, not a feature gate. |
| **Multi-user, roles, sharing, client portal** | Changes everything: auth, tenancy, licensing/redistribution of exchange data (legal), uptime obligations. Premature before the single-user product proves value. |
| **Broker research aggregation (other houses' notes)** | Copyright/licensing minefield; content arrives via private email channels; summarising third-party paywalled research for redistribution is a legal risk. Personal notes attachment (upload your own PDFs to a company) is a small V1.x compromise. |
| **Advanced charting / technical analysis** | Commodity capability available elsewhere; low pain-point ranking (P9). Basic EOD chart suffices. |
| **Portfolio tracking & P&L** | Different product with different accuracy/tax semantics. Watchlists cover the research need. |
| **Macro dashboard (CBSL rates, CCPI inflation, FX, GDP)** | Genuinely useful context, but macro data lives in accessible CBSL publications and changes the ingestion scope. V2: a thin macro strip (policy rates, T-bill yields, USD/LKR, CCPI) on the home screen. |
| **Earnings-call transcripts / audio** | Structured earnings calls are rare on the CSE; annual reports and interim commentary carry the narrative. Revisit only if disclosure culture changes. |
| **Mobile app** | Responsive web is sufficient for one power user at a desk. |
| **Excel add-in / public API** | High leverage for analysts, but only after the DB schema stabilises through a few quarters of real use. CSV/XLSX export (FR-13) bridges the gap. |
| **Screening engine (full-universe filters)** | Screening over 60 names is a sortable peer table (FR-15). A real screener earns its keep only with broader structured coverage. |

---

## 11. User Journeys

### UJ-1 — "What's the story with this company?" (the 5-minute brief)
**Trigger:** A client asks about, or news mentions, a coverage company.
1. User types "Hemas" in global search → snapshot opens (<3s).
2. Reads header + valuation strip (30s), latest-quarter panel with YoY/QoQ deltas (60s), 12-quarter trend sparklines (30s), AI narrative summary with citations (60s), recent disclosures (30s).
3. Asks one follow-up: "what drove the consumer segment margin this quarter?" → cited answer from the interim's segment note (60s).
4. Exports the peer valuation row for the client reply.
**Success:** ≤5 minutes; every number citable; no cse.lk visit needed.

### UJ-2 — Results day
**Trigger:** Coverage company files its interim; it appears in the Today feed same evening.
1. Feed shows "COMB — Interim Q1 FY26 — extracted ✓ validated ✓".
2. User opens the auto-generated quarterly review note (FR-20), checks the highlighted figures against the side-by-side PDF view, edits two sentences of interpretation.
3. Exports/copies the note into the client channel.
**Success:** ≤20 minutes from opening the feed to a client-ready note, vs ~2 hours today.

### UJ-3 — Extraction review (human-in-the-loop)
**Trigger:** A statement fails validation (e.g., balance sheet doesn't balance).
1. Review queue shows the statement with failed checks flagged; side-by-side PDF and extracted values.
2. User corrects the offending line (mis-mapped subtotal), revalidates → passes → commits.
3. Correction is recorded; template updated so next quarter parses cleanly.
**Success:** ≤3 minutes per item; weekly queue ≤10 items after the first two quarters.

### UJ-4 — Peer comparison
**Trigger:** "How does Sampath stack up against the other banks right now?"
1. User opens the "Banks" preset peer set → table with PBV, PER, ROE, NIM, Stage-3 ratio, CAR across ~8 banks, latest verified periods labelled per company (periods may differ — the table must show which quarter each figure is from).
2. Sorts by PBV, exports to XLSX.
**Success:** ≤2 minutes; previously ~1 hour of PDF mining.

### UJ-5 — Shareholder movements
**Trigger:** New interim/annual report with a top-20 shareholder table.
1. User opens Company → Shareholding → "Compare vs previous period".
2. Platform outputs new entrants, exits, buyers, sellers with share deltas, plus the formatted three-tab export matching the user's existing deliverable.
**Success:** ≤2 minutes; fully replaces the current manual spreadsheet workflow.

### UJ-6 — Off-universe company (degraded mode)
**Trigger:** Question about an illiquid, non-covered counter.
1. Snapshot renders with price/market data and document library, plus a clear banner: "Not in structured coverage — answers below are read live from filings."
2. AI answers Q&A directly over the archived PDFs with citations; headline figures shown as document quotes, not database facts.
**Success:** Useful in ≤10 minutes; the user is never misled about data quality tier.

---

## 12. Information Architecture

```
Home (Today)
├── Market summary (ASPI, S&P SL20, turnover, top movers)
├── New filings feed (all; coverage universe highlighted)
├── Review queue status
└── Watchlist strip

Company (hub for each counter)
├── Snapshot (5-minute brief)          ← default landing
├── Financials
│   ├── Income statement | Balance sheet | Cash flow | Per-share
│   ├── Quarterly / Annual / TTM views, YoY/QoQ deltas
│   └── Sector pack tab (e.g., Bank metrics)
├── Shareholding (top-20 history, movement comparison)
├── Disclosures & Documents (viewer, search)
├── Chart (basic EOD)
└── Ask (company-scoped AI chat)

Compare
└── Peer tables (presets by sector + custom sets), export

Watchlists
└── User-defined lists → consolidated monitoring view

Ask (global)
└── Cross-company AI chat over verified data

Admin
├── Coverage universe management
├── Extraction review queue
├── Ingestion health / source status
└── Backfill jobs
```

**Data-model spine (conceptual):** `Company → Filing (immutable document) → ExtractedStatement (versioned, validated) → CanonicalLineItem (point-in-time) → DerivedMetric (ratios, TTM) ` with `PriceBar (EOD)` and `Disclosure` alongside; every AI answer references `CanonicalLineItem` IDs or `Filing` page anchors.

---

## 13. Product Constraints

- **C1 — Source dependency:** cse.lk is effectively the sole primary source for filings and market data. It is JavaScript-rendered, has no public API, and can change layout without notice. The ingestion layer must isolate all source-specific logic behind adapters so a site change is a one-module fix.
- **C2 — Data licensing:** Automated collection and internal single-user use of publicly published filings and EOD figures is a materially different posture from redistributing that data to clients or other users. **Any multi-user or client-facing expansion requires a data-licensing review with the CSE first.** This constraint gates the V2 roadmap, not just informs it.
- **C3 — Document quality:** Some filings (especially older or smaller-cap) are scanned images requiring OCR; extraction accuracy targets apply only to digitally native PDFs, with OCR-sourced figures flagged as such.
- **C4 — Fiscal-year heterogeneity:** CSE companies split mainly between March and December year-ends. All period logic (YoY, TTM, "latest quarter") must be driven by each company's fiscal calendar, never by calendar quarters.
- **C5 — Currency & units:** Figures are reported in LKR '000 or LKR mn inconsistently across companies; unit normalisation is a first-class extraction step with validation.
- **C6 — Budget:** Solo project; NFR-7 cost ceiling and no dedicated ops team. Prefer boring, low-maintenance technology.
- **C7 — LLM non-determinism:** Model outputs vary across versions; all AI behaviour that affects stored data must run behind evaluation tests before model upgrades (NFR-11).

## 14. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Silent extraction error reaches the user and damages trust in the entire platform | Medium | Critical | Validation gates (FR-5), citation-always (M5), quality-tier banners (UJ-6), sampled audits (M2), zero-tolerance post-mortems (M8) |
| R2 | cse.lk layout change breaks ingestion | High | High | Adapter isolation (C1), health monitoring + alerting on ingestion gaps (NFR-6), immutable raw-HTML/PDF capture for replay |
| R3 | Scraping posture challenged / access blocked | Low–Med | High | Respectful rates, personal use only (A1/A6), no redistribution; fallback to manual upload workflow so the platform still functions |
| R4 | Template maintenance burden grows faster than value (each company × each format drift) | Medium | High | Coverage universe discipline (§6.1), LLM-assisted line-item mapping to absorb drift, review-queue metrics to spot decaying templates |
| R5 | LLM cost or quality regression | Medium | Medium | Vendor-abstracted interface + eval harness (NFR-11), caching, batch processing |
| R6 | Scope creep toward trading-terminal features | High | Medium | This PRD; §10.2 deferral table is the contract |
| R7 | Data loss of the accumulated verified DB | Low | Critical | NFR-8 backups + tested restores |
| R8 | Key-person risk (solo builder/operator) | High | Medium (V1) | Documentation, infrastructure-as-config, boring tech (C6); becomes Critical if V2 users onboard — hire/partner before that |
| R9 | Regulatory sensitivity if AI output resembles investment advice when shared onward | Low (V1) | High (V2) | V1 output is internal research tooling; V2 client-facing features require compliance review (SEC of Sri Lanka context) and disclaimers |

## 15. Future Roadmap

**V1.x (fast follows, same quarter):** insurance sector pack; dividend history (FR-10); personal notes/PDF attachments per company; cross-company structured Q&A (FR-22); daily digest polishing (FR-24).

**V2 (multi-quarter horizon):** push alerting; plantation/telco/hotel packs; coverage universe → 120+; macro strip (CBSL policy rates, T-bill yields, USD/LKR, CCPI); valuation model templates pre-filled with verified historicals; screening over expanded coverage; Excel export API for internal use.

**V3 (conditional on C2 licensing + demand):** multi-user tenancy for analyst teams; shared watchlists and note collaboration; client-portal or distribution features; possible commercialisation as a CSE research data product — at which point the accumulated verified point-in-time database (O3) is the moat, exactly as designed.

## 16. Open Questions for the Engineering Kick-off

1. Hosting posture: local machine vs small cloud instance (affects NFR-3/8 design).
2. Backfill depth: is 12 quarters + 5 annual reports sufficient, or is 10-year history wanted for select names (cost/time trade-off)?
3. Initial coverage-universe list: owner to supply the exact ~60 tickers, ranked, so backfill can be sequenced by usage priority.
4. Review-queue SLA: is same-evening human review realistic on results-season peak days (30+ filings/day), or should coverage names be prioritised and the tail batched?
5. Export formats: confirm the exact XLSX layouts expected for shareholder-movement and peer-table exports (existing deliverable formats to be provided as fixtures).

---

*End of document.*
