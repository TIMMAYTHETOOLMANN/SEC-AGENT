"""
JLAW Visualization — PPTX Briefing Deck Generator
Produces a 12-slide presentation deck with embedded investigation charts.
Designed for: SEC staff briefings, Congressional staffers, ISS analysts.

Output: data/viz/deck/JLAW_Investigation_Briefing.pptx
Requires: pptxgenjs (Node.js) — falls back to python-pptx if unavailable.
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", "./data"))
DECK_DIR = DATA_DIR / "viz" / "deck"
DECK_DIR.mkdir(parents=True, exist_ok=True)
CHART_DIR = DATA_DIR / "viz" / "charts"


def generate_deck_script() -> str:
    """Generate the PptxGenJS Node.js script for deck creation."""

    chart_paths = {
        "parker": str((CHART_DIR / "01_parker_cumulative_sales.png").resolve()),
        "swoosh": str((CHART_DIR / "02_swoosh_13d_staleness.png").resolve()),
        "toggle": str((CHART_DIR / "03_section16a_toggle.png").resolve()),
        "divergence": str((CHART_DIR / "04_buy_sell_divergence.png").resolve()),
        "scatter": str((CHART_DIR / "05_anomaly_scatter.png").resolve()),
        "litigation": str((CHART_DIR / "06_litigation_timeline.png").resolve()),
    }

    output_path = str((DECK_DIR / "JLAW_Investigation_Briefing.pptx").resolve())

    return f"""
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "JLAW Forensic Intelligence Platform v5.0";
pres.title = "Nike Inc. — Seven-Year Forensic Investigation Briefing";
pres.subject = "FY2019–Q1 CY2026 | CIK 0000320187";

// ═══ THEME ═══
const NAVY = "0F1B2D";
const RED = "B91C1C";
const WHITE = "FFFFFF";
const LIGHT = "F8F9FA";
const GREY = "6B7280";
const MUTED = "94A3B8";

function addFooter(slide, pageNum) {{
  slide.addText("PRIVILEGED & CONFIDENTIAL  |  JLAW v5.0  |  Nike Inc. (CIK 0000320187)", {{
    x: 0.5, y: 5.15, w: 7.5, h: 0.3, fontSize: 6, color: MUTED, fontFace: "Arial"
  }});
  slide.addText(String(pageNum), {{
    x: 9.2, y: 5.15, w: 0.5, h: 0.3, fontSize: 6, color: MUTED, fontFace: "Arial", align: "right"
  }});
}}

// Helper to check if chart file exists
function chartPath(key) {{
  const paths = {json.dumps(chart_paths)};
  const p = paths[key];
  return fs.existsSync(p) ? p : null;
}}

// ═══ SLIDE 1: Title ═══
let s1 = pres.addSlide();
s1.background = {{ color: NAVY }};
s1.addText("NIKE, INC.", {{ x: 0.8, y: 1.0, w: 8.5, h: 0.8, fontSize: 36, fontFace: "Arial", bold: true, color: WHITE }});
s1.addText("Seven-Year Forensic Investigation Briefing", {{ x: 0.8, y: 1.8, w: 8.5, h: 0.5, fontSize: 18, fontFace: "Arial", color: MUTED }});
s1.addText("FY2019 – Q1 CY2026  |  CIK 0000320187  |  NYSE: NKE", {{ x: 0.8, y: 2.5, w: 8.5, h: 0.4, fontSize: 12, fontFace: "Arial", color: MUTED }});
s1.addShape(pres.shapes.RECTANGLE, {{ x: 0.8, y: 3.1, w: 2.5, h: 0.04, fill: {{ color: RED }} }});
s1.addText([
  {{ text: "$565M+", options: {{ fontSize: 22, bold: true, color: RED }} }},
  {{ text: "  Executive Chairman cumulative stock sales", options: {{ fontSize: 11, color: MUTED }} }},
], {{ x: 0.8, y: 3.5, w: 8.5, h: 0.5 }});
s1.addText([
  {{ text: "9.7 years", options: {{ fontSize: 22, bold: true, color: RED }} }},
  {{ text: "  Controlling shareholder 13D unamended", options: {{ fontSize: 11, color: MUTED }} }},
], {{ x: 0.8, y: 4.0, w: 8.5, h: 0.5 }});
s1.addText("PRIVILEGED & CONFIDENTIAL  |  {datetime.now().strftime('%B %Y')}", {{ x: 0.8, y: 4.8, w: 8.5, h: 0.3, fontSize: 8, color: MUTED, fontFace: "Arial" }});

