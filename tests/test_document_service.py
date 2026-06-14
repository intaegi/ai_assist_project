from backend.app.schemas.models import ApprovalForm
from backend.app.services.document_service import DocumentService
from backend.app.services.rag_service import RagService


def test_basic_field_extraction():
    service = DocumentService()
    fields = service.extract_basic_fields(
        "請求元: ABC株式会社\nサービス名: Cloud Standard\n請求金額: 120,000円\n請求日: 2026年6月1日"
    )
    assert fields["vendor"] == "ABC株式会社"
    assert fields["service_name"] == "Cloud Standard"
    assert fields["amount"] == 120000
    assert fields["invoice_date"] == "2026-06-01"


def test_required_document_validation():
    results = RagService._validate(
        ["請求書", "見積書"],
        {"請求書"},
        ApprovalForm(vendor="ABC株式会社", service_name="Cloud", amount=120000),
    )
    assert [item.code for item in results] == ["REQUIRED_DOCUMENT_MISSING"]
    assert "見積書" in results[0].message
