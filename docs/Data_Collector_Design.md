# Service Design Document — Service 1: CSE Data Collector
## An unattended, AI-free data collection engine for the Colombo Stock Exchange

| | |
|---|---|
| **Document version** | 1.0 (Draft for engineering review) |
| **Date** | 7 July 2026 |
| **Companion documents** | PRD v1.0 · Research Framework Specification v1.0 |
| **Scope** | Service 1 only. No AI, no analysis, no UI, no extraction. |
| **Design goal** | Runs unattended for years; never loses a document; never lies about what it has. |

---

## 0. Assessment of the Redesign (candid, before the design)

Two opinions you should hear before committing:

**The Collector-first decision is correct — the best decision in the project so far.** It isolates the only component with an external dependency (cse.lk), it produces the durable asset (PRD §O3) independently of everything else, and it can start accumulating history *today* while the rest of the platform is still being designed. Every week the Collector isn't running is a week of history you may later have to backfill under worse conditions. It also enforces the right dependency direction: everything downstream reads from the Collector's store; nothing ever writes back into it.

**Four independent services is one correct boundary and two premature ones.** The Collector genuinely deserves process/service independence: different availability profile (must run at 16:30 every trading day regardless of what else is broken), different failure domain (a source-site change must not take down your reading UI), zero shared code with AI layers. But splitting the *remaining* platform into three more "independent services" now — before any of them exist — is speculative microservice architecture for a single-user system. The pragmatic posture: **treat "four services" as four modules with hard interface contracts, deploy the Collector as a genuinely separate process, and let the other three live in one deployable until pain proves otherwise.** Nothing in this document constrains that choice; the Collector's contract (its database and file store, read-only to consumers) is identical either way.

One boundary clarification adopted throughout: **the Collector's "no AI" rule is kept absolute, including no ML-based document classification.** This is workable because the CSE's own feed carries category labels; classification here is rule-based mapping of source categories, and anything unmappable is stored under `UNCLASSIFIED` rather than guessed. Reclassification is a downstream concern.

### 0.1 Data Acquisition Reality Check (read before building anything)

Section 1.3's "internal JSON endpoints" strategy is an **assumption, not a confirmed fact.** It has not been validated against the live site. Everything from §3 onward is sequenced as if that validation already happened. It hasn't. Before writing a single adapter:

1. **Open cse.lk in a browser, open the Network tab, load the announcements/disclosures page and a price page.** Confirm whether internal JSON/XHR endpoints exist, what they return, and whether they're stable across a few reloads.
2. **Check for an official bulk-data or historical-data download** on cse.lk — many exchanges quietly publish daily files (CSV/TXT) for exactly this purpose, which is a far more stable source than a reverse-engineered internal API and worth ruling in or out first.
3. **Read cse.lk's robots.txt and terms of use.** This determines whether automated collection is even a path worth pursuing at personal-use scale, or whether the manual/semi-manual path (below) should be the primary strategy rather than a bridge.

This is a day of investigation, not a sprint, and it should happen before Phase 1 of §0.2.

### 0.2 Manual capture is not a stopgap — it's a permanent, parallel input

The honest answer to "how does data get in" has two channels, and they solve different problems:

- **Automated collection** (this document) is the only way to build the historical depth the PRD needs — 5–10 years of statements across ~60 companies, continuous EOD prices, a live disclosure feed. Manual entry cannot do this at that volume; the hours saved is the entire point of the platform.
- **Manual/semi-manual capture** — a human reading cse.lk (or a terminal) and entering what they see — is *faster and more accurate* than any scraper for today's index level, the day's top turnover names, and a handful of crossings. Low volume, high stakes-per-item, and the human is often looking at the page anyway.

These aren't in competition. The design treats manual capture as a **first-class ingestion path from day one**, not a fallback: a `manual_import` job accepts structured input (typed, pasted, or read off a screenshot) and writes into the *same* tables as the automated adapters, tagged with provenance (§3.1, `source_type`). This means the collector is useful immediately — via manual entry — while the automated adapters for a given category are still being built or are down, and it means every downstream consumer can tell, for any figure, whether it came from an automated fetch or a human transcription.

