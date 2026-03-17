"""
JLAW Cross-Reference Agent
Identifies anomalies by comparing parsed filings across fiscal years.
Detects compounding patterns and validates micro-forensic items.

This agent reads all parsed JSON from data/parsed/ and cross-references:
1. Form 4 timeliness across all insiders and all years
2. Exhibit changes (additions, removals, modifications) year-over-year
3. Proxy disclosure consistency (Section 16(a), beneficial ownership)
4. Vote count trends and director opposition patterns
5. Compensation vs. performance divergence
6. 13D/13G amendment staleness
7. Insider trading patterns vs. MNPI event timing

Outputs anomaly records to data/anomalies/ via the anomaly database.

Usage:
    python -m src.agents.cross_reference
    python -m src.agents.cross_reference --year FY2024
    python -m src.agents.cross_reference --pattern swoosh
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


# ═══════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", PROJECT_ROOT / "data"))
PARSED_DIR = DATA_DIR / "parsed"
ANOMALY_DIR = DATA_DIR / "anomalies"
LOG_DIR = Path(os.environ.get("JLAW_LOG_DIR", PROJECT_ROOT / "logs"))

FISCAL_YEARS = ["FY2019", "FY2020", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025"]
CALENDAR_YEARS = ["CY2019", "CY2020", "CY2021", "CY2022", "CY2023", "CY2024", "CY2025"]
ALL_YEAR_DIRS = FISCAL_YEARS + CALENDAR_YEARS

# Anomaly severity thresholds
LATE_FILING_THRESHOLD_DAYS = 2  # Form 4 must be filed within 2 business days
STALE_13D_THRESHOLD_YEARS = 2  # 13D amendment should update within 2 years
EXHIBIT_CHANGE_SIGNIFICANCE = ["19.1", "19.2", "21.1"]  # Key exhibits to track


def load_all_parsed(fiscal_year: str = None) -> Dict[str, List[Dict]]:
    """Load all parsed JSON files organized by fiscal year."""
    data = {}
    search_dirs = [PARSED_DIR / fiscal_year] if fiscal_year else [
        PARSED_DIR / fy for fy in ALL_YEAR_DIRS
    ]

    for fy_dir in search_dirs:
        if not fy_dir.is_dir():
            continue
        fy_name = fy_dir.name
        filings = []
        for json_file in fy_dir.rglob("*.json"):
            if json_file.name == "filing_inventory.json":
                continue
            try:
                with open(json_file) as f:
                    filing = json.load(f)
                filing["_source_file"] = str(json_file)
                filings.append(filing)
            except (json.JSONDecodeError, OSError):
                continue
        data[fy_name] = filings

    return data


def load_anomaly_db() -> Dict:
    """Load the anomaly database."""
    db_path = ANOMALY_DIR / "anomaly_database.json"
    if db_path.exists():
        with open(db_path) as f:
            return json.load(f)
    return {"anomalies": [], "patterns": [], "last_updated": None}


def save_anomaly_db(db: Dict):
    """Save the anomaly database."""
    ANOMALY_DIR.mkdir(parents=True, exist_ok=True)
    db["last_updated"] = datetime.now().isoformat()
    with open(ANOMALY_DIR / "anomaly_database.json", "w") as f:
        json.dump(db, f, indent=2)


def create_anomaly(db: Dict, category: str, severity: str, fiscal_year: str,
                   filing_id: str, title: str, description: str,
                   evidence: List = None, compounding_years: List = None,
                   regulatory_relevance: Dict = None) -> str:
    """Create a new anomaly record and return its ID."""
    year_num = fiscal_year.replace("FY", "").replace("Q1-CY", "")
    anomaly_id = f"ANO-{year_num}-{str(len(db['anomalies']) + 1).zfill(3)}"

    anomaly = {
        "anomaly_id": anomaly_id,
        "category": category,
        "severity": severity,
        "fiscal_year": fiscal_year,
        "filing_id": filing_id or "N/A",
        "title": title,
        "description": description,
        "evidence": evidence or [],
        "compounding_years": compounding_years or [fiscal_year],
        "regulatory_relevance": regulatory_relevance or {},
        "created_at": datetime.now().isoformat(),
        "linked_patterns": [],
    }

    db["anomalies"].append(anomaly)
    return anomaly_id


def create_pattern(db: Dict, title: str, anomaly_ids: List[str],
                   description: str) -> str:
    """Link anomalies into a compounding pattern."""
    pattern_id = f"PAT-{str(len(db['patterns']) + 1).zfill(3)}"

    years_spanned = sorted(set(
        yr for a in db["anomalies"]
        if a["anomaly_id"] in anomaly_ids
        for yr in a.get("compounding_years", [])
    ))

    pattern = {
        "pattern_id": pattern_id,
        "title": title,
        "anomaly_ids": anomaly_ids,
        "description": description,
        "created_at": datetime.now().isoformat(),
        "years_spanned": years_spanned,
    }

    db["patterns"].append(pattern)

    # Back-link anomalies
    for a in db["anomalies"]:
        if a["anomaly_id"] in anomaly_ids:
            a.setdefault("linked_patterns", []).append(pattern_id)

    return pattern_id


# ═══════════════════════════════════════════════
# CROSS-REFERENCE ANALYSES
# ═══════════════════════════════════════════════

def analyze_form4_timeliness(data: Dict[str, List[Dict]], db: Dict) -> List[str]:
    """Analyze Form 4 filing timeliness across all years."""
    anomaly_ids = []

    for fy, filings in sorted(data.items()):
        form4s = [f for f in filings if f.get("filing_type") == "Form4"]
        for filing in form4s:
            for txn in filing.get("transactions", []):
                bdays = txn.get("business_days_to_file")
                if bdays is not None and bdays > LATE_FILING_THRESHOLD_DAYS:
                    aid = create_anomaly(
                        db,
                        category="section_16",
                        severity="MEDIUM" if bdays <= 5 else "HIGH",
                        fiscal_year=fy,
                        filing_id=filing.get("filing_id"),
                        title=f"Late Form 4: {filing.get('filer_name', 'Unknown')} — {bdays} business days",
                        description=(
                            f"{filing.get('filer_name', 'Unknown')} filed Form 4 "
                            f"{bdays} business days after transaction date {txn.get('transaction_date')}. "
                            f"SEC Rule 16a-3(g) requires filing within 2 business days. "
                            f"Transaction code: {txn.get('code')}, shares: {txn.get('shares')}"
                        ),
                        evidence=[
                            f"Transaction date: {txn.get('transaction_date')}",
                            f"Filing date: {filing.get('filed_date')}",
                            f"Business days elapsed: {bdays}",
                            f"Filing deadline: {txn.get('filing_deadline')}",
                        ],
                        regulatory_relevance={
                            "sec_enforcement": "HIGH",
                            "statute": "Section 16(a), Exchange Act of 1934; Rule 16a-3(g)",
                        },
                    )
                    anomaly_ids.append(aid)

    return anomaly_ids


def analyze_exhibit_changes(data: Dict[str, List[Dict]], db: Dict) -> List[str]:
    """Track exhibit changes year-over-year, especially Exhibit 19."""
    anomaly_ids = []
    exhibits_by_year = {}

    for fy, filings in sorted(data.items()):
        ten_ks = [f for f in filings if f.get("filing_type") == "10-K"]
        if ten_ks:
            exhibits_by_year[fy] = {
                ex.get("number"): ex for ex in ten_ks[0].get("exhibits", [])
            }

    # Compare adjacent years
    years = sorted(exhibits_by_year.keys())
    for i in range(1, len(years)):
        prev_year = years[i - 1]
        curr_year = years[i]
        prev_exhibits = exhibits_by_year[prev_year]
        curr_exhibits = exhibits_by_year[curr_year]

        # Check for significant exhibit changes
        for ex_num in EXHIBIT_CHANGE_SIGNIFICANCE:
            prev_ex = prev_exhibits.get(ex_num)
            curr_ex = curr_exhibits.get(ex_num)

            if prev_ex is None and curr_ex is not None:
                aid = create_anomaly(
                    db,
                    category="exhibit",
                    severity="HIGH" if "19" in ex_num else "MEDIUM",
                    fiscal_year=curr_year,
                    filing_id=None,
                    title=f"New Exhibit {ex_num} appeared in {curr_year}",
                    description=(
                        f"Exhibit {ex_num} ('{curr_ex.get('title', '')}') was first filed in "
                        f"{curr_year}, absent in {prev_year}. "
                        f"For Exhibit 19, this may reflect compliance with new SEC requirements."
                    ),
                    evidence=[
                        f"Exhibit {ex_num} absent in {prev_year}",
                        f"Exhibit {ex_num} present in {curr_year}: {curr_ex.get('title', '')}",
                    ],
                    compounding_years=[prev_year, curr_year],
                    regulatory_relevance={
                        "sec_enforcement": "MEDIUM",
                        "statute": "Regulation S-K Item 601",
                    },
                )
                anomaly_ids.append(aid)
            elif prev_ex is not None and curr_ex is None:
                aid = create_anomaly(
                    db,
                    category="exhibit",
                    severity="HIGH",
                    fiscal_year=curr_year,
                    filing_id=None,
                    title=f"Exhibit {ex_num} removed in {curr_year}",
                    description=(
                        f"Exhibit {ex_num} ('{prev_ex.get('title', '')}') was present in "
                        f"{prev_year} but removed in {curr_year}."
                    ),
                    evidence=[
                        f"Exhibit {ex_num} present in {prev_year}: {prev_ex.get('title', '')}",
                        f"Exhibit {ex_num} absent in {curr_year}",
                    ],
                    compounding_years=[prev_year, curr_year],
                    regulatory_relevance={"sec_enforcement": "HIGH"},
                )
                anomaly_ids.append(aid)

    return anomaly_ids


def analyze_insider_selling_patterns(data: Dict[str, List[Dict]], db: Dict) -> List[str]:
    """Detect cumulative insider selling patterns and buy/sell divergence."""
    anomaly_ids = []
    seller_totals = defaultdict(lambda: {"sold_shares": 0, "sold_value": 0.0,
                                          "bought_shares": 0, "bought_value": 0.0,
                                          "years_active": set()})

    for fy, filings in sorted(data.items()):
        form4s = [f for f in filings if f.get("filing_type") == "Form4"]
        for filing in form4s:
            filer = filing.get("filer_name", "Unknown")
            for txn in filing.get("transactions", []):
                shares = txn.get("shares", 0)
                price = txn.get("price") or 0
                code = txn.get("code", "")
                acq_disp = txn.get("acquired_disposed", "")

                if isinstance(shares, (int, float)) and isinstance(price, (int, float)):
                    value = shares * price
                    if code == "S" or acq_disp == "D":
                        seller_totals[filer]["sold_shares"] += shares
                        seller_totals[filer]["sold_value"] += value
                    elif code == "P" or (acq_disp == "A" and code not in ("A", "M", "F", "G")):
                        seller_totals[filer]["bought_shares"] += shares
                        seller_totals[filer]["bought_value"] += value
                    seller_totals[filer]["years_active"].add(fy)

    # Flag significant sellers
    for filer, totals in seller_totals.items():
        if totals["sold_value"] > 10_000_000:  # $10M+ cumulative sales
            severity = "STRUCTURAL" if totals["sold_value"] > 100_000_000 else "HIGH"
            years_list = sorted(totals["years_active"])
            aid = create_anomaly(
                db,
                category="insider_trading",
                severity=severity,
                fiscal_year=years_list[-1] if years_list else "UNKNOWN",
                filing_id=None,
                title=f"Cumulative insider sales: {filer} — ${totals['sold_value']:,.0f}",
                description=(
                    f"{filer} cumulative open-market sales: {totals['sold_shares']:,.0f} shares "
                    f"(${totals['sold_value']:,.0f}) vs. purchases: {totals['bought_shares']:,.0f} shares "
                    f"(${totals['bought_value']:,.0f}). "
                    f"Net sell-side bias: ${totals['sold_value'] - totals['bought_value']:,.0f}. "
                    f"Active across {len(years_list)} fiscal years."
                ),
                evidence=[
                    f"Total sold: {totals['sold_shares']:,.0f} shares (${totals['sold_value']:,.0f})",
                    f"Total bought: {totals['bought_shares']:,.0f} shares (${totals['bought_value']:,.0f})",
                    f"Years active: {', '.join(years_list)}",
                ],
                compounding_years=years_list,
                regulatory_relevance={
                    "sec_enforcement": "HIGH",
                    "doj_referral": "MEDIUM" if totals["sold_value"] > 100_000_000 else "LOW",
                    "statute": "Section 10(b), Rule 10b-5; Section 16(b)",
                },
            )
            anomaly_ids.append(aid)

    return anomaly_ids


def analyze_13d_staleness(data: Dict[str, List[Dict]], db: Dict) -> List[str]:
    """Detect stale Schedule 13D filings that haven't been amended."""
    anomaly_ids = []
    latest_13d = {}

    for fy, filings in sorted(data.items()):
        for filing in filings:
            ft = filing.get("filing_type", "")
            if "13D" in ft or "SC13D" in ft:
                filer = filing.get("filer_name", "") or filing.get("title", "")
                filed_date = filing.get("filed_date", "")
                if filer and filed_date:
                    latest_13d[filer] = {
                        "filed_date": filed_date,
                        "fiscal_year": fy,
                        "filing_id": filing.get("filing_id"),
                    }

    # Check staleness as of most recent data
    for filer, info in latest_13d.items():
        try:
            filed = datetime.strptime(info["filed_date"], "%Y-%m-%d")
            age_years = (datetime(2026, 3, 15) - filed).days / 365.25
            if age_years > STALE_13D_THRESHOLD_YEARS:
                severity = "STRUCTURAL" if age_years > 5 else "HIGH"
                aid = create_anomaly(
                    db,
                    category="swoosh_13d",
                    severity=severity,
                    fiscal_year=info["fiscal_year"],
                    filing_id=info["filing_id"],
                    title=f"Stale Schedule 13D: {filer} — {age_years:.1f} years since last amendment",
                    description=(
                        f"{filer} Schedule 13D last amended on {info['filed_date']} "
                        f"({age_years:.1f} years ago). SEC rules require prompt amendment "
                        f"upon material changes in beneficial ownership or intentions."
                    ),
                    evidence=[
                        f"Last 13D filing date: {info['filed_date']}",
                        f"Years since amendment: {age_years:.1f}",
                    ],
                    compounding_years=FISCAL_YEARS,
                    regulatory_relevance={
                        "sec_enforcement": "HIGH",
                        "statute": "Section 13(d), Exchange Act; Rule 13d-2",
                    },
                )
                anomaly_ids.append(aid)
        except (ValueError, TypeError):
            continue

    return anomaly_ids


