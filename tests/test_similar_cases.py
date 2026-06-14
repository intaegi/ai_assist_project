from backend.app.schemas.models import ApprovalForm
from backend.app.services.rag_service import RagService


def test_similar_cases_prioritize_matching_category_and_amount():
    references = [
        {
            "id": "ai",
            "case_id": "ai",
            "knowledge_type": "past_case",
            "title": "開発支援AIサービス利用料",
            "approval_category_no": "IT-420",
            "amount": 98000,
            "@search.score": 0.04,
        },
        {
            "id": "cloud",
            "case_id": "cloud",
            "knowledge_type": "past_case",
            "title": "クラウド監視サービス年間利用料",
            "approval_category_no": "IT-410",
            "amount": 132000,
            "@search.score": 0.03,
        },
    ]

    result = RagService._similar_cases(
        references,
        ApprovalForm(approval_category_no="IT-410", amount=132000),
    )

    assert result[0].case_id == "cloud"
    assert "決裁科目番号が一致" in result[0].reason
