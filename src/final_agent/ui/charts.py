from __future__ import annotations

from typing import Any


_CJK_FONT_CANDIDATES = [
    "Microsoft YaHei",
    "SimHei",
    "Microsoft JhengHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Arial Unicode MS",
]


def unpack_pie_result(result: tuple[Any, ...]) -> tuple[Any, Any, list[Any]]:
    """Normalize matplotlib pie return values across autopct branches."""
    wedges, texts, *rest = result
    autotexts = list(rest[0]) if rest else []
    return wedges, texts, autotexts


def cjk_font_properties() -> Any | None:
    """Return a matplotlib FontProperties that can render Chinese text."""
    try:
        from matplotlib import font_manager
    except Exception:
        return None

    available = {font.name: font.fname for font in font_manager.fontManager.ttflist}
    for name in _CJK_FONT_CANDIDATES:
        if name in available:
            return font_manager.FontProperties(fname=available[name])
    return None

