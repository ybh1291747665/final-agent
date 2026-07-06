from __future__ import annotations


def test_unpack_pie_result_accepts_without_autopct():
    from final_agent.ui.charts import unpack_pie_result

    wedges, texts, autotexts = unpack_pie_result((["wedge"], ["label"]))

    assert wedges == ["wedge"]
    assert texts == ["label"]
    assert autotexts == []


def test_unpack_pie_result_accepts_with_autopct():
    from final_agent.ui.charts import unpack_pie_result

    wedges, texts, autotexts = unpack_pie_result((["wedge"], ["label"], ["percent"]))

    assert wedges == ["wedge"]
    assert texts == ["label"]
    assert autotexts == ["percent"]

