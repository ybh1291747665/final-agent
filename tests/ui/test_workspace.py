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