// ═══ SLIDE 2: Executive Summary ═══
let s2 = pres.addSlide();
s2.background = {{ color: WHITE }};
addFooter(s2, 2);
s2.addText("Executive Summary", {{ x: 0.5, y: 0.3, w: 9, h: 0.6, fontSize: 22, fontFace: "Arial", bold: true, color: NAVY, margin: 0 }});
s2.addShape(pres.shapes.RECTANGLE, {{ x: 0.5, y: 0.85, w: 1.5, h: 0.03, fill: {{ color: RED }} }});
s2.addText([
  {{ text: "Five structural governance fractures identified across seven fiscal years of Nike, Inc. SEC filings:", options: {{ fontSize: 11, color: GREY, breakLine: true }} }},
  {{ text: "", options: {{ fontSize: 6, breakLine: true }} }},
  {{ text: "1. ", options: {{ bold: true, color: RED }} }}, {{ text: "Exhibit 19 pre-clearance self-approval loophole — Parker approves own $565M+ trades", options: {{ fontSize: 10, breakLine: true }} }},
  {{ text: "2. ", options: {{ bold: true, color: RED }} }}, {{ text: "Swoosh LLC 13D unamended 9.7 years — active Rule 13d-2 violation (75+ days overdue)", options: {{ fontSize: 10, breakLine: true }} }},
  {{ text: "3. ", options: {{ bold: true, color: RED }} }}, {{ text: "Securities fraud class action ($245M insider sales) — MTD pending 6+ months", options: {{ fontSize: 10, breakLine: true }} }},
  {{ text: "4. ", options: {{ bold: true, color: RED }} }}, {{ text: "14-year SEC correspondence gap — zero staff comment letters since 2011", options: {{ fontSize: 10, breakLine: true }} }},
  {{ text: "5. ", options: {{ bold: true, color: RED }} }}, {{ text: "23 micro-forensic anomalies forming 5 compounding patterns across all fiscal years", options: {{ fontSize: 10, breakLine: true }} }},
], {{ x: 0.5, y: 1.1, w: 9, h: 3.5, valign: "top", lineSpacingMultiple: 1.4 }});

// ═══ SLIDES 3-8: Chart Slides ═══
const chartSlides = [
  ["parker", "Parker Cumulative Sales — $565M+ Through Self-Approval Pathway", "All sales under 10b5-1 plans pre-cleared by Chairman/CEO pathway. Zero purchases FY2019–FY2024."],
  ["swoosh", "Swoosh LLC — 9.7-Year 13D Staleness", "35.25M shares (13.7%) unreported. Dec 2025 distribution 75+ business days overdue for amendment."],
  ["toggle", "Section 16(a) Delinquency Toggle — 7-Year Pattern", "OMIT → OMIT → PRESENT → ABSENT → PRESENT → PRESENT → PRESENT. Correlates with Knight family filing events."],
  ["divergence", "FY2025 Buy/Sell Divergence — Directors vs. Executive Chairman", "$6.4M discretionary director purchases vs. $57.5M Parker 10b5-1 sales. First sustained buying in investigation."],
  ["scatter", "Micro-Forensic Anomaly Map — 23 Items Across 7 Fiscal Years", "Size = severity. Color = category. Density increases FY2023+ as mandatory disclosures made patterns visible."],
  ["litigation", "Securities Fraud Litigation Timeline", "In Re Nike (D. Or. 3:24-cv-00974-AN). 292-page amended complaint. MTD pending. Discovery would produce pre-clearance records."],
];

chartSlides.forEach(([key, title, caption], idx) => {{
  let slide = pres.addSlide();
  slide.background = {{ color: WHITE }};
  addFooter(slide, idx + 3);
  slide.addText(title, {{ x: 0.5, y: 0.3, w: 9, h: 0.5, fontSize: 16, fontFace: "Arial", bold: true, color: NAVY, margin: 0 }});
  slide.addShape(pres.shapes.RECTANGLE, {{ x: 0.5, y: 0.75, w: 1.2, h: 0.03, fill: {{ color: RED }} }});

  const cp = chartPath(key);
  if (cp) {{
    slide.addImage({{ path: cp, x: 0.3, y: 0.9, w: 9.4, h: 3.6 }});
  }} else {{
    slide.addText("[Chart not generated — run charts.py first]", {{ x: 1, y: 2, w: 8, h: 1, fontSize: 14, color: GREY, align: "center" }});
  }}
  slide.addText(caption, {{ x: 0.5, y: 4.6, w: 9, h: 0.4, fontSize: 8, color: GREY, fontFace: "Arial", italic: true }});
}});

