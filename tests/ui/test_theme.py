from __future__ import annotations


def test_apple_theme_css_contains_design_tokens_and_accessibility_guards():
    from final_agent.ui.theme import apple_theme_css

    css = apple_theme_css()

    assert "--fa-bg: #f5f5f7" in css
    assert "--fa-blue: #007aff" in css
    assert "-apple-system" in css
    assert "min-height: 44px" in css
    assert "prefers-reduced-motion" in css
    assert "letter-spacing: 0" in css


def test_app_header_html_escapes_dynamic_status_values():
    from final_agent.ui.theme import app_header_html

    html = app_header_html(
        knowledge_status="知识库状态：<ready>",
        active_mode="问答",
        course_label="全部课件",
    )

    assert "RAG-Powered Study Assistant" in html
    assert "知识库状态：&lt;ready&gt;" in html
    assert "当前模式：问答" in html
    assert "课程范围：全部课件" in html

