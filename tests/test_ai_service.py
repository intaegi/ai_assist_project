import json

from backend.app.core.config import Settings
from backend.app.schemas.models import ApprovalForm
from backend.app.services.ai_service import AzureAIService, LocalAIService


def test_azure_revision_preserves_fields_outside_selected_target(monkeypatch):
    service = AzureAIService(
        Settings(
            _env_file=None,
            azure_openai_endpoint="https://example.openai.azure.com",
            azure_openai_api_key="test",
            azure_openai_chat_deployment="chat",
        )
    )
    monkeypatch.setattr(
        service,
        "_json_completion",
        lambda _: {
            "title": "AIが変更したタイトル",
            "vendor": "AIが変更した取引先",
            "service_name": "AIが変更したサービス",
            "amount": 999999,
            "body": "短縮した本文",
            "required_documents": ["請求書"],
        },
    )
    original = ApprovalForm(
        title="元タイトル",
        vendor="元取引先",
        service_name="元サービス",
        amount=132000,
        body="元の本文",
        required_documents=["請求書"],
    )

    revised = service.revise(original, "本文だけ短縮", "body")

    assert revised.body == "短縮した本文"
    assert revised.title == "元タイトル"
    assert revised.vendor == "元取引先"
    assert revised.amount == 132000


def test_local_revision_updates_selected_amount_only():
    original = ApprovalForm(
        title="元タイトル",
        vendor="元取引先",
        amount=132000,
        body="元の本文",
    )

    revised = LocalAIService().revise(original, "金額を150,000円に変更", "amount")

    assert revised.amount == 150000
    assert revised.title == "元タイトル"
    assert revised.vendor == "元取引先"
    assert revised.body == "元の本文"


def test_local_revision_can_shorten_body_to_one_sentence():
    original = ApprovalForm(
        title="元タイトル",
        body="第一文です。第二文です。第三文です。",
    )

    revised = LocalAIService().revise(
        original,
        "決裁本文を1文にまとめて",
        "body",
    )

    assert revised.body == "第一文です。"


def test_azure_generation_sends_additional_instruction(monkeypatch):
    service = AzureAIService(
        Settings(
            _env_file=None,
            azure_openai_endpoint="https://example.openai.azure.com",
            azure_openai_api_key="test",
            azure_openai_chat_deployment="chat",
        )
    )
    captured = {}

    def fake_completion(messages):
        captured["request"] = json.loads(messages[1]["content"])
        return {
            "summary": "更新済み",
            "extracted_fields": {},
            "approval_form": {
                "title": "更新案",
                "body": "追加請求書を反映しました。",
            },
            "checklist": [],
        }

    monkeypatch.setattr(service, "_json_completion", fake_completion)

    service.generate(
        description="年間利用料",
        document_text="請求書",
        extracted_fields={},
        references=[],
        required_documents=["請求書"],
        instruction="追加請求書の支払期限を反映してください。",
    )

    assert captured["request"]["additional_instruction"] == (
        "追加請求書の支払期限を反映してください。"
    )
