import json
from datetime import date
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
        validations = self._validate(
            required_documents,
            present_documents,
            payload.approval_form,
            requirement.get("conditional_documents", []),
            " ".join([case.title, case.description, payload.approval_form.body]),
            requirement.get("required_fields", []),
        )
        validations = self._merge_validations(
            validations,
            self._document_consistency_validations(case, payload.approval_form),
        )
        case.extracted_fields = payload.extracted_fields
        case.summary = payload.summary
        case.approval_form = payload.approval_form
        case.title = payload.approval_form.title
        case.amount = payload.approval_form.amount
        case.checklist = self._reconcile_checklist(payload.checklist, validations)
        case.validation_results = validations
        case.similar_cases = self._similar_cases(references, payload.approval_form)
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
        self._save_generated_output(case)
        self.data_store.save_case(case.model_dump(mode="json"))
        return case

    def revise(self, case: CaseRecord, instruction: str, target_field: str) -> CaseRecord:
        case.approval_form = self.ai_service.revise(case.approval_form, instruction, target_field)
        self.refresh_validation(case)
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
        self._save_generated_output(case)
        self.data_store.save_case(case.model_dump(mode="json"))
        return case

    def _save_generated_output(self, case: CaseRecord) -> None:
        path = f"cases/{case.case_id}/versions/{case.current_version}.json"
        self.blob_store.upload(
            "generated-outputs",
            path,
            json.dumps(
                {
                    "case_id": case.case_id,
                    "version": case.current_version,
                    "approval_form": case.approval_form.model_dump(mode="json"),
                    "summary": case.summary,
                    "checklist": case.checklist,
                    "validation_results": [
                        item.model_dump(mode="json")
                        for item in case.validation_results
                    ],
                    "created_at": case.last_generated_at,
                },
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
            "application/json",
        )

    def refresh_validation(self, case: CaseRecord) -> CaseRecord:
        requirement = self.data_store.get_requirement(case.business_category, case.approval_type) or {}
        present_documents = self.document_service.document_types(case.files)
        case.validation_results = self._validate(
            requirement.get("required_documents", []),
            present_documents,
            case.approval_form,
            requirement.get("conditional_documents", []),
            " ".join([case.title, case.description, case.approval_form.body]),
            requirement.get("required_fields", []),
        )
        case.validation_results = self._merge_validations(
            case.validation_results,
            self._document_consistency_validations(case, case.approval_form),
        )
        case.checklist = self._reconcile_checklist(case.checklist, case.validation_results)
        return case

    def _document_consistency_validations(
        self,
        case: CaseRecord,
        form: ApprovalForm,
    ) -> list[ValidationResult]:
        field_specs = (
            ("vendor", "取引先", "DOCUMENT_VENDOR_MISMATCH"),
            ("service_name", "製品・サービス名", "DOCUMENT_SERVICE_NAME_MISMATCH"),
            ("amount", "金額", "DOCUMENT_AMOUNT_MISMATCH"),
            ("service_start_date", "利用開始日", "DOCUMENT_SERVICE_PERIOD_MISMATCH"),
            ("service_end_date", "利用終了日", "DOCUMENT_SERVICE_PERIOD_MISMATCH"),
        )
        extracted = [
            {
                "document": self.document_service.document_label(file),
                "file_name": file.file_name,
                "values": self.document_service.extract_file_fields(file),
            }
            for file in case.files
        ]
        results: list[ValidationResult] = []
        period_messages: list[str] = []
        period_basis: dict[str, Any] = {}

        for field, label, code in field_specs:
            document_values = [
                {
                    "document": item["document"],
                    "file_name": item["file_name"],
                    "value": item["values"][field],
                }
                for item in extracted
                if item["values"].get(field) not in (None, "")
            ]
            normalized_values = {
                self._normalize_comparison_value(item["value"], field)
                for item in document_values
            }
            if len(document_values) < 2 or len(normalized_values) <= 1:
                continue

            details = " / ".join(
                f"{item['document']}: {self._display_comparison_value(item['value'], field)}"
                for item in document_values
            )
            form_value = getattr(form, field)
            form_text = self._display_comparison_value(form_value, field)
            message = f"添付書類間で{label}が一致しません。{details} / AI決裁フォーム: {form_text}"
            basis = {
                "field": field,
                "documents": document_values,
                "form_value": form_value,
            }
            if code == "DOCUMENT_SERVICE_PERIOD_MISMATCH":
                period_messages.append(message)
                period_basis[field] = basis
                continue
            results.append(
                ValidationResult(
                    severity="warning",
                    code=code,
                    message=message,
                    actions=["compare_documents", "manual_confirm"],
                    basis=basis,
                )
            )

        if period_messages:
            results.append(
                ValidationResult(
                    severity="warning",
                    code="DOCUMENT_SERVICE_PERIOD_MISMATCH",
                    message=" ".join(period_messages),
                    actions=["compare_documents", "manual_confirm"],
                    basis=period_basis,
                )
            )
        return results

    @staticmethod
    def _normalize_comparison_value(value: Any, field: str) -> str:
        if value in (None, ""):
            return ""
        if field == "amount":
            return str(int(float(value)))
        return "".join(str(value).split())

    @staticmethod
    def _display_comparison_value(value: Any, field: str) -> str:
        if value in (None, ""):
            return "未入力"
        if field == "amount":
            return f"{float(value):,.0f}円"
        return str(value)

    @staticmethod
    def _merge_validations(
        base: list[ValidationResult],
        additional: list[ValidationResult],
    ) -> list[ValidationResult]:
        if not additional:
            return base
        return [item for item in base if item.code != "BASIC_CHECKS_PASSED"] + additional

    @staticmethod
    def _reconcile_checklist(
        checklist: list[str],
        validations: list[ValidationResult],
    ) -> list[str]:
        current = [item for item in checklist if not item.startswith("要確認: ")]
        mismatch_codes = {item.code for item in validations}
        conflict_terms = {
            "DOCUMENT_AMOUNT_MISMATCH": ("金額", "一致"),
            "DOCUMENT_VENDOR_MISMATCH": ("取引先", "一致"),
            "DOCUMENT_SERVICE_NAME_MISMATCH": ("サービス", "一致"),
            "DOCUMENT_SERVICE_PERIOD_MISMATCH": ("期間", "一致"),
        }
        for code, terms in conflict_terms.items():
            if code in mismatch_codes:
                current = [
                    item
                    for item in current
                    if not all(term in item for term in terms)
                ]
        for validation in validations:
            if validation.severity in {"error", "warning"}:
                item = f"要確認: {validation.message}"
                if item not in current:
                    current.append(item)
        return current

    @staticmethod
    def _validate(
        required_documents: list[str],
        present_documents: set[str],
        form: ApprovalForm,
        conditional_documents: list[dict[str, Any]] | None = None,
        context: str = "",
        required_fields: list[dict[str, Any]] | None = None,
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
        for item in conditional_documents or []:
            document = str(item.get("document", ""))
            condition = str(item.get("condition", ""))
            if document and document not in present_documents and RagService._condition_applies(condition, form, context):
                results.append(
                    ValidationResult(
                        severity="warning",
                        code="CONDITIONAL_DOCUMENT_MISSING",
                        message=f"条件付き必要書類「{document}」が不足しています（条件: {condition}）。",
                        actions=["upload_file", "confirm_condition"],
                        basis={"document": document, "condition": condition},
                    )
                )
        required_keys = {
            str(item.get("key"))
            for item in (required_fields or [])
            if item.get("required", True)
        } or {"vendor", "service_name", "amount"}
        for field, label in (("vendor", "取引先"), ("service_name", "製品・サービス名"), ("amount", "金額")):
            if field not in required_keys:
                continue
            if not getattr(form, field):
                results.append(
                    ValidationResult(
                        severity="warning",
                        code=f"{field.upper()}_NOT_FOUND",
                        message=f"{label}を資料から確認できません。",
                        actions=["manual_input"],
                    )
                )
        if "service_period" in required_keys and not (form.service_start_date and form.service_end_date):
            results.append(
                ValidationResult(
                    severity="warning",
                    code="SERVICE_PERIOD_NOT_FOUND",
                    message="利用期間（開始日・終了日）を確認または入力してください。",
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
    def _condition_applies(condition: str, form: ApprovalForm, context: str) -> bool:
        checks: list[bool] = []
        if "10万円以上" in condition:
            checks.append(bool(form.amount is not None and form.amount >= 100000))
        if "年間契約" in condition:
            annual = "年間" in context
            if form.service_start_date and form.service_end_date:
                try:
                    start = date.fromisoformat(form.service_start_date)
                    end = date.fromisoformat(form.service_end_date)
                    annual = annual or (end - start).days >= 300
                except ValueError:
                    pass
            checks.append(annual)
        for keyword in ("新規契約", "新規取引", "新規取引先", "継続契約"):
            if keyword in condition:
                checks.append(keyword in context)
        return any(checks)

    @staticmethod
    def _similar_cases(references: list[dict[str, Any]], form: ApprovalForm) -> list[SimilarCase]:
        result = []
        for item in references:
            if item.get("knowledge_type") != "past_case" and item.get("source_type") != "past_case":
                continue
            score = float(item.get("@search.score", 0))
            reasons = ["カテゴリ・決裁種類が一致"]
            if form.approval_category_no and item.get("approval_category_no") == form.approval_category_no:
                score += 2
                reasons.append("決裁科目番号が一致")
            if form.amount and item.get("amount") is not None:
                difference_ratio = abs(float(item["amount"]) - form.amount) / max(form.amount, 1)
                if difference_ratio <= 0.1:
                    score += 1
                    reasons.append("金額帯が近い")
            result.append(
                SimilarCase(
                    case_id=str(item.get("case_id") or item.get("id")),
                    title=str(item.get("title", "過去決裁")),
                    score=score,
                    reason="、".join(reasons),
                    approval_category_no=item.get("approval_category_no"),
                    amount=item.get("amount"),
                )
            )
        return sorted(result, key=lambda item: item.score, reverse=True)[:3]

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
                                quote=RagService._matching_quote(text, value),
                            )
                        )
        if references:
            item = references[0]
            sources.setdefault("body", []).append(
                SourceRef(
                    source_type=str(item.get("knowledge_type", "reference")),
                    source_id=str(item.get("source_id") or item.get("id", "")),
                    title=str(item.get("title", "")),
                    quote=str(item.get("content", ""))[:180],
                )
            )
        return sources

    @staticmethod
    def _matching_quote(text: str, value: Any) -> str:
        normalized_value = str(value).replace(",", "").replace(".0", "").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            normalized_line = line.replace(",", "").replace(".0", "")
            if normalized_value and normalized_value in normalized_line:
                start = max(0, index - 1)
                end = min(len(lines), index + 2)
                return "\n".join(lines[start:end])[:300]
        return text[:300]
