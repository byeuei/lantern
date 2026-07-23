# Institutional Research Framework Specification
## The Analytical "Brain" of the CSE Research Platform

| | |
|---|---|
| **Document version** | 1.0 (Draft for review) |
| **Date** | 7 July 2026 |
| **Companion document** | PRD v1.0 (Lantern) |
| **Purpose** | Defines the research methodology every AI-generated output must follow. An AI engineer should be able to build the reasoning engine directly from this specification. |
| **Scope exclusions** | No software architecture, no databases, no implementation detail. |

---

## 0. Governing Principles (read first — these override everything below)

Before the framework itself, seven rules that bind every analytical output the platform produces. These exist because the failure mode of AI research is not ignorance — it is **fluent, confident, generic mush**.

**GP-1. Evidence before inference, inference before opinion.** Every analytical statement must be classifiable as one of: *Fact* (cited to a filing/price record), *Derived* (computed from facts, formula shown), *Inference* (reasoning from facts, premises stated), or *Judgement* (explicitly labelled as such, with confidence). An output that cannot be decomposed this way is rejected.

**GP-2. Frontier-market context is not a footnote.** Sri Lanka is a post-default, IMF-programme frontier market with a managed float currency, episodic capital controls, policy volatility, thin liquidity, and concentrated family/conglomerate ownership. Every module below carries CSE-specific adaptations. Analysis that would be written identically about a NYSE company has failed.

**GP-3. Absence of evidence is a finding.** If segment margins aren't disclosed, if no independent directors chair the audit committee, if management never explains a miss — the platform says so. "Not disclosed" is an analytically meaningful output, never silently skipped.

**GP-4. Asymmetry of error.** A false "high quality / cheap / Buy-tier" conclusion is far more costly than a false negative. Where evidence is thin, the framework defaults to the conservative reading and a lower confidence score, never to optimistic interpolation.

**GP-5. Liquidity gates everything.** A conclusion about a stock that trades LKR 200,000/day is an academic exercise. Liquidity and free float are assessed *before* valuation and recommendation, and can cap the final output regardless of fundamental attractiveness (§8).

**GP-6. Sector lenses are mandatory.** Banks, insurers, plantations, hotels, and trading conglomerates are analysed with different metrics, different "good/bad" thresholds, and different valuation anchors. A single generic template applied to all sectors is a specification violation.

**GP-7. Consistency through time.** The same company analysed twice on the same data must yield the same conclusions. Judgements change only when evidence changes, and every change is logged with its trigger (§10).

---

## 1. Company Understanding

### 1.1 The Company Dossier — what the platform must know

Every covered company maintains a structured dossier with these mandatory sections. Items marked ⚑ are CSE-specific and non-negotiable.

1. **Identity & structure:** legal name, ticker(s) — voting and non-voting classes ⚑ (X shares trade at persistent discounts; both must be tracked), GICS sector, fiscal year-end, listing date, group parentage ⚑ (most CSE value sits inside pyramids — JKH, LOLC, Hayleys, Melstacorp, Vallibel, Browns; the dossier must map the pyramid position: who controls this company, what does this company control).
2. **Business description in plain language** (§1.2).
3. **Segment map:** reported segments, revenue/profit contribution, geographic split, currency of revenue vs currency of costs ⚑ (the single most important classification in a devaluation-prone economy: net USD earner, net USD payer, or LKR-pure).
4. **Revenue driver tree** (§1.3).
5. **Customer & supplier concentration:** where disclosed; where not, flagged per GP-3.
6. **Ownership & float:** top-20 shareholders, controlling bloc %, free float %, EPF/ETF presence ⚑, foreign holding % and trend ⚑, average daily turnover (3M/12M).
7. **Competitive position** (§1.4) and **business quality grade** (§1.5).
8. **Key people:** chairman, MD/CEO, FD, tenure, family relationships to controlling shareholder ⚑.
9. **Regulatory perimeter:** which regulators bind it (CBSL, IRCSL, PUCSL, SEC, TRCSL, tourism/plantation ministries), licence dependencies.
10. **History file:** capital actions, restatements, auditor changes, major acquisitions/disposals, past crises and how management behaved in them ⚑ (2022 default year behaviour is a permanent character reference).

### 1.2 Explaining the business to an unfamiliar reader

The standard is: **a competent generalist investor abroad understands what the company does, how it makes money, and what it depends on, in under 150 words** — before any numbers. Mandatory structure:

1. *What it sells and to whom* — in product/customer language, not GICS language ("collects fixed deposits from savers and lends to SMEs at a spread", not "provides financial services").
2. *How money is made* — the unit economics sentence: price × volume, spread × book, room rate × occupancy, commission × turnover.
3. *Scale anchors* — market position ("Sri Lanka's largest private bank by assets"), size in absolute terms a foreigner can parse (USD equivalents alongside LKR ⚑).
4. *The one dependency* — the single factor the business lives or dies by (tea auction prices, tourist arrivals, policy rates, import licensing).

