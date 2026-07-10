from __future__ import annotations


def test_pdf_documents_filters_non_pdf_sources():
    from final_agent.ui.pdf_viewer import pdf_documents

    documents = {
        "pdf": {"source_path": "E:/courses/lecture.PDF"},
        "markdown": {"source_path": "E:/courses/lesson.md"},
        "missing": {},
    }

    assert pdf_documents(documents) == {
        "pdf": {"source_path": "E:/courses/lecture.PDF"}
    }


def test_pdf_image_html_uses_zoom_as_visible_width():
    from final_agent.ui.pdf_viewer import pdf_page_image_html

    html = pdf_page_image_html(b"\x89PNG\r\n", zoom=150, alt="lecture page", page_num=3)

    assert "width: 150%;" in html
    assert 'class="fa-pdf-page"' in html
    assert 'data-page="3"' in html
    assert "data:image/png;base64," in html
    assert 'alt="lecture page"' in html


def test_pdf_document_html_wraps_pages_in_one_scroll_container():
    from final_agent.ui.pdf_viewer import pdf_document_html

    html = pdf_document_html(
        [
            (1, b"\x89PNG\r\n"),
            (2, b"\x89PNG\r\n"),
        ],
        zoom=125,
        label="lecture.pdf",
    )

    assert html.count('class="fa-pdf-page"') == 2
    assert 'class="fa-pdf-document-scroll"' in html
    assert "lecture.pdf" in html
    assert "width: 125%;" in html
