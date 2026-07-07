from __future__ import annotations

from decimal import Decimal
from difflib import SequenceMatcher
import re

from .models import (
    InvoiceData,
    ReceiptData,
    ReconciliationResult,
    ReconciliationRow,
    ReconciliationStatus,
    ReconciliationSummary,
)


class CompareEngine(object):
    """
    Compare invoice va receipt theo rule deterministic.
    """

    def __init__(self, fuzzy_threshold=0.9):
        self._fuzzy_threshold = float(fuzzy_threshold)

    def compare(self, invoice_data, receipt_data):
        """
        :param InvoiceData invoice_data:
        :param ReceiptData receipt_data:
        :return: ReconciliationResult
        :rtype: ReconciliationResult
        """
        invoice_items = self._prepare_items(invoice_data.items)
        receipt_items = self._prepare_items(receipt_data.items)

        rows = []
        invoice_pool, invoice_no_code_pool = self._build_invoice_pool(invoice_items)

        # Luôn đi theo thứ tự receipt gốc
        for receipt_item in receipt_items:
            rows.append(self._compare_receipt_row(receipt_item, invoice_pool, invoice_no_code_pool))

        # Item còn dư trên invoice mà receipt không có
        for code, pool in invoice_pool.items():
            if pool["remaining_qty"] > Decimal("0"):
                rows.append(self._build_missing_receipt_row_from_pool(code, pool))
        for pool in invoice_no_code_pool:
            if pool["remaining_qty"] > Decimal("0"):
                rows.append(self._build_missing_receipt_row_from_pool(None, pool))

        summary = self._build_summary(rows, invoice_items, receipt_items)
        return ReconciliationResult(rows=rows, summary=summary)

    def _build_invoice_pool(self, invoice_items):
        pool = {}
        no_code_pool = []
        for item in invoice_items:
            code = self._normalize_code(item["item_code"])

            qty = item["quantity"] or Decimal("0")
            amount = item["amount"] or Decimal("0")
            if not code:
                no_code_pool.append(
                    {
                        "item_code": item["item_code"],
                        "description": item["description"],
                        "total_qty": qty,
                        "remaining_qty": qty,
                        "unit_price": item["unit_price"],
                        "total_amount": amount,
                    }
                )
                continue

            if code not in pool:
                pool[code] = {
                    "item_code": item["item_code"],
                    "description": item["description"],
                    "total_qty": Decimal("0"),
                    "remaining_qty": Decimal("0"),
                    "unit_price": item["unit_price"],
                    "total_amount": Decimal("0"),
                }
            pool[code]["total_qty"] += qty
            pool[code]["remaining_qty"] += qty
            pool[code]["total_amount"] += amount
            if pool[code]["unit_price"] is None and item["unit_price"] is not None:
                pool[code]["unit_price"] = item["unit_price"]

        return pool, no_code_pool

    def _compare_receipt_row(self, receipt_item, invoice_pool, invoice_no_code_pool):
        code_key = self._normalize_code(receipt_item["item_code"])
        receipt_qty = receipt_item["quantity"] or Decimal("0")
        receipt_price = receipt_item["unit_price"]
        receipt_amount = receipt_item["amount"]

        if code_key and code_key in invoice_pool:
            pool = invoice_pool[code_key]
        else:
            pool = self._find_best_no_code_pool(receipt_item, invoice_no_code_pool)
            if pool is None:
                return self._build_missing_invoice_row(receipt_item)
        remaining_qty = pool["remaining_qty"]
        invoice_price = pool["unit_price"]

        # Không còn số lượng invoice để cover
        if remaining_qty <= Decimal("0"):
            return self._build_missing_invoice_row(receipt_item)

        matched_qty = receipt_qty if receipt_qty <= remaining_qty else remaining_qty
        missing_qty = receipt_qty - matched_qty
        pool["remaining_qty"] = remaining_qty - matched_qty

        if missing_qty > Decimal("0"):
            missing_amount = self._compute_amount_from_qty_price(missing_qty, receipt_price, receipt_amount, receipt_qty)
            return ReconciliationRow(
                item_code=receipt_item["item_code"],
                description=receipt_item["description"],
                invoice_qty=matched_qty,
                receipt_qty=receipt_qty,
                qty_status=ReconciliationStatus.QTY_MISMATCH,
                invoice_unit_price=invoice_price,
                receipt_unit_price=receipt_price,
                price_status=ReconciliationStatus.PASS if self._equal_decimal(invoice_price, receipt_price) else ReconciliationStatus.PRICE_MISMATCH,
                invoice_amount=self._compute_amount_from_qty_price(matched_qty, receipt_price, receipt_amount, receipt_qty),
                receipt_amount=receipt_amount,
                amount_status=ReconciliationStatus.AMOUNT_MISMATCH,
                final_status=ReconciliationStatus.MISSING_IN_INVOICE,
                note="Chua xuat hoa don phan bo sung (thieu so luong %s)" % self._fmt_decimal(missing_qty),
                receipt_no=receipt_item.get("receipt_no"),
                receipt_date=receipt_item.get("receipt_date"),
                po_no=receipt_item.get("po_no"),
                missing_amount=missing_amount,
            )

        # Cover full row -> pass / mismatch theo price-amount
        qty_status = ReconciliationStatus.PASS
        price_status = ReconciliationStatus.PASS if self._equal_decimal(invoice_price, receipt_price) else ReconciliationStatus.PRICE_MISMATCH

        expected_amount = self._compute_amount_from_qty_price(receipt_qty, receipt_price, receipt_amount, receipt_qty)
        amount_status = ReconciliationStatus.PASS
        final_status = ReconciliationStatus.PASS
        note = "Khop hoa don"

        if price_status != ReconciliationStatus.PASS:
            final_status = ReconciliationStatus.PRICE_MISMATCH
            note = "Lech don gia"

        if receipt_amount is not None and expected_amount is not None and not self._equal_decimal(expected_amount, receipt_amount):
            amount_status = ReconciliationStatus.AMOUNT_MISMATCH
            if final_status == ReconciliationStatus.PASS:
                final_status = ReconciliationStatus.AMOUNT_MISMATCH
                note = "Lech thanh tien"

        return ReconciliationRow(
            item_code=receipt_item["item_code"],
            description=receipt_item["description"],
            invoice_qty=receipt_qty,
            receipt_qty=receipt_qty,
            qty_status=qty_status,
            invoice_unit_price=invoice_price,
            receipt_unit_price=receipt_price,
            price_status=price_status,
            invoice_amount=expected_amount,
            receipt_amount=receipt_amount,
            amount_status=amount_status,
            final_status=final_status,
            note=note,
            receipt_no=receipt_item.get("receipt_no"),
            receipt_date=receipt_item.get("receipt_date"),
            po_no=receipt_item.get("po_no"),
            missing_amount=Decimal("0"),
        )

    def _find_best_no_code_pool(self, receipt_item, invoice_no_code_pool):
        best_pool = None
        best_score = 0.0
        for pool in invoice_no_code_pool:
            if pool["remaining_qty"] <= Decimal("0"):
                continue
            score = self._description_similarity(receipt_item.get("description"), pool.get("description"))
            if score > best_score:
                best_score = score
                best_pool = pool

        if best_pool is None:
            return None
        if best_score < self._fuzzy_threshold:
            return None
        return best_pool

    def _prepare_items(self, items):
        prepared = []
        for item in items:
            prepared.append(
                {
                    "item_code": self._clean(item.item_code),
                    "description": self._clean(item.description),
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "amount": item.amount,
                    "receipt_no": self._clean(item.receipt_no),
                    "receipt_date": self._clean(item.receipt_date),
                    "po_no": self._clean(item.po_no),
                }
            )
        return prepared

    def _match_items(self, invoice_items, receipt_items):
        matches = []
        used_receipt_indices = set()
        matched_invoice_indices = set()

        # Priority 1: match by item code
        receipt_code_map = {}
        for index, item in enumerate(receipt_items):
            code = self._normalize_code(item["item_code"])
            if not code:
                continue
            if code not in receipt_code_map:
                receipt_code_map[code] = []
            receipt_code_map[code].append(index)

        for invoice_index, invoice_item in enumerate(invoice_items):
            code = self._normalize_code(invoice_item["item_code"])
            if not code:
                continue

            receipt_indices = receipt_code_map.get(code, [])
            for receipt_index in receipt_indices:
                if receipt_index in used_receipt_indices:
                    continue
                matches.append((invoice_index, receipt_index))
                used_receipt_indices.add(receipt_index)
                matched_invoice_indices.add(invoice_index)
                break

        # Priority 2: fuzzy by description if missing item code
        for invoice_index, invoice_item in enumerate(invoice_items):
            if invoice_index in matched_invoice_indices:
                continue

            invoice_code = self._normalize_code(invoice_item["item_code"])
            if invoice_code:
                continue

            best_score = 0.0
            best_receipt_index = None
            for receipt_index, receipt_item in enumerate(receipt_items):
                if receipt_index in used_receipt_indices:
                    continue

                score = self._description_similarity(
                    invoice_item["description"], receipt_item["description"]
                )
                if score > best_score:
                    best_score = score
                    best_receipt_index = receipt_index

            if best_receipt_index is not None and best_score >= self._fuzzy_threshold:
                matches.append((invoice_index, best_receipt_index))
                used_receipt_indices.add(best_receipt_index)
                matched_invoice_indices.add(invoice_index)

        missing_receipt_indices = [
            index for index in range(len(invoice_items)) if index not in matched_invoice_indices
        ]
        missing_invoice_indices = [
            index for index in range(len(receipt_items)) if index not in used_receipt_indices
        ]
        return matches, missing_invoice_indices, missing_receipt_indices

    def _build_matched_row(self, invoice_item, receipt_item):
        qty_status = self._field_status(
            invoice_item["quantity"], receipt_item["quantity"], ReconciliationStatus.QTY_MISMATCH
        )
        price_status = self._field_status(
            invoice_item["unit_price"], receipt_item["unit_price"], ReconciliationStatus.PRICE_MISMATCH
        )
        amount_status = self._field_status(
            invoice_item["amount"], receipt_item["amount"], ReconciliationStatus.AMOUNT_MISMATCH
        )

        mismatch_sequence = (
            (qty_status, ReconciliationStatus.QTY_MISMATCH),
            (price_status, ReconciliationStatus.PRICE_MISMATCH),
            (amount_status, ReconciliationStatus.AMOUNT_MISMATCH),
        )

        final_status = ReconciliationStatus.PASS
        notes = []
        for status, mismatch_status in mismatch_sequence:
            if status == ReconciliationStatus.PASS:
                continue
            final_status = mismatch_status
            notes.append(mismatch_status.value)

        if len(notes) > 1:
            final_status = ReconciliationStatus.QTY_MISMATCH

        return ReconciliationRow(
            item_code=invoice_item["item_code"] or receipt_item["item_code"],
            description=invoice_item["description"] or receipt_item["description"],
            invoice_qty=invoice_item["quantity"],
            receipt_qty=receipt_item["quantity"],
            qty_status=qty_status,
            invoice_unit_price=invoice_item["unit_price"],
            receipt_unit_price=receipt_item["unit_price"],
            price_status=price_status,
            invoice_amount=invoice_item["amount"],
            receipt_amount=receipt_item["amount"],
            amount_status=amount_status,
            final_status=final_status,
            note=", ".join(notes) if notes else None,
        )

    def _build_missing_receipt_row(self, invoice_item):
        return ReconciliationRow(
            item_code=invoice_item["item_code"],
            description=invoice_item["description"],
            invoice_qty=invoice_item["quantity"],
            receipt_qty=None,
            qty_status=None,
            invoice_unit_price=invoice_item["unit_price"],
            receipt_unit_price=None,
            price_status=None,
            invoice_amount=invoice_item["amount"],
            receipt_amount=None,
            amount_status=None,
            final_status=ReconciliationStatus.MISSING_IN_RECEIPT,
            note="Item chi co tren invoice",
        )

    def _build_missing_receipt_row_from_pool(self, code, pool):
        remaining_qty = pool["remaining_qty"]
        unit_price = pool["unit_price"]
        remaining_amount = self._compute_amount_from_qty_price(remaining_qty, unit_price, None, remaining_qty)

        return ReconciliationRow(
            item_code=pool["item_code"] or code,
            description=pool["description"],
            invoice_qty=remaining_qty,
            receipt_qty=None,
            qty_status=None,
            invoice_unit_price=unit_price,
            receipt_unit_price=None,
            price_status=None,
            invoice_amount=remaining_amount,
            receipt_amount=None,
            amount_status=None,
            final_status=ReconciliationStatus.MISSING_IN_RECEIPT,
            note="Invoice co hang chua thay tren receipt",
            missing_amount=None,
        )

    def _build_missing_invoice_row(self, receipt_item):
        return ReconciliationRow(
            item_code=receipt_item["item_code"],
            description=receipt_item["description"],
            invoice_qty=None,
            receipt_qty=receipt_item["quantity"],
            qty_status=None,
            invoice_unit_price=None,
            receipt_unit_price=receipt_item["unit_price"],
            price_status=None,
            invoice_amount=None,
            receipt_amount=receipt_item["amount"],
            amount_status=None,
            final_status=ReconciliationStatus.MISSING_IN_INVOICE,
            note="Item chi co tren receipt",
            receipt_no=receipt_item.get("receipt_no"),
            receipt_date=receipt_item.get("receipt_date"),
            po_no=receipt_item.get("po_no"),
            missing_amount=receipt_item.get("amount"),
        )

    def _build_summary(self, rows, invoice_items, receipt_items):
        total_invoice_amount = self._sum_amount(item["amount"] for item in invoice_items)
        total_receipt_amount = self._sum_amount(item["amount"] for item in receipt_items)

        matched_count = 0
        mismatch_count = 0
        missing_count = 0
        for row in rows:
            if row.final_status == ReconciliationStatus.PASS:
                matched_count += 1
            elif row.final_status in (
                ReconciliationStatus.MISSING_IN_INVOICE,
                ReconciliationStatus.MISSING_IN_RECEIPT,
            ):
                missing_count += 1
            else:
                mismatch_count += 1

        return ReconciliationSummary(
            total_invoice_amount=total_invoice_amount,
            total_receipt_amount=total_receipt_amount,
            matched_count=matched_count,
            mismatch_count=mismatch_count,
            missing_count=missing_count,
        )

    def _field_status(self, invoice_value, receipt_value, mismatch_status):
        if self._equal_decimal(invoice_value, receipt_value):
            return ReconciliationStatus.PASS
        return mismatch_status

    def _equal_decimal(self, left, right):
        if left is None and right is None:
            return True
        if left is None or right is None:
            return False
        return Decimal(left) == Decimal(right)

    def _description_similarity(self, left, right):
        a = self._normalize_description(left)
        b = self._normalize_description(right)
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    def _normalize_description(self, text):
        if not text:
            return ""
        normalized = str(text).lower().strip()
        return " ".join(normalized.split())

    def _normalize_code(self, code):
        if not code:
            return ""
        text = str(code).strip().upper()
        match = re.match(r"^[A-Z0-9]+", text)
        if match:
            return match.group(0)
        return text

    def _clean(self, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _sum_amount(self, amounts):
        total = Decimal("0")
        for value in amounts:
            if value is None:
                continue
            total += Decimal(value)
        return total

    def _compute_amount_from_qty_price(self, qty, price, fallback_amount, fallback_qty):
        if qty is None:
            return None
        if price is not None:
            return Decimal(qty) * Decimal(price)
        if fallback_amount is None or fallback_qty in (None, Decimal("0"), 0):
            return None
        return (Decimal(fallback_amount) / Decimal(fallback_qty)) * Decimal(qty)

    def _fmt_decimal(self, value):
        if value is None:
            return "0"
        normalized = Decimal(value).normalize()
        text = format(normalized, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
