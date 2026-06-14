import io
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from backend.app.schemas.models import FileRecord
from backend.app.services.document_fields import (
    document_label,
    extract_document_values,
    joined_page_text,
)


ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}


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
        return "\n".join(joined_page_text(file.pages) for file in files if file.pages)

    def document_types(self, files: list[FileRecord]) -> set[str]:
        return {
            document_label(file.file_name, joined_page_text(file.pages))
            for file in files
        }

    def extract_basic_fields(self, text: str) -> dict[str, object]:
        return extract_document_values(text)

    def extract_file_fields(self, file: FileRecord) -> dict[str, object]:
        return extract_document_values(joined_page_text(file.pages))

    def document_label(self, file: FileRecord) -> str:
        return document_label(file.file_name, joined_page_text(file.pages))
