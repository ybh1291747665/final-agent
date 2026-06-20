from __future__ import annotations

import importlib
import sys
import warnings


def test_query_expander_import_is_lazy():
    sys.modules.pop("final_agent.retrieval.query_expander", None)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module("final_agent.retrieval.query_expander")

    assert not any("pkg_resources is deprecated" in str(item.message) for item in caught)


def test_expand_query_suppresses_jieba_pkg_resources_warning():
    from final_agent.retrieval.query_expander import expand_query

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        variants = expand_query("配置管理")

    assert variants[0] == "配置管理"
    assert not any("pkg_resources is deprecated" in str(item.message) for item in caught)
