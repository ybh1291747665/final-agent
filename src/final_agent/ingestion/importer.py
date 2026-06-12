"""Unified import pipeline — PDF/Markdown → parsed → chunked."""

from __future__ import annotations

import logging
from pathlib import Path

from final_agent.ingestion.chunker import chunk_markdown
from final_agent.ingestion.doubao_parser import parse_pdf_doubao
from final_agent.ingestion.image_analyzer import analyze_images_in_markdown
# pdf_parser (MinerU) kept as reference — import if switching back:
# from final_agent.ingestion.pdf_parser import parse_pdf
from final_agent.schemas import Chunk
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)


def import_document(
    path: str | Path,
    settings: Settings | None = None,
    *,
    doc_id: str = "",
    course_id: str = "",
) -> list[Chunk]:
    """Import a PDF or Markdown file, returning semantic chunks.

    - PDF files are first converted to Markdown via Doubao VLM API, then chunked.
    - Markdown files are chunked directly.

    Args:
        path: Path to a ``.pdf`` or ``.md`` file.
        settings: Application settings (auto-loaded if omitted).
        doc_id: Document identifier (defaults to file stem).
        course_id: Course grouping key (defaults to "默认课程").

    Returns:
        Ordered list of ``Chunk`` instances.
    """
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if settings is None:
        settings = load_settings()

    if not doc_id:
        doc_id = path.stem
    if not course_id:
        course_id = "默认课程"

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        logger.info("PDF detected — parsing with Doubao API: %s", path)
        md_path = parse_pdf_doubao(path, settings=settings)

        # Image analysis via VLM (if enabled)
        if settings.vision.enabled:
            # Doubao API outputs inline image descriptions; extracted images are rare.
            # Still scan the markdown for any ![](...) references.
            images_root = md_path.parent / "images"
            if not images_root.exists():
                images_root = Path(settings.data.images_dir)
                if not images_root.is_absolute():
                    images_root = settings.project_root / images_root
            logger.info("Running VLM image analysis on %s ...", md_path.name)
            enriched_md = analyze_images_in_markdown(md_path, images_root, settings=settings)
            # Overwrite markdown with enriched version (includes image descriptions)
            md_path.write_text(enriched_md, encoding="utf-8")
            logger.info("Markdown enriched with image descriptions")

        chunks = chunk_markdown(md_path, settings=settings, doc_id=doc_id)
    elif suffix in (".md", ".markdown"):
        logger.info("Markdown detected — chunking directly: %s", path)
        chunks = chunk_markdown(path, settings=settings, doc_id=doc_id)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: .pdf, .md")

    # Stamp course_id on every chunk
    for ch in chunks:
        ch.course_id = course_id

    logger.info("Imported %s → %d chunks (course=%s)", path.name, len(chunks), course_id)
    return chunks
