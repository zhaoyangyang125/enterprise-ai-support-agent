"""PDF の分块結果を単一HTMLに書き出して目視確認する。 / Dumps parsed chunks into one self-contained HTML page.

Usage (repo root, venv active):
    python -m scripts.inspect_chunks --only COROLLA
Output: .chunk_preview/<name>.html (open in a browser; search box + "long only" filter).
"""
import argparse
import html
import json
from pathlib import Path

from app.document_processing.toyota_manual_parser import ToyotaManualParser

_PAGE = """<!doctype html><meta charset="utf-8"><title>{title}</title>
<style>body{{font:14px system-ui;margin:16px}}.c{{border:1px solid #ccc;border-radius:6px;margin:8px 0;padding:8px}}
.c.long{{border-color:#d33}}.m{{color:#666;font-size:12px}}pre{{white-space:pre-wrap;margin:4px 0 0}}</style>
<h3>{title}</h3><input id=q placeholder="search" size=30> <label><input type=checkbox id=l> long (&gt;{maxc})</label>
<span id=n></span><div id=o></div>
<script>const D={data};const q=document.getElementById('q'),l=document.getElementById('l'),o=document.getElementById('o'),n=document.getElementById('n');
function r(){{const s=q.value.toLowerCase();let k=0;o.innerHTML='';D.forEach((c,i)=>{{
if(l.checked&&c.t.length<={maxc})return;if(s&&!c.t.toLowerCase().includes(s))return;k++;
const d=document.createElement('div');d.className='c'+(c.t.length>{maxc}?' long':'');
d.innerHTML='<div class=m>#'+i+' | p.'+(c.p||'?')+' | '+c.k+' | '+c.t.length+' chars | '+(c.s||'(no section)')+'</div><pre></pre>';
d.querySelector('pre').textContent=c.t;o.appendChild(d)}});n.textContent=' '+k+' / '+D.length}}
q.oninput=l.onchange=r;r()</script>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path(__file__).resolve().parents[2] / "toyota-manuals")
    ap.add_argument("--only", required=True, help="file-name substring, e.g. COROLLA")
    ap.add_argument("--out", type=Path, default=Path(".chunk_preview"))
    args = ap.parse_args()
    args.out.mkdir(exist_ok=True)
    for path in sorted(p for p in args.dir.glob("*.pdf") if args.only.casefold() in p.name.casefold()):
        blocks = ToyotaManualParser().parse(path)
        data = [{"t": b.content, "p": b.page, "k": b.content_type, "s": getattr(b, "section", None)} for b in blocks]
        target = args.out / f"{path.stem}.html"
        target.write_text(_PAGE.format(title=html.escape(path.name), maxc=700,
                                       data=json.dumps(data, ensure_ascii=False).replace("</", "<\\/")),
                          encoding="utf-8")
        print(target)


if __name__ == "__main__":
    main()
