import argparse
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "sample_data" / "test_documents" / "upload"
OUTPUT_DIR = PROJECT_ROOT / "sample_data" / "test_documents" / "pdf"


def register_font() -> str:
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        return "HeiseiKakuGo-W5"
    except Exception:
        pass
    candidates = [
        Path(r"C:\Windows\Fonts\BIZ-UDGothicR.ttc"),
        Path(r"C:\Windows\Fonts\msgothic.ttc"),
        Path(r"C:\Windows\Fonts\meiryo.ttc"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont("Japanese", str(path), subfontIndex=0))
            return "Japanese"
    raise RuntimeError("日本語PDF生成用フォントが見つかりません。")


def render_markdown(source: Path, output: Path, font_name: str) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "JapaneseTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=20,
        leading=28,
        alignment=TA_CENTER,
        textColor=HexColor("#123B66"),
        spaceAfter=12 * mm,
    )
    body_style = ParagraphStyle(
        "JapaneseBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=11,
        leading=18,
        textColor=HexColor("#202833"),
        spaceAfter=3 * mm,
    )
    number_style = ParagraphStyle(
        "JapaneseNumber",
        parent=body_style,
        alignment=TA_RIGHT,
    )

    lines = source.read_text(encoding="utf-8").splitlines()
    story = []
    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            story.append(Spacer(1, 2 * mm))
            continue
        if index == 0 and line.startswith("# "):
            story.append(Paragraph(line[2:], title_style))
            continue
        text = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        style = number_style if any(token in line for token in ("金額:", "小計:", "消費税:", "単価:")) else body_style
        story.append(Paragraph(text, style))

    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=24 * mm,
        rightMargin=24 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=source.stem,
        author="Decision RAG UI Test",
    )
    document.build(story)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="既存PDFを上書きせず、不足しているPDFだけを生成します。",
    )
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    font_name = register_font()
    for source in sorted(SOURCE_DIR.glob("*.md")):
        output = OUTPUT_DIR / f"{source.stem}.pdf"
        if args.only_missing and output.exists():
            continue
        render_markdown(source, output, font_name)
        print(f"generated: {output.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