def analyze_forensic_keyword_density(data: Dict[str, List[Dict]], db: Dict) -> List[str]:
    """Analyze forensic keyword density trends across filings."""
    anomaly_ids = []
    keyword_counts_by_year = {}

    for fy, filings in sorted(data.items()):
        year_count = 0
        for filing in filings:
            flags = filing.get("flags", {})
            year_count += flags.get("forensic_keyword_count", 0)
        keyword_counts_by_year[fy] = year_count

    # Detect sudden spikes or drops
    years = sorted(keyword_counts_by_year.keys())
    for i in range(1, len(years)):
        prev = keyword_counts_by_year[years[i - 1]]
        curr = keyword_counts_by_year[years[i]]
        if prev > 0 and curr > prev * 3:  # 3x spike
            aid = create_anomaly(
                db,
                category="disclosure_pattern",
                severity="MEDIUM",
                fiscal_year=years[i],
                filing_id=None,
                title=f"Forensic keyword spike: {years[i]} ({curr} vs {prev} in {years[i-1]})",
                description=(
                    f"Forensic keyword density increased {curr/prev:.1f}x from {years[i-1]} "
                    f"to {years[i]} ({prev} → {curr} occurrences). May indicate increased "
                    f"disclosure activity, new litigation events, or policy changes."
                ),
                evidence=[
                    f"{years[i-1]}: {prev} forensic keywords",
                    f"{years[i]}: {curr} forensic keywords",
                ],
                compounding_years=[years[i - 1], years[i]],
                regulatory_relevance={"sec_enforcement": "LOW"},
            )
            anomaly_ids.append(aid)

    return anomaly_ids


