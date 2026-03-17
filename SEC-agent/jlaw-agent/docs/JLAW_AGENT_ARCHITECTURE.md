# JLAW Agent Platform — System Architecture
## Justice Legal Analysis Workbench: Autonomous Forensic Intelligence & Regulatory Submission Engine

**Version:** 5.0 | **Date:** March 14, 2026
**Platform:** Claude Agent SDK (Python) + Custom MCP Servers
**Purpose:** Ingest, cross-reference, and generate prosecution-grade forensic intelligence from SEC EDGAR filings, then autonomously submit and manage regulatory communications.

---

## 1. System Overview

The JLAW Agent Platform is a multi-agent system built on Anthropic's Claude Agent SDK that transforms raw SEC filings and investigative deliverables into submission-ready regulatory bundles. The system operates in four phases:

```
PHASE 1: INGEST → Raw EDGAR filings (PDF, XLS, RSS/XML) + 36 DOCX deliverables
PHASE 2: CROSS-REFERENCE → Filing-level anomaly detection across 7 fiscal years
PHASE 3: SYNTHESIZE → Formal research reports + submission bundles
PHASE 4: SUBMIT → Secure email submission + ongoing communication management
```

---

## 2. Agent Architecture

### 2.1 Primary Agents

| Agent | Role | Tools | Model |
|-------|------|-------|-------|
| `edgar_ingest` | Parse all EDGAR filings into structured JSON | Read, Bash, Glob, custom MCP | claude-sonnet-4-20250514 |
| `cross_reference` | Identify anomalies across fiscal years | Read, Grep, Glob, custom MCP | claude-sonnet-4-20250514 |
| `report_generator` | Produce formal research reports + submission bundles | Read, Write, Edit, Bash | claude-sonnet-4-20250514 |
| `submission_manager` | Submit via secure email + manage responses | custom MCP (Proton), Read, Write | claude-sonnet-4-20250514 |
| `orchestrator` | Coordinate all agents, maintain state, handle escalation | All subagents | claude-sonnet-4-20250514 |

### 2.2 Agent Communication Flow

```
orchestrator
├── edgar_ingest (reads raw files → produces structured JSON)
│   └── Outputs: /data/parsed/{fiscal_year}/{filing_type}.json
├── cross_reference (reads parsed JSON → produces anomaly reports)
│   └── Outputs: /data/anomalies/{pattern_id}.json
├── report_generator (reads anomalies + deliverables → produces reports)
│   └── Outputs: /data/reports/{report_type}_{date}.docx
└── submission_manager (reads reports → submits via secure email)
    └── Outputs: /data/submissions/{agency}_{date}_{status}.json
```

---

## 3. Data Pipeline

### 3.1 Input Sources

```
/data/raw-edgar/
├── filings/                    # Year-by-year EDGAR downloads
│   ├── FY2019/                 # PDF + XLS for each filing type
│   │   ├── 10-K/
│   │   ├── 10-Q/
│   │   ├── 8-K/
│   │   ├── DEF14A/
│   │   ├── Form4/
│   │   ├── 13D/
│   │   └── ...
│   ├── FY2020/
│   ├── FY2021/
│   ├── FY2022/
│   ├── FY2023/
│   ├── FY2024/
│   ├── FY2025/
│   └── Q1-CY2026/
├── rss-dump/                   # SEC EDGAR RSS/XML full filing index
│   └── nike_full_index.xml     # Complete filing history
└── reference/
    ├── trading_calendar.json   # Nike blackout windows FY2019-FY2026
    └── accession_map.json      # All known accession numbers

/data/deliverables/
├── timelines/                  # 7 Comparative Forensic Timelines
├── sec-bundles/                # 7 SEC Enforcement Evidence Bundles
├── iss-memos/                  # 7 ISS Briefing Memos
├── supplemental/               # Q1 CY2026 supplemental set (3 docs)
├── micro-forensic/             # Micro-forensic re-audit report
├── proxy-focused/              # 12 proxy-focused deliverables
└── foundation/                 # 3 FY2019 foundation documents
```

