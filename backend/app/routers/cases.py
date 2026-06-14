import json
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from backend.app.schemas.models import CasePatch, CaseRecord, ChatRequest, FileRecord, utc_now

router = APIRouter(tags=["cases"])


def _get_case(request: Request, case_id: str) -> CaseRecord:
    item = request.app.state.services.data_store.get_case(case_id)
    if not item:
        raise HTTPException(status_code=404, detail="案件が見つかりません。")
    return CaseRecord.model_validate(item)


async def _store_file(request: Request, case_id: str, upload: UploadFile) -> FileRecord:
    services = request.app.state.services
    content = await upload.read()
    file_name = Path(upload.filename or "document").name
    file_id = f"file_{uuid4().hex[:12]}"
    path = f"cases/{case_id}/original/{file_id}_{file_name}"
    storage_path = services.blob_store.upload(
        "uploaded-documents",
        path,
        content,
        upload.content_type or "application/octet-stream",
    )
    record = services.document_service.create_file_record(
        case_id,
        file_name,
        upload.content_type or "application/octet-stream",
        content,
        storage_path,
    )
    record.id = file_id
    extracted_path = f"cases/{case_id}/text/{file_id}.json"
    services.blob_store.upload(
        "extracted-texts",
        extracted_path,
        json.dumps(
            {
                "case_id": case_id,
                "file_id": file_id,
                "file_name": file_name,
                "pages": record.pages,
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
        "application/json",
    )
    return record


@router.get("/requirements")
def get_requirements(request: Request, business_category: str, approval_type: str) -> dict:
    services = request.app.state.services
    requirement = services.data_store.get_requirement(business_category, approval_type)
    if requirement:
        return {**requirement, "source_status": "rule_found"}
    references = services.search_service.search(
        query=f"{business_category} {approval_type}",
        business_category=business_category,
        approval_type=approval_type,
        top=1,
    )
    return {
        "business_category": business_category,
        "approval_type": approval_type,
        "source_status": "history_only" if references else "no_reference",
        "required_fields": [
            {"key": "purpose", "label": "目的", "type": "textarea", "required": True},
            {"key": "vendor", "label": "取引先", "type": "text", "required": True},
            {"key": "service_name", "label": "製品・サービス名", "type": "text", "required": True},
            {"key": "amount", "label": "金額または未定理由", "type": "text", "required": True},
        ],
        "required_documents": [],
        "conditional_documents": [],
    }


@router.post("/cases")
async def create_case(
    request: Request,
    business_category: str = Form(...),
    approval_type: str = Form(...),
    description: str = Form(...),
    business_category_other: str | None = Form(None),
    approval_type_other: str | None = Form(None),
    title: str = Form(""),
    approval_no: str = Form(""),
    approval_category_no: str = Form(""),
    amount: str | None = Form(None),
    category_fields: str = Form("{}"),
    requester_id: str = Form("demo-user"),
    files: list[UploadFile] = File(default=[]),
) -> dict:
    case_id = f"case_{uuid4().hex[:12]}"
    try:
        parsed_fields = json.loads(category_fields or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="category_fieldsはJSON形式で指定してください。") from exc
    normalized_amount = float(amount) if amount not in (None, "") else None
    case = CaseRecord(
        id=case_id,
        case_id=case_id,
        requester_id=requester_id,
        business_category=business_category,
        business_category_other=business_category_other,
        approval_type=approval_type,
        approval_type_other=approval_type_other,
        description=description,
        title=title,
        approval_no=approval_no,
        approval_category_no=approval_category_no,
        amount=normalized_amount,
        category_fields=parsed_fields,
    )
    for upload in files:
        if upload.filename:
            case.files.append(await _store_file(request, case_id, upload))
    request.app.state.services.data_store.save_case(case.model_dump(mode="json"))
    return case.model_dump(mode="json")


@router.get("/cases")
def list_cases(request: Request) -> list[dict]:
    return request.app.state.services.data_store.list_cases()


@router.get("/cases/{case_id}")
def get_case(case_id: str, request: Request) -> dict:
    return _get_case(request, case_id).model_dump(mode="json")


@router.post("/cases/{case_id}/generate")
def generate_case(case_id: str, request: Request) -> dict:
    case = _get_case(request, case_id)
    case.status = "processing"
    request.app.state.services.data_store.save_case(case.model_dump(mode="json"))
    try:
        return request.app.state.services.rag_service.generate(case).model_dump(mode="json")
    except Exception as exc:
        case.status = "failed"
        case.updated_at = utc_now()
        request.app.state.services.data_store.save_case(case.model_dump(mode="json"))
        raise HTTPException(status_code=502, detail=f"決裁案の生成に失敗しました: {exc}") from exc


@router.patch("/cases/{case_id}")
def patch_case(case_id: str, payload: CasePatch, request: Request) -> dict:
    case = _get_case(request, case_id)
    for key in payload.model_fields_set:
        setattr(case, key, getattr(payload, key))
    request.app.state.services.rag_service.refresh_validation(case)
    case.updated_at = utc_now()
    request.app.state.services.data_store.save_case(case.model_dump(mode="json"))
    return case.model_dump(mode="json")


@router.post("/cases/{case_id}/chat")
def revise_case(case_id: str, payload: ChatRequest, request: Request) -> dict:
    case = _get_case(request, case_id)
    return request.app.state.services.rag_service.revise(
        case,
        payload.instruction,
        payload.target_field,
    ).model_dump(mode="json")


@router.post("/cases/{case_id}/files")
async def add_file(case_id: str, request: Request, file: UploadFile = File(...)) -> dict:
    case = _get_case(request, case_id)
    case.files.append(await _store_file(request, case_id, file))
    case.updated_at = utc_now()
    request.app.state.services.data_store.save_case(case.model_dump(mode="json"))
    return case.model_dump(mode="json")


@router.delete("/cases/{case_id}/files/{file_id}")
def delete_file(case_id: str, file_id: str, request: Request) -> dict:
    case = _get_case(request, case_id)
    match = next((item for item in case.files if item.id == file_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="ファイルが見つかりません。")
    request.app.state.services.blob_store.delete("uploaded-documents", match.storage_path)
    try:
        request.app.state.services.blob_store.delete(
            "extracted-texts",
            f"cases/{case_id}/text/{file_id}.json",
        )
    except Exception:
        # Older cases may predate extracted-text persistence.
        pass
    case.files = [item for item in case.files if item.id != file_id]
    case.updated_at = utc_now()
    request.app.state.services.data_store.save_case(case.model_dump(mode="json"))
    return case.model_dump(mode="json")


@router.get("/cases/{case_id}/files/{file_id}")
def get_file(case_id: str, file_id: str, request: Request) -> Response:
    case = _get_case(request, case_id)
    match = next((item for item in case.files if item.id == file_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="ファイルが見つかりません。")
    content = request.app.state.services.blob_store.download("uploaded-documents", match.storage_path)
    return Response(
        content=content,
        media_type=match.content_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(match.file_name)}"},
    )


@router.post("/cases/{case_id}/clone")
def clone_case(case_id: str, request: Request) -> dict:
    services = request.app.state.services
    source = _get_case(request, case_id)
    new_id = f"case_{uuid4().hex[:12]}"
    clone = source.model_copy(deep=True)
    clone.id = new_id
    clone.case_id = new_id
    clone.cloned_from_case_id = source.case_id
    clone.status = "editing"
    clone.current_version = 0
    clone.versions = []
    clone.chat_logs = []
    clone.created_at = utc_now()
    clone.updated_at = utc_now()
    clone.last_generated_at = None
    copied_files = []
    for file in source.files:
        new_file_id = f"file_{uuid4().hex[:12]}"
        destination = f"cases/{new_id}/original/{new_file_id}_{file.file_name}"
        storage_path = services.blob_store.copy(
            "uploaded-documents",
            file.storage_path,
            destination,
            file.content_type,
        )
        copied = file.model_copy(deep=True)
        copied.id = new_file_id
        copied.case_id = new_id
        copied.storage_path = storage_path
        copied.copied_from_case_id = source.case_id
        copied.requires_reconfirmation = True
        services.blob_store.upload(
            "extracted-texts",
            f"cases/{new_id}/text/{new_file_id}.json",
            json.dumps(
                {
                    "case_id": new_id,
                    "file_id": new_file_id,
                    "file_name": copied.file_name,
                    "pages": copied.pages,
                    "copied_from_case_id": source.case_id,
                },
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
            "application/json",
        )
        copied_files.append(copied)
    clone.files = copied_files
    services.data_store.save_case(clone.model_dump(mode="json"))
    return clone.model_dump(mode="json")
