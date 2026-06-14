from pathlib import Path

import pytest

from backend.app.services.document_service import DocumentService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = PROJECT_ROOT / "sample_data" / "test_documents" / "pdf"


def test_all_ui_test_pdfs_exist() -> None:
    expected = {
        "TC-DOC-01_it_invoice_cloudguard.pdf",
        "TC-DOC-02_it_estimate_cloudguard.pdf",
        "TC-DOC-03_it_contract_cloudguard.pdf",
        "TC-DOC-04_finance_invoice_accounting.pdf",
        "TC-DOC-05_sales_estimate_tablet.pdf",
        "TC-DOC-06_finance_estimate_mismatch.pdf",
        "TC-DOC-07_it_estimate_vendor_mismatch.pdf",
        "TC-DOC-08_it_contract_period_mismatch.pdf",
    }
    assert {path.name for path in PDF_DIR.glob("*.pdf")} == expected


@pytest.mark.parametrize(
    ("file_name", "document_label", "expected_vendor", "expected_service", "expected_amount"),
    [
        (
            "TC-DOC-01_it_invoice_cloudguard.pdf",
            "請求書",
            "株式会社ネクストクラウド",
            "CloudGuard Pro 年間ライセンス",
            132000.0,
        ),
        (
            "TC-DOC-02_it_estimate_cloudguard.pdf",
            "見積書",
            "株式会社ネクストクラウド",
            "CloudGuard Pro 年間ライセンス",
            132000.0,
        ),
        (
            "TC-DOC-03_it_contract_cloudguard.pdf",
            "契約書",
            "株式会社ネクストクラウド",
            "CloudGuard Pro 年間ライセンス",
            132000.0,
        ),
        (
            "TC-DOC-04_finance_invoice_accounting.pdf",
            "請求書",
            "株式会社ビジネス会計サポート",
            "会計システム月次保守",
            88000.0,
        ),
        (
            "TC-DOC-05_sales_estimate_tablet.pdf",
            "見積書",
            "株式会社デジタルワークス",
            "BizTab 11 タブレット端末",
            240000.0,
        ),
        (
            "TC-DOC-06_finance_estimate_mismatch.pdf",
            "見積書",
            "株式会社ビジネス会計サポート",
            "会計システム月次保守",
            99000.0,
        ),
        (
            "TC-DOC-07_it_estimate_vendor_mismatch.pdf",
            "見積書",
            "株式会社オルタナクラウド",
            "CloudGuard Pro 年間ライセンス",
            132000.0,
        ),
        (
            "TC-DOC-08_it_contract_period_mismatch.pdf",
            "契約書",
            "株式会社ネクストクラウド",
            "CloudGuard Pro 年間ライセンス",
            132000.0,
        ),
    ],
)
def test_pdf_is_text_extractable(
    file_name: str,
    document_label: str,
    expected_vendor: str,
    expected_service: str,
    expected_amount: float,
) -> None:
    service = DocumentService()
    content = (PDF_DIR / file_name).read_bytes()

    pages = service.extract_pages(content, "application/pdf")
    text = "\n".join(str(page["text"]) for page in pages)
    fields = service.extract_basic_fields(text)
    record = service.create_file_record(
        case_id="test-case",
        file_name=file_name,
        content_type="application/pdf",
        content=content,
        storage_path=file_name,
    )

    assert document_label in text
    assert document_label in service.document_types([record])
    assert fields["vendor"] == expected_vendor
    assert fields["service_name"] == expected_service
    assert fields["amount"] == expected_amount
