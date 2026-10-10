#!/usr/bin/env python3
"""
build_site.py — Build the static website into ``_site/``.

The site is plain HTML/CSS/JS in ``site/`` (no framework, no npm). This script
copies it to ``_site/`` and writes ``_site/library.json``: ``catalog.json``
merged with the AI enrichment in ``catalog_ai.json``, trimmed to what the page
needs. The page fetches that one file and does search, filtering and sorting
in the browser.

Usage
-----
    python3 tools/build_site.py                 # site + data only (PDFs link to GitHub)
    python3 tools/build_site.py --with-pdfs     # also copy PDFs (what CI deploys)
    python3 tools/build_site.py --serve         # build, then serve on :8000

With ``--with-pdfs`` the PDFs sit next to the page and open in the browser's
viewer. Without it, PDF links point at ``--pdf-base`` (GitHub by default).
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "site"
OUT = REPO_ROOT / "_site"
REPO_URL = "https://github.com/zlatko-minev/zlatko-minev-quantum-repository"
GITHUB_PDF_BASE = f"{REPO_URL}/blob/main/"

# AI summaries often open with the speaker's name; the page already says whose
# archive this is, so drop the preamble.
PREAMBLE_RE = re.compile(
    r"^(?:Dr\.\s*)?(?:Zlatko\s+)?(?:K\.\s*)?Minev\s+(discusses|presents|explores|"
    r"covers|introduces|explains|reviews|provides|outlines|shares|describes)\s+",
    re.IGNORECASE)
BYLINE_RE = re.compile(r"\s+(?:by|from)\s+(?:Dr\.\s*)?(?:Zlatko\s+)?(?:K\.\s*)?Minev\b",
                       re.IGNORECASE)


def tidy(text: str | None) -> str | None:
    if not text:
        return None
    text = BYLINE_RE.sub("", PREAMBLE_RE.sub(lambda m: m.group(1).capitalize() + " ", text.strip()))
    return text[:1].upper() + text[1:]


def build_library(pdf_base: str) -> dict:
    catalog = json.loads((REPO_ROOT / "catalog.json").read_text())["items"]
    ai_path = REPO_ROOT / "catalog_ai.json"
    ai = json.loads(ai_path.read_text())["items"] if ai_path.exists() else {}

    items = []
    for it in catalog:
        a = ai.get(it["id"], {})
        thumb = SRC / "thumbs" / f"{it['id']}.jpg"
        items.append({
            "id": it["id"],
            "title": it["title"],
            "category": it["category"],
            "series": it.get("series"),
            "year": it.get("year"),
            "venue": it.get("venue"),
            "speaker": it.get("speaker"),
            "note_id": it.get("note_id"),
            "tags": [t for t in it.get("tags", []) if t != "featured"],
            "featured": "featured" in it.get("tags", []) or bool(it.get("featured")),
            "pages": it.get("pages"),
            "size": it.get("size_bytes"),
            "file": it["file"],
            "thumb": f"thumbs/{it['id']}.jpg" if thumb.exists() else None,
            # curated description wins over the AI one
            "description": it.get("description") or tidy(a.get("short_description")),
            "summary": tidy(a.get("summary")),
            "key_points": a.get("key_points") or [],
            "topics": a.get("topics") or [],
            "level": a.get("audience_level"),
            "ai": bool(a) and not it.get("description"),
        })
    return {"pdf_base": pdf_base, "repo_url": REPO_URL, "items": items}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--with-pdfs", action="store_true",
                    help="copy PDFs into _site/ and link to them locally")
    ap.add_argument("--pdf-base", default=None,
                    help="URL prefix for PDF links (default: GitHub, or '' "
                         "with --with-pdfs)")
    ap.add_argument("--serve", action="store_true",
                    help="serve _site/ on http://localhost:8000 after building")
    args = ap.parse_args()

    pdf_base = args.pdf_base
    if pdf_base is None:
        pdf_base = "" if args.with_pdfs else GITHUB_PDF_BASE

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)
    lib = build_library(pdf_base)
    (OUT / "library.json").write_text(
        json.dumps(lib, ensure_ascii=False, separators=(",", ":")))
    (OUT / ".nojekyll").write_text("")

    if args.with_pdfs:
        for it in lib["items"]:
            dst = OUT / it["file"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / it["file"], dst)

    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"Built {OUT.relative_to(REPO_ROOT)}/ — {len(lib['items'])} items, "
          f"{size / 1e6:.1f} MB, PDFs {'bundled' if args.with_pdfs else 'linked'}")

    if args.serve:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                    directory=str(OUT))
        print("Serving on http://localhost:8000  (Ctrl-C to stop)")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
