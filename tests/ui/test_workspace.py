from __future__ import annotations


def test_workspace_mode_groups_keep_existing_generation_modes():
    from final_agent.ui.workspace import mode_group_options

    groups = mode_group_options()

    assert groups["Ask"] == [("qa", "问答"), ("deep", "深度问答")]
    assert groups["Summarize"] == [
        ("page_by_page", "逐页输出"),
        ("full_summary", "全文总结"),
        ("key_points", "重点总结"),
    ]
    assert groups["Coach"] == [("study_coach", "Study Coach")]


def test_latest_assistant_evidence_prefers_newest_answer_with_sources():
    from final_agent.ui.workspace import latest_assistant_evidence

    history = [
        {"role": "assistant", "content": "old", "citations": ["old"], "flags": []},
        {"role": "user", "content": "question"},
        {
            "role": "assistant",
            "content": "new",
            "citations": ["chunk-a"],
            "flags": [{"flagged": False}],
            "chunk_registry": {"chunk-a": {"heading": "Intro", "text": "Body", "score": 0.91, "source": "dense"}},
        },
    ]

    evidence = latest_assistant_evidence(history)

    assert evidence["content"] == "new"
    assert evidence["citations"] == ["chunk-a"]
    assert evidence["flags"] == [{"flagged": False}]
    assert evidence["chunk_registry"]["chunk-a"]["heading"] == "Intro"


def test_validation_summary_counts_clean_and_suspect_flags():
    from final_agent.ui.workspace import validation_summary

    summary = validation_summary([
        {"flagged": False},
        {"flagged": True},
        {"flagged": False},
    ])

    assert summary == {"total": 3, "clean": 2, "suspect": 1}


def test_evidence_popover_config_keeps_supporting_views_hidden_by_default():
    from final_agent.ui.workspace import evidence_popover_config

    assert evidence_popover_config() == {"label": "Evidence", "caption": "引用 / 校验 / Coach"}


def test_input_placeholder_matches_current_learning_mode():
    from final_agent.ui.workspace import input_placeholder

    assert input_placeholder("qa") == "输入你的问题..."
    assert input_placeholder("deep") == "输入需要跨页或多文档推理的问题..."
    assert input_placeholder("full_summary") == "输入总结侧重点，或直接发送开始总结..."
    assert input_placeholder("study_coach") == "输入学习目标，或提交你对当前题目的回答..."
    assert input_placeholder("unknown") == "输入你的学习任务..."


def test_course_maintenance_copy_uses_user_facing_language():
    from final_agent.ui.workspace import course_maintenance_copy

    copy = course_maintenance_copy()

    assert copy["expander_label"] == "课程知识库维护"
    assert copy["repair_button"] == "修复当前课程知识库"
    assert copy["advanced_button"] == "仅迁移旧向量数据"
    assert copy["caption_template"].format(course_id="高等数学") == "当前课程知识库：高等数学"
    assert "Chroma" not in " ".join(copy.values())
    assert "BM25" not in " ".join(copy.values())
    assert "dense" not in " ".join(copy.values())


def test_course_maintenance_summaries_hide_index_jargon():
    from final_agent.ui.workspace import (
        format_course_migration_summary,
        format_course_repair_summary,
    )

    summary = {
        "legacy_chunks": 8,
        "migrated_chunks": 3,
        "skipped_existing": 5,
        "sparse_rebuilt_chunks": 21,
    }

    repair = format_course_repair_summary(summary)
    migration = format_course_migration_summary(summary)

    assert repair == "修复完成：已整理 3 / 8 个旧片段，重建 21 个检索片段"
    assert migration == "整理完成：已迁移 3 / 8 个旧片段，5 个已存在并跳过"
    combined = f"{repair} {migration}"
    assert "Chroma" not in combined
    assert "BM25" not in combined
    assert "dense" not in combined


def test_course_management_guidance_closes_upload_ownership_loop():
    from final_agent.ui.workspace import course_management_guidance

    guidance = course_management_guidance("Software Engineering")

    assert guidance["selected_course"] == "Software Engineering"
    assert guidance["upload_assignment"] == "Uploads will be added to: Software Engineering"
    assert guidance["empty_course_delete"] == "Empty courses can be deleted after selection."
    assert guidance["all_courses_warning"] == "Select or create a course before uploading to avoid mixing materials."


def test_course_management_guidance_handles_all_courses_scope():
    from final_agent.ui.workspace import course_management_guidance

    guidance = course_management_guidance("")

    assert guidance["selected_course"] == "All courses"
    assert guidance["upload_assignment"] == "Uploads will be added to: Default course"
    assert guidance["all_courses_warning"] == "Select or create a course before uploading to avoid mixing materials."


