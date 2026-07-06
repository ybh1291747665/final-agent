from __future__ import annotations


def test_format_knowledge_status_reports_empty_library():
    from final_agent.ui.knowledge_status import format_knowledge_status

    assert format_knowledge_status({}, "") == "知识库状态：空"


def test_format_knowledge_status_reports_selected_course_scope():
    from final_agent.ui.knowledge_status import format_knowledge_status

    info = {
        "course-a": {
            "chunk_count": 12,
            "doc_ids": ["doc-a"],
            "bm25_snapshot_path": "E:/snapshots/course-a.json",
        },
        "course-b": {
            "chunk_count": 5,
            "doc_ids": ["doc-b"],
            "bm25_snapshot_path": "E:/snapshots/course-b.json",
        },
    }

    assert format_knowledge_status(info, "course-a") == "知识库状态：按课程惰性加载（course-a，12 chunks）"


def test_format_knowledge_status_reports_course_count_when_showing_all_courses():
    from final_agent.ui.knowledge_status import format_knowledge_status

    info = {
        "course-a": {
            "chunk_count": 12,
            "doc_ids": ["doc-a"],
            "bm25_snapshot_path": "E:/snapshots/course-a.json",
        },
        "course-b": {
            "chunk_count": 5,
            "doc_ids": ["doc-b"],
            "bm25_snapshot_path": "E:/snapshots/course-b.json",
        },
    }

    assert format_knowledge_status(info, "") == "知识库状态：按课程惰性加载（2 门课程）"
