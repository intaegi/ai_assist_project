from backend.app.schemas.models import ApprovalForm, CaseRecord, FileRecord
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


def test_basic_field_extraction_includes_service_period():
    service = DocumentService()
    fields = service.extract_basic_fields(
        "契約期間: 2026年7月1日 ～ 2027年6月30日\n契約金額: 132,000円"
    )

    assert fields["service_start_date"] == "2026-07-01"
    assert fields["service_end_date"] == "2027-06-30"


def test_required_document_validation():
    results = RagService._validate(
        ["請求書", "見積書"],
        {"請求書"},
        ApprovalForm(vendor="ABC株式会社", service_name="Cloud", amount=120000),
    )
    assert [item.code for item in results] == ["REQUIRED_DOCUMENT_MISSING"]
    assert "見積書" in results[0].message


def test_conditional_document_validation_for_high_amount():
    results = RagService._validate(
        ["請求書"],
        {"請求書"},
        ApprovalForm(vendor="ABC株式会社", service_name="Cloud", amount=120000),
        [{"document": "見積書", "condition": "新規契約または10万円以上の場合"}],
    )

    assert [item.code for item in results] == ["CONDITIONAL_DOCUMENT_MISSING"]
    assert "見積書" in results[0].message


def test_conditional_document_validation_for_annual_contract():
    results = RagService._validate(
        ["請求書"],
        {"請求書", "見積書"},
        ApprovalForm(
            vendor="ABC株式会社",
            service_name="Cloud",
            amount=120000,
            service_start_date="2026-07-01",
            service_end_date="2027-06-30",
        ),
        [{"document": "契約書", "condition": "年間契約の場合"}],
    )

    assert [item.code for item in results] == ["CONDITIONAL_DOCUMENT_MISSING"]
    assert "契約書" in results[0].message


def test_required_service_period_validation():
    results = RagService._validate(
        ["請求書"],
        {"請求書"},
        ApprovalForm(vendor="ABC株式会社", service_name="Cloud", amount=120000),
        required_fields=[
            {"key": "vendor", "required": True},
            {"key": "service_name", "required": True},
            {"key": "amount", "required": True},
            {"key": "service_period", "required": True},
        ],
    )

    assert [item.code for item in results] == ["SERVICE_PERIOD_NOT_FOUND"]


def _file_record(file_id: str, file_name: str, text: str) -> FileRecord:
    return FileRecord(
        id=file_id,
        case_id="case-test",
        file_name=file_name,
        content_type="application/pdf",
        size=len(text),
        storage_path=file_name,
        pages=[{"page": 1, "text": text}],
    )


def _case_with_files(*files: FileRecord) -> CaseRecord:
    return CaseRecord(
        id="case-test",
        case_id="case-test",
        business_category="it",
        approval_type="支払",
        description="CloudGuard Pro年間利用料",
        files=list(files),
    )


def test_document_amount_mismatch_validation():
    rag = RagService(None, None, DocumentService(), None, None)
    case = _case_with_files(
        _file_record(
            "invoice",
            "invoice.pdf",
            "請求書\n請求元: ABC株式会社\nサービス名: Cloud\n請求金額: 88,000円",
        ),
        _file_record(
            "estimate",
            "estimate.pdf",
            "見積書\n会社名: ABC株式会社\n商品名: Cloud\n合計金額: 99,000円",
        ),
    )

    results = rag._document_consistency_validations(
        case,
        ApprovalForm(vendor="ABC株式会社", service_name="Cloud", amount=88000),
    )

    assert [item.code for item in results] == ["DOCUMENT_AMOUNT_MISMATCH"]
    assert "88,000円" in results[0].message
    assert "99,000円" in results[0].message


def test_document_vendor_and_period_mismatch_validation():
    rag = RagService(None, None, DocumentService(), None, None)
    case = _case_with_files(
        _file_record(
            "invoice",
            "invoice.pdf",
            "請求書\n請求元: ABC株式会社\nサービス名: Cloud\n"
            "利用期間: 2026年7月1日 ～ 2027年6月30日\n請求金額: 132,000円",
        ),
        _file_record(
            "contract",
            "contract.pdf",
            "契約書\n取引先: XYZ株式会社\nサービス名: Cloud\n"
            "契約期間: 2026年8月1日 ～ 2027年7月31日\n契約金額: 132,000円",
        ),
    )

    results = rag._document_consistency_validations(
        case,
        ApprovalForm(
            vendor="ABC株式会社",
            service_name="Cloud",
            amount=132000,
            service_start_date="2026-07-01",
            service_end_date="2027-06-30",
        ),
    )

    assert {item.code for item in results} == {
        "DOCUMENT_VENDOR_MISMATCH",
        "DOCUMENT_SERVICE_PERIOD_MISMATCH",
    }


def test_validation_warnings_are_added_to_checklist():
    validation = RagService._validate(
        ["請求書", "見積書"],
        {"請求書"},
        ApprovalForm(vendor="ABC株式会社", service_name="Cloud", amount=120000),
    )

    checklist = RagService._reconcile_checklist(["金額が一致していること"], validation)

    assert "金額が一致していること" in checklist
    assert any(item.startswith("要確認: 必要書類「見積書」") for item in checklist)


def test_resolved_document_notice_is_added_and_removed_if_missing_again():
    rag = RagService(None, None, DocumentService(), None, None)
    case = _case_with_files(_file_record("invoice", "invoice.pdf", "請求書"))
    previous = RagService._validate(
        ["請求書"],
        set(),
        ApprovalForm(vendor="ABC株式会社", service_name="Cloud", amount=120000),
    )
    case.validation_results = RagService._validate(
        ["請求書"],
        {"請求書"},
        ApprovalForm(vendor="ABC株式会社", service_name="Cloud", amount=120000),
    )

    rag.update_resolution_notices(case, previous)

    assert case.resolution_notices[0].code == "MISSING_DOCUMENT_RESOLVED"
    assert "請求書" in case.resolution_notices[0].message

    previous = list(case.validation_results)
    case.validation_results = RagService._validate(
        ["請求書"],
        set(),
        ApprovalForm(vendor="ABC株式会社", service_name="Cloud", amount=120000),
    )
    rag.update_resolution_notices(case, previous)

    assert case.resolution_notices == []


def test_condition_change_does_not_claim_document_was_attached():
    rag = RagService(None, None, DocumentService(), None, None)
    case = _case_with_files()
    previous = [
        RagService._validate(
            [],
            set(),
            ApprovalForm(
                vendor="ABC株式会社",
                service_name="Cloud",
                amount=120000,
                service_start_date="2026-07-01",
                service_end_date="2027-06-30",
            ),
            [{"document": "契約書", "condition": "年間契約の場合"}],
        )[0]
    ]
    case.validation_results = RagService._validate(
        [],
        set(),
        ApprovalForm(
            vendor="ABC株式会社",
            service_name="Cloud",
            amount=120000,
            service_start_date="2026-07-01",
            service_end_date="2026-07-31",
        ),
        [{"document": "契約書", "condition": "年間契約の場合"}],
    )

    rag.update_resolution_notices(case, previous)

    assert case.resolution_notices == []