def test_course_maintenance_failure_is_readable_for_users():
    from final_agent.ui.workspace import format_course_maintenance_failure

    message = format_course_maintenance_failure("repair", RuntimeError("snapshot file is locked"))

    assert message == (
        "Repair failed for the current course. "
        "Reason: snapshot file is locked. "
        "Try again after closing other processes, or rebuild this course from its source documents."
    )


def test_format_build_result_message_reports_incremental_skip():
    from final_agent.ui.workspace import format_build_result_message

    message = format_build_result_message(
        {
            "chunks": 2,
            "doc_id": "doc-a",
            "course_id": "course-a",
            "skipped": True,
            "skip_reason": "unchanged-document",
        }
    )

    assert message == "No changes detected for doc-a; skipped rebuild for course-a."


def test_format_build_result_message_reports_regular_build():
    from final_agent.ui.workspace import format_build_result_message

    message = format_build_result_message(
        {
            "chunks": 2,
            "doc_id": "doc-a",
            "course_id": "course-a",
            "bm25_scope_chunks": 5,
            "skipped": False,
        }
    )

    assert message == "Built doc-a: 2 chunks; course-a now has 5 searchable chunks."


def test_evidence_status_summary_counts_citations_and_sources():
    from final_agent.ui.workspace import evidence_status_summary

    summary = evidence_status_summary(
        {
            "citations": ["c1", "c2"],
            "chunk_registry": {
                "c1": {"source": "rrf"},
                "c2": {"source": "rerank"},
            },
        }
    )

    assert summary == "2 cited chunks from rerank, rrf."


def test_evidence_status_summary_handles_empty_state():
    from final_agent.ui.workspace import evidence_status_summary

    assert evidence_status_summary({"citations": [], "chunk_registry": {}}) == "No cited evidence yet."


def test_format_citation_label_prefers_file_name_and_page():
    from final_agent.ui.workspace import format_citation_label

    assert format_citation_label(
        "aaaabbbb1111",
        {
            "source_path": "E:/courses/software-engineering.pdf",
            "doc_id": "doc-a",
            "page_num": 12,
        },
    ) == "software-engineering.pdf，第 12 页"


def test_format_citation_label_falls_back_when_page_or_file_is_missing():
    from final_agent.ui.workspace import format_citation_label

    assert format_citation_label("aaaabbbb1111", {"source_path": "E:/courses/software-engineering.pdf"}) == (
        "software-engineering.pdf"
    )
    assert format_citation_label("aaaabbbb1111", {"doc_id": "doc-a", "page_num": 3}) == "doc-a，第 3 页"
    assert format_citation_label("aaaabbbb1111", {}) == "chunk aaaabbbb"


def test_replace_citation_labels_hides_raw_chunk_ids():
    from final_agent.ui.workspace import replace_citation_labels

    text = "CI runs automated tests [aaaabbbb1111]. It catches integration issues [ccccdddd2222]."
    registry = {
        "aaaabbbb1111": {
            "source_path": "E:/courses/software-engineering.pdf",
            "page_num": 12,
        },
        "ccccdddd2222": {
            "source_path": "E:/courses/software-engineering.pdf",
            "page_num": 13,
        },
    }

    assert replace_citation_labels(text, registry) == (
        "CI runs automated tests [software-engineering.pdf，第 12 页]. "
        "It catches integration issues [software-engineering.pdf，第 13 页]."
    )


def test_build_chunk_registry_adds_readable_citation_metadata():
    from final_agent.schemas import Chunk, ScoredChunk
    from final_agent.ui.workspace import build_chunk_registry

    registry = build_chunk_registry(
        [
            ScoredChunk(
                chunk=Chunk(
                    chunk_id="aaaabbbb1111",
                    doc_id="doc-a",
                    text="CI runs tests.",
                    heading_path=["CI"],
                    page_num=7,
                ),
                score=0.91,
                source="rrf",
            )
        ],
        {"doc-a": {"source_path": "E:/courses/software-engineering.pdf"}},
    )

    assert registry["aaaabbbb1111"]["citation_label"] == "software-engineering.pdf，第 7 页"
    assert registry["aaaabbbb1111"]["source_path"] == "E:/courses/software-engineering.pdf"
    assert registry["aaaabbbb1111"]["page_num"] == 7


def test_validation_status_summary_is_scannable():
    from final_agent.ui.workspace import validation_status_summary

    assert validation_status_summary([{"flagged": False}, {"flagged": True}, {"flagged": False}]) == (
        "2 passed, 1 needs review."
    )
    assert validation_status_summary([]) == "No validation data yet."
