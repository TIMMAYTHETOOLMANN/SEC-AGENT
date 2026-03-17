"""
JLAW DOCX Chart Embedder — Injects Static Charts into Report Documents
Adds PNG chart images to existing or new DOCX reports with proper formatting.

Integrates with src/agents/report_generator.py to embed charts during Phase 3.

Usage:
    from src.visualization.docx_embedder import DocxEmbedder
    embedder = DocxEmbedder(chart_images)
    embedder.embed_into_report(docx_path, chart_placements)
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH


# Chart placement configurations for each report type
MASTER_REPORT_CHARTS = [
    {
        "chart_key": "insider_timeline",
        "section_heading": "Insider Trading Analysis",
        "caption": "Figure 1: Nike Insider Trading — Seven-Year Cadence (FY2019–FY2025)",
        "width": Inches(6.5),
    },
    {
        "chart_key": "severity_heatmap",
        "section_heading": "Anomaly Severity Analysis",
        "caption": "Figure 2: Anomaly Severity Matrix — Year × Category",
        "width": Inches(6.5),
    },
    {
        "chart_key": "staleness_gauge",
        "section_heading": "Swoosh LLC 13D Analysis",
        "caption": "Figure 3: Swoosh LLC Schedule 13D Staleness Indicator",
        "width": Inches(5.0),
    },
    {
        "chart_key": "timeliness_boxplot",
        "section_heading": "Section 16(a) Timeliness Analysis",
        "caption": "Figure 4: Form 4 Filing Timeliness Distribution by Insider",
        "width": Inches(6.5),
    },
    {
        "chart_key": "pattern_network",
        "section_heading": "Compounding Patterns",
        "caption": "Figure 5: Compounding Pattern Network — Anomaly Linkage Map",
        "width": Inches(6.5),
    },
    {
        "chart_key": "regulatory_radar",
        "section_heading": "Regulatory Recommendation Matrix",
        "caption": "Figure 6: Regulatory Enforcement Readiness Scorecard",
        "width": Inches(5.0),
    },
]

SEC_BUNDLE_CHARTS = [
    {"chart_key": "insider_timeline",  "section_heading": "Evidence by Violation Type",
     "caption": "Insider Trading Pattern Visualization", "width": Inches(6.0)},
    {"chart_key": "timeliness_boxplot", "section_heading": "Section 16(a) — Late Form 4 Filings",
     "caption": "Filing Timeliness Distribution", "width": Inches(6.0)},
    {"chart_key": "staleness_gauge",   "section_heading": "Section 13(d) — Schedule 13D Staleness",
     "caption": "Swoosh 13D Staleness Indicator", "width": Inches(5.0)},
]

DOJ_REFERRAL_CHARTS = [
    {"chart_key": "insider_timeline",  "section_heading": "Securities Fraud Pattern Summary",
     "caption": "Cumulative Insider Selling Pattern", "width": Inches(6.0)},
    {"chart_key": "regulatory_radar",  "section_heading": "Enforcement Assessment",
     "caption": "Regulatory Enforcement Readiness", "width": Inches(5.0)},
]

LEGISLATIVE_CHARTS = [
    {"chart_key": "severity_heatmap",  "section_heading": "Regulatory Gap Analysis",
     "caption": "Seven-Year Anomaly Severity Overview", "width": Inches(6.0)},
    {"chart_key": "regulatory_radar",  "section_heading": "Recommended Legislative Reforms",
     "caption": "Cross-Agency Enforcement Scorecard", "width": Inches(5.0)},
]

CHART_PLACEMENTS = {
    "master": MASTER_REPORT_CHARTS,
    "sec": SEC_BUNDLE_CHARTS,
    "doj": DOJ_REFERRAL_CHARTS,
    "legislative": LEGISLATIVE_CHARTS,
    "leg": LEGISLATIVE_CHARTS,
}


class DocxEmbedder:
    """Embeds static chart images into DOCX reports."""

    def __init__(self, chart_images: Dict[str, Path]):
        """
        Args:
            chart_images: Map of chart_key → PNG file path
        """
        self.chart_images = chart_images

    def embed_into_existing(self, docx_path: Path, report_type: str = "master") -> Path:
        """
        Embed charts into an existing DOCX report.
        Searches for section headings and inserts charts after them.
        """
        doc = Document(str(docx_path))
        placements = CHART_PLACEMENTS.get(report_type, MASTER_REPORT_CHARTS)

        for placement in placements:
            chart_key = placement["chart_key"]
            img_path = self.chart_images.get(chart_key)
            if not img_path or not Path(img_path).exists():
                continue

            target_heading = placement["section_heading"]
            caption = placement["caption"]
            width = placement["width"]

            # Find the heading paragraph
            inserted = False
            for i, paragraph in enumerate(doc.paragraphs):
                if (target_heading.lower() in paragraph.text.lower()
                        and paragraph.style.name.startswith("Heading")):
                    # Insert after this heading's content block
                    self._insert_chart_after_paragraph(
                        doc, paragraph, img_path, caption, width
                    )
                    inserted = True
                    break

            if not inserted:
                # Append at end if heading not found
                self._append_chart(doc, img_path, caption, width)

        doc.save(str(docx_path))
        return docx_path

    def create_chart_appendix(self, output_path: Path) -> Path:
        """
        Create a standalone DOCX appendix with all available charts.
        Can be merged with any report document.
        """
        doc = Document()

        # Classification header
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("PRIVILEGED & CONFIDENTIAL")
        run.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(192, 0, 0)

        doc.add_heading("Forensic Visualization Appendix", level=1)
        doc.add_paragraph(
            "This appendix contains visual analyses generated by the JLAW "
            "Forensic Intelligence Platform. All charts are derived from the "
            "anomaly database and parsed EDGAR filing data."
        )

        chart_titles = {
            "insider_timeline":   "Insider Trading — Seven-Year Cadence",
            "severity_heatmap":   "Anomaly Severity Matrix",
            "staleness_gauge":    "Swoosh LLC 13D Staleness",
            "timeliness_boxplot": "Form 4 Filing Timeliness",
            "pattern_network":    "Compounding Pattern Network",
            "regulatory_radar":   "Regulatory Enforcement Scorecard",
        }

        fig_num = 1
        for chart_key, title in chart_titles.items():
            img_path = self.chart_images.get(chart_key)
            if not img_path or not Path(img_path).exists():
                continue

            doc.add_page_break()
            doc.add_heading(title, level=2)

            # Insert chart image
            doc.add_picture(str(img_path), width=Inches(6.5))
            last_para = doc.paragraphs[-1]
            last_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Caption
            caption_para = doc.add_paragraph()
            caption_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = caption_para.add_run(f"Figure {fig_num}: {title}")
            run.font.size = Pt(9)
            run.font.italic = True
            run.font.color.rgb = RGBColor(89, 89, 89)

            fig_num += 1

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        return Path(output_path)

    def _insert_chart_after_paragraph(self, doc: Document, heading_para,
                                       img_path: Path, caption: str,
                                       width=Inches(6.5)):
        """Insert a chart image after a specific paragraph in the document."""
        # We add the picture to the document and the caption
        # This appends at the end; for proper insertion we use the
        # paragraph's XML element to insert after it
        from docx.oxml.ns import qn
        from copy import deepcopy
        import lxml.etree as etree

        # Create a new paragraph for the image
        new_para = doc.add_paragraph()
        new_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = new_para.add_run()
        run.add_picture(str(img_path), width=width)

        # Create caption paragraph
        cap_para = doc.add_paragraph()
        cap_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_run = cap_para.add_run(caption)
        cap_run.font.size = Pt(9)
        cap_run.font.italic = True
        cap_run.font.color.rgb = RGBColor(89, 89, 89)

        # Move the image and caption paragraphs after the heading
        # by manipulating the XML tree
        body = doc.element.body
        heading_elem = heading_para._element

        # Find the next sibling (content after heading)
        # Insert image paragraph after the heading
        body.remove(new_para._element)
        body.remove(cap_para._element)
        heading_elem.addnext(cap_para._element)
        heading_elem.addnext(new_para._element)

    def _append_chart(self, doc: Document, img_path: Path, caption: str,
                      width=Inches(6.5)):
        """Append a chart at the end of the document."""
        doc.add_paragraph()
        doc.add_picture(str(img_path), width=width)
        last_para = doc.paragraphs[-1]
        last_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        cap_para = doc.add_paragraph()
        cap_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cap_para.add_run(caption)
        run.font.size = Pt(9)
        run.font.italic = True
        run.font.color.rgb = RGBColor(89, 89, 89)
