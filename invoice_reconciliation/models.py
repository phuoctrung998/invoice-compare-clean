from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import List, Optional

try:
    from pydantic import BaseModel, ConfigDict, Field
except ImportError:
    def ConfigDict(**kwargs):
        return kwargs

    def Field(default=None, default_factory=None):
        if default_factory is not None:
            return default_factory()
        return default

    class BaseModel(object):
        def __init__(self, **kwargs):
            fields = getattr(self.__class__, "__annotations__", {})
            for field_name in fields:
                if field_name in kwargs:
                    value = kwargs[field_name]
                else:
                    value = getattr(self.__class__, field_name, None)
                    if isinstance(value, list):
                        value = list(value)
                    elif isinstance(value, dict):
                        value = dict(value)
                setattr(self, field_name, value)

        @classmethod
        def model_validate(cls, data):
            if isinstance(data, cls):
                return data
            if not isinstance(data, dict):
                raise ValueError("model_validate expects dict data.")
            return cls(**data)


class ReconciliationStatus(str, Enum):
    PASS = "PASS"
    QTY_MISMATCH = "QTY_MISMATCH"
    PRICE_MISMATCH = "PRICE_MISMATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_IN_INVOICE = "MISSING_IN_INVOICE"
    MISSING_IN_RECEIPT = "MISSING_IN_RECEIPT"


class LineItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    item_code: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    receipt_no: Optional[str] = None
    receipt_date: Optional[str] = None
    po_no: Optional[str] = None


class InvoiceData(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    invoice_number: Optional[str] = None
    supplier_name: Optional[str] = None
    currency: Optional[str] = None
    items: List[LineItem] = Field(default_factory=list)


class ReceiptData(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    receipt_number: Optional[str] = None
    items: List[LineItem] = Field(default_factory=list)


class ReconciliationRow(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    item_code: Optional[str] = None
    description: Optional[str] = None

    invoice_qty: Optional[Decimal] = None
    receipt_qty: Optional[Decimal] = None
    qty_status: Optional[ReconciliationStatus] = None

    invoice_unit_price: Optional[Decimal] = None
    receipt_unit_price: Optional[Decimal] = None
    price_status: Optional[ReconciliationStatus] = None

    invoice_amount: Optional[Decimal] = None
    receipt_amount: Optional[Decimal] = None
    amount_status: Optional[ReconciliationStatus] = None

    final_status: ReconciliationStatus
    note: Optional[str] = None
    receipt_no: Optional[str] = None
    receipt_date: Optional[str] = None
    po_no: Optional[str] = None
    missing_amount: Optional[Decimal] = None


class ReconciliationSummary(BaseModel):
    total_invoice_amount: Decimal = Decimal("0")
    total_receipt_amount: Decimal = Decimal("0")
    matched_count: int = 0
    mismatch_count: int = 0
    missing_count: int = 0


class ReconciliationResult(BaseModel):
    rows: List[ReconciliationRow] = Field(default_factory=list)
    summary: ReconciliationSummary