### 0.3 Recommended build sequence (supersedes attempting the full document at once)

| Phase | Goal | Notes |
|---|---|---|
| **Phase 0** | Source investigation (§0.1) — confirm what's actually scrapable, check for an official bulk download, check ToS | Do this before writing code |
| **Phase 1** | Minimal collector: one script, SQLite is fine, a plain folder of PDFs, just EOD prices + one disclosure category, manual_import working from day one | No circuit breakers, no Playwright yet — prove the concept |
| **Phase 2** | Harden: dedup, retry queue, the full schema (§3), more categories | Iterative, driven by what Phase 1 actually breaks on |
| **Phase 3** | Full resilience: Postgres, backups, alerting, restore drills — everything below this point in the document | Only once Phase 1–2 prove the automated source is viable |

**Playwright/headless-browser fallback (§1.3 Strategy B) is deliberately cut from V1 regardless of Phase 0's findings.** Headless browsers are often *more* likely to trigger anti-bot defenses than a plain HTTP client, and maintaining browser automation against a site that can change its bot-detection at any time is significant ongoing toil for a solo operator. If Strategy A (direct endpoint calls) doesn't work, the fallback is manual capture (§0.2), not a heavier scraper.

---

## 1. Overall Architecture

### 1.1 Principles

1. **Store first, interpret never.** The Collector's output is (a) immutable original files and (b) faithful metadata. It performs zero content interpretation beyond checksums, page counts, and MIME sniffing.
2. **Append-only truth.** Nothing is ever updated destructively. New observations create new rows; supersession is recorded, not overwritten.
3. **Idempotent everything.** Any job can be re-run at any time for any date range without creating duplicates or corrupting state. This single property is what makes "unattended for years" achievable — recovery from any failure is "run it again".
4. **The source is hostile-adjacent.** cse.lk is a JavaScript-rendered SPA with no contractual API, which changes without notice and may throttle. All source knowledge is quarantined inside *adapters*; the rest of the service knows nothing about cse.lk.
5. **Polite by construction.** Global rate limiting, identifying User-Agent, off-peak heavy work, unconditional backoff on any 4xx/5xx pressure. A collector that gets blocked collects nothing.
6. **Observable silence.** The default state is silent success; anything abnormal must reach the operator without being asked (heartbeat + alerts), because "unattended" fails in the mode where the collector died in March and you notice in June.

### 1.2 Component diagram (logical)

```
┌────────────────────────── Scheduler (cron/APScheduler) ─────────────────────────┐
│  triggers named jobs with (job_type, params); one process, job-level locking    │
└───────┬───────────────┬─────────────────┬───────────────────┬──────────────────┘
        │               │                 │                   │
   DisclosureSync   PriceSync        DocumentFetch        Housekeeping
   (discover new    (EOD prices,     (download queued     (backups, retention
   filings, enqueue  indices,         files, verify,       of logs, integrity
   downloads)        turnover)        store, register)     re-verification)
        │               │                 │
        └───────────────┴────────┬────────┘
                                 │  all source I/O through ↓
                     ┌───────────▼────────────┐
                     │   Source Adapter Layer │   cse_disclosures_adapter
                     │  (rate limiter, retry, │   cse_prices_adapter
                     │   circuit breaker,     │   cse_company_adapter
                     │   raw-response capture)│   (each independently versioned)
                     └───────────┬────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 │                               │
        ┌────────▼────────┐            ┌─────────▼─────────┐
        │  PostgreSQL     │            │  Object store      │
        │  (metadata,     │            │  (filesystem dir,  │
        │  registry, logs)│            │  content-addressed │
        │                 │            │  immutable blobs)  │
        └─────────────────┘            └───────────────────┘
                 ▲
        read-only│ views/role
                 │
         Downstream services (extraction, AI, UI) — NEVER write here
```

### 1.3 Source strategy (the part most likely to be wrong in a naive design)

cse.lk renders via client-side JavaScript; plain HTML fetches return an empty shell. Two collection strategies, in order of preference:

