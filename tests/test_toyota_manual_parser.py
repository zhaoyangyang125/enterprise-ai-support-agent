from pathlib import Path

from app.document_processing.toyota_manual_parser import (
    ToyotaManualParser, model_name_from_file, normalize_cid, version_from_file)


def test_model_name_from_file():
    assert model_name_from_file(Path("COROLLA-COROLLA-TOURING_MM_JP_M12F43_2_2207.pdf")) == "COROLLA COROLLA TOURING"


def test_split_body_keeps_callout_with_procedure():
    body = ["画面の指示に従って手順を実行します。完了すると接続状態が表示されます。", "\n【警告】", "●運転中は安全のため操作しないでください。"]
    pieces = ToyotaManualParser._split_body(body)
    assert len(pieces) == 1 and "【警告】" in pieces[0]


def test_toc_page_detected():
    lines = [{"text": f"項目{i}………{i}"} for i in range(8)]
    assert ToyotaManualParser._is_toc(lines)


def test_version_from_file_uses_trailing_yymm():
    assert version_from_file(Path("PRIUS_MM_JP_M47F64N_1_2507.pdf")) == "2025-07"
    assert version_from_file(Path("manual.pdf")) == "manual"


def test_normalize_cid_restores_bullet_and_drops_unknown():
    assert normalize_cid("(cid:79)画面を選択する(cid:111)P.27") == "●画面を選択する→P.27"
    assert normalize_cid("a(cid:9999)b") == "ab"


def test_split_section_label():
    from app.document_processing.toyota_manual_parser import split_section_label
    assert split_section_label("2-11. Bluetooth 設定") == ("2-11", "2")
    assert split_section_label("") == (None, None)
    assert split_section_label("はじめに") == (None, None)


def test_wrapped_heading_lines_are_merged():
    def line(text, top):
        return {"text": text, "size": 12.0, "bold": True, "top": top, "col": 0}
    groups = ToyotaManualParser()._group([line("Bluetooth 機器を登", 100), line("録する", 114),
                                          {"text": "本文です。", "size": 9.0, "bold": False, "top": 130, "col": 0}])
    assert groups == [("Bluetooth 機器を登録する", ["本文です。"])]


def test_parse_assigns_sequential_chunk_index(monkeypatch):
    from app.schemas.document import ParsedBlock
    blocks = [ParsedBlock(content=f"b{i}") for i in range(3)]

    class _Pdf:
        pages = [object()]
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr("app.document_processing.toyota_manual_parser.pdfplumber.open", lambda p: _Pdf())
    monkeypatch.setattr(ToyotaManualParser, "_parse_page", lambda self, page, n, model: blocks)
    out = ToyotaManualParser().parse(Path("X_MM_JP_1_2507.pdf"))
    assert [b.chunk_index for b in out] == [0, 1, 2]


def test_extract_page_refs():
    from app.document_processing.toyota_manual_parser import extract_page_refs
    assert extract_page_refs("接続します。（→P.41）また（→P.50、57）を参照。") == "41,50,57"
    assert extract_page_refs("（→P.41）（→P.41）") == "41"
    assert extract_page_refs("（→P.19）", own_page=19) is None
    assert extract_page_refs("参照なし") is None


def test_split_header_returns_printed_page():
    lines = [{"text": "18 1-1. 基本操作", "size": 9.0, "bold": False, "top": 10, "col": 0},
             {"text": "本文", "size": 9.0, "bold": False, "top": 30, "col": 0}]
    label, page, rest = ToyotaManualParser._split_header(lines)
    assert (label, page, [l["text"] for l in rest]) == ("1-1. 基本操作", 18, ["本文"])