Prohibited: corporate boilerplate ("leading diversified conglomerate with a rich heritage"), adjective-led descriptions, any sentence that could describe three other companies.

### 1.3 Revenue driver identification

The platform decomposes revenue into a **driver tree**: Revenue = Σ segments; each segment = volume driver × price driver, each classified along four axes:

- **Controllability:** company-set (branded consumer pricing) vs market-set (tea auctions, world rubber, palm oil) vs regulator-set (energy tariffs, plantation wages ⚑, interest rate caps when imposed ⚑).
- **Currency:** USD-linked, LKR, or administered.
- **Cyclicality:** structural growth / GDP-cyclical / rate-cyclical / commodity-cyclical / tourism-cyclical.
- **Data observability:** which external series proxy the driver (CBSL private credit growth for banks, tourist arrivals for hotels, tea auction averages for plantations, CCPI for consumer staples pricing). The news engine (§9) uses this mapping to propagate macro news to company impact.

*Good* looks like: a driver tree where ≥80% of revenue is explained by identified, observable drivers. *Bad*: "other income" or unexplained segments >15% of profit — automatic earnings-quality flag (§3.12).

### 1.4 Competitive advantage identification

Test for moats using evidence, not assertion. Each claimed advantage must cite its **financial fingerprint** — a moat that leaves no trace in the numbers is presumed absent:

| Moat type | CSE examples to test for | Required fingerprint |
|---|---|---|
| Regulatory/licence | Banking licences, telco spectrum, casino licences, power PPAs | Stable ROE above sector despite entry attempts |
| Distribution density | FMCG route-to-market, fuel/retail networks | Gross margin + working-capital advantage vs peers |
| Brand/habit | Consumer staples, alcohol ⚑ (Mendis/DCSL dynamics), dairy | Pricing through inflation without volume loss |
| Cost position | Scale in plantations is *rarely* a moat (regulated wages ⚑); low-cost deposits (CASA) in banks *is* | CASA ratio, cost/income, NIM durability |
| Switching costs | Corporate banking, insurance persistency, software | Retention/persistency ratios |
| Network effects | Rare on CSE; test claims skeptically | Take-rate stability with share gains |

⚑ Frontier caveat the platform must encode: **many CSE "moats" are actually relationships with the state or protection via import tariffs**. These are real but fragile — they must be labelled *policy-contingent advantages*, scored lower for durability, and linked to the political-risk module (§6).

### 1.5 Business quality grade

Composite A–E grade from five equally-weighted tests, each scored on evidence over the trailing 5 years (min. 3 years to grade at all; else "Unrated — insufficient history"):

1. **Returns test:** ROE (financials) / ROIC (non-financials) vs the company's real cost of equity ⚑ (CSE CoE is high: risk-free from 12M T-bill yields + equity premium; a 15% ROE can destroy value in Sri Lanka — the framework must never import developed-market hurdle rates).
2. **Stability test:** margin and return volatility through the cycle, explicitly including 2020 (COVID) and 2022 (default/devaluation) behaviour.
3. **Cash conversion test:** cumulative CFO / cumulative EBITDA (or CFO/NPAT for financials-lite view).
4. **Reinvestment test:** does incremental capital earn ≥ historical returns (incremental ROIC), or is growth dilutive/rights-issue-funded ⚑?
5. **Fragility test:** leverage, refinancing dependence, single-driver dependence, licence dependence.

---

## 2. Industry Analysis

Every company inherits an **Industry File** — maintained once per industry, cited by all member companies, refreshed on trigger events (§9) and at least semi-annually.

### 2.1 Industry structure
Map: number of meaningful players, market-share concentration (HHI where estimable), formal vs informal competition ⚑ (informal sector is a real competitor in food, retail, construction, finance/money-lending), vertical integration norms, import competition and the tariff wall protecting incumbents ⚑, capacity situation. Use Porter's five forces as the checklist but **report only forces that bind** — reciting all five with generic text is prohibited (GP-1).

### 2.2 Industry attractiveness
Judged by the evidence of member economics, not narrative: distribution of member ROEs vs CoE over 5–10 years; who captures the profit pool along the chain (e.g., in tea: grower vs broker vs exporter vs brand); pricing power evidence through the 2021–23 inflation shock — the single best natural experiment the CSE offers ⚑ (who passed through 70% CCPI inflation, who ate it).

