"""
JLAW Deliverable Extractor Agent
═══════════════════════════════════════════════════════════════════════
Extracts forensic anomalies from the 24 parsed deliverable DOCX files
into the anomaly database.  This bridges the investigative trio bundles
(Timelines, SEC Bundles, ISS Memos) into machine-readable anomaly records.

Usage:
    python -m src.agents.deliverable_extractor
"""

import json
import re
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
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

# ═══════════════════════════════════════════════
# SEVERITY / CATEGORY CLASSIFICATION
# ═══════════════════════════════════════════════

STRUCTURAL_KEYWORDS = re.compile(
    r"(?:systemic|structural|governance\s*failure|dual-class|controlling\s*shareholder|"
    r"14-year\s*gap|chronic\s*staleness|self-?approv|loophole)", re.I)

HIGH_KEYWORDS = re.compile(
    r"(?:material|violation|delinquen|late\s*fil|fraud|misstatement|"
    r"omission|non-?disclos|prohibited|breach|scheme|scienter|"
    r"securities\s*fraud|obstruct|insider\s*trading|10b-?5|manipulat)", re.I)

MEDIUM_KEYWORDS = re.compile(
    r"(?:discrepanc|inconsisten|irregular|overdue|"
    r"divergen|deviation|anomal|spike|unusual|understat|overstat)", re.I)

CATEGORY_PATTERNS = {
    "swoosh_13d": re.compile(r"(?:Swoosh|13[DG]|Schedule\s*13|beneficial\s*own.*Swoosh|Knight\s*family)", re.I),
    "section_16": re.compile(r"(?:Section\s*16|Form\s*4|Form\s*5|Rule\s*16a|late\s*fil.*Form)", re.I),
    "insider_trading": re.compile(r"(?:insider\s*(?:trad|sell|buy)|10b5-1|pre-?clear|blackout|MNPI|Parker.*sell|sell.*Parker)", re.I),
    "governance": re.compile(r"(?:governance|board\s*independen|audit\s*committee|proxy|DEF\s*14A|director\s*bio|cross-director)", re.I),
    "disclosure": re.compile(r"(?:disclosure|proxy\s*(?:omission|gap)|Reg\s*S-K|Item\s*(?:401|404|405)|misstat)", re.I),
    "regulatory": re.compile(r"(?:CORRESP|SEC\s*(?:enforce|investigat|correspondence)|regulatory\s*gap|14-year)", re.I),
    "compensation": re.compile(r"(?:compensation|say-on-pay|executive\s*pay|stock\s*option|equity\s*award)", re.I),
    "securities_fraud": re.compile(r"(?:securities\s*fraud|10b-?5|scheme\s*to\s*defraud|class\s*action|scienter)", re.I),
}

ACCESSION_RE = re.compile(r"\d{10}-\d{2}-\d{6}")
MONEY_RE = re.compile(r"\$[\d,]+(?:\.\d{1,2})?\s*(?:million|billion|thousand|M|B|K)?", re.I)
DATE_RE = re.compile(
    r"\b(?:(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{1,2},?\s+\d{4}|"
    r"\d{4}-\d{2}-\d{2})\b")

STATUTE_PATTERNS = {
    "Section 13(d), Securities Exchange Act of 1934; Rule 13d-2": re.compile(r"13[dD]|Schedule\s*13", re.I),
    "Section 16(a), Exchange Act of 1934; Rule 16a-3(g)": re.compile(r"Section\s*16|Rule\s*16a|Form\s*[45].*late", re.I),
    "Section 10(b), Exchange Act; Rule 10b-5": re.compile(r"10b-?5|insider\s*trad|securities\s*fraud|MNPI", re.I),
    "Regulation S-K Items 401, 404, 405": re.compile(r"Reg\s*S-K|Item\s*(?:401|404|405)|proxy\s*disclos", re.I),
    "Section 14(a), Exchange Act": re.compile(r"Section\s*14|proxy\s*(?:statement|mislead|omission)", re.I),
    "Regulation S-K Item 601": re.compile(r"Exhibit\s*(?:19|21)|Item\s*601", re.I),
    "NYSE Listed Company Manual §303A": re.compile(r"NYSE|board\s*independen|governance\s*standard", re.I),
}


def classify_severity(text: str) -> str:
    if STRUCTURAL_KEYWORDS.search(text):
        return "STRUCTURAL"
    if HIGH_KEYWORDS.search(text):
        return "HIGH"
    if MEDIUM_KEYWORDS.search(text):
        return "MEDIUM"
    return "LOW"


def classify_category(text: str) -> str:
    for cat, pat in CATEGORY_PATTERNS.items():
        if pat.search(text):
            return cat
    return "disclosure"


