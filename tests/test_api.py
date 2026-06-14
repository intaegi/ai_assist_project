def create_case(client, category="it", approval_type="支払"):
    response = client.post(
        "/cases",
        data={
            "business_category": category,
            "approval_type": approval_type,
            "description": "開発チームで利用するクラウドサービスの年間利用料を支払います。",
            "requester_id": "demo-user",
            "category_fields": "{}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_requirements_are_seeded(client):
    response = client.get(
        "/requirements",
        params={"business_category": "it", "approval_type": "支払"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"] == "rule_found"
    assert "請求書" in payload["required_documents"]


def test_generate_warns_when_required_document_is_missing(client):
    case = create_case(client)
    response = client.post(f"/cases/{case['case_id']}/generate")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "generated"
    assert payload["current_version"] == 1
    codes = {item["code"] for item in payload["validation_results"]}
    assert "REQUIRED_DOCUMENT_MISSING" in codes


def test_patch_auto_saves_form(client):
    case = create_case(client)
    generated = client.post(f"/cases/{case['case_id']}/generate").json()
    form = generated["approval_form"]
    form["vendor"] = "テスト株式会社"
    response = client.patch(
        f"/cases/{case['case_id']}",
        json={"approval_form": form},
    )
    assert response.status_code == 200
    assert response.json()["approval_form"]["vendor"] == "テスト株式会社"
    codes = {item["code"] for item in response.json()["validation_results"]}
    assert "VENDOR_NOT_FOUND" not in codes


def test_chat_creates_new_version(client):
    case = create_case(client)
    client.post(f"/cases/{case['case_id']}/generate")
    response = client.post(
        f"/cases/{case['case_id']}/chat",
        json={"instruction": "本文を3文以内にしてください。", "target_field": "body"},
    )
    assert response.status_code == 200
    assert response.json()["current_version"] == 2
    assert len(response.json()["chat_logs"]) == 2


def test_clone_creates_editable_case(client):
    case = create_case(client)
    generated = client.post(f"/cases/{case['case_id']}/generate").json()
    response = client.post(f"/cases/{case['case_id']}/clone")
    assert response.status_code == 200
    clone = response.json()
    assert clone["case_id"] != generated["case_id"]
    assert clone["cloned_from_case_id"] == generated["case_id"]
    assert clone["status"] == "editing"
    assert clone["current_version"] == 0


def test_file_add_inline_get_and_delete(client):
    case = create_case(client)
    added = client.post(
        f"/cases/{case['case_id']}/files",
        files={"file": ("invoice.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )
    assert added.status_code == 200, added.text
    file_record = added.json()["files"][0]

    fetched = client.get(f"/cases/{case['case_id']}/files/{file_record['id']}")
    assert fetched.status_code == 200
    assert fetched.headers["content-disposition"].startswith("inline;")

    deleted = client.delete(f"/cases/{case['case_id']}/files/{file_record['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["files"] == []


def test_requirement_setting_can_be_updated(client):
    payload = {
        "business_category": "other",
        "approval_type": "その他",
        "required_fields": [{"key": "purpose", "label": "目的", "type": "textarea", "required": True}],
        "required_documents": ["申請根拠資料"],
        "conditional_documents": [],
        "form_template": {},
    }
    saved = client.post("/settings/requirements", json=payload)
    assert saved.status_code == 200
    fetched = client.get(
        "/requirements",
        params={"business_category": "other", "approval_type": "その他"},
    )
    assert fetched.json()["required_documents"] == ["申請根拠資料"]
