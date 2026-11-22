"""分块結果の目視確認用ページを自動生成する。 / Generates local pages for eyeballing chunks.

出力先 (.chunk_preview/、git管理外):
    index.html          処理済み手册の一覧と統計
    <手册名>.html       左=分块一覧(検索/超長のみ)、右=クリックした分块の元PDFページ
The right pane shows the chunk's PDF page as a small JPEG (rendered once, cached under .chunk_preview/pages/).
"""
from __future__ import annotations

import html
import json
import statistics
from datetime import datetime
from pathlib import Path

from app.schemas.document import ParsedBlock

LONG_CHARS = 700
SHORT_CHARS = 100
DEFAULT_OUT = Path(".chunk_preview")

_BOOK_PAGE = """<!doctype html><meta charset="utf-8"><title>{title}</title>
<style>
body{{margin:0;font:14px system-ui;display:grid;grid-template-columns:minmax(380px,44%) 1fr;height:100vh}}
#l{{overflow:auto;padding:10px 14px;border-right:1px solid #ccc}}#r{{display:flex;flex-direction:column;min-width:0}}
#w{{flex:1;overflow:auto;background:#888}}#pg{{display:block;width:100%;max-width:900px;margin:0 auto}}
#bar{{padding:6px 10px;border-bottom:1px solid #ccc;font-size:12px;color:#555}}
.c{{border:1px solid #ccc;border-radius:6px;margin:8px 0;padding:8px;cursor:pointer}}
.c.long{{border-color:#d33}}.c.short{{border-color:#d90}}.c.sel{{background:#eef5ff;outline:2px solid #4a8af4}}
.m{{color:#666;font-size:12px}}pre{{white-space:pre-wrap;margin:4px 0 0;font:13px/1.5 system-ui}}
input[type=text]{{width:220px}}h3{{margin:0 0 6px}}a{{color:#0a58ca}}
</style>
<div id=l><h3>{title}</h3><a href="index.html">&larr; index</a><div class=m>{summary}</div>
<p><input type=text id=q placeholder="search text / section / heading">
<label><input type=checkbox id=lg> long (&gt;{long})</label>
<label><input type=checkbox id=sh> short (&lt;{short})</label>
<label><input type=checkbox id=ns> no section</label> <span id=n></span></p>
<div class=m>click a chunk (or use &uarr; &darr;) &mdash; the PDF page appears on the right</div><div id=o></div></div>
<div id=r><div id=bar><span id=bt></span> <a id=pl target=_blank>open PDF at this page</a></div>
<div id=w><img id=pg alt="page image"></div></div>
<script>
const D={data},IMG={img},PDF={pdf},o=document.getElementById('o'),pg=document.getElementById('pg'),pl=document.getElementById('pl'),
 bt=document.getElementById('bt'),w=document.getElementById('w'),q=document.getElementById('q'),lg=document.getElementById('lg'),
 sh=document.getElementById('sh'),ns=document.getElementById('ns'),n=document.getElementById('n');
let sel=null,els=[];
function show(c,el){{if(sel)sel.classList.remove('sel');sel=el;el.classList.add('sel');
 pg.src=IMG+c.p+'.jpg';pg.onerror=()=>{{pg.removeAttribute('src');}};w.scrollTop=0;
 bt.textContent='PDF p.'+c.p+(c.pp?' (printed '+c.pp+')':'')+' · chunk #'+c.i;pl.href=PDF+'#page='+c.p;
 el.scrollIntoView({{block:'nearest'}});}}
function r(){{const s=q.value.toLowerCase();let k=0;o.innerHTML='';els=[];sel=null;
 D.forEach((c,i)=>{{const L=c.t.length;
  if(lg.checked&&L<={long})return;if(sh.checked&&L>={short})return;if(ns.checked&&c.sn)return;
  if(s&&!(c.t+' '+(c.s||'')+' '+(c.h||'')).toLowerCase().includes(s))return;k++;
  const d=document.createElement('div');d.className='c'+(L>{long}?' long':'')+(L<{short}?' short':'');
  d.innerHTML='<div class=m></div><pre></pre>';
  d.firstChild.textContent='#'+c.i+' | PDF p.'+c.p+(c.pp?' (printed '+c.pp+')':'')+' | '+c.k+' | '+L+' chars | '+(c.s||'(no section)')+(c.refs?' | refs '+c.refs:'');
  d.lastChild.textContent=c.t;d.onclick=()=>show(c,d);d.cdata=c;o.appendChild(d);els.push(d)}});
 n.textContent=k+' / '+D.length;if(els.length)show(els[0].cdata,els[0])}}
document.addEventListener('keydown',e=>{{if(e.target===q||!els.length)return;
 const i=els.indexOf(sel);if(e.key==='ArrowDown'){{e.preventDefault();const t=els[Math.min(els.length-1,i+1)];show(t.cdata,t)}}
 if(e.key==='ArrowUp'){{e.preventDefault();const t=els[Math.max(0,i-1)];show(t.cdata,t)}}}});
q.oninput=lg.onchange=sh.onchange=ns.onchange=r;r();
</script>"""

