"""トヨタ車載機取扱書(MM)向けの構造認識パーサ。 / Structure-aware parser for Toyota multimedia owner's manuals.

固定長ではなく見出し階層で分割し、各チャンクに「車種 / 章 / 節 / 見出し」のパンくずを付ける。
Chunks follow the heading hierarchy; each carries a breadcrumb "model / chapter / section / heading".
警告・注意・知識 callouts stay with the procedure they belong to. Real tables become key-value rows.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pdfplumber

from app.schemas.document import ParsedBlock

_HEADER_RE = re.compile(r"^(?:(\d{1,3})\s+)?(\d{1,2}-\d{1,2}\.\s*\S.*?)(?:\s+(\d{1,3}))?$")
_CALLOUT_LABELS = {"警告": "警告", "注意": "注意", "知識": "知識", "参考": "参考"}
_BULLET = "●"
_MAX_CHARS = 700
_MIN_CHARS = 40
_MIN_HEADED_CHARS = 8  # 見出しの下の短い本文は単独の分块として残す / short bodies under a heading are kept
_TARGET_CHARS = 400  # この長さに達したら、次の ● の行で区切る(それまでは1塊のまま)
_SINGLE_COLUMN_CROSS_RATIO = 0.15
_HEADING_SHADE = (0.7, 0.86)  # 見出しボックスの灰色(0.82)。説明ボックスは0.9で本文なので除外 / heading boxes are 0.82; lighter 0.9 boxes hold body text
_ROW_CENTRE_RATIO = 0.55  # 同一行とみなす垂直中心の差(字高に対する比) / max centre offset on one line, as a share of font size
_HEADING_WRAP_GAP = 30  # 見出しの折り返しとみなす行間(pt)
_HEADER_BAND = 150  # ページ上部の全幅ヘッダ領域
_SENTENCE_END_RE = re.compile(r"(?<=[。！？])")
_TOC_LEADER_RE = re.compile(r"[….・.]{3,}\s*\d+\s*$")


def model_name_from_file(path: Path) -> str:
    """ファイル名から車種名を取り出す。 / Derives the model name from the file name."""
    return path.name.split("_MM_")[0].replace("-", " ")


_CID_MAP = {79: "●", 111: "→", 81: "■"}
_CID_RE = re.compile(r"\(cid:(\d+)\)")


def normalize_cid(text: str) -> str:
    """フォント未対応で `(cid:N)` と出力された記号を戻す(COROLLA版)。未知のCIDは削除。
    Restores undecoded glyphs such as `(cid:79)` -> bullet; unknown CIDs are dropped."""
    return _CID_RE.sub(lambda m: _CID_MAP.get(int(m.group(1)), ""), text)


def _luminance(color) -> float | None:
    """pdfplumberの塗り色(数値/タプル)を0..1の明るさにする。 / Normalizes a fill colour to 0..1 brightness."""
    if isinstance(color, (int, float)):
        return float(color)
    if isinstance(color, (list, tuple)) and color and all(isinstance(c, (int, float)) for c in color):
        return sum(color) / len(color) if len(color) != 4 else 1 - min(1.0, sum(color[:3]) / 3 + color[3])
    return None


def gray_heading_boxes(page) -> list[tuple[float, float, float, float]]:
    """灰色の塗りつぶし横長ボックス(本文と同じ字でも見出しとして使われる)の範囲。
    Wide, short gray filled boxes: this manual styles some headings by background only."""
    boxes = []
    for r in page.rects:
        if not r.get("fill"):
            continue
        shade = _luminance(r.get("non_stroking_color"))
        if shade is not None and _HEADING_SHADE[0] < shade < _HEADING_SHADE[1] and r["width"] > 100 and 10 < r["height"] < 45:
            boxes.append((r["x0"], r["top"], r["x1"], r["bottom"]))
    return boxes


_SECTION_NO_RE = re.compile(r"^(\d{1,2})-\d{1,2}(?=\.)")


def split_section_label(label: str) -> tuple[str | None, str | None]:
    """"2-11. Bluetooth 設定" -> ("2-11", "2")。節ラベルから節番号と章番号を取り出す。
    Extracts (section_no, chapter) from a section label; (None, None) if absent."""
    m = _SECTION_NO_RE.match(label or "")
    return (m.group(0), m.group(1)) if m else (None, None)


_PAGE_REF_RE = re.compile(r"P\.\s*(\d{1,3})((?:\s*[、,・]\s*(?:P\.\s*)?\d{1,3})*)")


def extract_page_refs(text: str, own_page: int | None = None) -> str | None:
    """「(→P.41)」「P.50、57」などの参照先ページをカンマ区切りで返す(自ページは除く)。
    Returns referenced printed pages as "41,55" (order kept, deduplicated), or None."""
    pages: list[int] = []
    for m in _PAGE_REF_RE.finditer(text):
        for value in [m.group(1), *re.findall(r"\d{1,3}", m.group(2))]:
            page = int(value)
            if page != own_page and page not in pages:
                pages.append(page)
    return ",".join(map(str, pages)) or None


def version_from_file(path: Path) -> str:
    """ファイル名末尾の発行年月(YYMM)から版ラベルを作る。 / Builds a version label from the trailing YYMM, e.g. 2025-07."""
    tail = path.stem.rsplit("_", 1)[-1]
    if re.fullmatch(r"\d{4}", tail):
        return f"20{tail[:2]}-{tail[2:]}"
    return path.stem


class ToyotaManualParser:
    """トヨタMM取扱書PDFをParsedBlockへ変換する。 / Converts a Toyota MM manual PDF into ParsedBlocks."""

    def parse(self, path: Path, document_id: str | None = None,
              document_version_id: str | None = None) -> list[ParsedBlock]:
        model = model_name_from_file(path)
        blocks: list[ParsedBlock] = []
        with pdfplumber.open(path) as pdf:
            for number, page in enumerate(pdf.pages, start=1):
                blocks.extend(self._parse_page(page, number, model))
        return [b.model_copy(update={"chunk_index": i}) for i, b in enumerate(blocks)]

    # -- page level -------------------------------------------------------
    def _parse_page(self, page, number: int, model: str) -> list[ParsedBlock]:
        if len(page.chars) < 30:
            return []
        table_blocks, table_boxes = self._tables(page, number, model)
        lines = self._lines(page, table_boxes)
        if not lines or self._is_toc(lines):
            return []
        label, printed_page, lines = self._split_header(lines)
        if number <= 8 and not label and not any(l["bold"] and l["size"] >= 11.5 for l in lines):
            return []  # front-matter contents/illustration index
        table_blocks = self._label_tables(page, table_blocks, table_boxes, label, model)
        section_no, chapter = split_section_label(label)
        table_blocks = [b.model_copy(update={"chapter": chapter, "section_no": section_no,
                                             "printed_page": printed_page,
                                             "refs": extract_page_refs(b.content, printed_page)})
                        for b in table_blocks]
        chunks = self._group(lines)
        blocks = list(table_blocks)
        for heading, body in chunks:
            for piece in self._split_body(body, _MIN_HEADED_CHARS if heading else _MIN_CHARS):
                crumb = " / ".join(p for p in (model, label, heading) if p)
                blocks.append(ParsedBlock(
                    content=f"[{crumb}]\n{piece}", content_type="paragraph",
                    extraction_method="text_layer", page=number,
                    section=" / ".join(p for p in (label, heading) if p) or None,
                    chapter=chapter, section_no=section_no, heading=heading or None,
                    printed_page=printed_page, refs=extract_page_refs(piece, printed_page)))
        return blocks

    @staticmethod
    def _is_toc(lines: list[dict]) -> bool:
        leaders = sum(1 for ln in lines if _TOC_LEADER_RE.search(ln["text"]))
        return leaders >= 5 or (len(lines) > 8 and leaders / len(lines) > 0.4)

    # -- tables -----------------------------------------------------------
    def _tables(self, page, number: int, model: str):
        blocks: list[ParsedBlock] = []
        boxes: list[tuple[float, float, float, float]] = []
        try:
            found = page.find_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
        except Exception:
            return blocks, boxes
        for table in found:
            rows = [[(c or "").replace("\n", "") for c in r] for r in table.extract()]
            rows = [r for r in rows if any(r)]
            if len(rows) < 2 or len(rows[0]) < 2 or not all(rows[0]):
                continue  # not a key-value table: leave to normal text flow
            header = rows[0]
            lines_out = ["; ".join(f"{h}: {v}" for h, v in zip(header, r) if v) for r in rows[1:]]
            text = "\n".join(l for l in lines_out if l)
            if len(text) < _MIN_CHARS:
                continue
            boxes.append(table.bbox)
            blocks.append(ParsedBlock(
                content=f"[{model} / 表]\n" + text, content_type="table",
                extraction_method="text_layer", page=number,
                rows=f"{len(rows) - 1}行"))
        return blocks, boxes

    def _label_tables(self, page, blocks, boxes, label, model):
        """表の左右範囲内で直前にある ■ 見出しと節ラベルを付ける。 / Adds the nearest ■ caption above each table."""
        words = page.extract_words()
        caps = [w for w in words if w["text"].startswith("■")]
        out = []
        for blk, box in zip(blocks, boxes):
            above = [c for c in caps if c["bottom"] <= box[1] + 2 and box[0] - 30 <= c["x0"] <= box[2]]
            cap = ""
            if above:
                y = max(c["top"] for c in above)
                row = sorted((w for w in words if abs(w["top"] - y) < 3 and box[0] - 30 <= w["x0"] <= box[2]),
                             key=lambda w: w["x0"])
                cap = "".join(w["text"] for w in row)[:30]
            crumb = " / ".join(p for p in (model, label, cap) if p)
            body = blk.content.split("\n", 1)[1]
            out.append(blk.model_copy(update={"content": f"[{crumb}]\n{body}",
                                              "section": " / ".join(p for p in (label, cap) if p) or None}))
        return out

    # -- lines ------------------------------------------------------------
    def _lines(self, page, boxes) -> list[dict]:
        def inside(w) -> bool:
            return any(b[0] - 1 <= w["x0"] and w["x1"] <= b[2] + 1 and
                       b[1] - 1 <= w["top"] and w["bottom"] <= b[3] + 1 for b in boxes)
        mid = page.width / 2
        gray = gray_heading_boxes(page)
        two_col = self._is_two_column(page.chars, mid)
        columns = defaultdict(list)
        if two_col:
            # char-level split: Japanese runs have no spaces, so word-level splitting merges across the gutter
            parts = {0: lambda o: o.get("object_type") != "char" or o["top"] < _HEADER_BAND or o["x0"] < mid - 15,
                     1: lambda o: o.get("object_type") == "char" and o["top"] >= _HEADER_BAND and o["x0"] >= mid - 15}
        else:
            parts = {0: lambda o: True}
        for col, keep in parts.items():
            for w in page.filter(keep).extract_words(extra_attrs=["size", "fontname"]):
                w["text"] = normalize_cid(w["text"])
                if w["text"] and not inside(w):
                    columns[col].append(w)
        out: list[dict] = []
        for col in sorted(columns):
            for r in self._cluster_rows(columns[col]):
                x0, x1 = min(w["x0"] for w in r), max(w["x1"] for w in r)
                top, bottom = min(w["top"] for w in r), max(w["bottom"] for w in r)
                boxed = any(b[0] - 2 <= x0 and x1 <= b[2] + 2 and b[1] - 2 <= top and bottom <= b[3] + 2 for b in gray)
                out.append({"text": self._join(r), "boxed": boxed,
                            "size": max(w["size"] for w in r),
                            "bold": any("Bold" in w["fontname"] for w in r),
                            "top": r[0]["top"], "col": col})
        return [l for l in out if l["text"]]

    @staticmethod
    def _is_two_column(chars: list[dict], mid: float) -> bool:
        """中央の余白帯に文字が来る行が少なければ2段組。 / Two-column if few body rows put text in the centre gutter."""
        rows: dict[int, bool] = {}
        for c in chars:
            if c["top"] < _HEADER_BAND:
                continue
            key = round(c["top"] / 4)
            rows[key] = rows.get(key, False) or (mid - 6 < (c["x0"] + c["x1"]) / 2 < mid + 6)
        if len(rows) < 4:
            return False
        return sum(rows.values()) / len(rows) < _SINGLE_COLUMN_CROSS_RATIO

    @staticmethod
    def _cluster_rows(words: list[dict]) -> list[list[dict]]:
        """垂直中心が近い語を同じ行にまとめる。上付き(®)や別フォントのハイフンは数pt上下にずれるため、
        top座標の丸めで分けると別の行になり読み順が壊れる。
        Groups words onto one line when their vertical centres are close: superscripts (®) and hyphens in
        another font sit a few points off, and bucketing by rounded top split them into separate lines."""
        lines: list[dict] = []
        for w in sorted(words, key=lambda w: (w["top"] + w["bottom"]) / 2):
            centre = (w["top"] + w["bottom"]) / 2
            for line in reversed(lines[-3:]):
                if abs(centre - line["centre"]) <= _ROW_CENTRE_RATIO * max(line["size"], w["size"]):
                    line["words"].append(w)
                    if w["size"] > line["size"]:  # the tallest word defines the line
                        line["size"], line["centre"] = w["size"], centre
                    break
            else:
                lines.append({"words": [w], "centre": centre, "size": w["size"]})
        return [sorted(line["words"], key=lambda w: w["x0"]) for line in lines]

    @staticmethod
    def _join(words: list[dict]) -> str:
        """隙間が空いた語だけ空白で結合する。 / Joins words, adding a space only where a visible gap exists."""
        text = words[0]["text"]
        for prev, cur in zip(words, words[1:]):
            text += (" " if cur["x0"] - prev["x1"] > 2.5 else "") + cur["text"]
        return text.strip()

    @staticmethod
    def _split_header(lines):
        for i, ln in enumerate(lines[:3]):
            m = _HEADER_RE.match(ln["text"])
            if m and ln["size"] < 11.5:
                page_text = m.group(1) or m.group(3)
                return m.group(2).strip(), (int(page_text) if page_text else None), lines[:i] + lines[i + 1:]
        return "", None, lines

    # -- grouping -----------------------------------------------------------
    def _group(self, lines: list[dict]):
        groups: list[tuple[str, list[str]]] = []
        heading, body = "", []
        prev = None  # 直前の見出し行 / previous heading line
        for ln in lines:
            text = ln["text"]
            is_big = ln["size"] >= 11.5 and ln["bold"] and len(text) < 40
            is_boxed = (ln.get("boxed") and len(text) < 60 and text not in _CALLOUT_LABELS
                        and not text.startswith(_BULLET))
            if is_big or is_boxed:
                wrapped = (heading and not body and prev is not None and prev["col"] == ln["col"]
                           and 0 <= ln["top"] - prev["top"] < _HEADING_WRAP_GAP)
                if wrapped:
                    heading += text  # 折り返された見出しの続き / continuation of a wrapped heading
                    prev = ln
                    continue
                if body:
                    groups.append((heading, body))
                heading, body = text, []
                prev = ln
                continue
            elif text.startswith("■") and len(text) < 40:
                body.append("\n" + text)
            elif text in _CALLOUT_LABELS:
                body.append("\n【" + _CALLOUT_LABELS[text] + "】")
            else:
                body.append(text)
        if body:
            groups.append((heading, body))
        return groups

    @staticmethod
    def _split_body(body: list[str], min_chars: int = _MIN_CHARS) -> list[str]:
        """行を結合して段落化し、_MAX_CHARS を超えるときだけ ■/●/【 の境界で分割する。"""
        text = ""
        pieces: list[str] = []
        in_callout = False  # 警告/注意/知識/参考の中の ● は見出しラベルと切り離さない
        for ln in body:
            joiner = "\n" if (ln.startswith(("\n", _BULLET)) or ln.startswith("【")) else ""
            if ln.startswith("\n【") or ln.startswith("【"):
                in_callout = True
            elif ln.startswith("\n"):
                in_callout = False
            bullet_break = ln.startswith(_BULLET) and not in_callout and len(text) >= _TARGET_CHARS
            if joiner and text and (bullet_break or len(text) > _MAX_CHARS):
                pieces.append(text.strip())
                text = ""
            text += joiner + ln
        if text.strip():
            pieces.append(text.strip())
        pieces = [q for p in pieces for q in ToyotaManualParser._split_long(p)]
        return [p for p in pieces if len(p) >= min_chars] or ([text.strip()] if len(text.strip()) >= min_chars else [])

    @staticmethod
    def _split_long(piece: str) -> list[str]:
        """区切り記号の無い超過分を文末(。)で分割する。 / Falls back to sentence boundaries for oversize pieces."""
        if len(piece) <= _MAX_CHARS:
            return [piece]
        out, cur = [], ""
        for sent in _SENTENCE_END_RE.split(piece):
            if cur and len(cur) + len(sent) > _MAX_CHARS:
                out.append(cur.strip())
                cur = ""
            cur += sent
        if cur.strip():
            out.append(cur.strip())
        return out
