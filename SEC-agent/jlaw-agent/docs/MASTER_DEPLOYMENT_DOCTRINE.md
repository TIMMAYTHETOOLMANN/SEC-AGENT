# JLAW Agent Platform — Master Deployment Doctrine
# Version: 1.0 | Effective: 2026-03-18
# This document is the operational translation layer for the JLAW Agent Platform v5.0.
# Load sequence: CLAUDE.md → MASTER_DEPLOYMENT_DOCTRINE.md → MASTER_FORENSIC_DOSSIER.md

---

## Section 1 — Evidence Grounding Protocol ("Ten Toes Down")

Every factual claim produced by any agent module **MUST** be grounded with all nine of the
following fields before it is written into any output artifact. Partial citations are
inadmissible. A claim with seven of nine fields is as invalid as a claim with zero.

### 1.1 Required Citation Fields

| # | Field | Format / Example |
|---|-------|------------------|
| 1 | **Accession Number** | `0000320187-24-000044` (no hyphens optional; always 18-digit) |
| 2 | **Filing Date** | `YYYY-MM-DD` exact; no "circa", no "approximately" |
| 3 | **Page / Section Reference** | `p. 47, ¶ 3` or `Exhibit 19, Section 2.1` or `Item 9A` |
| 4 | **EDGAR Hyperlink** | `https://www.sec.gov/Archives/edgar/data/320187/<accession>/...` |
| 5 | **Statute / Rule Citation** | e.g., `Section 16(a), Exchange Act` or `Rule 13d-2(a)` |
| 6 | **Violation Description** | One sentence: what obligation, how breached, when discovered |
| 7 | **Penalty Range** | Civil (e.g., `$10,000–$207,183 per violation`) and/or criminal |
| 8 | **Party Identification** | Full legal name, role, CIK if applicable |
| 9 | **Independent Corroboration** | At minimum one cross-reference: second filing, press release, court docket, CIK0000320187.json XBRL item, or Anomaly DB entry ID |

### 1.2 Evidence Tier Classification

- **Tier A (Primary):** Direct EDGAR filings — the accession is the evidence.
- **Tier B (Derivative):** Computations from Tier A data (e.g., business-day timeliness). Must show formula and inputs.
- **Tier C (Corroborative):** Court documents, press reports, analyst filings. Always paired with Tier A.
- **Tier D (Contextual):** Historical background, academic/regulatory commentary. Never used alone to establish a violation.

### 1.3 Prohibited Constructions

- "Parker sold approximately $565M in stock" — amount must be bounded with methodology note
- "The SEC has not responded for 14 years" — must cite last correspondence date and accession
- "Swoosh LLC has not updated its 13D" — must state original filing date, last amendment date, and elapsed business days
- Any dollar figure derived from option exercises or gifts without explicit exclusion note

---

## Section 2 — Dual-Track Output Architecture

The agent produces two simultaneous output tracks for every deployment run:

**Track 1 — Regulatory Evidence Packages** (precision-maximized, citation-dense)
**Track 2 — Engagement Packages** (readability-optimized, finding-led)

### 2.1 Bundle Customization Matrix

Every recipient in `config/submission_targets.yaml` is mapped to a row in this matrix.
The report_generator agent reads `bundle_emphasis` from the YAML and routes findings accordingly.

