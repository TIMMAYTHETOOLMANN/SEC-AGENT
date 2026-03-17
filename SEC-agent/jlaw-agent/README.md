# JLAW Agent Platform v5.0
## Justice Legal Analysis Workbench — Autonomous Forensic Intelligence & Regulatory Submission Engine

**Nike Inc. (CIK 0000320187) | Seven-Year Investigation: FY2019–Q1 CY2026**

---

## Quick Start

```bash
# 1. Clone/download this project
cd jlaw-agent

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy .env.template to .env and fill in your keys
cp config/.env.template .env

# 5. Initialize data pipeline
python scripts/init_data_pipeline.py

# 6. Copy your deliverables into data/deliverables/
# Copy your raw EDGAR files into data/raw-edgar/

# 7. Run the orchestrator
python -m src.agents.orchestrator
```

## Architecture

See `docs/JLAW_AGENT_ARCHITECTURE.md` for the complete system design.

### Agents
- **orchestrator** — Primary coordination, manages all sub-agents
- **edgar_ingest** — Parses raw EDGAR filings into structured JSON
- **cross_reference** — Detects anomalies across 7 fiscal years
- **report_generator** — Produces formal research reports
- **submission_manager** — Manages secure regulatory communications

### MCP Servers
- **edgar_mcp** — EDGAR filing data access tools
- **anomaly_mcp** — Anomaly database tools
- **submission_mcp** — Proton Bridge email tools (with mandatory human gates)

### Security
- All regulatory submissions require explicit human approval
- Proton Bridge provides end-to-end encrypted email
- No autonomous sending — every draft must be reviewed
- Session logs preserved for audit trail

## Deliverable Inventory (36 documents)

| Category | Count | Years |
|----------|-------|-------|
| Full-corpus timelines | 6 | FY2020–FY2025 |
| Full-corpus SEC bundles | 6 | FY2020–FY2025 |
| Full-corpus ISS memos | 6 | FY2020–FY2025 |
| Proxy-focused timelines | 3 | FY2019–FY2021 |
| Proxy-focused SEC bundles | 3 | FY2019–FY2021 |
| Proxy-focused ISS memos | 3 | FY2019–FY2021 |
| FY2019 foundation | 3 | FY2019 |
| Q1 CY2026 supplemental | 3 | Q1 2026 |
| Micro-forensic re-audit | 1 | FY2019–Q1 2026 |
| **TOTAL** | **34+** | |

## License

PRIVILEGED & CONFIDENTIAL — Attorney Work Product