_INDEX_PAGE = """<!doctype html><meta charset="utf-8"><title>chunk preview</title>
<style>body{{font:14px system-ui;margin:20px}}table{{border-collapse:collapse}}
td,th{{border:1px solid #ccc;padding:5px 10px;text-align:right}}td:first-child,th:first-child{{text-align:left}}
.bad{{color:#d33;font-weight:600}}</style>
<h3>Chunk preview ({count} books)</h3>
<table><tr><th>book<th>chunks<th>median<th>p90<th>long &gt;{long}<th>short &lt;{short}<th>no section<th>tables<th>updated</tr>
{rows}</table>"""


def _stats(blocks: list[ParsedBlock]) -> dict:
    sizes = sorted(len(b.content) for b in blocks) or [0]
    return {
        "chunks": len(blocks),
        "median": int(statistics.median(sizes)),
        "p90": sizes[int(len(sizes) * 0.9)] if len(sizes) > 1 else sizes[0],
        "long": sum(s > LONG_CHARS for s in sizes),
        "short": sum(s < SHORT_CHARS for s in sizes),
        "no_section": sum(not b.section for b in blocks),
        "tables": sum(b.content_type == "table" for b in blocks),
    }


def _json_for_script(value: object) -> str:
    # "</" would end the <script> block early; U+2028/2029 break old JS parsers.
    return (json.dumps(value, ensure_ascii=False)
            .replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _render_pages(pdf_path: Path, pages: set[int], target_dir: Path) -> int:
    """分块が参照するPDFページを小さな画像にして保存する(既にあれば飛ばす)。 / Renders the referenced PDF pages to small JPEGs; existing files are reused."""
    if not pdf_path.exists():
        return 0
    try:
        import pymupdf
    except ImportError:
        return 0
    target_dir.mkdir(parents=True, exist_ok=True)
    made = 0
    with pymupdf.open(pdf_path) as doc:
        for number in sorted(pages):
            path = target_dir / f"p{number}.jpg"
            if path.exists() or not 1 <= number <= len(doc):
                continue
            pix = doc[number - 1].get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25))
            pix.save(str(path), jpg_quality=70)
            made += 1
    return made


def write_preview(pdf_path: Path, blocks: list[ParsedBlock], out_dir: Path = DEFAULT_OUT, render: bool = True) -> Path:
    """この手册の分块ページを書き出し、一覧(index.html)も更新する。 / Writes the book page and refreshes index.html."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if render:
        _render_pages(pdf_path, {b.page or 1 for b in blocks}, out_dir / "pages" / pdf_path.stem)
    stats = _stats(blocks)
    data = [{"i": b.chunk_index if b.chunk_index is not None else n, "t": b.content, "p": b.page or 1,
             "pp": b.printed_page, "k": b.content_type, "s": b.section, "h": b.heading,
             "sn": b.section_no, "refs": b.refs} for n, b in enumerate(blocks)]
    summary = (f"{stats['chunks']} chunks, median {stats['median']}, p90 {stats['p90']}, "
               f"long {stats['long']}, short {stats['short']}, no-section {stats['no_section']}")
    target = out_dir / f"{pdf_path.stem}.html"
    target.write_text(_BOOK_PAGE.format(
        title=html.escape(pdf_path.name), summary=html.escape(summary), long=LONG_CHARS, short=SHORT_CHARS,
        data=_json_for_script(data), img=_json_for_script(f"pages/{pdf_path.stem}/p"),
        pdf=_json_for_script(pdf_path.resolve().as_uri())), encoding="utf-8")
    _update_index(out_dir, pdf_path.stem, stats)
    return target


def _update_index(out_dir: Path, stem: str, stats: dict) -> None:
    index_json = out_dir / "index.json"
    try:
        books = json.loads(index_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        books = {}
    books[stem] = {**stats, "updated": datetime.now().strftime("%Y-%m-%d %H:%M")}
    index_json.write_text(json.dumps(books, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = "\n".join(
        f"<tr><td><a href=\"{html.escape(name)}.html\">{html.escape(name)}</a>"
        f"<td>{s['chunks']}<td>{s['median']}<td>{s['p90']}"
        f"<td{' class=bad' if s['long'] else ''}>{s['long']}"
        f"<td>{s['short']}<td{' class=bad' if s['no_section'] else ''}>{s['no_section']}"
        f"<td>{s['tables']}<td>{html.escape(s['updated'])}</tr>"
        for name, s in sorted(books.items()))
    (out_dir / "index.html").write_text(
        _INDEX_PAGE.format(count=len(books), long=LONG_CHARS, short=SHORT_CHARS, rows=rows), encoding="utf-8")
