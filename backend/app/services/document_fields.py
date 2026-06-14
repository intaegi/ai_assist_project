import re
from datetime import date
from pathlib import Path
from typing import Any


DOCUMENT_LABELS = (
    ("invoice", "請求書"),
    ("請求書", "請求書"),
    ("請求", "請求書"),
    ("estimate", "見積書"),
    ("quotation", "見積書"),
    ("見積書", "見積書"),
    ("見積", "見積書"),
    ("contract", "契約書"),
    ("契約書", "契約書"),
    ("契約", "契約書"),
    ("order", "発注書"),
    ("発注書", "発注書"),
)


def joined_page_text(pages: list[dict[str, Any]]) -> str:
    return "\n".join(str(page.get("text", "")) for page in pages if page.get("text"))


def document_label(file_name: str, text: str) -> str:
    file_target = file_name.lower()
    for token, label in DOCUMENT_LABELS:
        if token.lower() in file_target:
            return label
    target = text[:160].lower()
    for token, label in DOCUMENT_LABELS:
        if token.lower() in target:
            return label
    return Path(file_name or "添付書類").stem


def normalize_date(value: str) -> str:
    match = re.search(r"(20\d{2})[年/\-.](\d{1,2})[月/\-.](\d{1,2})", value)
    if not match:
        return value.strip()
    year, month, day = map(int, match.groups())
    return date(year, month, day).isoformat()


def extract_document_values(text: str) -> dict[str, Any]:
    values: dict[str, Any] = {}

    vendor = re.search(r"(?:請求元|取引先|会社名|見積元|契約先)[:：\s]+([^\n]+)", text)
    if vendor:
        values["vendor"] = vendor.group(1).strip()

    service = re.search(r"(?:サービス名|商品名|製品名|件名)[:：\s]+([^\n]+)", text)
    if service:
        values["service_name"] = service.group(1).strip()

    amounts = re.findall(
        r"(?:合計金額|請求金額|契約金額|合計|金額)[^\d]{0,10}([\d,]+)\s*円",
        text,
    )
    if amounts:
        values["amount"] = float(amounts[-1].replace(",", ""))

    invoice_date = re.search(
        r"(?:請求日|見積日|契約日)[:：\s]+"
        r"((?:20\d{2})[年/\-.]\d{1,2}[月/\-.]\d{1,2}日?)",
        text,
    )
    if invoice_date:
        values["invoice_date"] = normalize_date(invoice_date.group(1))

    period = re.search(
        r"(?:利用期間|契約期間|対象期間)[:：\s]+"
        r"((?:20\d{2})[年/\-.]\d{1,2}[月/\-.]\d{1,2}日?)"
        r"\s*[～〜~\-]\s*"
        r"((?:20\d{2})[年/\-.]\d{1,2}[月/\-.]\d{1,2}日?)",
        text,
    )
    if period:
        values["service_start_date"] = normalize_date(period.group(1))
        values["service_end_date"] = normalize_date(period.group(2))

    return values


def normalize_comparison_value(value: Any, field: str) -> str:
    if value in (None, ""):
        return ""
    if field == "amount":
        return str(int(float(value)))
    return re.sub(r"\s+", "", str(value))