### 3.2 Parsed Data Schema

Every filing gets parsed into a standardized JSON structure:

```json
{
  "filing_id": "0000320187-24-000044",
  "filing_type": "10-K",
  "fiscal_year": "FY2024",
  "period_end": "2024-05-31",
  "filed_date": "2024-07-25",
  "signer_ceo": "John J. Donahoe II",
  "signer_cfo": "Matthew Friend",
  "exhibits": [
    {"number": "19.1", "title": "Insider Trading Policy", "status": "new", "bytes": 39027},
    {"number": "19.2", "title": "Blackout and Pre-clearance Policy", "status": "new", "bytes": 26782}
  ],
  "anomalies": [],
  "cross_references": []
}
```

### 3.3 Anomaly Schema

```json
{
  "anomaly_id": "ANO-2024-001",
  "severity": "STRUCTURAL",
  "category": "insider_trading_policy",
  "fiscal_year": "FY2024",
  "filing_id": "0000320187-24-000044",
  "title": "Exhibit 19.2 Pre-clearance Self-Approval Loophole",
  "description": "Chairman/CEO pre-clearance pathway allows Parker to self-approve trades",
  "evidence": ["EX-19.2 text", "Form 4 Parker sales $508M+"],
  "compounding_years": ["FY2019", "FY2020", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025"],
  "regulatory_relevance": {
    "sec_enforcement": "HIGH",
    "doj_referral": "MEDIUM",
    "legislative_interest": "HIGH"
  }
}
```

---

## 4. MCP Server Definitions

### 4.1 EDGAR MCP Server (`edgar_mcp`)

Provides tools for interacting with parsed EDGAR data:

```python
# Tools:
edgar_search_filings     # Search by CIK, type, date range
edgar_get_filing          # Get full parsed filing by accession
edgar_get_exhibit         # Get exhibit text by filing + exhibit number
edgar_compare_exhibits    # Diff exhibits across fiscal years
edgar_get_form4           # Get Form 4 with timeliness calculation
edgar_get_proxy_section   # Get specific proxy section (e.g., §16(a))
edgar_get_vote_counts     # Get annual meeting vote tallies
edgar_timeline_query      # Query events by date range across all years
```

### 4.2 Anomaly MCP Server (`anomaly_mcp`)

Provides tools for cross-referencing and pattern detection:

```python
# Tools:
anomaly_search            # Search anomalies by category, severity, year
anomaly_get_pattern       # Get compounding pattern across years
anomaly_create            # Register a new anomaly with evidence
anomaly_link              # Link anomalies to form compounding patterns
anomaly_get_timeline      # Get chronological anomaly sequence
anomaly_export            # Export anomalies for report generation
```

### 4.3 Submission MCP Server (`submission_mcp`)

Provides tools for secure regulatory communication:

```python
# Tools:
submission_draft           # Draft submission email with attachments
submission_review          # Present draft for human approval (REQUIRED)
submission_send            # Send via Proton Bridge SMTP (after approval)
submission_check_inbox     # Check for regulatory responses
submission_log             # Log all communications with timestamps
submission_escalate        # Flag responses requiring human attention
```

---

## 5. Report Generation Templates

### 5.1 Master Research Report (FY2019–FY2025)
- Executive summary with 7-year arc narrative
- Year-by-year findings catalog (all 23+ micro-forensic items per year)
- Compounding pattern analysis (5 identified patterns)
- Evidence index with accession numbers
- Regulatory recommendation matrix

### 5.2 SEC Division of Enforcement Submission Bundle
- Form TCR (Tips, Complaints, and Referrals) cover letter
- Evidence summary organized by violation type
- Chronological anomaly timeline
- Exhibit 19 analysis with peer comparison
- Swoosh 13D delinquency documentation
- Section 16(a) timeliness audit results
- Recommended enforcement actions (prioritized)

