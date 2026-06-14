from backend.app.services.rag_service import RagService


def test_matching_quote_uses_line_containing_amount():
    text = (
        "サービス名: CloudGuard Pro 年間ライセンス\n"
        "消費税: 12,000円\n"
        "請求金額: 132,000円\n"
        "支払期限: 2026年6月30日"
    )

    quote = RagService._matching_quote(text, 132000.0)

    assert "請求金額: 132,000円" in quote
    assert not quote.endswith("請求金額: 1")


def test_matching_quote_uses_line_containing_vendor():
    text = "請求書\n請求元: 株式会社ネクストクラウド\nサービス名: CloudGuard Pro"

    quote = RagService._matching_quote(text, "株式会社ネクストクラウド")

    assert "請求元: 株式会社ネクストクラウド" in quote
