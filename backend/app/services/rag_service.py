from typing import Any

from backend.app.schemas.models import (
    ApprovalForm,
    CaseRecord,
    SimilarCase,
    SourceRef,
    ValidationResult,
    utc_now,
)


class RagService:
    def __init__(self, data_store: Any, blob_store: Any, document_service: Any, ai_service: Any, search_service: Any):
        self.data_store = data_store
        self.blob_store = blob_store
        self.document_service = document_service
        self.ai_service = ai_service
        self.search_service = search_service

    def generate(self, case: CaseRecord) -> CaseRecord:
        requirement = self.data_store.get_requirement(case.business_category, case.approval_type) or {}
        document_text = self.document_service.joined_text(case.files)
        extracted = self.document_service.extract_basic_fields(document_text)
        if case.amount is not None:
            extracted["amount"] = case.amount
        query = " ".join(
            filter(
                None,
                [
                    case.title,
                    case.description,
                    str(extracted.get("vendor", "")),
                    str(extracted.get("service_name", "")),
                    case.approval_category_no,
                ],
            )
        )
        references = self.search_service.search(
            query=query,
            business_category=case.business_category,
            approval_type=case.approval_type,
        )
        required_documents = requirement.get("required_documents", [])
        payload = self.ai_service.generate(
            description=case.description,
            document_text=document_text,
            extracted_fields=extracted,
            references=references,
            required_documents=required_documents,
        )
        present_documents = self.document_service.document_types(case.files)
        validations = self._validate(required_documents, present_documents, payload.approval_form)
        case.extracted_fields = payload.extracted_fields
        case.summary = payload.summary
        case.approval_form = payload.approval_form
        case.title = payload.approval_form.title
        case.amount = payload.approval_form.amount
        case.checklist = payload.checklist
        case.validation_results = validations
        case.similar_cases = self._similar_cases(references)
        case.field_sources = self._field_sources(case, document_text, references)
        case.status = "generated"
        case.current_version += 1
        case.last_generated_at = utc_now()
        case.updated_at = utc_now()
        case.versions.append(
            {
                "version": case.current_version,
                "approval_form": case.approval_form.model_dump(mode="json"),
                "field_sources": {
                    key: [source.model_dump(mode="json") for source in value]
                    for key, value in case.field_sources.items()
                },
                "instruction": "initial_generation",
                "created_at": utc_now(),
            }
        )
        self.data_store.save_case(case.model_dump(mode="json"))
        return case

    def revise(self, case: CaseRecord, instruction: str, target_field: str) -> CaseRecord:
        case.approval_form = self.ai_service.revise(case.approval_form, instruction, target_field)
        case.current_version += 1
        case.updated_at = utc_now()
        case.last_generated_at = utc_now()
        case.chat_logs.extend(
            [
                {"role": "user", "message": instruction, "target_field": target_field, "created_at": utc_now()},
                {"role": "assistant", "message": "決裁案を更新しました。", "target_field": target_field, "created_at": utc_now()},
            ]
        )
        case.versions.append(
            {
                "version": case.current_version,
                "approval_form": case.approval_form.model_dump(mode="json"),
                "instruction": instruction,
                "created_at": utc_now(),
            }
        )
        self.data_store.save_case(case.model_dump(mode="json"))
        return case

    def refresh_validation(self, case: CaseRecord) -> CaseRecord:
        requirement = self.data_store.get_requirement(case.business_category, case.approval_type) or {}
        present_documents = self.document_service.document_types(case.files)
        case.validation_results = self._validate(
            requirement.get("required_documents", []),
            present_documents,
            case.approval_form,
        )
        return case

    @staticmethod
    def _validate(
        required_documents: list[str],
        present_documents: set[str],
        form: ApprovalForm,
    ) -> list[ValidationResult]:
        results = []
        for document in required_documents:
            if document not in present_documents:
                results.append(
                    ValidationResult(
                        severity="error",
                        code="REQUIRED_DOCUMENT_MISSING",
                        message=f"必要書類「{document}」を確認できません。",
                        actions=["upload_file", "mark_exception"],
                    )
                )
        for field, label in (("vendor", "取引先"), ("service_name", "製品・サービス名"), ("amount", "金額")):
            if not getattr(form, field):
                results.append(
                    ValidationResult(
                        severity="warning",
                        code=f"{field.upper()}_NOT_FOUND",
                        message=f"{label}を資料から確認できません。",
                        actions=["manual_input"],
                    )
                )
        if not results:
            results.append(
                ValidationResult(
                    severity="success",
                    code="BASIC_CHECKS_PASSED",
                    message="基本項目と必要書類を確認しました。",
                )
            )
        return results

    @staticmethod
    def _similar_cases(references: list[dict[str, Any]]) -> list[SimilarCase]:
        result = []
        for item in references:
            if item.get("knowledge_type") != "past_case" and item.get("source_type") != "past_case":
                continue
            result.append(
                SimilarCase(
                    case_id=str(item.get("case_id") or item.get("id")),
                    title=str(item.get("title", "過去決裁")),
                    score=float(item.get("@search.score", 0)),
                    reason="カテゴリ、決裁種類、申請内容が類似",
                    approval_category_no=item.get("approval_category_no"),
                    amount=item.get("amount"),
                )
            )
        return result[:3]

    @staticmethod
    def _field_sources(
        case: CaseRecord,
        document_text: str,
        references: list[dict[str, Any]],
    ) -> dict[str, list[SourceRef]]:
        sources: dict[str, list[SourceRef]] = {}
        for file in case.files:
            for page in file.pages:
                text = str(page.get("text", ""))
                for field, value in case.extracted_fields.items():
                    if value not in (None, "") and str(value).replace(".0", "") in text.replace(",", ""):
                        sources.setdefault(field, []).append(
                            SourceRef(
                                source_type="uploaded_document",
                                file_id=file.id,
                                file_name=file.file_name,
                                page=int(page["page"]),
                                quote=text[:180],
                            )
                        )
        if references:
            item = references[0]
            sources.setdefault("body", []).append(
                SourceRef(
                    source_type=str(item.get("knowledge_type", "reference")),
                    source_id=str(item.get("id", "")),
                    title=str(item.get("title", "")),
                    quote=str(item.get("content", ""))[:180],
                )
            )
        return sources
