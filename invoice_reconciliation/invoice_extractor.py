from __future__ import annotations

import json
import os
from decimal import Decimal, InvalidOperation

import pdfplumber
from openai import OpenAI

from .models import InvoiceData


class InvoiceExtractor(object):
    """
    Trich xuat du lieu hoa don tu PDF bang OpenAI API.

    Luu y:
    - Chi dung LLM cho buoc extraction.
    - Du lieu tra ve luon duoc normalize va validate qua Pydantic.
    """

    DEFAULT_MODEL = "gpt-4.1-mini"

    def __init__(self, model=None, api_key=None):
        self._model = model or self.DEFAULT_MODEL
        self._client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def extract(self, pdf_path):
        """
        Doc PDF va tra ve du lieu hoa don da chuan hoa.

        :param str pdf_path: Duong dan toi file invoice PDF
        :return: InvoiceData
        :rtype: InvoiceData
        """
        invoice_text = self._read_pdf_text(pdf_path)
        raw_payload = self._extract_with_openai(invoice_text)
        normalized_payload = self._normalize_payload(raw_payload)
        return InvoiceData.model_validate(normalized_payload)

    def _read_pdf_text(self, pdf_path):
        """
        Trich text tu toan bo trang PDF.

        :param str pdf_path: Duong dan PDF
        :return: Noi dung text da ghep theo trang
        :rtype: str
        """
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for index, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                pages.append("=== PAGE %s ===\n%s" % (index + 1, page_text))

        text = "\n\n".join(pages).strip()
        if not text:
            raise ValueError("Khong doc duoc noi dung text tu invoice PDF.")

        return text

    def _extract_with_openai(self, invoice_text):
        """
        Goi OpenAI API de trich xuat JSON co cau truc.

        :param str invoice_text: Noi dung text invoice
        :return: JSON dict
        :rtype: dict
        """
        system_prompt = (
            "Ban la bo trich xuat du lieu hoa don. "
            "Chi tra ve JSON hop le, khong kem markdown hoac dien giai."
        )
        user_prompt = (
            "Hay trich xuat du lieu invoice theo JSON object voi cau truc:\n"
            "{\n"
            '  "invoice_number": string|null,\n'
            '  "supplier_name": string|null,\n'
            '  "currency": string|null,\n'
            '  "items": [\n'
            "    {\n"
            '      "item_code": string|null,\n'
            '      "description": string|null,\n'
            '      "quantity": number|null,\n'
            '      "unit_price": number|null,\n'
            '      "amount": number|null\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Quy tac extraction:\n"
            "- item_code: chi lay ma hang hoa (phan truoc dau '-' dau tien neu co), vi du '100001614190V-BRACKET' -> item_code='100001614190V'.\n"
            "- description: mo ta hang hoa (phan sau ma hang).\n"
            "- So lieu dung dinh dang Viet Nam: dau cham '.' la phan cach hang nghin, dau phay ',' la phan cach thap phan.\n"
            "  Vi du: 6.072,00 = 6072 | 1.287 = 1287 | 12.611.544 = 12611544 | 663,00 = 663.\n"
            "  Tra ve so nguyen hoac thap phan chuan (khong co dau cham/phay dinh dang).\n"
            "- quantity, unit_price, amount lay theo tung dong hang, chuyen ve so thuc chuan.\n"
            "- Khong tu suy luan, khong them dong khong co trong invoice.\n\n"
            "Invoice text:\n%s"
        ) % invoice_text

        response = self._client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = getattr(response, "output_text", "") or ""
        if not content:
            raise ValueError("OpenAI khong tra ve output_text cho invoice extraction.")

        try:
            return json.loads(content)
        except ValueError:
            parsed_json = self._try_extract_json_object(content)
            if parsed_json is None:
                raise ValueError("OpenAI tra ve noi dung khong phai JSON hop le.")
            return parsed_json

    def _try_extract_json_object(self, content):
        """
        Fallback khi response co text thua ngoai JSON.

        :param str content: Raw text tu model
        :return: dict hoac None
        :rtype: dict|None
        """
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end < 0 or end <= start:
            return None

        candidate = content[start : end + 1]
        try:
            return json.loads(candidate)
        except ValueError:
            return None

    def _normalize_payload(self, payload):
        """
        Chuan hoa du lieu truoc khi validate boi Pydantic.

        :param dict payload: JSON tho tu OpenAI
        :return: JSON dict da chuan hoa
        :rtype: dict
        """
        normalized = {
            "invoice_number": payload.get("invoice_number"),
            "supplier_name": payload.get("supplier_name"),
            "currency": payload.get("currency"),
            "items": [],
        }

        for item in payload.get("items", []):
            normalized["items"].append(
                {
                    "item_code": self._clean_string(item.get("item_code")),
                    "description": self._clean_string(item.get("description")),
                    "quantity": self._normalize_decimal(item.get("quantity")),
                    "unit_price": self._normalize_decimal(item.get("unit_price")),
                    "amount": self._normalize_decimal(item.get("amount")),
                }
            )

        return normalized

    def _clean_string(self, value):
        """
        Trim chuoi va tra ve None neu rong.

        :param any value: Gia tri dau vao
        :return: Chuoi da lam sach hoac None
        :rtype: str|None
        """
        if value is None:
            return None

        text = str(value).strip()
        return text or None

    def _normalize_decimal(self, value):
        """
        Chuan hoa so theo nhieu dinh dang (vd: 20.300,00 hoac 20300.00).

        :param any value: Gia tri dau vao
        :return: Decimal hoac None
        :rtype: Decimal|None
        """
        if value is None:
            return None

        if isinstance(value, Decimal):
            return value

        raw = str(value).strip()
        if not raw:
            return None

        cleaned = raw.replace(" ", "")
        has_dot = "." in cleaned
        has_comma = "," in cleaned

        if has_dot and has_comma:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif has_comma:
            cleaned = cleaned.replace(",", ".")

        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
