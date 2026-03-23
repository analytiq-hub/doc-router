"""Regression: image-only / no LINE text must still yield a per-page text map."""

from analytiq_data.aws.textract import page_text_map_from_ocr_document


class _Page:
    def __init__(self, page_num, text="", pid="p"):
        self.page_num = page_num
        self.text = text
        self.id = pid


class _Doc:
    def __init__(self, pages):
        self.pages = pages


def test_page_text_map_fallback_when_page_num_invalid():
    """No page has page_num > 0 — still map one row per page (often empty)."""
    doc = _Doc(
        [
            _Page(0, "", "a"),
            _Page(0, "", "b"),
        ]
    )
    m = page_text_map_from_ocr_document(doc)
    assert m == {0: "", 1: ""}


def test_page_text_map_normal_path_by_page_num():
    doc = _Doc([_Page(1, "hello\n", "a")])
    m = page_text_map_from_ocr_document(doc)
    assert m == {0: "hello\n"}
