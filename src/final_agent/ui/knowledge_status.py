from __future__ import annotations


def format_knowledge_status(course_index_info: dict[str, dict], course_id: str) -> str:
    if not course_index_info:
        return "知识库状态：空"
    if course_id and course_id in course_index_info:
        chunk_count = int(course_index_info[course_id].get("chunk_count", 0))
        return f"知识库状态：按课程惰性加载（{course_id}，{chunk_count} chunks）"
    return f"知识库状态：按课程惰性加载（{len(course_index_info)} 门课程）"