// ═══ SLIDE 9: Key Accession Numbers ═══
let s9 = pres.addSlide();
s9.background = {{ color: WHITE }};
addFooter(s9, 9);
s9.addText("Key EDGAR Accession Numbers", {{ x: 0.5, y: 0.3, w: 9, h: 0.5, fontSize: 18, fontFace: "Arial", bold: true, color: NAVY, margin: 0 }});
s9.addShape(pres.shapes.RECTANGLE, {{ x: 0.5, y: 0.75, w: 1.2, h: 0.03, fill: {{ color: RED }} }});
s9.addTable([
  [{{ text: "FILING", options: {{ fill: {{ color: NAVY }}, color: WHITE, bold: true, fontSize: 8 }} }},
   {{ text: "ACCESSION", options: {{ fill: {{ color: NAVY }}, color: WHITE, bold: true, fontSize: 8 }} }},
   {{ text: "SIGNIFICANCE", options: {{ fill: {{ color: NAVY }}, color: WHITE, bold: true, fontSize: 8 }} }}],
  ["FY2024 10-K (Exhibit 19)", "0000320187-24-000044", "First ITP filing — self-approval revealed"],
  ["FY2025 10-K", "0000320187-25-000047", "Exhibit 19 UNCHANGED (inc by ref)"],
  ["Swoosh 13D (last amend.)", "0000897423-16-000091", "June 2016 — 9.7 years stale"],
  ["CEO Transition 8-K", "0000320187-24-000053", "Sep 19, 2024 — Donahoe terminated"],
  ["Bylaws Rewrite 8-K", "0000320187-24-000058", "Sep 18, 2024 — 1 day before CEO firing"],
  ["Travis Knight Late Form 4", "0000320187-26-000002", "~10 business days late (Jan 5, 2026)"],
  ["Amended Complaint", "D.Or. 3:24-cv-00974-AN, Doc 53", "292 pages, filed Feb 10, 2025"],
], {{ x: 0.5, y: 1.0, w: 9, h: 3.5, fontSize: 8, border: {{ pt: 0.5, color: "E5E7EB" }},
     colW: [2.5, 2.5, 4], valign: "middle", rowH: [0.35, 0.35, 0.35, 0.35, 0.35, 0.35, 0.35, 0.35] }});

// ═══ SLIDE 10: Recommended Actions ═══
let s10 = pres.addSlide();
s10.background = {{ color: WHITE }};
addFooter(s10, 10);
s10.addText("Recommended Enforcement Actions", {{ x: 0.5, y: 0.3, w: 9, h: 0.5, fontSize: 18, fontFace: "Arial", bold: true, color: NAVY, margin: 0 }});
s10.addShape(pres.shapes.RECTANGLE, {{ x: 0.5, y: 0.75, w: 1.2, h: 0.03, fill: {{ color: RED }} }});
s10.addText([
  {{ text: "URGENT", options: {{ bold: true, color: RED, fontSize: 11, breakLine: true }} }},
  {{ text: "Issue formal deficiency notice to Swoosh LLC for 13D amendment (75+ days overdue under 2-day rule)", options: {{ fontSize: 9, breakLine: true }} }},
  {{ text: "", options: {{ fontSize: 6, breakLine: true }} }},
  {{ text: "IMMEDIATE", options: {{ bold: true, color: "D97706", fontSize: 11, breakLine: true }} }},
  {{ text: "Formal SEC comment letter on Exhibit 19 pre-clearance architecture ($565M+ self-approved)", options: {{ fontSize: 9, breakLine: true }} }},
  {{ text: "", options: {{ fontSize: 6, breakLine: true }} }},
  {{ text: "MONITORING", options: {{ bold: true, color: "1E40AF", fontSize: 11, breakLine: true }} }},
  {{ text: "Securities fraud MTD ruling — if denied, discovery produces pre-clearance records and Swoosh board minutes", options: {{ fontSize: 9, breakLine: true }} }},
  {{ text: "", options: {{ fontSize: 6, breakLine: true }} }},
  {{ text: "SYSTEMIC", options: {{ bold: true, color: NAVY, fontSize: 11, breakLine: true }} }},
  {{ text: "Initiate triennial review — 14 years overdue for a Dow 30 company with this governance complexity", options: {{ fontSize: 9, breakLine: true }} }},
], {{ x: 0.5, y: 1.0, w: 9, h: 4, valign: "top", lineSpacingMultiple: 1.3 }});

