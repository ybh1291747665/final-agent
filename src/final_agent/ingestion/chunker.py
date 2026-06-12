"""Markdown chunker — title-aware splitting with recursive sub-chunk fallback."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from final_agent.schemas import Chunk
from final_agent.settings import ChunkingSettings, Settings, load_settings

logger = logging.getLogger(__name__)

_MIN_CHUNK_CHARS = 20

# Matches <!-- page_start: N --> inserted by doubao_parser
_PAGE_MARKER_RE = re.compile(r"<!--\s*page_start:\s*(\d+)\s*-->")


def chunk_markdown(
    markdown_path: str | Path,
    settings: Settings | None = None,
    *,
    doc_id: str = "",
    min_chars: int = _MIN_CHUNK_CHARS,
) -> list[Chunk]:
    """Split a Markdown file into semantic chunks.

    Strategy (title-aware + recursive sub-chunk):

    1. Split at heading lines into logical sections.
    2. Sections <= chunk_size become a single chunk.
    3. Sections > chunk_size are recursively sub-split on sentence/newline
       boundaries, preserving overlap.
    4. Sections < min_chars are merged into the preceding chunk.
    5. Empty sections are skipped.
    """
    markdown_path = Path(markdown_path).resolve()
    if not markdown_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

    if settings is None:
        settings = load_settings()

    if not doc_id:
        doc_id = markdown_path.stem

    cfg: ChunkingSettings = settings.chunking
    raw = markdown_path.read_bytes()
    # Strip UTF-8 BOM if present
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    text = raw.decode("utf-8")
    # Normalize line endings: \r\n → \n, then strip any leftover \r
    text = text.replace("\r\n", "\n").replace("\r", "")

    sections = _split_by_headings(text, cfg.separators)
    chunks: list[Chunk] = []

    for heading_path, section_text, body_start in sections:
        section_len = len(section_text)
        if section_len == 0:
            continue

        if section_len <= cfg.size:
            chunks.append(_make_chunk(
                doc_id=doc_id,
                text=section_text.strip(),
                heading_path=heading_path,
                char_start=body_start,
                char_end=body_start + section_len,
            ))
        else:
            chunks.extend(_split_long_text(
                doc_id=doc_id,
                text=section_text,
                heading_path=heading_path,
                base_offset=body_start,
                chunk_size=cfg.size,
                overlap=cfg.overlap,
            ))

    chunks = _merge_undersized(chunks, min_chars)

    # --- Assign page numbers from <!-- page_start: N --> markers ---
    _assign_page_nums(chunks, text)

    logger.info("Chunked %s -> %d chunks (size=%d, overlap=%d)",
                markdown_path.name, len(chunks), cfg.size, cfg.overlap)
    return chunks


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _split_by_headings(
    text: str, separators: list[str]
) -> list[tuple[list[str], str, int]]:
    """Split text at heading boundaries -> (heading_path, body_text, body_start)."""
    escaped = [re.escape(s) for s in separators]
    pattern = re.compile(r"^(" + "|".join(escaped) + r")(.+)$", re.MULTILINE)

    matches = list(pattern.finditer(text))
    if not matches:
        return [([], text, 0)]

    sections: list[tuple[list[str], str, int]] = []
    heading_stack: list[str] = []

    if matches[0].start() > 0:
        sections.append(([], text[:matches[0].start()], 0))

    for i, m in enumerate(matches):
        prefix = m.group(1).strip()
        title = m.group(2).strip()
        level = len(prefix)

        while heading_stack and len(heading_stack) >= level - 1:
            heading_stack.pop()
        heading_stack.append(title)
        current_path = list(heading_stack)

        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]

        sections.append((current_path, body, body_start))

    return sections


def _split_long_text(
    doc_id: str,
    text: str,
    heading_path: list[str],
    base_offset: int,
    chunk_size: int,
    overlap: int,
) -> list[Chunk]:
    """Recursively split oversized text on sentence/newline boundaries."""
    chunks: list[Chunk] = []
    sentences = _sentence_split(text)
    buffer = ""
    buf_start = 0
    pos = 0

    for sent in sentences:
        # Hard-split a single sentence that exceeds chunk_size
        if len(sent) > chunk_size:
            if buffer.strip():
                chunks.append(_make_chunk(
                    doc_id=doc_id, text=buffer.strip(),
                    heading_path=heading_path,
                    char_start=base_offset + buf_start,
                    char_end=base_offset + buf_start + len(buffer),
                ))
                buffer = ""
                buf_start = pos
            # Collect sub-chunks (no overlap — we're inside a single sentence)
            subs: list[str] = []
            step = max(chunk_size, 1)
            for sub_start in range(0, len(sent), step):
                sub = sent[sub_start:sub_start + chunk_size]
                if sub.strip():
                    subs.append(sub)
            if len(subs) >= 2 and len(subs[-1]) < max(10, chunk_size // 3):
                subs[-2] += subs[-1]
                subs.pop()
            off = pos
            for sub in subs:
                chunks.append(_make_chunk(
                    doc_id=doc_id, text=sub.strip(),
                    heading_path=heading_path,
                    char_start=base_offset + off,
                    char_end=base_offset + off + len(sub),
                ))
                off += len(sub)
            pos += len(sent)
            continue

        if len(buffer) + len(sent) <= chunk_size:
            buffer += sent
        else:
            if buffer.strip():
                chunks.append(_make_chunk(
                    doc_id=doc_id, text=buffer.strip(),
                    heading_path=heading_path,
                    char_start=base_offset + buf_start,
                    char_end=base_offset + buf_start + len(buffer),
                ))
            if overlap > 0 and buffer.strip():
                overlap_text = buffer[-overlap:]
                buffer = overlap_text + sent
                buf_start = pos - len(overlap_text)
            else:
                buffer = sent
                buf_start = pos
        pos += len(sent)

    if buffer.strip():
        chunks.append(_make_chunk(
            doc_id=doc_id, text=buffer.strip(),
            heading_path=heading_path,
            char_start=base_offset + buf_start,
            char_end=base_offset + buf_start + len(buffer),
        ))

    return chunks


_SENTENCE_RE = re.compile(r"([\u3002\uff01\uff1f.!?\n])\s*")


def _sentence_split(text: str) -> list[str]:
    """Split text into sentence-like segments including the delimiter."""
    parts = _SENTENCE_RE.split(text)
    sentences: list[str] = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts) and _SENTENCE_RE.match(parts[i + 1]):
            sentences.append(parts[i] + parts[i + 1])
            i += 2
        else:
            sentences.append(parts[i])
            i += 1
    merged: list[str] = []
    for s in sentences:
        if s and len(s) < 4 and merged:
            merged[-1] += s
        elif s:
            merged.append(s)
    return merged


def _make_chunk(
    doc_id: str, text: str, heading_path: list[str],
    char_start: int, char_end: int,
) -> Chunk:
    return Chunk(
        doc_id=doc_id, text=text, heading_path=heading_path,
        char_start=char_start, char_end=char_end,
    )


def _merge_undersized(chunks: list[Chunk], min_chars: int) -> list[Chunk]:
    """Merge only truly tiny chunks (< min_chars) into the previous chunk,
    and only when they share heading_path and the merge stays compact."""
    if not chunks:
        return chunks
    merged: list[Chunk] = []
    for ch in chunks:
        if (len(ch.text) < min_chars
                and merged
                and merged[-1].heading_path == ch.heading_path):
            prev = merged[-1]
            merged[-1] = Chunk(
                doc_id=prev.doc_id,
                text=prev.text + "\n\n" + ch.text,
                heading_path=prev.heading_path,
                char_start=prev.char_start,
                char_end=ch.char_end,
                metadata=prev.metadata,
            )
        else:
            merged.append(ch)
    return merged


def _assign_page_nums(chunks: list[Chunk], full_text: str) -> None:
    """Scan for <!-- page_start: N --> markers and set Chunk.page_num."""
    markers: list[tuple[int, int]] = []  # (char_pos, page_num)
    for m in _PAGE_MARKER_RE.finditer(full_text):
        markers.append((m.start(), int(m.group(1))))

    if not markers:
        return

    # For each chunk, find the last marker before (or at) its char_start
    for ch in chunks:
        pn = 1
        for pos, page in markers:
            if pos <= ch.char_start:
                pn = page
            else:
                break
        ch.page_num = pn