def identify_statute(text: str) -> Dict:
    for statute, pat in STATUTE_PATTERNS.items():
        if pat.search(text):
            return {"statute": statute, "sec_enforcement": "HIGH"}
    return {"statute": "Securities Exchange Act of 1934", "sec_enforcement": "MEDIUM"}


def deduplicate_key(title: str, description: str, fiscal_year: str) -> str:
    norm_t = re.sub(r'\s+', ' ', title.lower().strip())[:100]
    norm_d = re.sub(r'\s+', ' ', description.lower().strip())[:100]
    return f"{fiscal_year}|{norm_t}|{norm_d}"


# ═══════════════════════════════════════════════
# EXTRACTION FUNCTIONS
# ═══════════════════════════════════════════════

def extract_from_section(section: Dict, doc_info: Dict) -> List[Dict]:
    heading = section.get("heading", "")
    content = section.get("content_excerpt", "") or ""
    full_text = f"{heading}\n{content}"
    if not full_text.strip() or len(full_text) < 30:
        return []

    has_signal = bool(re.search(
        r"(?:anomal|finding|violation|discrepan|evidence|analysis|"
        r"timeline|pattern|compliance|disclosure|gap|deficien|"
        r"delinquen|stale|omission|late|irregular|"
        r"section\s*16|13[dD]|10b|insider|swoosh|parker|knight|"
        r"graf|donahoe|friend|sprunk|nielsen)", full_text, re.I))
    if not has_signal:
        return []

    accessions = list(set(ACCESSION_RE.findall(full_text)))
    fy = doc_info.get("fiscal_year", "UNKNOWN")

    chunks = re.split(r'\n(?=(?:[\d]+[.)]\s|[•●◦▪-]\s|Evidence|Finding|Anomaly|Violation|Gap|Pattern))',
                       content, flags=re.I)
    if not chunks or (len(chunks) == 1 and len(chunks[0]) > 2000):
        chunks = [c.strip() for c in content.split('\n\n') if c.strip()]
    if not chunks:
        chunks = [content]

    anomalies = []
    for chunk in chunks:
        chunk = chunk.strip()
        if len(chunk) < 20:
            continue
        combined = f"{heading}: {chunk}"
        severity = classify_severity(combined)
        category = classify_category(combined)

        chunk_acc = list(set(ACCESSION_RE.findall(chunk)))
        chunk_amt = list(set(MONEY_RE.findall(chunk)))
        chunk_dates = list(set(DATE_RE.findall(chunk)))

        evidence = [f"Source: {doc_info.get('filename', 'Unknown')}",
                     f"Section: {heading}"]
        if chunk_acc:
            evidence.append(f"Accession numbers: {', '.join(chunk_acc[:5])}")

        title_text = chunk[:120].replace('\n', ' ').strip()
        if heading and heading != "(Document Body)":
            title = f"{heading}: {title_text}"[:200]
        else:
            title = title_text[:200]

        anomalies.append({
            "category": category, "severity": severity, "fiscal_year": fy,
            "filing_id": chunk_acc[0] if chunk_acc else None,
            "title": title, "description": chunk[:500],
            "evidence": evidence,
            "accession_numbers": chunk_acc or accessions[:3],
            "dollar_amounts": chunk_amt, "dates_referenced": chunk_dates,
            "source_document": doc_info.get("filename", ""),
            "source_type": doc_info.get("deliverable_type", ""),
            "compounding_years": [fy] if fy != "UNKNOWN" else ["UNKNOWN"],
            "regulatory_relevance": identify_statute(combined),
        })
    return anomalies


def extract_from_tables(tables: List[Dict], doc_info: Dict) -> List[Dict]:
    anomalies = []
    fy = doc_info.get("fiscal_year", "UNKNOWN")
    for table in tables:
        headers = [h.lower() for h in table.get("headers", [])]
        rows = table.get("rows", [])
        is_evidence = any(kw in ' '.join(headers) for kw in
                          ['filing', 'accession', 'evidence', 'finding',
                           'date', 'violation', 'anomaly', 'type'])
        if not is_evidence or not rows:
            continue
        for row in rows:
            row_text = ' '.join(str(c) for c in row if c)
            if len(row_text) < 15:
                continue
            accessions = list(set(ACCESSION_RE.findall(row_text)))
            severity = classify_severity(row_text)
            category = classify_category(row_text)
            title_parts = [str(c)[:60] for c in row if c and len(str(c)) > 5]
            title = ' — '.join(title_parts[:3])[:200]
            anomalies.append({
                "category": category, "severity": severity, "fiscal_year": fy,
                "filing_id": accessions[0] if accessions else None,
                "title": f"Evidence: {title}",
                "description": row_text[:500],
                "evidence": [f"Evidence Index Row: {row_text[:300]}"],
                "accession_numbers": accessions,
                "dollar_amounts": list(set(MONEY_RE.findall(row_text))),
                "dates_referenced": list(set(DATE_RE.findall(row_text))),
                "source_document": doc_info.get("filename", ""),
                "source_type": doc_info.get("deliverable_type", ""),
                "compounding_years": [fy] if fy != "UNKNOWN" else ["UNKNOWN"],
                "regulatory_relevance": identify_statute(row_text),
            })
    return anomalies


