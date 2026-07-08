from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import re

from final_agent.schemas import ScoredChunk


_CITATION_TOKEN_RE = re.compile(r"\[([A-Za-z0-9_-]{3,64})\]")


def mode_group_options() -> dict[str, list[tuple[str, str]]]:
    """Return the product-level mode groups shown in the study workspace."""
    return {
        "Ask": [("qa", "问答"), ("deep", "深度问答")],
        "Summarize": [
            ("page_by_page", "逐页输出"),
            ("full_summary", "全文总结"),
            ("key_points", "重点总结"),
        ],
        "Coach": [("study_coach", "Study Coach")],
    }


def mode_display_names() -> dict[str, str]:
    return {
        key: label
        for options in mode_group_options().values()
        for key, label in options
    }


def latest_assistant_evidence(history: Sequence[dict]) -> dict:
    for msg in reversed(history):
        if msg.get("role") == "assistant" and (msg.get("citations") or msg.get("flags")):
            return {
                "content": msg.get("content", ""),
                "citations": msg.get("citations", []),
                "flags": msg.get("flags", []),
                "chunk_registry": msg.get("chunk_registry", {}),
            }
    return {"content": "", "citations": [], "flags": [], "chunk_registry": {}}


def validation_summary(flags: Sequence[dict]) -> dict[str, int]:
    total = len(flags)
    suspect = sum(1 for flag in flags if flag.get("flagged"))
    return {"total": total, "clean": total - suspect, "suspect": suspect}


def evidence_status_summary(evidence: dict) -> str:
    citations = evidence.get("citations", [])
    if not citations:
        return "No cited evidence yet."
    registry = evidence.get("chunk_registry", {})
    sources = sorted(
        {
            str(registry.get(cid, {}).get("source", "")).strip()
            for cid in citations
            if registry.get(cid, {}).get("source")
        }
    )
    source_text = ", ".join(sources) if sources else "available sources"
    return f"{len(citations)} cited chunks from {source_text}."


def format_citation_label(chunk_id: str, entry: dict) -> str:
    source_path = str(entry.get("source_path") or "").strip()
    file_name = str(entry.get("file_name") or "").strip()
    doc_id = str(entry.get("doc_id") or "").strip()
    page_num = entry.get("page_num")

    if not file_name and source_path:
        file_name = Path(source_path).name
    base = file_name or doc_id

    try:
        page = int(page_num) if page_num not in (None, "") else 0
    except (TypeError, ValueError):
        page = 0

    if base and page > 0:
        return f"{base}，第 {page} 页"
    if base:
        return base
    if page > 0:
        return f"第 {page} 页"
    return f"chunk {chunk_id[:8]}"


def replace_citation_labels(text: str, chunk_registry: dict) -> str:
    def _replace(match: re.Match[str]) -> str:
        chunk_id = match.group(1)
        entry = chunk_registry.get(chunk_id)
        if not entry:
            return match.group(0)
        return f"[{format_citation_label(chunk_id, entry)}]"

    return _CITATION_TOKEN_RE.sub(_replace, text)


def build_chunk_registry(results: Sequence[ScoredChunk], documents: dict | None = None) -> dict:
    documents = documents or {}
    registry = {}
    for result in results:
        chunk = result.chunk
        doc_meta = documents.get(chunk.doc_id, {})
        source_path = str(doc_meta.get("source_path", "") or chunk.metadata.get("source_path", ""))
        file_name = Path(source_path).name if source_path else ""
        heading = " > ".join(chunk.heading_path) if chunk.heading_path else "(top)"
        entry = {
            "heading": heading,
            "text": chunk.text,
            "score": result.score,
            "source": result.source,
            "doc_id": chunk.doc_id,
            "source_path": source_path,
            "file_name": file_name,
            "page_num": chunk.page_num,
        }
        entry["citation_label"] = format_citation_label(chunk.chunk_id, entry)
        registry[chunk.chunk_id] = entry
    return registry


def validation_status_summary(flags: Sequence[dict]) -> str:
    summary = validation_summary(flags)
    if summary["total"] == 0:
        return "No validation data yet."
    if summary["suspect"] == 0:
        return f"{summary['clean']} passed, none need review."
    return f"{summary['clean']} passed, {summary['suspect']} needs review."


def evidence_popover_config() -> dict[str, str]:
    return {"label": "Evidence", "caption": "引用 / 校验 / Coach"}


def course_maintenance_copy() -> dict[str, str]:
    return {
        "expander_label": "课程知识库维护",
        "caption_template": "当前课程知识库：{course_id}",
        "repair_button": "修复当前课程知识库",
        "advanced_button": "仅迁移旧向量数据",
        "repair_failed_prefix": "修复失败",
        "migration_failed_prefix": "迁移失败",
    }


def course_management_guidance(course_id: str) -> dict[str, str]:
    selected_course = course_id.strip() if course_id else "All courses"
    upload_course = course_id.strip() if course_id else "Default course"
    return {
        "selected_course": selected_course,
        "upload_assignment": f"Uploads will be added to: {upload_course}",
        "empty_course_delete": "Empty courses can be deleted after selection.",
        "all_courses_warning": "Select or create a course before uploading to avoid mixing materials.",
    }


def format_course_maintenance_failure(action: str, error: Exception) -> str:
    action_label = "Repair" if action == "repair" else "Migration"
    return (
        f"{action_label} failed for the current course. "
        f"Reason: {error}. "
        "Try again after closing other processes, or rebuild this course from its source documents."
    )


def format_build_result_message(summary: dict) -> str:
    doc_id = summary.get("doc_id") or "document"
    course_id = summary.get("course_id") or "Default course"
    if summary.get("skipped"):
        return f"No changes detected for {doc_id}; skipped rebuild for {course_id}."
    return (
        f"Built {doc_id}: {summary.get('chunks', 0)} chunks; "
        f"{course_id} now has {summary.get('bm25_scope_chunks', 0)} searchable chunks."
    )


def format_course_repair_summary(summary: dict) -> str:
    return (
        "修复完成：已整理 "
        f"{summary['migrated_chunks']} / {summary['legacy_chunks']} 个旧片段，"
        f"重建 {summary['sparse_rebuilt_chunks']} 个检索片段"
    )


def format_course_migration_summary(summary: dict) -> str:
    text = (
        "整理完成：已迁移 "
        f"{summary['migrated_chunks']} / {summary['legacy_chunks']} 个旧片段"
    )
    if summary.get("skipped_existing"):
        text += f"，{summary['skipped_existing']} 个已存在并跳过"
    return text


def input_placeholder(mode: str) -> str:
    placeholders = {
        "qa": "输入你的问题...",
        "deep": "输入需要跨页或多文档推理的问题...",
        "page_by_page": "输入逐页总结侧重点，或直接发送开始总结...",
        "full_summary": "输入总结侧重点，或直接发送开始总结...",
        "key_points": "输入你关心的重点方向，或直接发送提炼重点...",
        "study_coach": "输入学习目标，或提交你对当前题目的回答...",
    }
    return placeholders.get(mode, "输入你的学习任务...")