### 2.3 Industry cycle position
Classify each industry's cycle type and current position with named indicators: **rate cycle** (banks, NBFIs, leasing: policy rates, AWPLR, private credit growth), **tourism cycle** (arrivals, RevPAR, source-market mix), **construction cycle** (cement volumes, government capex under IMF constraints ⚑), **commodity cycles** (tea auction prices, rubber, palm oil, global freight for logistics), **consumer cycle** (real wages, remittances ⚑ — a major household income source, worker departures). State the position (early/mid/late/trough) as a Judgement with its indicator evidence.

### 2.4 Growth drivers
Separate **structural** (formalisation, penetration gaps — insurance penetration <1.5% of GDP ⚑, credit/GDP, per-capita consumption), **cyclical** (recovery from the 2022–23 contraction), and **policy-manufactured** (tax holidays, tariff protection, mandated purchases) growth. Policy-manufactured growth is scored as lower quality and higher risk.

### 2.5 Industry risks, competition, and disruption
Standing risk register per industry: import liberalisation risk ⚑ (IMF programme pushes tariff rationalisation — protected industries carry this as a live risk), new-entrant licence issuance, technology substitution (digital payments vs branch banking), climate exposure (plantations, hydropower, tourism), demand migration abroad.

### 2.6 Government influence — a first-class module ⚑
Not a sub-bullet in Sri Lanka. Score every industry 1–5 on **state entanglement**: price administration (fuel, energy, pharma price controls history, bread/dhal moments), wage boards (plantations), state-owned competitors (state banks, SriLankan, CPC/CEB), taxation targeting (banks' financial VAT and surcharge taxes ⚑ — the state's history of taxing whoever has profits), licence discretion, procurement dependence. High entanglement caps industry attractiveness regardless of demand outlook.

### 2.7 Commodity exposure
For each industry: input commodities (fuel, palm oil, wheat, milk powder, coal), output commodities (tea, rubber, coconut, garments as quasi-commodity), hedging norms (rare on CSE — most exposure is unhedged ⚑), pass-through lags in days/months, and the observable price series to monitor.

### 2.8 Macroeconomic sensitivity map
Each industry gets a signed sensitivity vector to the seven macro variables that dominate CSE earnings: **policy rates, USD/LKR, CCPI inflation, tourist arrivals, remittances, government fiscal stance (IMF programme milestones ⚑), and global commodity indices**. Direction (+/–/mixed), magnitude (H/M/L), and lag. This vector is the routing table the news engine (§9) uses.


---

## 3. Financial Analysis

The financial framework runs the same 12 modules on every company, but with sector-specific metric sets and thresholds (GP-6). "Good/bad" markers below are for **non-financial corporates**; the bank overlay follows in §3.13. All multi-period analysis uses the company's fiscal calendar, group/consolidated figures, and — where inflation distorts — real (CCPI-deflated) growth alongside nominal ⚑ (nominal revenue "growth" of 40% in FY23 was frequently a real decline; the platform must always show both for 2021–24 periods).

### 3.1 Revenue quality
Assess: recurrence (contracted/repeat vs one-off), diversification (segment, customer, geography), currency composition, organic vs acquired vs price-inflation-driven growth, and channel checks against external drivers (bank loan growth vs system credit; hotel revenue vs arrivals — divergence demands explanation).
**Good:** diversified, recurring, driver-consistent, positive real growth. **Bad:** growth explained only by inflation or one-offs; single-customer dependence; revenue outrunning its external driver with no stated reason (possible channel stuffing or recognition aggression).

### 3.2 Profitability & 3.4 Margins
Full margin ladder (gross → EBITDA → EBIT → pre-tax → net) with 5-year trend, peer percentile, and decomposition of every material margin move into price/volume/mix/input-cost/FX per the driver tree.
**Good:** stable-to-rising margins with identified causes; gross margin held through the 2022 cost shock. **Bad:** margin expansion driven by *other income*, *fair value gains on investment property* ⚑ (a chronic CSE earnings inflater), or one-off disposal gains — these are stripped in the adjusted view (§3.12).

### 3.3 Cash flow
The framework treats the cash flow statement as the lie detector. Compute: CFO/EBITDA (target >70% cumulative over 3y), FCF = CFO – maintenance capex (estimated as min(capex, depreciation) where unspecified), FCF conversion of NPAT, and the **funding identity**: over 5 years, where did cash come from (operations vs debt vs rights issues ⚑) and where did it go (capex, acquisitions, dividends, related parties ⚑).
**Good:** operations fund growth and dividends. **Bad:** dividends funded by borrowings or rights issues; persistent CFO<NPAT; recurring "receivables from related parties" absorbing cash ⚑ (a first-class red flag on the CSE, not a footnote).

