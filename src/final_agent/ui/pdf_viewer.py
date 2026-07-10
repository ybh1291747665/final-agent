from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any

import streamlit as st

from final_agent.ui.agent_client import AgentApiClient, AgentApiError


def pdf_documents(documents: dict[str, dict]) -> dict[str, dict]:
    return {
        doc_id: info
        for doc_id, info in documents.items()
        if Path(str(info.get("source_path", ""))).suffix.lower() == ".pdf"
    }


def pdf_page_image_html(image: bytes, *, zoom: int, alt: str, page_num: int) -> str:
    encoded = base64.b64encode(image).decode("ascii")
    safe_alt = html.escape(alt, quote=True)
    safe_zoom = max(50, min(int(zoom), 200))
    return f"""
<figure class="fa-pdf-page" data-page="{int(page_num)}">
  <img
    src="data:image/png;base64,{encoded}"
    alt="{safe_alt}"
    style="width: {safe_zoom}%; max-width: none; height: auto; display: block; margin: 0 auto;"
  />
</figure>
""".strip()


def pdf_document_html(
    pages: list[tuple[int, bytes]],
    *,
    zoom: int,
    label: str,
) -> str:
    safe_label = html.escape(label, quote=True)
    body = "\n".join(
        pdf_page_image_html(
            image,
            zoom=zoom,
            alt=f"{safe_label} page {page_num}",
            page_num=page_num,
        )
        for page_num, image in pages
    )
    return f"""
<div class="fa-pdf-document-scroll" aria-label="{safe_label}">
{body}
</div>
""".strip()


def render_pdf_viewer(state: Any, documents: dict[str, dict]) -> None:
    st.subheader("PDF 原文")
    available = pdf_documents(documents)
    if not available:
        st.info("上传 PDF 后，可以在这里连续滚动浏览原文并核验引用。")
        return

    doc_ids = list(available)
    if state.active_pdf_doc not in available:
        state.active_pdf_doc = doc_ids[-1]
        state.active_pdf_page = 1

    labels = {
        doc_id: Path(str(info.get("source_path", ""))).name or doc_id
        for doc_id, info in available.items()
    }

    toolbar_doc, toolbar_meta, toolbar_zoom = st.columns([0.58, 0.18, 0.24], gap="small")
    with toolbar_doc:
        selected = st.selectbox(
            "文档",
            doc_ids,
            index=doc_ids.index(state.active_pdf_doc),
            format_func=lambda doc_id: labels[doc_id],
            key="pdf_viewer_document",
            label_visibility="collapsed",
        )
    if selected != state.active_pdf_doc:
        state.active_pdf_doc = selected
        state.active_pdf_page = 1

    client = AgentApiClient()
    try:
        info = client.get_document(state.active_pdf_doc)
        total_pages = int(info["total_pages"])
    except AgentApiError as exc:
        st.warning(f"暂时无法打开 PDF：{exc}")
        return

    state.active_pdf_page = min(max(1, state.active_pdf_page), total_pages)
    with toolbar_meta:
        st.caption(f"{total_pages} 页")
    with toolbar_zoom:
        zoom = st.selectbox(
            "缩放",
            [100, 125, 150],
            index=[100, 125, 150].index(state.pdf_zoom),
            format_func=lambda value: f"{value}%",
            key="pdf_zoom",
            label_visibility="collapsed",
        )
    state.pdf_zoom = int(zoom)

    pages: list[tuple[int, bytes]] = []
    for page_num in range(1, total_pages + 1):
        try:
            pages.append(
                (
                    page_num,
                    client.get_document_page(
                        state.active_pdf_doc,
                        page_num,
                        state.pdf_zoom,
                    ),
                )
            )
        except AgentApiError as exc:
            st.warning(f"第 {page_num} 页渲染失败：{exc}")
            break

    if pages:
        st.markdown(
            pdf_document_html(
                pages,
                zoom=state.pdf_zoom,
                label=labels[state.active_pdf_doc],
            ),
            unsafe_allow_html=True,
        )
