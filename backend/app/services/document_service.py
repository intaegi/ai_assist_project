import io
import re
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from backend.app.schemas.models import FileRecord


ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
DOCUMENT_LABELS = {
    "invoice": "請求書",
    "estimate": "見積書",
    "quotation": "見積書",
    "contract": "契約書",
    "order": "発注書",
    "請求": "請求書",
    "見積": "見積書",
    "契約": "契約書",
}


class DocumentService:
    def extract_pages(self, content: bytes, content_type: str) -> list[dict[str, object]]:
        if content_type != "application/pdf":
            return []
        reader = PdfReader(io.BytesIO(content))
        return [
            {"page": index, "text": (page.extract_text() or "").strip()}
            for index, page in enumerate(reader.pages, start=1)
        ]

    def create_file_record(
        self,
        case_id: str,
        file_name: str,
        content_type: str,
        content: bytes,
        storage_path: str,
    ) -> FileRecord:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValueError("PDF、JPG、PNGファイルのみアップロードできます。")
        return FileRecord(
            id=f"file_{uuid4().hex[:12]}",
            case_id=case_id,
            file_name=Path(file_name).name,
            content_type=content_type,
            size=len(content),
            storage_path=storage_path,
            pages=self.extract_pages(content, content_type),
        )

    def joined_text(self, files: list[FileRecord]) -> str:
        return "\n".join(str(page["text"]) for file in files for page in file.pages if page.get("text"))

    def document_types(self, files: list[FileRecord]) -> set[str]:
        found: set[str] = set()
        for file in files:
            target = f"{file.file_name} {self.joined_text([file])}".lower()
            for token, label in DOCUMENT_LABELS.items():
                if token.lower() in target:
                    found.add(label)
        return found

    def extract_basic_fields(self, text: str) -> dict[str, object]:
        fields: dict[str, object] = {}
        amount_matches = re.findall(r"(?:合計|請求金額|金額)[^\d]{0,10}([\d,]+)\s*円", text)
        if amount_matches:
            fields["amount"] = float(amount_matches[-1].replace(",", ""))
        date_matches = re.findall(r"(20\d{2})[年/\-.](\d{1,2})[月/\-.](\d{1,2})", text)
        if date_matches:
            year, month, day = date_matches[0]
            fields["invoice_date"] = f"{year}-{int(month):02d}-{int(day):02d}"
        vendor = re.search(r"(?:請求元|取引先|会社名)[:：\s]+([^\n]+)", text)
        if vendor:
            fields["vendor"] = vendor.group(1).strip()
        service = re.search(r"(?:サービス名|商品名|件名)[:：\s]+([^\n]+)", text)
        if service:
            fields["service_name"] = service.group(1).strip()
        return fields