| Row | Recipient Class | Lead Finding | Supporting Findings (max 3) | Format | Tone |
|-----|----------------|--------------|----------------------------|--------|------|
| 1 | SEC Enforcement | Exhibit 19 self-approval loophole | Swoosh 13D staleness, Parker ~$344M open-market sales | TCR attachment + DOCX | Formal regulatory |
| 2 | SEC Whistleblower | Parker insider pattern | §16(a) toggle, 10b5-1 adoption during litigation | Form TCR | Neutral evidentiary |
| 3 | DOJ Fraud Section | Securities fraud pattern (class action) | MNPI sequence Sep 2024, CLO self-clearance | Criminal referral letter | Prosecutorial |
| 4 | Senate Banking Committee | Swoosh 13D governance gap | Exhibit 19 loophole, §16(a) toggle | Staff briefing + one-pager | Policy-legislative |
| 5 | House Financial Services | Same as Senate Banking | Same | Same | Same |
| 6 | Senate Judiciary | DOJ referral summary | Parker pattern, MNPI sequence | Letter + DOCX appendix | Legislative oversight |
| 7 | ISS Governance | Swoosh 13D staleness | Parker self-approval, §16(a) toggle | Engagement letter + memo | Governance advisory |
| 8 | Glass Lewis | Exhibit 19 loophole | CLO trades, Friend 10b5-1 | Research memo | Governance advisory |
| 9 | Activist shareholders | Parker selling vs board buying ($57.5M vs $6.2M) | MNPI sequence, named defendants | Investor brief | Investor-focused |
| 10 | Class action counsel | Full anomaly list (23 items) | Compounding patterns (5) | Dossier supplement | Legal support |
| 11 | Reuters / WSJ | Parker $344M open-market sales | Sep 2024 MNPI sequence | Press backgrounder | Journalistic |
| 12 | Bloomberg Law | Swoosh governance black box | 13D staleness, board composition | Legal news brief | Journalistic |
| 13 | Nike Beat reporters | Elliott Hill zero-equity appointment | Jan 2026 late Form 4, Win Now context | Story memo | Journalistic |
| 14 | Academic / think tanks | §16(a) toggle pattern | 7-year dataset methodology | Research summary | Academic |
| 15 | State AG offices | Nike Oregon nexus | Consumer protection angle | Referral letter | State regulatory |
| 16 | FINRA | Broker-dealer trading around MNPI | Sep 2024 sequence, Parker pattern | Regulatory referral | FINRA format |

### 2.2 Output Artifact Registry

Each deployment run generates the following artifact set:

```
data/reports/
├── master_cross_analysis_{date}.docx        # Primary deliverable — all 7 FY
├── sec_enforcement_bundle_{date}.docx       # Track 1 Rows 1–2
├── doj_referral_{date}.docx                 # Track 1 Row 3
├── congressional_brief_{date}.docx          # Track 1 Rows 4–6
├── iss_engagement_{date}.docx               # Track 2 Row 7
├── glass_lewis_memo_{date}.docx             # Track 2 Row 8
├── investor_brief_{date}.docx               # Track 2 Rows 9–10
├── press_backgrounder_{date}.docx           # Track 2 Rows 11–13
└── research_summary_{date}.docx             # Track 2 Row 14
```

---

## Section 3 — Visual Asset Specifications

The visualization agent (`src/agents/visualization_agent.py`) must produce all seven
assets below before the report generator runs. Missing assets halt Phase 3.

### 3.1 Asset 1 — Insider Trading Timeline

