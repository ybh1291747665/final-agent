from __future__ import annotations


def test_chunk_markdown_assigns_page_numbers(tmp_path):
    from final_agent.ingestion.chunker import chunk_markdown
    from final_agent.settings import Settings

    path = tmp_path / "lesson.md"
    path.write_text("<!-- page_start: 3 -->\n## Intro\nAutomation helps.\n<!-- page_start: 4 -->\n## Next\nPipelines test.\n", encoding="utf-8")

    settings = Settings()
    chunks = chunk_markdown(path, settings=settings, doc_id="lesson")

    assert [chunk.page_num for chunk in chunks] == [3, 4]
    assert chunks[0].heading_path == ["Intro"]
    assert chunks[1].heading_path == ["Next"]
