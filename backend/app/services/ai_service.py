import json
from typing import Any

from openai import AzureOpenAI
from pydantic import ValidationError

from backend.app.core.config import Settings
from backend.app.schemas.models import (
    ApprovalForm,
    ChecklistVerificationItem,
    ChecklistVerificationPayload,
    GenerationPayload,
)


SYSTEM_PROMPT = """あなたは社内決裁申請書の作成支援AIです。
検索された規程と必要書類基準を最優先し、過去事例は表現の参考だけにしてください。
資料にない事実を推測で確定しないでください。出力は指定されたJSONだけにしてください。"""


class LocalAIService:
    def generate(
        self,
        *,
        description: str,
        document_text: str,
        extracted_fields: dict[str, Any],
        references: list[dict[str, Any]],
        required_documents: list[str],
    ) -> GenerationPayload:
        vendor = str(extracted_fields.get("vendor", ""))
        service = str(extracted_fields.get("service_name", ""))
        amount = extracted_fields.get("amount")
        title_parts = [part for part in (vendor, service) if part]
        title = " ".join(title_parts) or description[:30] or "決裁申請"
        body = description.strip()
        if references:
            body += "\n\n社内基準と類似事例を参照し、添付資料の確認結果を反映しています。"
        return GenerationPayload(
            summary=description[:160],
            extracted_fields=extracted_fields,
            approval_form=ApprovalForm(
                title=f"{title}に関する決裁",
                vendor=vendor,
                service_name=service,
                amount=amount,
                body=body,
                required_documents=required_documents,
            ),
            checklist=[f"{name}が添付されていること" for name in required_documents]
            + ["金額、取引先、利用期間を原本と照合すること"],
        )

    def revise(self, form: ApprovalForm, instruction: str, target_field: str) -> ApprovalForm:
        updated = form.model_copy(deep=True)
        if target_field == "body":
            if "3文" in instruction:
                sentences = [part.strip() for part in updated.body.replace("。", "。\n").splitlines() if part.strip()]
                updated.body = "".join(sentences[:3])
            else:
                updated.body = f"{updated.body}\n\n修正指示: {instruction}".strip()
        return updated

    def verify_checklist(
        self,
        *,
        checklist: list[str],
        form: ApprovalForm,
        document_text: str,
        validation_results: list[dict[str, Any]],
    ) -> ChecklistVerificationPayload:
        issues = [
            str(item.get("message", ""))
            for item in validation_results
            if item.get("severity") in {"error", "warning"}
        ]
        results = []
        normalized_text = document_text.replace(",", "")
        for item in checklist:
            if item.startswith("要確認:"):
                results.append(
                    ChecklistVerificationItem(
                        item=item,
                        status="action_required",
                        message="未解消の警告があるため、ユーザー確認が必要です。",
                        evidence=issues[:3],
                    )
                )
                continue
            evidence = []
            if "金額" in item and form.amount is not None:
                amount = str(int(form.amount))
                if amount in normalized_text:
                    evidence.append(f"添付書類とフォームの金額: {form.amount:,.0f}円")
            if "取引先" in item and form.vendor and form.vendor in document_text:
                evidence.append(f"添付書類とフォームの取引先: {form.vendor}")
            if "利用期間" in item and form.service_start_date and form.service_end_date:
                evidence.append(
                    f"フォームの利用期間: {form.service_start_date} ～ {form.service_end_date}"
                )
            if "添付" in item or "必要書類" in item:
                matching_issues = [issue for issue in issues if "書類" in issue]
                if not matching_issues:
                    evidence.append("必要書類の未解消警告はありません。")
            results.append(
                ChecklistVerificationItem(
                    item=item,
                    status="verified" if evidence else "not_verifiable",
                    message=(
                        "添付書類とフォームから確認できました。"
                        if evidence
                        else "現在の資料だけでは自動確認できません。"
                    ),
                    evidence=evidence,
                )
            )
        return ChecklistVerificationPayload(results=results)

    def embed(self, text: str) -> list[float]:
        seed = [float((ord(char) % 31) / 31) for char in text[:64]]
        return (seed + [0.0] * 64)[:64]

    def check(self) -> bool:
        return True


class AzureAIService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )

    def _json_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.settings.azure_openai_chat_deployment,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=messages,
        )
        return json.loads(response.choices[0].message.content or "{}")

    def generate(
        self,
        *,
        description: str,
        document_text: str,
        extracted_fields: dict[str, Any],
        references: list[dict[str, Any]],
        required_documents: list[str],
    ) -> GenerationPayload:
        request = {
            "description": description,
            "document_text": document_text[:18000],
            "pre_extracted_fields": extracted_fields,
            "references": references[:5],
            "required_documents": required_documents,
            "output_schema": GenerationPayload.model_json_schema(),
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
        ]
        last_error: Exception | None = None
        for _ in range(2):
            try:
                return GenerationPayload.model_validate(self._json_completion(messages))
            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                messages.append(
                    {
                        "role": "user",
                        "content": "前回のJSONはスキーマに適合しません。必須項目を満たすJSONだけを再出力してください。",
                    }
                )
        raise RuntimeError(f"AI応答を検証できませんでした: {last_error}")

    def revise(self, form: ApprovalForm, instruction: str, target_field: str) -> ApprovalForm:
        payload = {
            "current_form": form.model_dump(mode="json"),
            "instruction": instruction,
            "target_field": target_field,
            "output_schema": ApprovalForm.model_json_schema(),
        }
        result = self._json_completion(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ]
        )
        return ApprovalForm.model_validate(result)

    def verify_checklist(
        self,
        *,
        checklist: list[str],
        form: ApprovalForm,
        document_text: str,
        validation_results: list[dict[str, Any]],
    ) -> ChecklistVerificationPayload:
        payload = {
            "task": "チェックリストの各項目を、添付書類とフォームの明示的な根拠だけで確認してください。",
            "rules": [
                "根拠がある場合だけverifiedにする",
                "未解消のエラーまたは警告に関係する項目はaction_requiredにする",
                "資料から判断できない項目はnot_verifiableにする",
                "推測で確認済みにしない",
            ],
            "checklist": checklist,
            "current_form": form.model_dump(mode="json"),
            "document_text": document_text[:18000],
            "validation_results": validation_results,
            "output_schema": ChecklistVerificationPayload.model_json_schema(),
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        last_error: Exception | None = None
        for _ in range(2):
            try:
                return ChecklistVerificationPayload.model_validate(
                    self._json_completion(messages)
                )
            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                messages.append(
                    {
                        "role": "user",
                        "content": "全チェック項目を含む、スキーマ適合JSONだけを再出力してください。",
                    }
                )
        raise RuntimeError(f"チェックリストのAI判定を検証できませんでした: {last_error}")

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model=self.settings.azure_openai_embedding_deployment,
            input=text,
        )
        return response.data[0].embedding

    def check(self) -> bool:
        self.embed("接続確認")
        return True
