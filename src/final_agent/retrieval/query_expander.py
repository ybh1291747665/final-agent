"""Query expansion — jieba tokenisation + synonym extension for better recall."""

from __future__ import annotations

import jieba

# Minimal synonym dictionary for Chinese academic terms
_SYNONYMS: dict[str, list[str]] = {
    "导数": ["微分", "求导", "derivative"],
    "极限": ["limit", "趋近"],
    "积分": ["不定积分", "定积分", "integral"],
    "函数": ["function", "映射"],
    "微积分": ["calculus", "微分学"],
    "矩阵": ["matrix", "方阵"],
    "向量": ["vector", "矢量"],
}


def expand_query(query: str, max_variants: int = 3) -> list[str]:
    """Generate query variants via token-level synonym substitution.

    Args:
        query: Original user query.
        max_variants: Cap on total variants returned (including original).

    Returns:
        List of query strings, with the original first.
    """
    tokens = [t.strip() for t in jieba.cut(query) if t.strip()]
    variants: list[str] = [query]

    for token in tokens:
        if token in _SYNONYMS:
            for syn in _SYNONYMS[token]:
                variant = query.replace(token, syn, 1)
                if variant != query and variant not in variants:
                    variants.append(variant)
                    if len(variants) >= max_variants:
                        return variants

    return variants
