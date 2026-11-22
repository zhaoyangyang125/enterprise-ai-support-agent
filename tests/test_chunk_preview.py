import json
import re
from pathlib import Path

from app.schemas.document import ParsedBlock
from scripts.chunk_preview import write_preview


def _blocks() -> list[ParsedBlock]:
    return [
        ParsedBlock(content="[M / 1-1. A]\n短い", page=3, section="1-1. A", section_no="1-1", chunk_index=0, printed_page=1),
        ParsedBlock(content="x" * 800 + "</script><b>", page=4, section=None, chunk_index=1),
    ]


def test_write_preview_creates_book_page_and_index(tmp_path: Path):
    out = tmp_path / "prev"
    page = write_preview(tmp_path / "BOOK_MM_JP_1_2507.pdf", _blocks(), out)
    assert page.name == "BOOK_MM_JP_1_2507.html"
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "BOOK_MM_JP_1_2507.html" in index
    stats = json.loads((out / "index.json").read_text(encoding="utf-8"))["BOOK_MM_JP_1_2507"]
    assert (stats["chunks"], stats["long"], stats["no_section"]) == (2, 1, 1)


def test_book_page_embeds_data_safely_and_links_pdf_page(tmp_path: Path):
    page = write_preview(tmp_path / "B.pdf", _blocks(), tmp_path / "p").read_text(encoding="utf-8")
    assert page.count("</script>") == 1  # chunk text containing </script> must not close the block
    assert "#page=" in page and "file:///" in page and "<img id=pg" in page


def test_second_book_is_added_to_index_not_replacing(tmp_path: Path):
    out = tmp_path / "p"
    write_preview(tmp_path / "A.pdf", _blocks(), out)
    write_preview(tmp_path / "B.pdf", _blocks(), out)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert re.search(r"A\.html", index) and re.search(r"B\.html", index)