### 5.3 DOJ Criminal Referral Package
- Criminal referral cover letter
- Securities fraud pattern summary
- Insider trading analysis ($565M+ Parker)
- Pre-clearance self-approval documentation
- Timeline correlation with MNPI events
- Witness identification (cross-referenced with complaint's 19 CWs)

### 5.4 Legislative Briefing Package
- One-page executive summary
- Dual-class governance case study
- Exhibit 19 policy comparison (Nike vs. Dow 30 peers)
- Regulatory gap analysis (14-year SEC correspondence silence)
- Recommended legislative reforms

---

## 6. Secure Communication Infrastructure

### 6.1 Proton Mail Integration

```
Architecture:
┌─────────────────────────────────────┐
│ JLAW Agent (submission_manager)     │
│  └── Proton Bridge SMTP Client      │
│       └── localhost:1025 (Bridge)    │
│            └── Proton Mail Server    │
│                 └── End-to-end E2E   │
└─────────────────────────────────────┘

Configuration:
- Proton Mail Plus or Professional account
- Proton Bridge installed locally (provides IMAP/SMTP)
- Agent connects via localhost SMTP (port 1025) and IMAP (port 1143)
- All regulatory submissions sent from dedicated address
- All responses monitored via IMAP polling
```

### 6.2 Communication Workflow

```
1. report_generator produces submission bundle
2. submission_manager drafts email with attachments
3. HUMAN REVIEW GATE: Draft presented for approval ← MANDATORY
4. On approval: submission_manager sends via Proton Bridge
5. submission_manager logs: recipient, timestamp, subject, attachments
6. submission_manager polls inbox every 4 hours for responses
7. Responses classified: ACKNOWLEDGMENT | INQUIRY | REQUEST_FOR_INFO | ESCALATION
8. INQUIRY/REQUEST_FOR_INFO → orchestrator assigns cross_reference agent
9. ESCALATION → human notification via secondary channel
```

### 6.3 Submission Targets

| Agency | Division | Submission Method | Email/Portal |
|--------|----------|-------------------|--------------|
| SEC | Division of Enforcement | TCR Form + Email | sec.gov/tcr |
| SEC | Office of the Whistleblower | Form TCR | whistleblower@sec.gov |
| DOJ | Fraud Section | Criminal Referral | fraud.section@usdoj.gov |
| PCAOB | Division of Enforcement | Tip Submission | pcaobus.org/enforcement |
| ISS | Governance Research | Engagement Letter | governance@issgovernance.com |
| Congress | Senate Banking Committee | Staff Briefing | banking@senate.gov |
| Congress | House Financial Services | Staff Briefing | financialsvcs@mail.house.gov |

---

## 7. Security Architecture

### 7.1 Data Classification

| Level | Description | Storage | Access |
|-------|-------------|---------|--------|
| PRIVILEGED | Attorney work product, whistleblower identity | Encrypted local, Proton | Agent + Human only |
| CONFIDENTIAL | Investigative reports, anomaly databases | Encrypted local | Agent + Human only |
| REFERENCE | Public SEC filings, EDGAR data | Local filesystem | Agent (read-only) |

### 7.2 Agent Permissions

```python
# Orchestrator: full access
# edgar_ingest: Read, Bash (read-only filesystem)
# cross_reference: Read, Grep, Glob (read-only)
# report_generator: Read, Write, Edit, Bash (write to /data/reports only)
# submission_manager: Read, custom MCP only (NO direct filesystem write)
#   - REQUIRES human approval for every send action
#   - All drafts logged before sending
#   - No autonomous sending without explicit confirmation
```

### 7.3 Human-in-the-Loop Gates

**MANDATORY human approval required for:**
1. Any email sent to a regulatory body
2. Any document marked PRIVILEGED
3. Any response to a regulatory inquiry
4. Any modification to the anomaly database that changes severity ratings
5. Any new submission target not in the pre-approved list

---

## 8. Deployment

### 8.1 Prerequisites

```bash
# Python 3.10+
# Node.js 18+
# Claude Agent SDK
pip install claude-agent-sdk

# Proton Bridge (for secure email)
# Download from proton.me/mail/bridge

# Document processing
pip install python-docx openpyxl pdfplumber lxml
```

### 8.2 Environment Configuration

```bash
# .env (NEVER commit to version control)
ANTHROPIC_API_KEY=sk-ant-...
PROTON_BRIDGE_HOST=127.0.0.1
PROTON_BRIDGE_SMTP_PORT=1025
PROTON_BRIDGE_IMAP_PORT=1143
PROTON_EMAIL=jlaw-submissions@proton.me
PROTON_PASSWORD=<bridge-password>
JLAW_DATA_DIR=/path/to/jlaw-agent/data
JLAW_LOG_DIR=/path/to/jlaw-agent/logs
HUMAN_NOTIFICATION_EMAIL=<your-personal-email>
```

### 8.3 Startup Sequence

```bash
# 1. Start Proton Bridge (GUI or headless)
protonmail-bridge --noninteractive

# 2. Initialize data pipeline
python scripts/init_data_pipeline.py

# 3. Run EDGAR ingestion
python -m src.agents.edgar_ingest

# 4. Run cross-reference analysis
python -m src.agents.cross_reference

# 5. Launch orchestrator (interactive mode)
python -m src.agents.orchestrator
```

---

## 9. File Manifest

```
jlaw-agent/
├── docs/
│   ├── JLAW_AGENT_ARCHITECTURE.md      ← This document
│   ├── SUBMISSION_PROTOCOLS.md         ← Regulatory submission procedures
│   └── ANOMALY_CATALOG.md              ← All 23+ micro-forensic items
├── config/
│   ├── .env                            ← Environment variables (gitignored)
│   ├── agent_config.yaml               ← Agent definitions + permissions
│   ├── mcp_servers.yaml                ← MCP server configurations
│   └── submission_targets.yaml         ← Pre-approved regulatory contacts
├── src/
│   ├── agents/
│   │   ├── orchestrator.py             ← Primary coordination agent
│   │   ├── edgar_ingest.py             ← EDGAR filing parser
│   │   ├── cross_reference.py          ← Anomaly detection engine
│   │   ├── report_generator.py         ← Report production
│   │   └── submission_manager.py       ← Secure submission handler
│   ├── mcp/
│   │   ├── edgar_mcp.py                ← EDGAR data MCP server
│   │   ├── anomaly_mcp.py              ← Anomaly database MCP server
│   │   └── submission_mcp.py           ← Proton email MCP server
│   ├── ingestion/
│   │   ├── pdf_parser.py               ← PDF text extraction
│   │   ├── xls_parser.py               ← XLS/XLSX data extraction
│   │   ├── rss_parser.py               ← EDGAR RSS/XML index parser
│   │   ├── docx_parser.py              ← DOCX deliverable parser
│   │   └── form4_parser.py             ← Form 4 XML parser with timeliness
│   ├── reports/
│   │   ├── master_report.py            ← FY2019-FY2025 compilation
│   │   ├── sec_bundle.py               ← SEC enforcement package
│   │   ├── doj_referral.py             ← DOJ criminal referral
│   │   └── legislative_brief.py        ← Congressional briefing
│   └── submission/
│       ├── proton_client.py            ← Proton Bridge SMTP/IMAP client
│       ├── draft_manager.py            ← Draft creation + human review
│       └── response_handler.py         ← Inbox monitoring + classification
├── scripts/
│   ├── init_data_pipeline.py           ← One-time data directory setup
│   ├── ingest_edgar_rss.py             ← Parse EDGAR RSS dump
│   └── validate_deliverables.py        ← Verify all 36 DOCX files present
├── data/                               ← All data (gitignored)
│   ├── raw-edgar/
│   ├── parsed/
│   ├── anomalies/
│   ├── deliverables/
│   ├── reports/
│   └── submissions/
├── requirements.txt
├── pyproject.toml
└── README.md
```
