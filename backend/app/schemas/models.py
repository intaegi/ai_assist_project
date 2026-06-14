from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RequiredField(BaseModel):
    key: str
    label: str
    type: str = "text"
    required: bool = True


class ConditionalDocument(BaseModel):
    document: str
    condition: str


class RequirementConfig(BaseModel):
    id: str | None = None
    business_category: str
    approval_type: str
    required_fields: list[RequiredField] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    conditional_documents: list[ConditionalDocument] = Field(default_factory=list)
    form_template: dict[str, Any] = Field(default_factory=dict)
    updated_by: str = "demo-user"
    updated_at: str = Field(default_factory=utc_now)


class SourceRef(BaseModel):
    source_type: str
    source_id: str | None = None
    file_id: str | None = None
    file_name: str | None = None
    page: int | None = None
    title: str | None = None
    quote: str | None = None


class SimilarCase(BaseModel):
    case_id: str
    title: str
    score: float
    reason: str
    approval_category_no: str | None = None
    amount: float | None = None


class ValidationResult(BaseModel):
    severity: Literal["error", "warning", "info", "success"]
    code: str
    message: str
    actions: list[str] = Field(default_factory=list)
    basis: dict[str, Any] | None = None


class ChecklistVerificationItem(BaseModel):
    item: str
    status: Literal["verified", "action_required", "not_verifiable"]
    message: str
    evidence: list[str] = Field(default_factory=list)


class ChecklistVerificationPayload(BaseModel):
    results: list[ChecklistVerificationItem] = Field(default_factory=list)


class ApprovalForm(BaseModel):
    title: str = ""
    vendor: str = ""
    service_name: str = ""
    service_start_date: str | None = None
    service_end_date: str | None = None
    amount: float | None = None
    approval_category_no: str = ""
    body: str = ""
    required_documents: list[str] = Field(default_factory=list)


class FileRecord(BaseModel):
    id: str
    case_id: str
    file_name: str
    content_type: str
    size: int
    storage_path: str
    pages: list[dict[str, Any]] = Field(default_factory=list)
    copied_from_case_id: str | None = None
    requires_reconfirmation: bool = False


class CaseRecord(BaseModel):
    id: str
    case_id: str
    requester_id: str = "demo-user"
    business_category: str
    business_category_other: str | None = None
    approval_type: str
    approval_type_other: str | None = None
    title: str = ""
    description: str
    approval_no: str = ""
    approval_category_no: str = ""
    amount: float | None = None
    category_fields: dict[str, Any] = Field(default_factory=dict)
    status: Literal["editing", "processing", "generated", "failed"] = "editing"
    files: list[FileRecord] = Field(default_factory=list)
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    approval_form: ApprovalForm = Field(default_factory=ApprovalForm)
    checklist: list[str] = Field(default_factory=list)
    checklist_verification: list[ChecklistVerificationItem] = Field(default_factory=list)
    field_sources: dict[str, list[SourceRef]] = Field(default_factory=dict)
    validation_results: list[ValidationResult] = Field(default_factory=list)
    resolution_notices: list[ValidationResult] = Field(default_factory=list)
    similar_cases: list[SimilarCase] = Field(default_factory=list)
    chat_logs: list[dict[str, Any]] = Field(default_factory=list)
    versions: list[dict[str, Any]] = Field(default_factory=list)
    cloned_from_case_id: str | None = None
    current_version: int = 0
    last_generated_at: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class CasePatch(BaseModel):
    business_category: str | None = None
    business_category_other: str | None = None
    approval_type: str | None = None
    approval_type_other: str | None = None
    description: str | None = None
    amount: float | None = None
    title: str | None = None
    approval_no: str | None = None
    approval_category_no: str | None = None
    approval_form: ApprovalForm | None = None
    checklist: list[str] | None = None
    category_fields: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    instruction: str
    target_field: str = "body"
    current_version: int | None = None


class GenerationRequest(BaseModel):
    instruction: str = "追加書類を反映して決裁案を再作成"


class MaterialRecord(BaseModel):
    id: str
    business_category: str
    approval_type: str
    knowledge_type: str
    title: str
    file_name: str
    storage_path: str
    content: str = ""


class GenerationPayload(BaseModel):
    summary: str
    extracted_fields: dict[str, Any]
    approval_form: ApprovalForm
    checklist: list[str]
    missing_information: list[str] = Field(default_factory=list)
