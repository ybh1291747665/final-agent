from __future__ import annotations


def test_token_budgeter_counts_and_truncates_multilingual_text():
    from final_agent.token_budget import TokenBudgeter

    budgeter = TokenBudgeter()
    text = "Continuous integration 持续集成 helps teams detect issues early."

    assert budgeter.count_tokens(text) > 0
    truncated = budgeter.truncate_to_tokens(text, 5)

    assert budgeter.count_tokens(truncated) <= 5
    assert truncated


def test_token_budgeter_fits_items_to_budget():
    from final_agent.token_budget import TokenBudgeter

    budgeter = TokenBudgeter()
    items = ["short", "another short", "x" * 500]

    selected = budgeter.fit_items_to_budget(items, 20, lambda item: item)

    assert selected
    assert selected[0] == "short"