def extract_from_anomaly_mentions(mentions: List[Dict], doc_info: Dict) -> List[Dict]:
    anomalies = []
    fy = doc_info.get("fiscal_year", "UNKNOWN")
    for mention in mentions:
        context = mention.get("context", "")
        keyword = mention.get("keyword", "")
        if len(context) < 20:
            continue
        severity = classify_severity(context)
        category = classify_category(context)
        evidence = [f"Source: {doc_info.get('filename', '')}", f"Keyword: {keyword}"]
        if mention.get("accession_numbers"):
            evidence.append(f"Accession: {', '.join(mention['accession_numbers'][:3])}")
            acc_nums = mention.get("accession_numbers", [])
            anomalies.append({
            "category": category, "severity": severity, "fiscal_year": fy,
            "filing_id": acc_nums[0] if acc_nums else None,
            "title": f"{keyword}: {context[:120]}",
            "description": context[:500],
            "evidence": evidence,
            "accession_numbers": mention.get("accession_numbers", []),
            "dollar_amounts": mention.get("monetary_amounts", []),
            "dates_referenced": mention.get("dates", []),
            "source_document": doc_info.get("filename", ""),
            "source_type": doc_info.get("deliverable_type", ""),
            "compounding_years": [fy] if fy != "UNKNOWN" else ["UNKNOWN"],
            "regulatory_relevance": identify_statute(context),
        })
    return anomalies


# ═══════════════════════════════════════════════
# COMPOUNDING PATTERNS
# ═══════════════════════════════════════════════

def build_patterns(anomalies: List[Dict]) -> List[Dict]:
    patterns = []
    by_category = defaultdict(list)
    for a in anomalies:
        by_category[a["category"]].append(a)

    configs = [
        ("Swoosh LLC Schedule 13D Chronic Staleness & Disclosure Opacity", "swoosh_13d",
         "Multi-year Schedule 13D amendment delinquency by Swoosh LLC. "
         "Cross-directorship arrangements undisclosed in proxy statements.", 1),
        ("Recurring Section 16(a) Late Filing Violations", "section_16",
         "Pattern of Form 4/5 filing delinquencies across multiple insiders and fiscal years.", 2),
        ("Concentrated Insider Selling — Executive Sell-Side Bias", "insider_trading",
         "Multi-year concentration of insider selling by senior executives, "
         "including pre-clearance self-approval and trading during sensitive periods.", 1),
        ("Proxy Statement Disclosure Gaps — Governance Opacity", "disclosure",
         "Systematic omission of material cross-directorship relationships and "
         "related-party transactions from proxy statements.", 2),
        ("Governance Independence Failures & Board Oversight Deficiencies", "governance",
         "Cross-directorship conflicts undermining board independence determinations.", 1),
        ("SEC Regulatory Correspondence Gap — 14-Year Oversight Failure", "regulatory",
         "14-year gap in SEC CORRESP filings (approx 2010-2024).", 1),
        ("Securities Fraud Pattern — Systematic Misrepresentation", "securities_fraud",
         "Pattern of securities fraud indicators including proxy misstatements.", 1),
        ("Executive Compensation Opacity & Self-Dealing Indicators", "compensation",
         "Compensation structures creating conflicts of interest.", 1),
    ]

    for title, category, description, min_count in configs:
        cat_anomalies = by_category.get(category, [])
        if len(cat_anomalies) >= min_count:
            pid = f"PAT-{str(len(patterns) + 1).zfill(3)}"
            aids = [a["anomaly_id"] for a in cat_anomalies if "anomaly_id" in a]
            years = sorted(set(yr for a in cat_anomalies for yr in a.get("compounding_years", [])))
            patterns.append({
                "pattern_id": pid, "title": title,
                "anomaly_ids": aids, "description": description,
                "created_at": datetime.now().isoformat(),
                "years_spanned": years, "anomaly_count": len(cat_anomalies),
            })
            for a in cat_anomalies:
                a.setdefault("linked_patterns", []).append(pid)

    return patterns


