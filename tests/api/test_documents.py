from __future__ import annotations

import httpx
import pytest


def _write_pdf(path, pages: int = 2) -> None:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(595, 842)
    pdf.save(path)
    pdf.close()


@pytest.mark.anyio
async def test_document_api_returns_info_and_png_page(tmp_path):
    from final_agent.api.app import create_app
    from final_agent.api.documents import DocumentService
    from final_agent.knowledge.metadata import register_document
    from final_agent.memory.repository import MemoryRepository
    from final_agent.settings import Settings

    pdf_path = tmp_path / "lecture.pdf"
    _write_pdf(pdf_path)
    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path / "index")
    register_document("doc-a", str(pdf_path), 2, settings=settings)
    app = create_app(
        repository=MemoryRepository(tmp_path / "api.sqlite"),
        document_service=DocumentService(settings=settings),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        info = await client.get("/documents/doc-a")
        page = await client.get("/documents/doc-a/pages/2", params={"zoom": 125})

    assert info.status_code == 200
    assert info.json() == {
        "doc_id": "doc-a",
        "file_name": "lecture.pdf",
        "media_type": "application/pdf",
        "total_pages": 2,
    }
    assert page.status_code == 200
    assert page.headers["content-type"] == "image/png"
    assert page.content.startswith(b"\x89PNG")


@pytest.mark.anyio
async def test_document_api_rejects_unknown_non_pdf_and_out_of_range(tmp_path):
    from final_agent.api.app import create_app
    from final_agent.api.documents import DocumentService
    from final_agent.knowledge.metadata import register_document
    from final_agent.memory.repository import MemoryRepository
    from final_agent.settings import Settings

    markdown_path = tmp_path / "lesson.md"
    markdown_path.write_text("# Lesson", encoding="utf-8")
    settings = Settings()
    settings.vector_store.persist_dir = str(tmp_path / "index")
    register_document("markdown", str(markdown_path), 1, settings=settings)
    app = create_app(
        repository=MemoryRepository(tmp_path / "api.sqlite"),
        document_service=DocumentService(settings=settings),
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        unknown = await client.get("/documents/missing")
        non_pdf = await client.get("/documents/markdown/pages/1")

        pdf_path = tmp_path / "lecture.pdf"
        _write_pdf(pdf_path, pages=1)
        register_document("pdf", str(pdf_path), 1, settings=settings)
        out_of_range = await client.get("/documents/pdf/pages/2")

    assert unknown.status_code == 404
    assert non_pdf.status_code == 415
    assert out_of_range.status_code == 416


def test_document_page_render_cache_uses_file_version(tmp_path, monkeypatch):
    from final_agent.api import documents

    pdf_path = tmp_path / "lecture.pdf"
    pdf_path.write_bytes(b"pdf")
    documents.clear_document_page_cache()
    calls = []
    monkeypatch.setattr(
        documents,
        "_render_pdf_page_uncached",
        lambda path, page_num, zoom: calls.append((path, page_num, zoom)) or b"png",
    )

    first = documents.render_pdf_page(pdf_path, 1, 100)
    second = documents.render_pdf_page(pdf_path, 1, 100)
    pdf_path.write_bytes(b"pdf-new")
    third = documents.render_pdf_page(pdf_path, 1, 100)

    assert first == second == third == b"png"
    assert len(calls) == 2
