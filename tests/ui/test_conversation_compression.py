from __future__ import annotations


def test_conversation_compressor_summarizes_old_messages_and_keeps_recent():
    from final_agent.ui.conversation_compression import ConversationCompressor

    history = [
        {
            "role": "assistant",
            "content": f"answer {idx}",
            "chunk_registry": {
                "chunk-a": {
                    "text": "full chunk text that should not stay in persisted history",
                    "doc_id": "doc-a",
                    "page_num": 1,
                    "heading": "Intro",
                }
            },
        }
        for idx in range(10)
    ]

    compressed = ConversationCompressor(max_messages=8, keep_recent=4).compress(
        {"name": "demo", "history": history}
    )

    assert "conversation_summary" in compressed
    assert len(compressed["history"]) == 4
    assert "answer 0" in compressed["conversation_summary"]
    assert "text" not in compressed["history"][0]["chunk_registry"]["chunk-a"]
    assert compressed["history"][0]["chunk_registry"]["chunk-a"]["summary"]


def test_conversation_compressor_sanitizes_registry_even_without_summary():
    from final_agent.ui.conversation_compression import ConversationCompressor

    compressed = ConversationCompressor(max_messages=8).compress(
        {
            "history": [
                {
                    "role": "assistant",
                    "content": "short",
                    "chunk_registry": {"chunk-a": {"text": "secret full text", "doc_id": "doc-a"}},
                }
            ]
        }
    )

    assert "text" not in compressed["history"][0]["chunk_registry"]["chunk-a"]
    assert compressed["history"][0]["chunk_registry"]["chunk-a"]["summary"] == "secret full text"
