"""
JLAW Ingestion Module
Parsers for SEC EDGAR filing formats: PDF, XLS/XLSX, XML (Form 4, RSS), DOCX deliverables, and CIK XBRL facts.
"""

from src.ingestion.form4_parser import parse_form4_xml, parse_form4_directory
from src.ingestion.rss_parser import parse_edgar_rss, build_filing_inventory
from src.ingestion.pdf_parser import parse_pdf, parse_pdf_directory
from src.ingestion.xls_parser import parse_xls, parse_xls_directory
from src.ingestion.docx_parser import parse_docx, parse_docx_directory
from src.ingestion.cik_parser import parse_cik_facts

__all__ = [
    "parse_form4_xml",
    "parse_form4_directory",
    "parse_edgar_rss",
    "build_filing_inventory",
    "parse_pdf",
    "parse_pdf_directory",
    "parse_xls",
    "parse_xls_directory",
    "parse_docx",
    "parse_docx_directory",
    "parse_cik_facts",
]