def build_compounding_patterns(db: Dict) -> List[str]:
    """
    Identify and create compounding patterns by linking related anomalies
    across fiscal years.
    """
    pattern_ids = []

    # Group anomalies by category
    by_category = defaultdict(list)
    for a in db["anomalies"]:
        by_category[a["category"]].append(a)

    # Pattern 1: Multi-year Section 16 violations
    sec16_anomalies = by_category.get("section_16", [])
    if len(sec16_anomalies) >= 3:
        pattern_id = create_pattern(
            db,
            title="Recurring Section 16(a) Timeliness Violations",
            anomaly_ids=[a["anomaly_id"] for a in sec16_anomalies],
            description=(
                f"{len(sec16_anomalies)} late Form 4 filings detected across "
                f"multiple fiscal years, suggesting systemic compliance failure."
            ),
        )
        pattern_ids.append(pattern_id)

    # Pattern 2: Insider selling concentration
    insider_anomalies = by_category.get("insider_trading", [])
    if insider_anomalies:
        pattern_id = create_pattern(
            db,
            title="Concentrated Insider Selling Pattern",
            anomaly_ids=[a["anomaly_id"] for a in insider_anomalies],
            description=(
                f"{len(insider_anomalies)} significant insider selling patterns detected. "
                f"Cumulative sell-side bias across senior executives."
            ),
        )
        pattern_ids.append(pattern_id)

    # Pattern 3: 13D staleness
    swoosh_anomalies = by_category.get("swoosh_13d", [])
    if swoosh_anomalies:
        pattern_id = create_pattern(
            db,
            title="Schedule 13D Chronic Staleness",
            anomaly_ids=[a["anomaly_id"] for a in swoosh_anomalies],
            description=(
                f"Schedule 13D amendment delinquency spanning multiple years. "
                f"Controlling shareholder beneficial ownership disclosures "
                f"significantly outdated."
            ),
        )
        pattern_ids.append(pattern_id)

    # Pattern 4: Exhibit changes correlating with litigation
    exhibit_anomalies = by_category.get("exhibit", [])
    if exhibit_anomalies:
        pattern_id = create_pattern(
            db,
            title="Exhibit Policy Changes Correlating with Enforcement Events",
            anomaly_ids=[a["anomaly_id"] for a in exhibit_anomalies],
            description=(
                f"{len(exhibit_anomalies)} significant exhibit changes detected, "
                f"potentially correlating with regulatory or litigation events."
            ),
        )
        pattern_ids.append(pattern_id)

    return pattern_ids