- **Type:** Horizontal bar / Gantt overlay
- **X-axis:** Date range FY2019 (Jun 2018) → Q1 CY2026 (Mar 2026)
- **Y-axis:** Filer names (Parker, Donahoe, Friend, O'Neill, Hill, Knight T., Knight P.)
- **Data series:** (a) Option exercises, (b) Open-market sales, (c) Open-market purchases, (d) Plan adoption dates
- **Overlay events:** Earnings announcements, 8-K material events, class action filing (Nov 2023), Donahoe termination (Oct 2024)
- **Output:** `data/visualizations/chart_01_insider_timeline.png` (2400×1200, 300 DPI) + interactive Plotly HTML
- **DOCX embed:** Master report Exhibit A

### 3.2 Asset 2 — Severity Heatmap

- **Type:** Matrix heatmap
- **X-axis:** Fiscal years FY2019–FY2025 (7 columns)
- **Y-axis:** 23 micro-forensic anomaly categories
- **Color scale:** 0 (none) → 5 (structural/systemic); diverging red/green
- **Cell value:** Anomaly count for that year × category intersection
- **Output:** `data/visualizations/chart_02_severity_heatmap.png` (2000×1600, 300 DPI)
- **DOCX embed:** Master report Exhibit B

### 3.3 Asset 3 — 13D Staleness Gauge

- **Type:** Radial gauge / odometer
- **Metric:** Business days since Swoosh LLC last amended SC 13D (filed 2016-06-22)
- **Danger threshold:** Rule 13d-2 requires amendment within 10 days of material change
- **Secondary metric:** Share count drift (reported 2016 shares vs current XBRL float)
- **Output:** `data/visualizations/chart_03_13d_gauge.png` (800×800, 300 DPI)
- **DOCX embed:** Swoosh governance section

### 3.4 Asset 4 — Timeliness Boxplot

- **Type:** Box-and-whisker per filer
- **Y-axis:** Business days late (negative = early, positive = late, 0 = on time)
- **X-axis:** Each Form 4 filer with ≥ 3 filings in scope period
- **Annotate:** Outliers by accession number; Travis Knight Jan 2026 outlier labeled
- **Output:** `data/visualizations/chart_04_timeliness_boxplot.png` (1600×900, 300 DPI)
- **DOCX embed:** §16(a) compliance section

### 3.5 Asset 5 — Pattern Network Diagram

- **Type:** Force-directed graph (NetworkX + Matplotlib)
- **Nodes:** 5 compounding patterns + 23 anomalies + 8 key individuals + 2 entities
- **Edges:** Causal / corroborative linkages (color-coded by edge type)
- **Node size:** Scaled by number of connected anomalies
- **Output:** `data/visualizations/chart_05_pattern_network.png` (2400×2400, 300 DPI)
- **DOCX embed:** Compounding patterns section

### 3.6 Asset 6 — Regulatory Radar Chart

- **Type:** Radar / spider chart (6 axes)
- **Axes:** SEC enforcement probability, DOJ referral strength, ISS governance concern, Shareholder impact, Market integrity risk, Systemic pattern severity
- **Series:** FY2019, FY2022, FY2025 (three overlapping polygons showing trajectory)
- **Output:** `data/visualizations/chart_06_regulatory_radar.png` (1200×1200, 300 DPI)
- **DOCX embed:** Executive summary section

### 3.7 Asset 7 — Interactive HTML Dashboard

- **Type:** Plotly Dash multi-tab application
- **Tab 1:** Anomaly Explorer (searchable, filterable data table)
- **Tab 2:** Insider Timeline (interactive version of Asset 1)
- **Tab 3:** Severity Heatmap (interactive version of Asset 2)
- **Tab 4:** Filing Index (browse by fiscal year, filing type, filer)
- **Tab 5:** Pattern Linkage (interactive version of Asset 5)
- **Output:** `data/visualizations/dashboard.html` (self-contained, no external CDN dependencies)
- **Distribution:** Attach as supplemental to congressional and ISS packages

---

## Section 4 — UUID File Processing Protocol

### 4.1 File Inventory

The `data/raw-edgar/filings/` directory contains 2,254 files with UUID-style names:
- Format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.{pdf|xls}`
- Type CANNOT be inferred from filename — must be detected from content
- The `CIK0000320187.json` XBRL facts file at `data/raw-edgar/reference/` is the authoritative filing index

### 4.2 Classification Algorithm

```
For each UUID file:
  1. Check CIK0000320187.json for matching accession reference → extract filing_type, period
  2. If PDF: extract first 500 chars; regex-match SEC form header patterns
     - "FORM 10-K", "ANNUAL REPORT" → 10-K
     - "FORM 10-Q", "QUARTERLY REPORT" → 10-Q
     - "FORM 4", "STATEMENT OF CHANGES" → Form4
     - "FORM DEF 14A", "PROXY STATEMENT" → DEF14A
     - "FORM 8-K" → 8-K
     - "FORM 3", "INITIAL STATEMENT" → Form3
  3. If XLS: check sheet names and column headers
     - "FORM 4", "transaction" columns → Form4 exhibit
     - "XBRL", financial statement labels → 10-K/10-Q exhibit
  4. Assign calendar year from file modification date or RSS index cross-reference
  5. Write classification to data/parsed/filing_index.json
```

### 4.3 Parsing Priority Order

Process files in this order to maximize cross-reference accuracy:

1. `CIK0000320187.json` — establish filing registry (all accession numbers, dates, types)
2. RSS/XML index files — supplement registry with filing metadata
3. Form 4 XML files — timeliness calculations depend on event_date and filed_date
4. DEF14A PDFs — proxy disclosures drive §16(a) toggle analysis
5. 10-K PDFs — Exhibit 19 insider trading policy text
6. 8-K PDFs — material event timestamps for MNPI analysis
7. SC 13D filings — Swoosh LLC staleness tracking
8. All remaining PDFs and XLS files

### 4.4 Timeliness Calculation Standard

```python
# Business day calculation — federal holiday calendar required
# Use: pandas_market_calendars or trading_calendars with NYSE calendar
# Form 4: event_date → filed_date, maximum 2 business days
# Form 3: appointment_date → filed_date, maximum 10 calendar days
# SC 13D amendment: material_change_date → filed_date, maximum 10 calendar days
```

---

## Section 5 — Deployment Sequence (8-Step Protocol)

Execute the following steps simultaneously where noted. Human gates are mandatory
and cannot be bypassed by any agent.

### Step 1 — Pre-Flight Validation (Automated)
- [ ] Verify `data/raw-edgar/reference/CIK0000320187.json` readable
- [ ] Verify `config/submission_targets.yaml` parseable
- [ ] Verify all 7 visual assets exist at specified output paths
- [ ] Verify anomaly database at `data/anomalies/` has ≥ 23 entries
- [ ] Verify parsed JSON output at `data/parsed/` covers FY2019–FY2025

### Step 2 — Ingestion Pass (Automated)
- Run `src/agents/edgar_ingest.py` on all unprocessed UUID files
- Classify and parse per Section 4 protocol
- Checkpoint: `data/parsed/filing_index.json` updated

### Step 3 — Cross-Reference Pass (Automated)
- Run `src/agents/cross_reference.py`
- Build/update anomaly database
- Generate compounding pattern linkage graph
- Checkpoint: `data/anomalies/anomaly_db.json` updated

### Step 4 — Visualization Pass (Automated)
- Run `src/agents/visualization_agent.py`
- Generate all 7 assets per Section 3 specifications
- Checkpoint: all 7 asset files present, manifest JSON written

### Step 5 — Report Generation Pass (Automated)
- Run `src/agents/report_generator.py` for all 9 output artifacts
- Apply bundle customization matrix (Section 2.1) to each recipient class
- Checkpoint: all DOCX artifacts written to `data/reports/`

### Step 6 — **MANDATORY HUMAN REVIEW GATE** ⛔
```
HALT. DO NOT PROCEED TO STEP 7 WITHOUT EXPLICIT HUMAN APPROVAL.

Present to human operator:
  - Summary of all anomalies discovered in this run (new vs. existing)
  - Any data corrections identified vs. prior run
  - Full list of 9 output artifacts with file sizes
  - Submission target list (from config/submission_targets.yaml)
  - Draft cover letter for each Tier 1 recipient

Human operator must explicitly type: APPROVE DEPLOYMENT
before Step 7 proceeds.
```

### Step 7 — Submission Pass (Requires Step 6 Approval)
- Load submission targets from `config/submission_targets.yaml`
- For each Tier 1 recipient: compose cover letter, attach relevant DOCX
- For each Tier 2 recipient: compose cover letter, attach relevant DOCX
- Present every draft email for human review before queuing
- Execute send sequence via `src/submission/proton_client.py`

### Step 8 — Post-Submission Monitoring (Automated)
- Activate inbox monitoring via `src/submission/response_handler.py`
- Classify all inbound responses: INQUIRY / REQUEST_FOR_INFO / ESCALATION / ACKNOWLEDGMENT / NO_ACTION
- Route ESCALATION responses to human immediately (do not queue)
- Log all responses to `data/submissions/response_log.json`

---

## Section 6 — Report Generation Standards

### 6.1 DOCX Format Requirements

All DOCX outputs must conform to:
- **Header:** "CONFIDENTIAL — PRIVILEGED INVESTIGATIVE COMMUNICATIONS" (every page)
- **Footer:** Document title, date, page n of N
- **Font:** Times New Roman 12pt body, 14pt section headers, 11pt table text
- **Margins:** 1-inch all sides
- **Evidence tables:** Three-column minimum (Finding | Accession | Statute)
- **Accession index:** Appendix A in every document — all cited accessions in chronological order

### 6.2 SEC Enforcement Bundle Structure

```
Section 1: Executive Summary (2 pages max)
Section 2: Jurisdiction and Standing
Section 3: Violation Catalog (organized by statute)
  3.1: Section 16(a) — Form 4 untimeliness findings
  3.2: Rule 13d-2 — Swoosh LLC amendment failure
  3.3: Exhibit 19 — Pre-clearance self-approval pathway
  3.4: 10b5-1 — Plan adoption during material litigation
Section 4: Insider Trading Pattern Analysis
Section 5: Systemic Pattern Analysis (compounding violations)
Section 6: Recommended Enforcement Actions
Appendix A: Accession Index
Appendix B: Key Individuals Reference
Appendix C: Visual Exhibits (embedded assets from Section 3)
```

### 6.3 DOJ Criminal Referral Structure

```
Section 1: Referral Summary — securities fraud pattern
Section 2: Factual Background
Section 3: Criminal Nexus Analysis
  3.1: Wire fraud / 18 U.S.C. § 1343 applicability
  3.2: Securities fraud / 18 U.S.C. § 1348 applicability
  3.3: Conspiracy / 18 U.S.C. § 371 applicability
Section 4: Evidence Summary by Individual
Section 5: Parallel SEC proceeding status
Appendix A: Accession Index
Appendix B: Class action docket citations (D. Or. 3:24-cv-00974-AN)
```

---

## Section 7 — Submission Infrastructure

### 7.1 Proton Bridge Configuration

The submission_mcp server handles all outbound email via Proton Bridge SMTP.
Required environment variables (set in `.env`, never committed to repo):
```
PROTON_BRIDGE_HOST=127.0.0.1
PROTON_BRIDGE_SMTP_PORT=1025
PROTON_BRIDGE_IMAP_PORT=1143
PROTON_EMAIL=<redacted>
PROTON_PASSWORD=<redacted>
HUMAN_NOTIFICATION_EMAIL=<redacted>
```

### 7.2 Draft Lifecycle

```
DRAFT_CREATED → DRAFT_REVIEWED → DRAFT_APPROVED → QUEUED → SENT → ACKNOWLEDGED
                                ↑                          ↓
                        (human gate)              RESPONSE_RECEIVED
```

### 7.3 Cover Letter Template Variables

The submission_manager agent populates these fields from `config/submission_targets.yaml`:
- `{recipient_name}` — full name of leadership contact
- `{recipient_title}` — title
- `{organization}` — organization name
- `{address_block}` — full mailing address (4 lines)
- `{lead_finding}` — from bundle_emphasis.lead_finding
- `{date}` — today's date (YYYY-MM-DD)
- `{case_ref}` — Nike, Inc. CIK 0000320187 / D. Or. 3:24-cv-00974-AN

---

## Section 8 — Quality Control Checklist

Before any artifact is finalized, the report_generator must verify:

- [ ] All dollar figures include methodology note (open-market sales vs. total transactions)
- [ ] All date calculations specify business-day vs. calendar-day basis
- [ ] All Form 4 timeliness findings specify event_date, filed_date, and business-day delta
- [ ] All 13D staleness findings specify original filing date, last amendment date, elapsed days
- [ ] All Exhibit 19 findings include direct quote from policy text (with page/section ref)
- [ ] Parker cumulative figures are split: ~$344M open-market; ~$565M total (including exercises and gifts)
- [ ] SEC correspondence gap stated as: ~12 years, last CORRESP filed 2014-02-18, accession 0000320187-14-000006
- [ ] Class action docket cited as: D. Or. 3:24-cv-00974-AN, filed November 2023
- [ ] Swoosh LLC 13D original filing: 2016-06-22; CIK 0001645433; no amendments as of this run date
- [ ] All visual assets confirmed present before report generation begins

---

## Section 9 — Critical Data Corrections

The following corrections supersede all prior documentation and agent outputs.
These corrections are authoritative. Any conflicting prior statement is superseded.

### 9.1 Parker Cumulative Sales Figure

| Version | Figure | Basis | Status |
|---------|--------|-------|--------|
| Prior documentation | ~$565M+ | All Form 4 transactions including option exercises and gift transfers | **SUPERSEDED** |
| **Corrected (authoritative)** | **~$344M** | **Verified open-market sales only (transaction code S)** | **USE THIS** |

**Methodology note:** The ~$565M figure included option exercise transactions (code M/F) and
gift transfers (code G), which do not represent open-market sale proceeds. The ~$344M figure
is derived solely from Form 4 transaction code "S" (open-market sale) entries for Mark G. Parker
covering the scope period FY2019–FY2025.

When the total transaction value (including exercises and gifts) is relevant (e.g., for §16(b)
short-swing profit analysis or total compensation context), cite ~$565M with explicit clarification
that this includes non-sale transactions. When discussing insider selling patterns, market impact,
or market integrity concerns, cite ~$344M (open-market sales only).

### 9.2 SEC Correspondence Gap

| Version | Figure | Last CORRESP Date | Status |
|---------|--------|-------------------|--------|
| Prior documentation | ~14 years | December 2011 | **SUPERSEDED** |
| **Corrected (authoritative)** | **~12 years** | **February 2014 (accession: 0000320187-14-000006)** | **USE THIS** |

**Methodology note:** A subsequent CORRESP filing in February 2014 was identified after the
original analysis. The gap should be calculated from 2014-02-18 (the verified last CORRESP
filing date) to the present, yielding approximately 12 years of SEC correspondence silence.

### 9.3 Travis Knight Late Form 4

- Event: Travis Knight filed a Form 4 reporting a January 2026 transaction
- Filed date: 2026-01-05 (verify against EDGAR at time of deployment)
- This represents the first identified §16 filing failure by any member of the Knight family
  in the 7-year scope period
- Do NOT conflate with Philip Knight's Class A distributions (those are separate events)

### 9.4 September 2024 MNPI Sequence

The precise sequence (bylaws amendment → CEO firing announcement):
- 2024-09-18: Nike board amends bylaws (8-K filed: verify accession at deployment)
- 2024-09-19: Nike announces Donahoe departure and Hill appointment (8-K filed: verify accession)
- The 24-hour gap between bylaws change and CEO announcement is the MNPI window of concern
- Any insider trades in this 24-hour window require specific analysis

---

## Section 10 — Agent SDK Integration Notes

### 10.1 File Load Sequence

When `setting_sources=["project"]` is set, the agent SDK loads in this order:
```
1. CLAUDE.md                           (identity + operating rules)
2. docs/MASTER_DEPLOYMENT_DOCTRINE.md  (this file — operational protocol)
3. config/agent_config.yaml            (agent definitions + MCP servers)
4. config/submission_targets.yaml      (recipient directory)
5. docs/MASTER_FORENSIC_DOSSIER.md     (intelligence corpus — paste separately)
```

### 10.2 State Persistence

The agent maintains investigation state across sessions via:
- `data/parsed/filing_index.json` — ingestion state
- `data/anomalies/anomaly_db.json` — cross-reference state
- `data/submissions/submission_log.json` — submission state
- `data/submissions/response_log.json` — response state

At session start, the orchestrator loads all four state files before proceeding.

### 10.3 Conflict Resolution

If this doctrine conflicts with CLAUDE.md on any factual point, this doctrine takes precedence.
If this doctrine conflicts with `docs/MASTER_FORENSIC_DOSSIER.md` on any factual point,
defer to human review before proceeding.

### 10.4 Version Control

This file is under version control. Do not edit inline during agent runs.
All data corrections must be proposed to the human operator and committed
to the repository before being incorporated into agent outputs.
