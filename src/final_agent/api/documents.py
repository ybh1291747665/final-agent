from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium

from final_agent.knowledge.metadata import list_documents
from final_agent.settings import Settings, load_settings


class DocumentNotFoundError(FileNotFoundError):
    pass


class UnsupportedDocumentError(ValueError):
    pass


class PageOutOfRangeError(ValueError):
    pass


def _render_pdf_page_uncached(path: str, page_num: int, zoom: int) -> bytes:
    pdf = pdfium.PdfDocument(path)
    try:
        page = pdf[page_num - 1]
        scale = (zoom / 100) * (96 / 72)
        image = page.render(scale=scale).to_pil()
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
    finally:
        pdf.close()


@lru_cache(maxsize=64)
def _render_pdf_page_cached(
    path: str,
    modified_ns: int,
    size: int,
    page_num: int,
    zoom: int,
) -> bytes:
    del modified_ns, size
    return _render_pdf_page_uncached(path, page_num, zoom)


def render_pdf_page(path: str | Path, page_num: int, zoom: int) -> bytes:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    return _render_pdf_page_cached(
        str(resolved),
        stat.st_mtime_ns,
        stat.st_size,
        page_num,
        zoom,
    )


def clear_document_page_cache() -> None:
    _render_pdf_page_cached.cache_clear()


class DocumentService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()

    def _path_for(self, doc_id: str) -> Path:
        metadata = list_documents(settings=self.settings)
        info = metadata.get(doc_id)
        if info is None:
            raise DocumentNotFoundError(doc_id)
        path = Path(str(info.get("source_path", ""))).resolve()
        if not path.exists():
            raise DocumentNotFoundError(doc_id)
        if path.suffix.lower() != ".pdf":
            raise UnsupportedDocumentError(doc_id)
        return path

    def info(self, doc_id: str) -> dict[str, object]:
        path = self._path_for(doc_id)
        try:
            pdf = pdfium.PdfDocument(str(path))
        except Exception as exc:
            raise UnsupportedDocumentError(doc_id) from exc
        try:
            total_pages = len(pdf)
        finally:
            pdf.close()
        return {
            "doc_id": doc_id,
            "file_name": path.name,
            "media_type": "application/pdf",
            "total_pages": total_pages,
        }

    def page(self, doc_id: str, page_num: int, zoom: int) -> bytes:
        info = self.info(doc_id)
        if page_num < 1 or page_num > int(info["total_pages"]):
            raise PageOutOfRangeError(str(page_num))
        if zoom not in (100, 125, 150):
            raise ValueError("zoom must be one of 100, 125, or 150")
        return render_pdf_page(self._path_for(doc_id), page_num, zoom)
