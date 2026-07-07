from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pandas as pd

from .models import LineItem, ReceiptData


class ReceiptParser(object):
    """
    Parse file receipt Excel (.xlsx) va chuyen ve ReceiptData.
    """

    COLUMN_ALIASES = {
        "item_code": (
            "item code",
            "material code",
            "product code",
            "part no",
            "part number",
            "item",
        ),
        "description": (
            "description",
            "item description",
            "product description",
            "name",
        ),
        "quantity": (
            "qty",
            "quantity",
            "received qty",
            "receipt quantity",
        ),
        "unit_price": (
            "unit price",
            "price",
            "receipt price",
        ),
        "amount": (
            "amount",
            "total amount",
            "receipt amount",
        ),
        "receipt_no": (
            "receipt no",
            "receipt number",
            "gr no",
        ),
        "receipt_date": (
            "receipt date",
            "date",
        ),
        "po_no": (
            "p/o no",
            "po no",
            "purchase order",
        ),
    }

    RECEIPT_NUMBER_ALIASES = (
        "receipt no",
        "receipt number",
        "gr no",
    )

    def parse(self, excel_path):
        """
        Parse receipt file va tra ve ReceiptData.

        :param str excel_path: Duong dan receipt .xlsx
        :return: ReceiptData
        :rtype: ReceiptData
        """
        raw_df = pd.read_excel(excel_path, sheet_name=0, header=None, dtype=object)
        header_row_index = self._detect_header_row(raw_df)
        if header_row_index is None:
            raise ValueError("Khong tim thay dong header hop le trong receipt file.")

        header_values = self._row_to_header(raw_df.iloc[header_row_index].tolist())
        field_to_col = self._map_fields(header_values)

        required_fields = ("item_code", "quantity", "unit_price", "amount")
        missing = [name for name in required_fields if name not in field_to_col]
        if missing:
            raise ValueError("Thieu cot bat buoc trong receipt: %s" % ", ".join(missing))

        data_df = raw_df.iloc[header_row_index + 1 :].reset_index(drop=True)
        data_df.columns = header_values

        items = []
        receipt_number = None
        receipt_no_col = self._find_receipt_number_column(header_values)

        for _, row in data_df.iterrows():
            item_code = self._clean_string(row.get(field_to_col["item_code"]))
            description = self._clean_string(
                row.get(field_to_col["description"]) if "description" in field_to_col else None
            )
            quantity = self._to_decimal(row.get(field_to_col["quantity"]))
            unit_price = self._to_decimal(row.get(field_to_col["unit_price"]))
            amount = self._to_decimal(row.get(field_to_col["amount"]))

            if receipt_no_col and receipt_number is None:
                receipt_number = self._clean_string(row.get(receipt_no_col))

            # Bo dong rong / dong khong co du lieu compare
            if not item_code and not description:
                continue
            if quantity is None and unit_price is None and amount is None:
                continue

            items.append(
                LineItem(
                    item_code=item_code,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    amount=amount,
                    receipt_no=self._clean_string(
                        row.get(field_to_col["receipt_no"]) if "receipt_no" in field_to_col else None
                    ),
                    receipt_date=self._clean_string(
                        row.get(field_to_col["receipt_date"]) if "receipt_date" in field_to_col else None
                    ),
                    po_no=self._clean_string(
                        row.get(field_to_col["po_no"]) if "po_no" in field_to_col else None
                    ),
                )
            )

        return ReceiptData(receipt_number=receipt_number, items=items)

    def _detect_header_row(self, raw_df):
        max_scan = min(len(raw_df.index), 50)
        for index in range(max_scan):
            row_values = self._row_to_header(raw_df.iloc[index].tolist())
            mapped = self._map_fields(row_values)
            if "item_code" in mapped and "quantity" in mapped and (
                "unit_price" in mapped or "amount" in mapped
            ):
                return index
        return None

    def _row_to_header(self, values):
        headers = []
        for i, value in enumerate(values):
            label = self._normalize_header_name(value)
            if not label:
                label = "unnamed_%s" % i
            headers.append(label)
        return headers

    def _map_fields(self, headers):
        mapped = {}
        for field_name, aliases in self.COLUMN_ALIASES.items():
            for header in headers:
                if self._matches_alias(header, aliases):
                    mapped[field_name] = header
                    break
        return mapped

    def _matches_alias(self, header, aliases):
        normalized_header = self._normalize_for_alias(header)
        for alias in aliases:
            if normalized_header == self._normalize_for_alias(alias):
                return True
        return False

    def _normalize_header_name(self, value):
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower().startswith("unnamed:"):
            return ""
        return text

    def _normalize_for_alias(self, value):
        return str(value).strip().lower().replace("_", " ")

    def _find_receipt_number_column(self, headers):
        for header in headers:
            if self._matches_alias(header, self.RECEIPT_NUMBER_ALIASES):
                return header
        return None

    def _clean_string(self, value):
        if value is None:
            return None
        text = str(value).strip()
        if text == "" or text.lower() == "nan":
            return None
        return text

    def _to_decimal(self, value):
        if value is None:
            return None

        if isinstance(value, Decimal):
            return value

        if isinstance(value, (int, float)):
            return Decimal(str(value))

        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None

        text = text.replace(" ", "")
        has_dot = "." in text
        has_comma = "," in text
        if has_dot and has_comma:
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", "")
        elif has_comma:
            text = text.replace(",", ".")

        try:
            return Decimal(text)
        except InvalidOperation:
            return None
