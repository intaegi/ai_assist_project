from typing import Any

from backend.app.services.document_fields import (
    document_label,
    extract_document_values as extract_values_from_text,
    joined_page_text,
    normalize_comparison_value,
)

FIELD_SPECS = [
    ("vendor", "取引先"),
    ("service_name", "製品・サービス名"),
    ("amount", "金額"),
    ("service_start_date", "利用開始日"),
    ("service_end_date", "利用終了日"),
]


def _joined_text(file: dict[str, Any]) -> str:
    return joined_page_text(file.get("pages", []))


def _document_label(file: dict[str, Any]) -> str:
    return document_label(str(file.get("file_name", "")), _joined_text(file))


def extract_document_values(file: dict[str, Any]) -> dict[str, Any]:
    return extract_values_from_text(_joined_text(file))


def _display_value(value: Any, field: str) -> str:
    if value in (None, ""):
        return "記載なし"
    if field == "amount":
        return f"{float(value):,.0f}円"
    return str(value)


def build_comparison_rows(case: dict[str, Any], form: dict[str, Any]) -> list[dict[str, str]]:
    documents = []
    labels: dict[str, int] = {}
    for file in case.get("files", []):
        base_label = _document_label(file)
        labels[base_label] = labels.get(base_label, 0) + 1
        label = base_label if labels[base_label] == 1 else f"{base_label}{labels[base_label]}"
        documents.append((label, extract_document_values(file)))

    rows = []
    for field, label in FIELD_SPECS:
        target = form.get(field)
        normalized_target = normalize_comparison_value(target, field)
        for document_label, values in documents:
            document_value = values.get(field)
            if not normalized_target:
                result = "フォーム未入力"
            elif document_value in (None, ""):
                result = "記載なし"
            elif normalize_comparison_value(document_value, field) == normalized_target:
                result = "一致"
            else:
                result = "差異あり"
            rows.append(
                {
                    "確認項目": label,
                    "AI決裁フォーム": _display_value(target, field),
                    "書類": document_label,
                    "書類記載値": _display_value(document_value, field),
                    "照合結果": result,
                }
            )
    return rows