### 3.5 Capital allocation (financial evidence; management judgement in §4)
Score the 5-year record: reinvestment returns (incremental ROIC), acquisition record (goodwill vs subsequent impairments), dividend policy consistency (payout ratio band vs erratic), rights-issue frequency ⚑ (serial rights issuers destroy minority returns; count issues per decade), buybacks (rare on CSE — treat announcements as weak signals until executed).

### 3.6 Working capital
Cash conversion cycle (DSO + DIO – DPO) trend and peer comparison; inventory build vs revenue growth (build >1.5× revenue growth = flag); receivables aging where disclosed; import-dependency working-capital shock analysis ⚑ (2022 LC restrictions forced inventory hoarding — distinguish strategic build from demand miss using the timeline).
**Good:** stable CCC, WC growing in line with revenue. **Bad:** structurally lengthening DSO; payables stretch masking cash weakness.

### 3.7 Balance sheet strength & 3.9 Debt
Compute: net debt/EBITDA (<2× comfortable, >3.5× stressed for LKR-cyclical earnings), interest cover (EBIT/interest — CSE stress test: recompute at +500bps refinancing rates ⚑, because AWPLR moved from ~9% to ~28% within 18 months in 2022 and can again), debt currency mix vs earnings currency ⚑ (USD debt against LKR earnings is the classic CSE fatality pattern), maturity wall vs cash+facilities, contingent liabilities and guarantees to related parties ⚑.
**Revaluation caveat ⚑:** CSE balance sheets carry large PPE revaluation reserves. Equity and NAV are stated after revaluations; the framework computes **tangible book excluding revaluation surpluses** as a parallel figure, because reported PBV is systematically flattered otherwise.

### 3.8 Liquidity
Current/quick ratios are secondary; primary is the 12-month cash bridge: opening cash + undrawn committed facilities + expected CFO vs debt maturities + committed capex + declared dividends. **Bad:** dependence on rolling short-term borrowings for structural funding.

### 3.10 Return ratios
ROE with full DuPont decomposition (margin × turnover × leverage — the platform must state *which lever* produces the ROE; leverage-manufactured ROE scores lower), ROIC vs the LKR-appropriate hurdle (§1.5), ROA for asset-heavy names, and returns on tangible equity ex-revaluation ⚑.

### 3.11 Growth
Always three views: nominal, real (CCPI-deflated) ⚑, and USD-terms ⚑ (what a foreign investor experienced). CAGR over 3/5 years plus trajectory. Growth quality hierarchy: volume-led > price-led > acquisition-led > inflation-illusory.

### 3.12 Earnings quality — the adjusted-earnings engine
Every company gets a **Reported → Core earnings bridge**, mechanically applied: strip fair-value gains on investment property and biological assets ⚑, disposal gains, one-off tax reversals, insurance one-off surplus transfers ⚑, exchange gains/losses on translation (shown separately), and — for banks — outsized trading gains on government securities ⚑ (the 2023–24 gilt rally inflated bank earnings; core = NII + fees – opex – normalised impairment). Beneish-style checks (receivables vs revenue divergence, accrual ratios) run as screens, flagged not asserted. **Audit signals:** auditor identity and changes, qualified opinions, emphasis-of-matter paragraphs, late filings ⚑ — each is a standing dossier flag.