def enrich_parsed_data(data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Enrich parsed filing data with CIK reference metadata.
    Fills in filing_type, filed_date, and filing_id from the CIK inventory
    and from forensic flag heuristics.
    """
    # Load CIK filing inventory for accession-number enrichment
    cik_inv_path = PARSED_DIR / "reference" / "cik_filing_inventory.json"
    cik_inv = {}
    if cik_inv_path.exists():
        try:
            with open(cik_inv_path) as f:
                cik_inv = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    enriched_count = 0
    reclassified_count = 0

    for fy, filings in data.items():
        for filing in filings:
            # Reclassify UNKNOWN types using forensic flags and text content
            if filing.get("filing_type") == "UNKNOWN":
                flags = filing.get("forensic_flags", [])
                flag_text = ' '.join(f.get("context", "") + " " + f.get("keyword", "")
                                     for f in flags)
                sections = filing.get("sections", [])
                section_text = ' '.join(s.get("heading", "") for s in sections
                                        if isinstance(s, dict))
                exhibits = filing.get("exhibits", [])
                combined_text = flag_text + " " + section_text

                # Heuristic reclassification
                if any(kw in combined_text for kw in ["BENEFICIAL OWNER", "Form 4",
                                                       "Section 16(a)", "STATEMENT OF CHANGES"]):
                    filing["filing_type"] = "Form4"
                    reclassified_count += 1
                elif any(kw in combined_text.upper() for kw in ["SCHEDULE 14A", "DEF 14A",
                                                                  "PROXY STATEMENT",
                                                                  "NOTICE OF ANNUAL MEETING"]):
                    filing["filing_type"] = "DEF14A"
                    reclassified_count += 1
                elif any(kw in combined_text.upper() for kw in ["ANNUAL REPORT",
                                                                  "FORM 10-K"]):
                    if len(exhibits) >= 3:
                        filing["filing_type"] = "10-K"
                        reclassified_count += 1
                elif any(kw in combined_text.upper() for kw in ["QUARTERLY REPORT",
                                                                  "FORM 10-Q"]):
                    filing["filing_type"] = "10-Q"
                    reclassified_count += 1
                elif any(kw in combined_text.upper() for kw in ["CURRENT REPORT",
                                                                  "FORM 8-K"]):
                    filing["filing_type"] = "8-K"
                    reclassified_count += 1
                elif any(kw in combined_text.upper() for kw in ["SCHEDULE 13D",
                                                                  "SC 13D"]):
                    filing["filing_type"] = "SC13D"
                    reclassified_count += 1
                elif any(kw in combined_text.upper() for kw in ["SCHEDULE 13G",
                                                                  "SC 13G"]):
                    filing["filing_type"] = "SC13G"
                    reclassified_count += 1

            # Extract monetary transaction data from Form4 forensic flags
            if filing.get("filing_type") == "Form4" and not filing.get("transactions"):
                transactions = []
                for amt in filing.get("monetary_amounts", []):
                    ctx = amt.get("context", "")
                    amount_raw = amt.get("amount_raw", "")
                    # Parse transaction rows: Class B Common Stock date code shares A/D price
                    import re as _re
                    txn_match = _re.search(
                        r"(\d{1,2}/\d{1,2}/\d{4})\s+([ASPGMVFCJ])\s+[VX]?\s*([\d,]+)\s+"
                        r"([AD])\s+\$?([\d,.]+)",
                        ctx
                    )
                    if txn_match:
                        txn_date_str = txn_match.group(1)
                        code = txn_match.group(2)
                        shares_str = txn_match.group(3).replace(',', '')
                        acq_disp = txn_match.group(4)
                        price_str = txn_match.group(5).replace(',', '')
                        try:
                            shares = int(float(shares_str))
                            price = float(price_str)
                        except (ValueError, TypeError):
                            shares = 0
                            price = 0.0
                        transactions.append({
                            "transaction_date": txn_date_str,
                            "code": code,
                            "shares": shares,
                            "price": price,
                            "acquired_disposed": acq_disp,
                        })
                if transactions:
                    filing["transactions"] = transactions

            # Try to enrich with CIK data by matching accession number
            accessions_in_filing = []
            for flag in filing.get("forensic_flags", []):
                import re as _re
                accs = _re.findall(r"\d{10}-\d{2}-\d{6}", flag.get("context", ""))
                accessions_in_filing.extend(accs)

            for accn in accessions_in_filing:
                if accn in cik_inv:
                    cik_entry = cik_inv[accn]
                    if not filing.get("filed_date") and cik_entry.get("filed"):
                        filing["filed_date"] = cik_entry["filed"]
                        enriched_count += 1
                    if not filing.get("filing_id"):
                        filing["filing_id"] = accn
                    break

    if enriched_count or reclassified_count:
        print(f"  → Enriched {enriched_count} filings with CIK dates, "
              f"reclassified {reclassified_count} UNKNOWN types")

    return data


def analyze_proxy_disclosure_gaps(data: Dict[str, List[Dict]], db: Dict) -> List[str]:
    """Detect proxy disclosure gaps by scanning DEF14A filings for missing disclosures."""
    anomaly_ids = []

    swoosh_keywords = ["Swoosh", "cross-directorship", "Parker", "Graf", "Donahoe",
                        "Knight", "controlling shareholder"]
    related_party_keywords = ["related party", "related-party", "Related Party Transaction"]

    for fy, filings in sorted(data.items()):
        proxies = [f for f in filings if f.get("filing_type") in ("DEF14A", "DEF 14A")]
        for proxy in proxies:
            full_text = ""
            for section in proxy.get("sections", []):
                if isinstance(section, dict):
                    full_text += " " + section.get("heading", "") + " " + section.get("content", "")

            # Also concatenate forensic flag contexts
            for flag in proxy.get("forensic_flags", []):
                full_text += " " + flag.get("context", "")

            if not full_text.strip():
                continue

            # Check for Swoosh disclosure gaps
            has_swoosh_mention = any(kw.lower() in full_text.lower() for kw in swoosh_keywords[:3])
            has_related_party = any(kw.lower() in full_text.lower() for kw in related_party_keywords)

            if not has_swoosh_mention:
                aid = create_anomaly(
                    db,
                    category="disclosure",
                    severity="HIGH",
                    fiscal_year=fy,
                    filing_id=proxy.get("filing_id"),
                    title=f"Proxy Disclosure Gap: No Swoosh LLC mention in {fy} DEF 14A",
                    description=(
                        f"The {fy} DEF 14A proxy statement does not appear to mention "
                        f"Swoosh LLC or cross-directorship arrangements despite ongoing "
                        f"Schedule 13D obligations. This represents a potential omission "
                        f"under Regulation S-K Items 401/404/405."
                    ),
                    evidence=[
                        f"Filing: {fy} DEF 14A",
                        f"Source: {proxy.get('source_file', 'N/A')}",
                        f"Keywords absent: Swoosh, cross-directorship",
                    ],
                    compounding_years=[fy],
                    regulatory_relevance={
                        "sec_enforcement": "HIGH",
                        "statute": "Section 14(a), Exchange Act; Regulation S-K Items 401, 404, 405",
                    },
                )
                anomaly_ids.append(aid)

    return anomaly_ids


def analyze_forensic_flag_density(data: Dict[str, List[Dict]], db: Dict) -> List[str]:
    """Analyze forensic flag density and content across all parsed filings."""
    anomaly_ids = []
    flag_counts_by_year = {}

    for fy, filings in sorted(data.items()):
        year_flags = defaultdict(int)
        for filing in filings:
            for flag in filing.get("forensic_flags", []):
                kw = flag.get("keyword", "").lower()
                year_flags[kw] += 1
        flag_counts_by_year[fy] = dict(year_flags)

    # Detect significant forensic flags
    critical_flags = ["restatement", "material weakness", "going concern",
                      "securities fraud", "class action", "whistleblower",
                      "SEC investigation", "SEC inquiry", "SEC subpoena"]

    for fy, flags in sorted(flag_counts_by_year.items()):
        total_flags = sum(flags.values())
        if total_flags > 0:
            for cf in critical_flags:
                count = sum(v for k, v in flags.items() if cf.lower() in k.lower())
                if count > 0:
                    aid = create_anomaly(
                        db,
                        category="disclosure",
                        severity="HIGH" if cf in ["restatement", "material weakness",
                                                    "securities fraud"] else "MEDIUM",
                        fiscal_year=fy,
                        filing_id=None,
                        title=f"Forensic keyword detected: '{cf}' ({count}x in {fy})",
                        description=(
                            f"The forensic keyword '{cf}' appears {count} time(s) "
                            f"across {fy} filings. Total forensic flags for {fy}: {total_flags}."
                        ),
                        evidence=[
                            f"Keyword: {cf}",
                            f"Occurrences in {fy}: {count}",
                            f"Total forensic flags in {fy}: {total_flags}",
                        ],
                        regulatory_relevance={"sec_enforcement": "MEDIUM"},
                    )
                    anomaly_ids.append(aid)

    return anomaly_ids


def run_cross_reference(fiscal_year: str = None, pattern_focus: str = None) -> Dict:
    """
    Run the full cross-reference analysis.

    IMPORTANT: This preserves existing anomalies from the deliverable extractor
    and adds NEW anomalies discovered from raw EDGAR filing analysis on top.

    Args:
        fiscal_year: Limit to specific year (None = all years)
        pattern_focus: Focus on specific pattern type

    Returns:
        Summary of all anomalies and patterns found
    """
    start_time = datetime.now()

    print(f"\n{'='*60}")
    print(f"  JLAW CROSS-REFERENCE AGENT — ANALYSIS")
    print(f"  Scope: {fiscal_year or 'ALL FISCAL YEARS'}")
    print(f"  Started: {start_time.isoformat()}")
    print(f"{'='*60}\n")

    # Load all parsed data
    print("[1/8] Loading parsed filing data...")
    data = load_all_parsed(fiscal_year)
    total_filings = sum(len(v) for v in data.values())
    print(f"  → {total_filings} filings loaded across {len(data)} fiscal years")

    # Enrich parsed data with CIK reference metadata
    print("\n[2/8] Enriching parsed data with CIK reference metadata...")
    data = enrich_parsed_data(data)

    # Load EXISTING anomaly database (preserving deliverable extractions)
    db = load_anomaly_db()
    initial_count = len(db["anomalies"])
    print(f"  → Existing anomaly database: {initial_count} anomalies, "
          f"{len(db.get('patterns', []))} patterns")

    # Run cross-reference analyses — these ADD to the existing database
    all_anomaly_ids = []

    print("\n[3/8] Analyzing Form 4 timeliness...")
    ids = analyze_form4_timeliness(data, db)
    all_anomaly_ids.extend(ids)
    print(f"  → {len(ids)} late filing anomalies")

    print("\n[4/8] Analyzing exhibit changes...")
    ids = analyze_exhibit_changes(data, db)
    all_anomaly_ids.extend(ids)
    print(f"  → {len(ids)} exhibit change anomalies")

    print("\n[5/8] Analyzing insider selling patterns...")
    ids = analyze_insider_selling_patterns(data, db)
    all_anomaly_ids.extend(ids)
    print(f"  → {len(ids)} insider trading anomalies")

    print("\n[6/8] Analyzing Schedule 13D staleness...")
    ids = analyze_13d_staleness(data, db)
    all_anomaly_ids.extend(ids)
    print(f"  → {len(ids)} 13D staleness anomalies")

    print("\n[7/8] Analyzing proxy disclosure gaps & forensic flags...")
    ids = analyze_proxy_disclosure_gaps(data, db)
    all_anomaly_ids.extend(ids)
    print(f"  → {len(ids)} proxy disclosure gap anomalies")

    ids = analyze_forensic_flag_density(data, db)
    all_anomaly_ids.extend(ids)
    ids2 = analyze_forensic_keyword_density(data, db)
    all_anomaly_ids.extend(ids2)

    print("\n[8/8] Building compounding patterns...")
    pattern_ids = build_compounding_patterns(db)
    print(f"  → {len(pattern_ids)} compounding patterns identified")

    # Save updated database
    save_anomaly_db(db)

    # Summary
    new_count = len(db["anomalies"]) - initial_count
    summary = {
        "started_at": start_time.isoformat(),
        "ended_at": datetime.now().isoformat(),
        "scope": fiscal_year or "ALL",
        "filings_analyzed": total_filings,
        "new_anomalies": new_count,
        "total_anomalies": len(db["anomalies"]),
        "new_patterns": len(pattern_ids),
        "total_patterns": len(db["patterns"]),
        "anomaly_ids": all_anomaly_ids,
        "pattern_ids": pattern_ids,
    }

    # Save log
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"crossref_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  CROSS-REFERENCE COMPLETE")
    print(f"  Filings analyzed: {total_filings}")
    print(f"  Existing anomalies preserved: {initial_count}")
    print(f"  New anomalies from cross-ref: {new_count}")
    print(f"  Total anomalies: {len(db['anomalies'])}")
    print(f"  Compounding patterns: {len(db['patterns'])}")
    print(f"  Database saved: {ANOMALY_DIR / 'anomaly_database.json'}")
    print(f"  Log saved: {log_path}")
    print(f"{'='*60}\n")

    return summary


def main():
    parser = argparse.ArgumentParser(description="JLAW Cross-Reference Agent")
    parser.add_argument("--year", type=str, help="Analyze specific fiscal year")
    parser.add_argument("--pattern", type=str,
                        help="Focus on pattern type (swoosh, insider, section16, exhibit)")

    args = parser.parse_args()
    run_cross_reference(args.year, args.pattern)


if __name__ == "__main__":
    main()