# ═══════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════

def run_deliverable_extraction() -> Dict:
    """Run the full deliverable extraction pipeline."""
    start_time = datetime.now()
    print(f"\n{'='*60}")
    print(f"  JLAW DELIVERABLE EXTRACTOR — ANOMALY EXTRACTION")
    print(f"  Started: {start_time.isoformat()}")
    print(f"{'='*60}\n")

    deliverables_dir = PARSED_DIR / "deliverables"
    if not deliverables_dir.exists():
        print("  ✗ No parsed deliverables found. Run ingest first.")
        return {"error": "no_deliverables"}

    parsed_files = sorted(deliverables_dir.glob("*_parsed.json"))
    print(f"[1/5] Found {len(parsed_files)} parsed deliverables")

    raw_anomalies = []
    docs_processed = 0
    for pf in parsed_files:
        try:
            with open(pf) as f:
                doc_data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ✗ Cannot read {pf.name}: {e}")
            continue

        doc_info = {
            "filename": doc_data.get("filename", pf.stem),
            "fiscal_year": doc_data.get("fiscal_year", "UNKNOWN"),
            "deliverable_type": doc_data.get("deliverable_type", "unknown"),
            "corpus_type": doc_data.get("corpus_type", "unknown"),
        }

        for section in doc_data.get("sections", []):
            raw_anomalies.extend(extract_from_section(section, doc_info))
        raw_anomalies.extend(extract_from_tables(doc_data.get("tables", []), doc_info))
        raw_anomalies.extend(extract_from_anomaly_mentions(
            doc_data.get("anomaly_mentions", []), doc_info))
        docs_processed += 1

    print(f"[2/5] Extracted {len(raw_anomalies)} raw anomalies from {docs_processed} deliverables")

    # Deduplicate
    seen: Set[str] = set()
    unique = []
    for a in raw_anomalies:
        key = deduplicate_key(a.get("title", ""), a.get("description", ""),
                              a.get("fiscal_year", ""))
        if key not in seen:
            seen.add(key)
            unique.append(a)

    print(f"[3/5] Deduplicated: {len(raw_anomalies)} → {len(unique)} unique anomalies")

    # Assign IDs
    for i, a in enumerate(unique):
        fy_num = a.get("fiscal_year", "UNKNOWN").replace("FY", "").replace("Q1-CY", "")
        a["anomaly_id"] = f"ANO-{fy_num}-{str(i + 1).zfill(3)}"
        a["created_at"] = datetime.now().isoformat()
        a.setdefault("linked_patterns", [])

    print(f"[4/5] Building compounding patterns...")
    patterns = build_patterns(unique)
    print(f"  → {len(patterns)} compounding patterns identified")

    severity_counts = defaultdict(int)
    category_counts = defaultdict(int)
    fy_counts = defaultdict(int)
    for a in unique:
        severity_counts[a.get("severity", "LOW")] += 1
        category_counts[a.get("category", "unknown")] += 1
        fy_counts[a.get("fiscal_year", "UNKNOWN")] += 1

    print(f"[5/5] Saving anomaly database...")
    ANOMALY_DIR.mkdir(parents=True, exist_ok=True)
    db = {
        "anomalies": unique, "patterns": patterns,
        "last_updated": datetime.now().isoformat(),
        "extraction_source": "deliverable_extractor",
    }
    with open(ANOMALY_DIR / "anomaly_database.json", "w") as f:
        json.dump(db, f, indent=2, default=str)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_data = {
        "started_at": start_time.isoformat(),
        "ended_at": datetime.now().isoformat(),
        "deliverables_processed": docs_processed,
        "raw_extractions": len(raw_anomalies),
        "unique_anomalies": len(unique),
        "database_anomalies": len(unique),
        "compounding_patterns": len(patterns),
        "severity_breakdown": dict(severity_counts),
        "category_breakdown": dict(category_counts),
        "fiscal_year_breakdown": dict(sorted(fy_counts.items())),
    }
    log_path = LOG_DIR / f"extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_path, "w") as f:
        json.dump(log_data, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  EXTRACTION COMPLETE")
    print(f"  Deliverables processed: {docs_processed}")
    print(f"  Unique anomalies: {len(unique)}")
    print(f"  Compounding patterns: {len(patterns)}")
    print(f"  Severity: {dict(severity_counts)}")
    print(f"  Categories: {dict(category_counts)}")
    print(f"  Database: {ANOMALY_DIR / 'anomaly_database.json'}")
    print(f"  Log: {log_path}")
    print(f"{'='*60}\n")

    return log_data


if __name__ == "__main__":
    run_deliverable_extraction()
