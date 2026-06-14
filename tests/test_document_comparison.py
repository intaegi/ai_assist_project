from frontend.document_comparison import build_comparison_rows, extract_document_values


def _file(name: str, text: str) -> dict:
    return {"file_name": name, "pages": [{"page": 1, "text": text}]}


def test_extract_document_values_from_contract():
    values = extract_document_values(
        _file(
            "contract.pdf",
            "取引先: 株式会社ネクストクラウド\n"
            "サービス名: CloudGuard Pro 年間ライセンス\n"
            "契約期間: 2026年7月1日 ～ 2027年6月30日\n"
            "契約金額: 132,000円（税込）",
        )
    )

    assert values == {
        "vendor": "株式会社ネクストクラウド",
        "service_name": "CloudGuard Pro 年間ライセンス",
        "amount": 132000,
        "service_start_date": "2026-07-01",
        "service_end_date": "2027-06-30",
    }


def test_comparison_rows_detect_match_missing_and_difference():
    case = {
        "files": [
            _file(
                "invoice.pdf",
                "請求書\n請求元: ABC株式会社\nサービス名: Cloud\n"
                "利用期間: 2026年7月1日 ～ 2027年6月30日\n請求金額: 120,000円",
            ),
            _file(
                "estimate.pdf",
                "見積書\n会社名: ABC株式会社\n商品名: Cloud\n合計金額: 110,000円",
            ),
        ]
    }
    form = {
        "vendor": "ABC株式会社",
        "service_name": "Cloud",
        "amount": 120000,
        "service_start_date": "2026-07-01",
        "service_end_date": "2027-06-30",
    }

    rows = build_comparison_rows(case, form)
    by_item_and_document = {
        (row["確認項目"], row["書類"]): row["照合結果"]
        for row in rows
    }

    assert by_item_and_document[("取引先", "請求書")] == "一致"
    assert by_item_and_document[("金額", "見積書")] == "差異あり"
    assert by_item_and_document[("利用開始日", "見積書")] == "記載なし"
