import json
from pathlib import Path
from typing import Any

from backend.app.schemas.models import RequirementConfig


def load_seed_data(project_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    sample_root = project_root / "sample_data"
    requirements = json.loads((sample_root / "requirements.json").read_text(encoding="utf-8"))
    decisions = json.loads((sample_root / "past_decisions.json").read_text(encoding="utf-8"))
    policy_path = sample_root / "policy_it_payment.md"
    materials = [
        {
            "id": "material_policy_it_payment",
            "business_category": "it",
            "approval_type": "支払",
            "knowledge_type": "policy",
            "rule_priority": 1,
            "title": "開発・IT 支払決裁基準",
            "file_name": policy_path.name,
            "storage_path": f"settings/it/支払/{policy_path.name}",
            "content": policy_path.read_text(encoding="utf-8"),
            "source_type": "policy",
        }
    ]
    return requirements, decisions, materials


def seed_store(data_store: Any, project_root: Path) -> dict[str, int]:
    requirements, decisions, materials = load_seed_data(project_root)
    for raw in requirements:
        data_store.save_requirement(RequirementConfig.model_validate(raw).model_dump(mode="json"))
    data_store.seed_past_decisions(decisions)
    existing_ids = {item["id"] for item in data_store.list_materials()}
    for material in materials:
        if material["id"] not in existing_ids:
            data_store.save_material(material)
    return {
        "requirements": len(requirements),
        "past_decisions": len(decisions),
        "materials": len(materials),
    }
