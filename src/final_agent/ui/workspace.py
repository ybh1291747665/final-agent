from __future__ import annotations

from collections.abc import Sequence


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


def evidence_popover_config() -> dict[str, str]:
    return {"label": "Evidence", "caption": "引用 / 校验 / Coach"}


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
