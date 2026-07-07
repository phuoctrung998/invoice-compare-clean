from __future__ import annotations

from .compare_engine import CompareEngine
from .excel_exporter import ExcelExporter
from .invoice_extractor import InvoiceExtractor
from .receipt_parser import ReceiptParser


class ReconciliationService(object):
    """
    Orchestrate extraction -> parse -> compare -> export.
    """

    def __init__(self, invoice_extractor=None, receipt_parser=None, compare_engine=None, excel_exporter=None):
        self.invoice_extractor = invoice_extractor or InvoiceExtractor()
        self.receipt_parser = receipt_parser or ReceiptParser()
        self.compare_engine = compare_engine or CompareEngine()
        self.excel_exporter = excel_exporter or ExcelExporter()

    def run(self, invoice_pdf_path, receipt_excel_path, output_path):
        invoice_data = self.invoice_extractor.extract(invoice_pdf_path)
        receipt_data = self.receipt_parser.parse(receipt_excel_path)
        result = self.compare_engine.compare(invoice_data, receipt_data)
        self.excel_exporter.export(result, output_path)
        return result

