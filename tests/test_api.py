from pathlib import Path


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
    assert "checklist_verification" in response.json()["features"]


def test_dependency_health_reports_local_mode(client):
    response = client.get("/health/dependencies")
    assert response.status_code == 200
    assert response.json()["mode"] == "local"
    assert response.json()["data_store_mode"] == "local"
    assert response.json()["checks"]["cosmos"]["status"] == "skipped"


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
    generated_output = (
        client.app.state.services.settings.data_dir
        / "files"
        / "generated-outputs"
        / "cases"
        / case["case_id"]
        / "versions"
        / "1.json"
    )
    assert generated_output.exists()


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
    generated = client.post(f"/cases/{case['case_id']}/generate").json()
    response = client.post(
        f"/cases/{case['case_id']}/chat",
        json={"instruction": "確認結果を本文末尾に追記", "target_field": "body"},
    )
    assert response.status_code == 200
    assert response.json()["current_version"] == 2
    assert len(response.json()["chat_logs"]) == 2
    assert "確認結果を本文末尾に追記" in response.json()["approval_form"]["body"]
    assert response.json()["approval_form"]["vendor"] == generated["approval_form"]["vendor"]
    assert "決裁本文を更新しました" in response.json()["chat_logs"][-1]["message"]
    assert "確認結果を本文末尾に追記" in response.json()["chat_logs"][-1]["message"]


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
    extracted_text = (
        client.app.state.services.settings.data_dir
        / "files"
        / "extracted-texts"
        / "cases"
        / case["case_id"]
        / "text"
        / f"{file_record['id']}.json"
    )
    assert extracted_text.exists()

    fetched = client.get(f"/cases/{case['case_id']}/files/{file_record['id']}")
    assert fetched.status_code == 200
    assert fetched.headers["content-disposition"].startswith("inline;")

    deleted = client.delete(f"/cases/{case['case_id']}/files/{file_record['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["files"] == []
    assert not extracted_text.exists()


def test_duplicate_file_content_is_not_added_twice(client):
    case = create_case(client)
    content = b"\x89PNG\r\n\x1a\nsame-file"

    first = client.post(
        f"/cases/{case['case_id']}/files",
        files={"file": ("invoice.png", content, "image/png")},
    )
    duplicate = client.post(
        f"/cases/{case['case_id']}/files",
        files={"file": ("renamed-invoice.png", content, "image/png")},
    )

    assert first.status_code == 200
    assert first.json()["file_upload"]["added"] is True
    assert duplicate.status_code == 200
    assert duplicate.json()["file_upload"]["added"] is False
    assert len(duplicate.json()["files"]) == 1
    assert duplicate.json()["files"][0]["content_hash"]


def test_missing_document_is_revalidated_and_marked_resolved_after_upload(client):
    case = create_case(client)
    generated = client.post(f"/cases/{case['case_id']}/generate").json()
    assert any(
        item["code"] == "REQUIRED_DOCUMENT_MISSING"
        and item["basis"]["document"] == "請求書"
        for item in generated["validation_results"]
    )

    added = client.post(
        f"/cases/{case['case_id']}/files",
        files={"file": ("invoice.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
    )

    assert added.status_code == 200, added.text
    payload = added.json()
    assert not any(
        item["code"] == "REQUIRED_DOCUMENT_MISSING"
        and item["basis"]["document"] == "請求書"
        for item in payload["validation_results"]
    )
    assert any(
        item["code"] == "MISSING_DOCUMENT_RESOLVED"
        and "請求書" in item["message"]
        for item in payload["resolution_notices"]
    )


def test_tc_ui_006_estimate_then_invoice_resolves_required_document(client):
    pdf_root = Path("sample_data/test_documents/pdf")
    created = client.post(
        "/cases",
        data={
            "business_category": "it",
            "approval_type": "支払",
            "description": "CloudGuard Proの年間利用料を支払います。",
            "category_fields": "{}",
        },
        files={
            "files": (
                "TC-DOC-02_it_estimate_cloudguard.pdf",
                (pdf_root / "TC-DOC-02_it_estimate_cloudguard.pdf").read_bytes(),
                "application/pdf",
            )
        },
    ).json()

    generated = client.post(f"/cases/{created['case_id']}/generate").json()
    assert any(
        item["code"] == "REQUIRED_DOCUMENT_MISSING"
        and item["basis"]["document"] == "請求書"
        for item in generated["validation_results"]
    )

    added = client.post(
        f"/cases/{created['case_id']}/files",
        files={
            "file": (
                "TC-DOC-01_it_invoice_cloudguard.pdf",
                (pdf_root / "TC-DOC-01_it_invoice_cloudguard.pdf").read_bytes(),
                "application/pdf",
            )
        },
    ).json()

    assert not any(
        item["code"] == "REQUIRED_DOCUMENT_MISSING"
        for item in added["validation_results"]
    )
    assert added["resolution_notices"][-1]["message"] == (
        "不足していた必要書類「請求書」が添付されました。"
    )


def test_regeneration_instruction_is_saved_as_new_version(client):
    case = create_case(client)
    client.post(f"/cases/{case['case_id']}/generate")

    response = client.post(
        f"/cases/{case['case_id']}/generate",
        json={"instruction": "追加請求書を反映して再作成"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["current_version"] == 2
    assert payload["versions"][-1]["instruction"] == "追加請求書を反映して再作成"
    assert "追加請求書を反映して再作成" in payload["summary"]
    assert "追加請求書を反映して再作成" in payload["approval_form"]["body"]


def test_ai_checklist_verification_is_saved(client):
    case = create_case(client)
    generated = client.post(f"/cases/{case['case_id']}/generate").json()

    response = client.post(f"/cases/{case['case_id']}/checklist/verify")

    assert response.status_code == 200, response.text
    results = response.json()["checklist_verification"]
    assert len(results) == len(generated["checklist"])
    assert {item["status"] for item in results} <= {
        "verified",
        "action_required",
        "not_verifiable",
    }
    assert any(item["status"] == "action_required" for item in results)
    invoice_check = next(item for item in results if "請求書" in item["item"])
    assert invoice_check["status"] == "action_required"


def test_chat_can_regenerate_entire_case(client):
    case = create_case(client)
    generated = client.post(f"/cases/{case['case_id']}/generate").json()

    response = client.post(
        f"/cases/{case['case_id']}/chat",
        json={
            "instruction": "追加資料を反映して全体を更新してください。",
            "target_field": "all",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["current_version"] == generated["current_version"] + 1
    assert "追加資料を反映して全体を更新してください。" in payload["summary"]
    assert payload["chat_logs"][-2]["target_field"] == "all"
    assert payload["versions"][-1]["instruction"] == (
        "追加資料を反映して全体を更新してください。"
    )


def test_chat_infers_target_fields_and_preserves_others(client):
    case = create_case(client)
    generated = client.post(f"/cases/{case['case_id']}/generate").json()
    form = generated["approval_form"]
    form.update(
        {
            "title": "CloudGuard Pro 年間利用料支払い申請",
            "vendor": "株式会社ネクストクラウド",
            "service_name": "CloudGuard Pro 年間ライセンス",
            "body": "第一文です。第二文です。第三文です。",
        }
    )
    patched = client.patch(f"/cases/{case['case_id']}", json={"approval_form": form}).json()

    response = client.post(
        f"/cases/{case['case_id']}/chat",
        json={
            "instruction": "決裁本文を2文でまとめてください\n製品・サービス名は英語で記載してください",
            "target_field": "all",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    revised = payload["approval_form"]
    assert revised["body"] == "第一文です。第二文です。"
    assert revised["service_name"] == "CloudGuard Pro"
    assert revised["title"] == patched["approval_form"]["title"]
    assert revised["vendor"] == patched["approval_form"]["vendor"]
    assert payload["chat_logs"][-1]["target_field"] == "body,service_name"


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


def test_local_reindex_does_not_duplicate_materials(client):
    uploaded = client.post(
        "/settings/materials",
        data={
            "business_category": "it",
            "approval_type": "支払",
            "knowledge_type": "policy",
            "title": "テスト決裁規程",
        },
        files={"file": ("policy.md", b"# policy", "text/markdown")},
    )
    assert uploaded.status_code == 200

    first = client.post("/settings/reindex")
    second = client.post("/settings/reindex")

    assert first.status_code == 200
    assert first.json()["mode"] == "local"
    assert second.json()["indexed"] == first.json()["indexed"]