### 3.13 Bank/NBFI overlay (mandatory replacement metrics)
For financials, §3.1–3.11 are replaced by: NIM and its decomposition (asset yields vs funding cost, CASA ratio), fee income share, cost/income, credit cost (impairment/average loans), Stage 3 ratio and coverage, restructured book ⚑ (post-2022 moratoria make headline NPLs understate stress — restructured/rescheduled loans are a mandatory line of inquiry), sovereign-securities share of assets ⚑ (banks are the state's largest creditors; sovereign exposure = the dominant balance-sheet risk), CAR/Tier 1 vs minimums, loan/deposit ratio, and ROE on tangible equity. "Good" = NIM stability through the rate cycle, CASA >35%, cost/income <45%, Stage 3 <5% with coverage >50%, CAR buffer >2.5% over minimum.

---

## 4. Management Quality

Management assessment is where AI research degenerates into flattery fastest. The framework therefore permits **only behavioural evidence** — words are scored against subsequent actions, never taken at face value.

1. **Capital allocation record (weight: highest).** The §3.5 financial evidence, attributed to the tenure of the current decision-makers. A CEO inherits or creates the record; the dossier maps which.
2. **Execution: promise-vs-delivery ledger.** Every forward-looking statement in chairman's/MD's reviews (expansion plans, margin targets, completion dates) is logged and scored when the outcome is observable. The ledger *is* the credibility score. ⚑ CSE annual-report rhetoric is florid; the ledger is the antidote.
3. **Governance structure:** board independence (genuine — the platform cross-references "independent" directors against group directorships across the pyramid ⚑), audit committee composition, related-party transaction volume and direction ⚑ (chronic value-leakage channel: intercompany loans, management fees to parent, asset transfers within pyramids — RPT notes are mandatory reading, and net RPT flows are computed annually), dual-class/voting structures, minority-squeeze history.
4. **Communication quality:** does the company explain misses or bury them; segment disclosure richness vs peers; consistency of KPIs reported year to year (silently dropped KPIs = flag); investor-access norms.
5. **Strategy coherence:** stated strategy vs actual capital deployment; diversification discipline ⚑ (conglomerate empire-building into unrelated ventures is the signature CSE value destroyer — new-segment entries are scored against subsequent returns).
6. **Track record through crises ⚑:** behaviour in 2020 and 2022 — who cut dividends to protect the balance sheet vs who borrowed to pay them; who hoarded, who panicked; treatment of employees and creditors. Crisis behaviour is weighted 2× normal-period behaviour.
7. **Insider and controlling-shareholder transactions:** director dealings from disclosures (buys > sells informationally, but ⚑ on the CSE the controlling family's *rights-issue subscription behaviour* and *pledging of shares* — where discoverable — are stronger signals than small director trades). ESOP/private placement pricing vs market.

Output: Management grade A–E with the evidence ledger attached; grade changes require a logged trigger (GP-7).

---

## 5. Valuation

### 5.1 Doctrine
Valuation answers *"what is priced in?"* before *"what is it worth?"*. The framework triangulates — no single method may drive a conclusion — and every multiple is used with its known CSE distortion corrected:

| Tool | Use | Mandatory CSE correction ⚑ |
|---|---|---|
| **PER** | Primary for stable earners | Use **core EPS** (§3.12), never reported; TTM and forward-if-estimable; meaningless for loss-makers and fair-value-gain-driven earners |
| **PBV** | Primary for banks, insurers, asset-heavy | Compute on **tangible book ex-revaluation reserves** alongside stated NAV; pair always with ROE (PBV without ROE is noise — the anchor is the PBV↔ROE regression across the sector) |
| **EV/EBITDA** | Non-financials, capex-heavy, conglomerate SOTP inputs | EV must include *all* debt incl. FX-adjusted USD debt and preference capital; never applied to financials |
| **Dividend yield** | Income lens; strong signal on CSE where payouts are the main minority return ⚑ | Yield quality-adjusted: payout funded by FCF scores; debt-funded yield is flagged as unsustainable, not attractive |
| **EV/sales, per-room, per-hectare, per-subscriber** | Sector anchors (hotels, plantations, telco) | Sector packs define the anchor metric |
| **SOTP** | Mandatory for holding companies/pyramids ⚑ | Listed stakes at market less holding discount (20–40% empirical CSE range, stated as assumption); unlisted at conservative multiples |
| **Intrinsic (DDM/DCF)** | Cross-check only, never headline | Discount rates from current 12M T-bill + 5–7% ERP ⚑ (CoE of 15–22% is normal; imported 8–10% WACCs are a specification violation); explicit currency consistency (LKR flows/LKR rates) |

### 5.2 Historical multiples
Each covered name carries a 5–10 year multiple history (PER, PBV, EV/EBITDA, yield) with percentile placement of the current multiple — **but** with regime awareness ⚑: pre-2022 and post-2022 Sri Lanka are different valuation regimes (different rates, different sovereign risk). Percentiles are shown per-regime and full-history, and the platform must never say "trading below its 10-year average" without noting the regime break.

### 5.3 Relative valuation
Peer tables use verified same-period data (per PRD FR-15), always pairing the multiple with its justifying fundamental (PBV↔ROE, PER↔growth+quality grade, yield↔payout sustainability). Cross-border frontier comparables (Bangladesh, Vietnam, Pakistan, Kenya) may be cited for context but never drive conclusions — different rates, different regimes.

### 5.4 When is a stock "cheap" or "expensive"?
The framework's definition — and this must be encoded verbatim in the reasoning engine:

> A stock is **cheap** when the market price implies expectations *materially below* what the evidence-based view of business quality, earnings power, and risk supports — after correcting earnings and book for §3.12/§3.7 distortions, and after the liquidity/governance discounts of §5.5. A low multiple alone is never "cheap".

**The value-trap protocol ⚑ (mandatory before any "cheap" conclusion):** roughly half the CSE trades at PBV <1 permanently. Before labelling anything cheap, the platform must test and report the four trap explanations: (1) returns below CoE (deservedly cheap), (2) governance/RPT leakage (minorities never see the value), (3) free-float/liquidity discount (value exists but is inaccessible at size), (4) structurally declining industry. Only when the traps are examined and rejected — with evidence — may "undervalued" appear. "Cheap for a reason" is the CSE base case; the platform's default skepticism must reflect that.

**Expensive** is the mirror: price implies expectations above what quality and growth evidence supports, with special attention to CSE retail-momentum episodes in small caps ⚑ (low-float names can multiply on turnover spikes; the framework flags price-vs-fundamentals divergence with the float context).

---

## 6. Risk Analysis

Every company carries a standing **risk register**: each risk scored Likelihood (1–5) × Impact (1–5), with the transmission channel to earnings/balance sheet stated, the monitoring indicator named, and mitigants assessed. Categories (all mandatory, "not material — because X" is an acceptable entry, silence is not):

1. **Operational:** concentration (plant, customer, supplier, key person), supply chain/import dependence ⚑ (LC availability history), energy reliability, labour (unionisation, wage boards ⚑), technology/cyber.
2. **Financial:** leverage, refinancing walls, covenant proximity, FX-mismatched debt ⚑, contingent liabilities, pension deficits.
3. **Regulatory:** licence renewal/discretion, price controls history in the sector ⚑, targeted taxation risk ⚑ (surcharge taxes, financial VAT — the state taxes visible profits; high-margin sectors carry standing risk), import-tariff dependence (protection removal under IMF commitments ⚑).
4. **Currency ⚑ (first-class, never merged into "financial"):** net USD exposure from §1.3 driver tree; devaluation impact on costs, debt, and demand; repatriation/capital-control history for foreign holders.
5. **Commodity:** input/output exposures from §2.7 with hedging status (assume unhedged unless disclosed ⚑).
6. **Interest rate:** for corporates — refinancing cost sensitivity (+500bps stress); for banks — NIM direction, gilt-portfolio mark-to-market, credit-cost lag; for consumers of the company's product — demand sensitivity to rates (vehicles, housing, leasing ⚑).
7. **Political & policy:** election-cycle policy reversal risk, IMF-programme slippage as a systemic scenario ⚑, expropriation/nationalisation history awareness (rare but non-zero), civil-disruption sensitivity (2019, 2022 as reference scenarios).
8. **ESG — materiality-first, not checkbox:** environmental (climate exposure of plantations/hydro/tourism, effluent/regulatory incidents), social (plantation-sector labour conditions as an export-market access risk ⚑, product harm), and governance — which on the CSE is *the* dominant ESG factor and is scored via §4.3, not via disclosure-volume ESG ratings. The framework explicitly rejects ESG scoring based on report thickness.
9. **Sovereign linkage ⚑ (added category — missing from the brief):** direct exposure to government paper (banks, insurers), receivables from state entities (CPC/CEB suppliers, construction), dependence on government spending. Post-default Sri Lanka makes sovereign linkage a distinct, quantified risk line for a large share of the market.
10. **Liquidity/exit risk ⚑ (added):** days-to-exit a reference position (e.g., LKR 50mn) at 20% of ADT — reported on every company, feeding §8's gate.

---

## 7. Investment Thesis Template

Every covered company maintains a living thesis document in this exact structure. Length discipline: the whole thesis ≤ 900 words; every quantitative claim cited (GP-1).

1. **The one-paragraph view (≤80 words):** what kind of business, what quality grade, what the market is pricing, where the framework's view differs — and *why the difference exists* (the mispricing hypothesis: neglect, forced selling, misunderstood accounting, over-extrapolated crisis, float constraints). ⚑ A thesis with no stated reason for the mispricing is incomplete — on a thin market, "nobody has looked" is a legitimate and common answer, but it must be said.
2. **Competitive position (≤100 words):** moat claims with fingerprints (§1.4), share trajectory, policy-contingency flags.
3. **Bull case:** the 3–5 things that must go right, each with (a) the driver it maps to, (b) the observable indicator that would confirm it, (c) rough earnings sensitivity. No bull case may rest on multiple re-rating alone.
4. **Bear case:** written to the same evidentiary standard as the bull case — the framework enforces symmetry (equal word count ±20%) to prevent the AI's optimism bias. Must include the value-trap tests (§5.4) outcome.
5. **Catalysts:** dated/datable events only (results, tariff decisions, IMF reviews, licence renewals, capital actions, index reviews ⚑ — S&P SL20 inclusion/exclusion moves flows on the CSE). "Continued execution" is not a catalyst.
6. **Key risks:** top 3–5 from the §6 register with monitoring indicators.
7. **Long-term outlook (3–5 years):** structural position of the industry (§2.4), reinvestment runway, terminal ownership question ⚑ (in pyramids: does the controller have incentive to ever surface this value for minorities? Delisting/squeeze-out and buy-out scenarios are legitimate thesis endpoints on the CSE).
8. **What would change our mind:** explicit falsification triggers, both directions. Mandatory — this section is what makes the thesis maintainable by the knowledge engine (§10) instead of regenerated.

---

## 8. Recommendation Framework

### 8.1 CHALLENGED: the premise itself
Two pushbacks before the design, per your instruction:

**(a) Point recommendations without price targets and horizons are astrology.** "Buy" is meaningless without "relative to what, over what horizon, at what size". The framework therefore outputs a **composite score + conviction tier + the price context**, and the label vocabulary is *evidence tiers*, not broker ratings. If broker-style labels are ever needed for external use, that is a compliance decision (SEC of Sri Lanka research-report regulations apply to distributed recommendations), not a methodology one.

**(b) Fixed universal weightings are analytically wrong.** Quality should weigh more for compounders, valuation more for asset plays, balance sheet more in tightening cycles. A single static weight vector is a false precision. Resolution: **one default vector, two published variants** (bank overlay; deep-value/asset-play overlay), selected by rule, all disclosed in the output. Never a hidden model soup.

### 8.2 Factor structure and default weights

| Pillar | Weight (default) | Inputs (each subscored 1–10 per rubric) |
|---|---|---|
| **Business quality** | 25% | §1.5 grade: returns vs CoE, stability, cash conversion, reinvestment, fragility |
| **Financial strength** | 15% | §3.7–3.9: leverage, coverage stressed +500bps, FX mismatch, liquidity bridge |
| **Earnings trajectory & quality** | 15% | §3.11–3.12: real growth, driver momentum, core-vs-reported gap (a large gap *subtracts*) |
| **Management & governance** | 15% | §4 grade; RPT leakage and rights-issue history are direct deductions |
| **Valuation** | 20% | §5: multiple vs justified level (PBV↔ROE regression residual, PER vs quality/growth), historical percentile (regime-aware), value-trap protocol passed |
| **Industry & macro position** | 10% | §2: attractiveness, cycle position, state entanglement (high entanglement deducts) |

**Bank overlay:** Quality 20 / Financial strength (capital & asset quality) 25 / Earnings 15 / Management 15 / Valuation 20 / Industry-macro 5.
**Deep-value overlay** (triggered when PBV<0.6× and quality ≥C): Valuation 30 / Governance 25 (because governance is what decides whether the value reaches minorities ⚑) / Quality 15 / Financial strength 15 / Earnings 5 / Industry 10.

### 8.3 Scoring logic
Each subscore comes from a **written rubric with numeric anchors** (e.g., Financial strength: net debt/EBITDA <0.5× and no FX mismatch = 9–10; >3.5× or unhedged USD debt >30% of debt = 1–3) so that scores are reproducible (GP-7) and auditable — the output must show every subscore, its anchor evidence, and the arithmetic. **No black boxes and no vibes:** if the engine cannot cite the anchor, the subscore defaults to the conservative bound (GP-4).

### 8.4 Gates (applied before any tier is assigned) ⚑
Hard gates that cap or suspend the output regardless of score:
- **Liquidity gate:** ADT below user-set floor → tier capped at "Monitor — illiquid" with the days-to-exit figure shown.
- **Data gate:** <8 quarters verified data or unresolved extraction flags on latest results → "Unrated — insufficient verified data".
- **Governance gate:** active qualified audit opinion, unexplained auditor resignation, or net RPT outflow >15% of equity over 3y → capped at "Avoid — governance" whatever the valuation.
- **Solvency gate:** liquidity bridge (§3.8) negative without identified funding → capped at "Speculative".

### 8.5 Tiers, thresholds, confidence
Composite 0–100 → tiers: **≥75 Strong evidence of undervaluation & quality** · **60–74 Attractive, on watch** · **45–59 Fairly assessed / Hold-equivalent** · **30–44 Unattractive** · **<30 Avoid**. 
**Confidence score (0–100%, reported alongside, never merged into the tier):** function of data completeness (verified quarters, disclosure richness), earnings-quality gap size, driver observability, and dispersion between the pillar scores (a company scoring 8 on quality and 2 on governance is *contested*, not average — high dispersion lowers confidence and forces the disagreement to be narrated). Low confidence (<50%) auto-appends "the correct next step is specific human diligence on X", listing the gaps.
**Presentation rule:** the tier is always shown as *"what the evidence supports"*, with the score table, gates, and confidence — never as a bare imperative verb. The platform is an analyst, not an order-giver.

---

## 9. News & Disclosure Analysis

Every incoming item (corporate disclosure, macro release, sector news) runs a fixed pipeline:

1. **Classify & verify:** type (results, dividend, capital action, RPT, board change, contract, macro print, policy decision), source tier (CSE filing = primary; ministry/CBSL = primary; press = secondary, corroboration required before high-materiality claims).
2. **What happened:** factual summary ≤3 sentences, numbers quoted with citation, no adjectives.
3. **Why it matters / materiality triage:** score 1–5 against the company's driver tree (§1.3) and risk register (§6). A disclosure that touches no driver and no risk is filed silently (⚑ the CSE feed is full of procedural noise — AGM notices, circular resolutions; triage is what makes the feed usable).
4. **Who is affected — propagation:** direct company; then **read-across** via the industry file (§2) and macro sensitivity vectors (§2.8): a policy-rate cut propagates to banks (NIM–), leasing (volume+), construction (demand+), high-debt corporates (interest–). Second-order mapping is mandatory for macro items ⚑ — this is where the platform out-researches a human on speed.
5. **Earnings impact:** order-of-magnitude estimate through the stated channel ("+100bps on gross margin ≈ LKR Xmn on TTM revenue"), labelled *Derived/Inference* per GP-1, with the sensitivity assumption shown. Where the channel is unquantifiable, say so — no fabricated precision.
6. **Valuation impact:** does it change earnings power, risk, or only timing? Multiple-relevant (changes the justified multiple) vs estimate-relevant (changes the E in PER) vs noise.
7. **Horizon split:** short-term (flow/sentiment/one-quarter optics — including index-flow mechanics ⚑) vs long-term (thesis-relevant). The output must say explicitly whether the item **changes the thesis (§7) or not**, and if yes, trigger a thesis update with the change logged (§10).
8. **Watch items:** what to monitor next (the confirming indicator, the follow-up filing).

---

## 10. Knowledge Base — the permanent company model

### 10.1 CHALLENGED: "knowledge that improves over time"
Correct instinct, but the naïve implementation — accumulating AI-written prose about each company — degrades into a self-referential sludge where old inferences masquerade as facts. The design principle is therefore: **facts accumulate; judgements are versioned; narrative is always regenerated from the current fact base.** The knowledge base stores *claims*, never essays.

### 10.2 Claim architecture
Every unit of knowledge is a claim with: statement · type (Fact / Derived / Inference / Judgement per GP-1) · source citation(s) · as-of date · status (active / superseded / falsified) · confidence · review trigger. Examples: *Fact:* "FY25 group revenue LKR 288bn [AR p.142]". *Judgement:* "Management grade B — promise-ledger 7/9 delivered [ledger v3], crisis behaviour positive [2022 file]".

### 10.3 What accumulates permanently
- The **promise-vs-delivery ledger** (§4.2) — only valuable *because* it spans years.
- The **crisis behaviour file** (2020, 2022, and future episodes) ⚑.
- Capital-actions history (rights issues, private placements, splits, buybacks with pricing).
- RPT flow history and shareholder-register evolution.
- The **estimate-vs-actual file**: every §9 earnings-impact estimate the platform makes is scored against the subsequent actuals — the platform keeps its own promise ledger on itself, and its systematic biases (e.g., over-optimism on margin recovery) are measured and fed back as calibration ⚑ (this is the single most important mechanism for "improving over time" and was missing from the brief).
- Thesis change-log: every edit to §7 with its triggering evidence.

### 10.4 Decay, review, and hygiene
Claims carry review triggers: time-based (industry files 6-monthly), event-based (any §9 item touching the claim), and contradiction-based (new fact conflicts with active claim → both surfaced to the user, never silently reconciled). Judgements older than 4 quarters without reconfirmation are displayed with a staleness marker. Nothing is deleted; superseded claims remain queryable ("what did we believe in 2026 and why") — the same point-in-time discipline the PRD imposes on financial data applies to beliefs.

### 10.5 Human-in-the-loop
The user can add claims (channel checks, meeting notes) — tagged as *User-supplied* with their own citation field — and can overrule any Judgement; overrules are logged and bind future outputs until the stated review trigger. The platform's brain is a collaboration, with the human as senior analyst of record.

---

## 11. Additions Beyond the Brief (summary of what was missing)

For traceability, the material additions this framework makes to your ten requested sections: governing principles with the four-way claim taxonomy (§0); voting/non-voting share classes, pyramid mapping, and currency-of-earnings classification (§1); state-entanglement scoring as a first-class industry module (§2.6); real/USD-terms growth triad and the revaluation-reserve book-value correction (§3); the promise-vs-delivery ledger and crisis-behaviour weighting (§4); the value-trap protocol and regime-aware multiple history (§5); sovereign-linkage and exit-liquidity as distinct risk categories (§6); mispricing-hypothesis and falsification-trigger requirements in the thesis (§7); hard gates, overlay weight vectors, and the tier/confidence separation (§8); second-order propagation and self-scoring of impact estimates (§9); and the claims architecture with platform self-calibration (§10).

---

*End of document.*
