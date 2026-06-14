from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from backend.app.schemas.models import MaterialRecord, RequirementConfig

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/requirements")
def list_requirements(request: Request) -> list[dict]:
    return request.app.state.services.data_store.list_requirements()


@router.post("/requirements")
def save_requirement(payload: RequirementConfig, request: Request) -> dict:
    if not payload.id:
        payload.id = f"requirement:{payload.business_category}:{payload.approval_type}"
    return request.app.state.services.data_store.save_requirement(payload.model_dump(mode="json"))


@router.post("/materials")
async def upload_material(
    request: Request,
    business_category: str = Form(...),
    approval_type: str = Form(...),
    knowledge_type: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    services = request.app.state.services
    content = await file.read()
    material_id = f"material_{uuid4().hex[:12]}"
    file_name = Path(file.filename or "material").name
    path = f"settings/{business_category}/{approval_type}/{material_id}/{file_name}"
    storage_path = services.blob_store.upload(
        "config-materials",
        path,
        content,
        file.content_type or "application/octet-stream",
    )
    pages = services.document_service.extract_pages(content, file.content_type or "")
    text = "\n".join(str(page["text"]) for page in pages)
    if not text and file_name.lower().endswith((".md", ".txt")):
        text = content.decode("utf-8", errors="replace")
    material = MaterialRecord(
        id=material_id,
        business_category=business_category,
        approval_type=approval_type,
        knowledge_type=knowledge_type,
        title=title,
        file_name=file_name,
        storage_path=storage_path,
        content=text,
    )
    services.data_store.save_material(material.model_dump(mode="json"))
    return material.model_dump(mode="json")


@router.post("/reindex")
def reindex(request: Request) -> dict[str, int]:
    services = request.app.state.services
    documents = services.data_store.list_materials() + services.data_store.list_past_decisions()
    if not documents:
        raise HTTPException(status_code=400, detail="インデックス対象の資料がありません。")
    normalized = []
    for item in documents:
        normalized.append(
            {
                "id": item["id"],
                "case_id": item.get("case_id", ""),
                "knowledge_type": item.get("knowledge_type", "past_case"),
                "rule_priority": int(item.get("rule_priority", 2)),
                "business_category": item.get("business_category", "all"),
                "approval_type": item.get("approval_type", "all"),
                "approval_no": item.get("approval_no", ""),
                "title": item.get("title", ""),
                "approval_category_no": item.get("approval_category_no", ""),
                "amount": item.get("amount"),
                "content": item.get("content") or item.get("body", ""),
                "required_documents": item.get("required_documents", []),
                "source_type": item.get("source_type", item.get("knowledge_type", "reference")),
                "file_name": item.get("file_name", ""),
                "page": item.get("page"),
            }
        )
    count = services.search_service.index_documents(normalized)
    return {"indexed": count}