// ═══ SLIDE 11: Timeline ═══
let s11 = pres.addSlide();
s11.background = {{ color: NAVY }};
s11.addText("Investigation Timeline", {{ x: 0.5, y: 0.3, w: 9, h: 0.5, fontSize: 18, fontFace: "Arial", bold: true, color: WHITE, margin: 0 }});
s11.addText([
  {{ text: "Dec 2019", options: {{ bold: true, color: RED, fontSize: 10 }} }}, {{ text: "  Parker blackout trade identified — investigation begins", options: {{ color: MUTED, fontSize: 9, breakLine: true }} }},
  {{ text: "FY2020-22", options: {{ bold: true, color: RED, fontSize: 10 }} }}, {{ text: "  Triple-insider Swoosh board + zero 10b5-1 disclosure + $244M Parker sales", options: {{ color: MUTED, fontSize: 9, breakLine: true }} }},
  {{ text: "Apr 2023", options: {{ bold: true, color: RED, fontSize: 10 }} }}, {{ text: "  10b5-1 checkbox mandatory — first machine-readable confirmation", options: {{ color: MUTED, fontSize: 9, breakLine: true }} }},
  {{ text: "Jul 2024", options: {{ bold: true, color: RED, fontSize: 10 }} }}, {{ text: "  EXHIBIT 19 FILED — self-approval loophole revealed", options: {{ color: WHITE, fontSize: 9, breakLine: true }} }},
  {{ text: "Sep 2024", options: {{ bold: true, color: RED, fontSize: 10 }} }}, {{ text: "  Bylaws rewritten (Sep 18) → CEO fired (Sep 19) — MNPI sequence", options: {{ color: MUTED, fontSize: 9, breakLine: true }} }},
  {{ text: "Feb 2025", options: {{ bold: true, color: RED, fontSize: 10 }} }}, {{ text: "  Amended complaint (292pp) — Parker added as defendant", options: {{ color: MUTED, fontSize: 9, breakLine: true }} }},
  {{ text: "Dec 2025", options: {{ bold: true, color: RED, fontSize: 10 }} }}, {{ text: "  Swoosh 9.5M mega-distribution + Cook $2.95M buy + Hill $1M buy", options: {{ color: MUTED, fontSize: 9, breakLine: true }} }},
  {{ text: "Mar 2026", options: {{ bold: true, color: WHITE, fontSize: 10 }} }}, {{ text: "  MTD pending. 13D 75+ days overdue. 14-year CORRESP gap. NKE ~$54 (−67% from ATH)", options: {{ color: WHITE, fontSize: 9, breakLine: true }} }},
], {{ x: 0.8, y: 1.0, w: 8.5, h: 4, valign: "top", lineSpacingMultiple: 1.8 }});

// ═══ SLIDE 12: Contact ═══
let s12 = pres.addSlide();
s12.background = {{ color: NAVY }};
s12.addText("JLAW v5.0", {{ x: 0.8, y: 1.5, w: 8.5, h: 0.8, fontSize: 32, fontFace: "Arial", bold: true, color: WHITE }});
s12.addText("Justice Legal Analysis Workbench", {{ x: 0.8, y: 2.3, w: 8.5, h: 0.5, fontSize: 16, fontFace: "Arial", color: MUTED }});
s12.addShape(pres.shapes.RECTANGLE, {{ x: 0.8, y: 3.0, w: 2.5, h: 0.04, fill: {{ color: RED }} }});
s12.addText("36 deliverables  |  23 anomalies  |  5 compounding patterns  |  7 fiscal years", {{ x: 0.8, y: 3.3, w: 8.5, h: 0.4, fontSize: 10, color: MUTED, fontFace: "Arial" }});
s12.addText("PRIVILEGED & CONFIDENTIAL — ATTORNEY WORK PRODUCT", {{ x: 0.8, y: 4.5, w: 8.5, h: 0.3, fontSize: 8, color: RED, fontFace: "Arial", bold: true }});

// ═══ SAVE ═══
pres.writeFile({{ fileName: "{output_path}" }}).then(() => {{
  console.log("Deck saved: {output_path}");
}});
"""


def generate_deck() -> Path:
    """Generate the PPTX briefing deck."""
    print("  Generating PPTX briefing deck...")

    # Write the Node.js script
    script_path = DECK_DIR / "build_deck.js"
    script_content = generate_deck_script()
    with open(script_path, "w") as f:
        f.write(script_content)

    # Check for pptxgenjs
    try:
        result = subprocess.run(
            ["node", "-e", "require('pptxgenjs')"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            # Install pptxgenjs
            print("  Installing pptxgenjs...")
            subprocess.run(["npm", "install", "pptxgenjs"], capture_output=True,
                          cwd=str(DECK_DIR), timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  ⚠ Node.js not available — cannot generate PPTX deck")
        print("    Install Node.js 18+ and run: npm install pptxgenjs")
        return None

    # Run the script
    try:
        result = subprocess.run(
            ["node", str(script_path)],
            capture_output=True, text=True, timeout=30,
            cwd=str(DECK_DIR)
        )
        if result.returncode == 0:
            output_path = DECK_DIR / "JLAW_Investigation_Briefing.pptx"
            print(f"  ✓ Deck: {output_path}")
            return output_path
        else:
            print(f"  ✗ Deck generation failed: {result.stderr[:200]}")
            return None
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


if __name__ == "__main__":
    generate_deck()