- **Strategy A — internal JSON endpoints (primary).** The SPA populates itself from internal HTTP endpoints (observable in the browser's network tab: company profiles, disclosure listings, daily price files, announcement feeds return JSON/files). The adapter layer calls these directly: faster, lighter, more stable in structure than rendered HTML, and no browser needed. These endpoints are undocumented and must be treated as discovered, not contracted: each adapter pins the endpoint, request shape, and a **response schema check** — if the response shape drifts, the adapter fails loudly rather than mis-parsing quietly.
- **Strategy B — headless browser (fallback).** A Playwright-based fallback path per adapter, used only when Strategy A fails schema checks, and flagged in logs as degraded mode. Heavier but survives endpoint changes that keep the UI functional.

Every adapter call stores the **raw response** (JSON/HTML/file bytes) before any parsing, so any parsing bug can be corrected retroactively by replaying stored raw responses without re-hitting the source. This is the collector's equivalent of a flight recorder and is non-negotiable.

### 1.4 Technology selection (with reasoning)

- **Language: Python 3.12+.** Ecosystem fit (httpx, Playwright, APScheduler, psycopg), and matches the skills profile of the wider project.
- **Database: PostgreSQL 16.** SQLite would honestly suffice for a single writer, but Postgres is chosen for: concurrent read access by future services without locking games, native `JSONB` for raw metadata, row-level constraints, and a mature backup story. Single instance, local or same-VM.
- **File store: local filesystem in a content-addressed layout** (§7), on a volume included in backups. No S3 dependency in V1; the layout is deliberately compatible with later sync to object storage.
- **Process model: one long-running daemon** hosting the scheduler and workers (systemd unit), not per-job cron processes — enables in-process locking, shared rate limiter, and a live heartbeat.

---

## 2. Folder Structure

```
cse-collector/
├── pyproject.toml
├── README.md
├── config/
│   ├── settings.yaml            # non-secret config (schedules, limits, paths)
│   ├── settings.local.yaml      # machine-specific overrides (gitignored)
│   └── document_types.yaml      # source-category → canonical doc-type mapping rules
├── src/collector/
│   ├── __main__.py              # entrypoint: `python -m collector [run|job|status|backfill]`
│   ├── scheduler.py             # job registry, locks, calendar awareness
│   ├── jobs/
│   │   ├── disclosure_sync.py   # discover new filings → enqueue fetches
│   │   ├── price_sync.py        # EOD prices, indices, market stats
│   │   ├── document_fetch.py    # drain fetch queue → store → register
│   │   ├── company_sync.py      # listed-entity master refresh (weekly)
│   │   ├── backfill.py          # historical range ingestion (manual trigger)
│   │   ├── manual_import.py     # human-entered data → same schema, source_type='manual' (§0.2)
│   │   └── housekeeping.py      # backup, integrity audit, log retention
│   ├── adapters/
│   │   ├── base.py              # HTTP client, rate limiter, retry, circuit breaker,
│   │   │                        #   raw-response capture, schema-check harness
│   │   ├── cse_disclosures.py
│   │   ├── cse_prices.py
│   │   ├── cse_company.py
│   │   └── browser_fallback.py  # Playwright degraded-mode implementations
│   ├── store/
│   │   ├── db.py                # connection, migrations runner
│   │   ├── registry.py          # document/price registration (idempotent upserts)
│   │   └── blobs.py             # content-addressed file store operations
│   ├── ops/
│   │   ├── logging.py           # structured JSON logging setup
│   │   ├── alerts.py            # operator notification (email/Telegram webhook)
│   │   └── health.py            # heartbeat file + status summary
│   └── util/                    # trading calendar, checksum, pdf sniffing
├── migrations/                  # numbered SQL migrations (raw SQL, no ORM magic)
├── tests/
│   ├── unit/
│   ├── fixtures/                # recorded raw responses for adapter tests
│   └── integration/
└── data/                        # runtime (configurable root, on backed-up volume)
    ├── blobs/                   # §7 content-addressed store
    ├── raw/                     # captured raw adapter responses (dated)
    ├── logs/
    └── backups/
```

---

## 3. Database Structure

Raw SQL schema (abridged to essentials; all tables carry `created_at timestamptz default now()`):

```sql
-- Listed-entity master (slowly changing, versioned by valid ranges)
CREATE TABLE company (
    company_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol          text NOT NULL,            -- e.g. 'JKH.N0000' (per share class)
    base_symbol     text NOT NULL,            -- 'JKH'
    share_class     text NOT NULL,            -- 'N' voting / 'X' non-voting
    name            text NOT NULL,
    gics_sector     text,
    status          text NOT NULL DEFAULT 'listed',  -- listed|suspended|delisted|renamed|merged
    superseded_by_company_id bigint REFERENCES company,  -- set on rename/ticker-change/merger; old row is never deleted
    first_seen_at   timestamptz NOT NULL,
    last_seen_at    timestamptz NOT NULL,
    UNIQUE (symbol)
);

-- One row per *published artefact* discovered at the source
CREATE TABLE document (
    document_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id      bigint REFERENCES company,        -- nullable: market-wide notices
    doc_type        text NOT NULL,        -- canonical: ANNUAL_REPORT|INTERIM_REPORT|
                                          -- ANNOUNCEMENT|DIVIDEND|CORPORATE_ACTION|
                                          -- DIRECTOR_DEALING|SHAREHOLDER_NOTICE|UNCLASSIFIED
    source_category text,                 -- verbatim label from cse.lk (never trusted, always kept)
    doc_type_rule_version text,           -- version tag of document_types.yaml used to classify this row
    title           text NOT NULL,
    published_at    timestamptz NOT NULL, -- source-stated publication time
    source_url      text,                 -- nullable: manual-capture rows may have no URL
    source_uid      text,                 -- source's own id for the disclosure, if exposed
    source_type     text NOT NULL DEFAULT 'automated',  -- automated|manual — provenance, always shown downstream
    entered_by      text,                  -- operator identifier, when source_type='manual'
    discovered_at   timestamptz NOT NULL,
    UNIQUE (source_url),                          -- primary dedup key for automated rows;
                                                   -- see §6.5 for the reuse-risk this assumes away
    UNIQUE NULLS NOT DISTINCT (source_uid)        -- secondary, when the source provides one
);

-- Source-native structured fields (e.g. XD date, DPS, ratio) that require zero interpretation —
-- the source gave you discrete fields, not prose; kept distinct from PDF metadata below.
CREATE TABLE document_attribute (
    document_id     bigint NOT NULL REFERENCES document,
    attr_name       text NOT NULL,         -- e.g. 'xd_date', 'dps_amount', 'rights_ratio'
    attr_value      text NOT NULL,         -- stored as verbatim text; typing is a downstream concern
    PRIMARY KEY (document_id, attr_name)
);

-- The actual bytes. A document may have several attachments (annexures) AND each
-- attachment may itself be superseded over time — these are two different axes,
-- not one, and are kept separate to avoid the versioning bug in the original schema.
CREATE TABLE document_file (
    file_id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id     bigint NOT NULL REFERENCES document,
    attachment_no   int  NOT NULL DEFAULT 1,   -- which attachment (1=primary, 2=annex A, ...)
    version_no      int  NOT NULL DEFAULT 1,   -- which version of that specific attachment
    sha256          char(64) NOT NULL,    -- content address; join key into blob store
    byte_size       bigint NOT NULL,
    mime_type       text NOT NULL,
    page_count      int,                  -- PDFs only; mechanical, not interpretive
    has_text_layer  boolean,              -- mechanical check only (PDF text extraction non-empty);
                                          -- flags likely-scanned docs for downstream OCR, no content read
    fetched_at      timestamptz NOT NULL,
    http_etag       text,
    http_last_modified text,
    supersedes_file_id bigint REFERENCES document_file,   -- set when source replaced this attachment
    status          text NOT NULL DEFAULT 'stored',       -- stored|quarantined|missing_at_source
    UNIQUE (document_id, attachment_no, version_no)
);
CREATE INDEX ON document_file (sha256);

-- EOD market data (append-only; one row per symbol per trading day)
CREATE TABLE price_bar (
    symbol          text NOT NULL,
    trade_date      date NOT NULL,
    open numeric, high numeric, low numeric, close numeric NOT NULL,
    prev_close      numeric,
    volume          bigint,
    turnover        numeric,
    trade_count     int,
    source_captured_at timestamptz NOT NULL,
    PRIMARY KEY (symbol, trade_date)
);

CREATE TABLE index_bar (
    index_code      text NOT NULL,        -- ASPI | SPSL20
    trade_date      date NOT NULL,
    close numeric NOT NULL, change_pct numeric,
    market_turnover numeric, market_volume bigint,
    PRIMARY KEY (index_code, trade_date)
);

-- Operational tables
CREATE TABLE crawl_run (
    run_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_name        text NOT NULL,
    started_at      timestamptz NOT NULL,
    finished_at     timestamptz,
    status          text NOT NULL DEFAULT 'running',  -- running|success|partial|failed
    items_discovered int DEFAULT 0,
    items_fetched    int DEFAULT 0,
    items_failed     int DEFAULT 0,
    detail          jsonb                              -- per-run summary, degraded-mode flags
);

CREATE TABLE fetch_queue (
    queue_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id     bigint NOT NULL REFERENCES document,
    url             text NOT NULL,
    state           text NOT NULL DEFAULT 'pending',   -- pending|in_flight|done|dead
    attempts        int NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_error      text,
    UNIQUE (document_id, url)
);

CREATE TABLE event_log (                               -- structured operational events
    event_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          bigint REFERENCES crawl_run,
    at              timestamptz NOT NULL DEFAULT now(),
    level           text NOT NULL,                     -- info|warn|error
    event           text NOT NULL,                     -- machine-readable code
    payload         jsonb
);
```

Downstream access is granted via a dedicated **read-only role**; the collector's writer role is the only writer. This is the four-service contract enforced at the database, not by convention.

---

## 4. New-Document Detection

1. **Polling, not scraping-the-world.** The disclosure feed is queried as a **listing sync**: fetch the most recent N pages of the announcements/disclosures listing (per category), newest first, several times per business day.
2. **High-water mark + overlap window.** Each listing sync records the newest `published_at`/`source_uid` seen. The next sync walks the listing until it passes the previous high-water mark **minus a 7-day overlap window** — the overlap exists because sources backfill items late, re-date items, and occasionally publish out of order. Idempotent registration (§5) makes the overlap free.
3. **Registration before download.** Discovery creates the `document` row and a `fetch_queue` entry; download is a separate concern (§6 pipeline). This means the catalogue of *what exists* is never blocked by download failures — the collector can know a filing exists even while the PDF link is broken, and `missing_at_source` becomes a trackable state rather than silent absence.
4. **Weekly full-reconciliation sweep.** Once a week, per covered category, walk the listing back 90 days regardless of watermarks and reconcile against the registry — the safety net against watermark logic bugs and source re-ordering.
5. **Company-master sync (weekly).** The listed-entity universe itself changes (new listings, suspensions, delistings, name changes). `company_sync` refreshes the master and marks disappeared symbols `last_seen_at` stale rather than deleting them.
6. **Prices are date-driven, not event-driven.** `price_sync` runs on the trading calendar (§12): on every expected trading day, EOD data for all symbols plus indices must exist by end of evening; a missing trading day is an *alertable absence*, not a silent gap. Non-trading days (weekends, Poya days, bank holidays — maintained in a calendar table with manual override) are expected-empty.

## 5. Duplicate Avoidance

Three independent layers, so no single bug produces duplicates:

1. **Identity dedup (registry):** `UNIQUE(source_url)` and `UNIQUE(source_uid)` on `document` — re-discovery of a known item is a no-op upsert that only refreshes `last_seen` metadata.
2. **Content dedup (blob store):** files are stored by `sha256` (§7). The same bytes arriving under two URLs (common: the same PDF linked from both a company page and the announcements feed) produce **one blob** and two registry references. Storage can never hold the same content twice.
3. **Queue dedup:** `UNIQUE(document_id, url)` on `fetch_queue`; enqueueing is `ON CONFLICT DO NOTHING`.

Duplicate *detection* is also reported: a daily housekeeping metric counts registry rows per blob; an unusual spike in many-URLs-one-blob is a signal the source restructured its links (adapter review trigger).

**§6.5 Open risk — URL reuse.** `UNIQUE(source_url)` on `document` assumes each URL identifies one disclosure forever. If cse.lk ever serves a stable URL (e.g. "latest annual report") that gets overwritten with different content each period, this design would misregister a genuinely new document as a new *version* of an old one — silently wrong, not loudly wrong. This must be checked empirically against real cse.lk behavior during Phase 0 (§0.1) before relying on it.

## 6. Changed-Document Handling (download only what changed)

1. **Conditional requests first.** Every stored file records `ETag`/`Last-Modified` when the source provides them; re-checks use `If-None-Match`/`If-Modified-Since` and a `304` costs almost nothing.
2. **Checksum verification second.** Where conditional headers are absent/untrustworthy (common), the file is re-fetched on its re-check schedule and hashed; identical sha256 → discard, touch `last verified` timestamp only.
3. **Versioning on real change.** A different sha256 for the same `document` creates `document_file version_no+1` with `supersedes_file_id` set. **The old version is never deleted** — a company silently replacing an interim PDF is precisely the event a research platform must preserve evidence of, and it is surfaced as a WARN event + operator alert, because replaced filings are analytically interesting.
4. **Re-check policy (bounded, cheap):** filings are effectively immutable at the source, so re-checks are: 48h after first fetch (catches quick corrections), 30 days after, then never — unless the weekly reconciliation sweep observes changed listing metadata for the item. Prices are never re-checked after T+3 except by explicit backfill command.

## 7. PDF / File Storage

**Content-addressed, immutable blob store on the filesystem:**

```
data/blobs/sha256/ab/cd/abcd…64hex          # the bytes, chmod 0444 after write
```

- Write path: download to `tmp/` → hash while streaming → verify size & non-truncation (PDF: `%PDF` magic + EOF marker present; else quarantine) → atomic `rename()` into place → register in DB. Atomic rename guarantees the store never contains partial files.
- Immutability: files are made read-only; the collector has no code path that modifies or deletes a blob (housekeeping can only *add* to a quarantine list).
- Human-friendly access is a **view, not the storage**: a maintained symlink tree `data/by-company/JKH/2026/INTERIM_REPORT/2026-05-15_Q4-FY26_<docid>.pdf` regenerated from the registry, so a human can browse without ever touching the canonical store.
- Integrity audit: housekeeping re-hashes a rolling sample (full store over ~90 days) and alerts on any mismatch (bit-rot/disk fault detection).

## 8. Metadata Storage

All metadata lives in PostgreSQL (§3), with these rules:

- **Verbatim + canonical, always both.** Source-provided fields (`source_category`, source dates, titles) are stored verbatim; canonical fields (`doc_type`, normalised timestamps) are derived by rule (`config/document_types.yaml`) and both are kept. When mapping rules improve, canonical fields can be recomputed from verbatim ones without touching the source.
- **UNCLASSIFIED is honest.** Anything not confidently mapped by rules lands as `UNCLASSIFIED` with its verbatim label — never guessed into a category. A count of UNCLASSIFIED items appears in the daily digest so mapping rules keep pace with source vocabulary.
- **Raw response capture** (§1.3) is metadata's backstop: `data/raw/YYYY-MM-DD/<adapter>/<hash>.json` retained ≥ 13 months, enabling retroactive re-parsing after any adapter bug.
- **Period tagging is deliberately out of scope.** Assigning "Q4 FY26" to an interim requires reading the document — interpretation, which belongs to the extraction service. The collector stores what the *listing* said, nothing more. (This is the discipline that keeps "no AI, no analysis" true.)

## 9. Activity Logging

- **Structured JSON logs** (one event per line: timestamp, level, job, run_id, event code, payload) to `data/logs/`, rotated daily, retained 400 days. Human-readable mirror at INFO+ for casual tailing.
- **Database event log** (`event_log`) for anything with operational meaning (run summaries, degraded-mode entries, version supersessions, quarantines) — queryable history that survives log rotation.
- **Run ledger** (`crawl_run`): every job invocation opens a run row and closes it with counts; a `running` row older than its job timeout is itself an alert condition (crashed-job detection).
- **Daily digest** (one message, evening): trading day? prices captured for N symbols; M new documents by type; queue depth; failures; UNCLASSIFIED count; degraded-mode flags. The digest doubles as the **positive heartbeat**: its absence is the alarm, which protects against the failure mode where the whole machine is off.

## 10. Error Handling

Errors are classified at the adapter boundary and handled by class, never generically:

| Class | Examples | Handling |
|---|---|---|
| **Transient network** | timeouts, connection resets, 502/503/504 | retry with backoff (§11); no alert unless persistent |
| **Throttling** | 429, sudden latency spikes | immediate long backoff, global rate halved for 6h, WARN |
| **Client error** | 404 on a listed document | mark `missing_at_source`, re-probe on schedule, WARN after 3 days missing |
| **Schema drift** | JSON shape fails adapter schema check, HTML parse empty | **fail loudly**: job aborts that category, degraded-mode flag, operator alert; optional automatic fallback to browser strategy where implemented |
| **Content invalid** | truncated PDF, HTML error page saved as .pdf, zero bytes | quarantine (stored but flagged, never registered as good), retry as transient |
| **Storage/DB** | disk full, DB down | job aborts, alert CRITICAL; scheduler pauses all jobs until health check passes (never crawl when you can't store) |
| **Logic** | unexpected exception | run marked failed, full traceback to event_log, alert |
| **Bot-challenge** | HTTP 200 but body matches a challenge-page fingerprint (Cloudflare/CAPTCHA interstitial), not real content | **not a retry candidate on normal cadence** — treated as a standing block: alert CRITICAL immediately, pause the affected adapter, fall back to manual capture (§0.2) until resolved |

Cardinal rule: **no silent partial success.** A run that fetched 180 of 200 items closes as `partial` with the 20 enumerated, and partials alert after 24h unresolved.

## 11. Retry Strategy

- **Per-request:** up to 4 attempts, exponential backoff with full jitter (2s → 8s → 30s → 120s), only for transient classes.
- **Per-queue-item:** failed fetches return to `fetch_queue` with `next_attempt_at` on a slower curve (15m, 2h, 12h, 24h×7), `attempts` capped at 12 → state `dead` + alert. Dead items are revivable manually (`collector job retry --dead`).
- **Circuit breaker per adapter:** ≥5 consecutive failures or ≥50% failure rate over 10 minutes opens the circuit for 30 minutes (all requests short-circuit), half-open probe afterwards. Prevents hammering a struggling source and turns an outage into one alert instead of a thousand log lines.
- **Never retry non-idempotent work:** all collector work is GET-idempotent by design, so retries are always safe — this is why §1.1(3) is a principle and not an aspiration.

## 12. Scheduling

Colombo time (Asia/Colombo), trading-calendar aware (weekends + Sri Lankan holidays incl. Poya, table-driven with manual override):

| Job | Schedule | Notes |
|---|---|---|
| disclosure_sync | 08:30, 11:00, 14:30, 17:30, 21:00 business days; 10:00 otherwise | catches pre-open, intraday, post-close filing waves |
| price_sync | 16:15 trading days, verify-retry 18:00 and 21:00 | market closes 14:30; EOD data settles by early evening; three shots then alert |
| document_fetch | continuous drain, max concurrency 2, paced by global rate limiter | heavier annual-report downloads deferred to 22:00–06:00 window |
| company_sync | Sun 09:00 weekly | |
| reconciliation sweep | Sat 22:00 weekly | 90-day lookback per §4.4 |
| housekeeping | 02:30 daily | backup, integrity sample, log rotation, digest prep |
| backfill | manual only | rate-capped harder than daily jobs |

Job locking: one instance per job via DB advisory locks (safe even if a second daemon is accidentally started). Missed schedules (machine asleep/off) run on next daemon start via catch-up logic keyed on the run ledger — a laptop-friendly property that matters for a personal deployment.

## 13. Scalability

Honest sizing first: ~300 core filings/year for the coverage universe, a few thousand disclosures/year market-wide, ~290 symbols × ~240 trading days ≈ 70k price rows/year, and perhaps 3–6 GB of PDFs/year. **This is a small-data system and must not be engineered as if it weren't.** Scalability concerns that do matter:

- **Backfill bursts:** ingesting 10 years of history is the only genuinely heavy workload; the queue + rate limiter + off-peak windows handle it over days, and idempotency means it can be interrupted freely.
- **Universe growth:** adding categories or future sources (CBSL series, a second exchange) = new adapters + config; no schema change.
- **Consumer growth:** downstream load is read-only on Postgres and the blob store; if the AI service later hammers reads, add replicas/caching downstream — the collector never changes.
- **Deliberate non-goals:** no horizontal scaling, no message brokers, no Kubernetes. The upgrade path if ever needed (blob store → S3-compatible, queue table → real queue) is preserved by the interfaces, not pre-built.

## 14. Performance

Targets (generous, because politeness > speed): complete daily disclosure sync < 5 min; EOD price capture for full market < 10 min; new filing discovered→stored median < 30 min during business hours; global source request rate ≤ 1 req/2s sustained, burst ≤ 3. Streaming downloads with 60s inactivity timeouts; hash-while-streaming so large annual reports (≤ ~100 MB) never buffer in memory. Postgres tuning is default-plus-nothing at this scale; the only indexes that matter are the ones in §3.

## 15. Security

- **Attack surface ≈ zero by design:** no inbound network service at all — the collector exposes no ports; status is read via CLI/digest. Runs as a dedicated non-privileged user; blob and raw directories writable only by it.
- **Egress discipline:** outbound allow-list (cse.lk + alert channel); TLS verification always on; identifying User-Agent with contact info (politeness and traceability).
- **Secrets:** only alert-channel credentials exist; environment/`.env` outside VCS, never in settings.yaml, never logged.
- **Supply chain:** pinned dependencies with hashes, monthly review; no auto-update of the runtime.
- **Data integrity as security:** immutability (0444 blobs), append-only tables, and the audit trail double as tamper-evidence.
- **Backups (availability security):** nightly `pg_dump` + blob rsync to a second disk, weekly to off-site/cloud, **quarterly restore drill** logged in housekeeping — an untested backup is a hope, not a backup. Restore procedure documented in README.

## 16. Configuration

`config/settings.yaml` (env-var overridable, validated at startup — the daemon refuses to start on invalid config):

```yaml
storage:
  data_root: /srv/cse-collector/data
  db_dsn: env:COLLECTOR_DB_DSN
source:
  base_delay_seconds: 2.0
  max_concurrency: 2
  user_agent: "cse-collector/1.0 (personal research; contact: <email>)"
  night_window: ["22:00", "06:00"]
schedules:            # cron-style, per job (see §12 defaults)
retry:
  request_attempts: 4
  queue_attempts_max: 12
  circuit_open_minutes: 30
alerts:
  channel: telegram          # or smtp
  credentials: env:COLLECTOR_ALERT_TOKEN
  quiet_hours: ["23:30", "07:30"]   # CRITICAL bypasses quiet hours
retention:
  raw_responses_days: 400
  logs_days: 400
  blobs: forever             # not configurable downward by design
calendar:
  timezone: Asia/Colombo
  holidays_file: config/holidays_lk.yaml
document_types: config/document_types.yaml
```

Change management: config is in VCS (minus secrets/local overrides); every daemon start logs the effective config hash into `event_log`, so behaviour changes are always attributable.

---

## 17. Definition of Done (acceptance criteria)

1. Runs 30 consecutive days unattended with zero manual interventions and a daily digest every day.
2. Kill-test: process killed mid-download and mid-transaction → restart resumes with no duplicates, no partial blobs, no lost queue items.
3. Drift-test: adapter fed a mutated fixture response → loud failure + alert, zero mis-parsed rows.
4. Backfill-test: 24 months of one company's filings ingested twice → identical registry state (idempotency proof).
5. Restore drill: fresh machine + backups → fully functional collector with intact store, documented time-to-restore.
6. A downstream reader, using only the read-only role and the blob store, can enumerate every filing for a company with correct metadata — without asking the collector anything.

*End of document.*
