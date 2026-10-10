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
    python3 tools/build_site.py --site-url https://talks.example.com/   # canonical URL

Besides the browser page it writes a citation page per item (``items/<id>/``)
and per series (``series/<slug>/``), with Google Scholar meta tags and BibTeX,
``citations.bib`` with every entry, ``sitemap.xml`` and ``robots.txt``.

With ``--with-pdfs`` the PDFs sit next to the page and open in the browser's
viewer. Without it, PDF links point at ``--pdf-base`` (GitHub by default).
"""
from __future__ import annotations

import argparse
import functools
import html
import http.server
import json
import re
import shutil
from pathlib import Path

from site_pages import THEME_BOOT, assign_citations, atom_feed, item_page, robots, series_page, sitemap

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "site"
OUT = REPO_ROOT / "_site"
REPO_URL = "https://github.com/zlatko-minev/zlatko-minev-quantum-repository"
GITHUB_PDF_BASE = f"{REPO_URL}/blob/main/"
# Canonical address of the deployed site (used in citations and the sitemap).
# CI passes the real Pages URL; change the default when a custom domain is set.
SITE_URL = "https://zlatko-minev.github.io/zlatko-minev-quantum-repository/"

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


def jpeg_size(path: Path) -> list[int] | None:
    """(width, height) from a JPEG's SOF marker, so pages can reserve image space."""
    data = path.read_bytes()
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker, seglen = data[i + 1], int.from_bytes(data[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2):
            return [int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")]
        i += 2 + seglen
    return None


def build_library(pdf_base: str) -> dict:
    catalog = json.loads((REPO_ROOT / "catalog.json").read_text())["items"]
    ai_path = REPO_ROOT / "catalog_ai.json"
    ai = json.loads(ai_path.read_text())["items"] if ai_path.exists() else {}

    items = []
    for it in catalog:
        a = ai.get(it.get("key", it["id"]), {})
        thumb = SRC / "thumbs" / f"{it['id']}.jpg"
        # Curated text (catalog_overrides.json → catalog.json) wins over the
        # older local-model enrichment in catalog_ai.json.
        curated = bool(it.get("summary") or it.get("description"))
        items.append({
            "id": it["id"],
            "title": it["title"],
            "shelf": it.get("shelf"),
            "category": it["category"],
            "series": it.get("series"),
            "year": it.get("year"),
            "venue": it.get("venue"),
            "speaker": it.get("speaker"),
            "authors": it.get("authors"),
            "note_id": it.get("note_id"),
            "tags": [t for t in it.get("tags", []) if t != "featured"],
            "featured": "featured" in it.get("tags", []) or bool(it.get("featured")),
            "pages": it.get("pages"),
            "size": it.get("size_bytes"),
            "file": it["file"],
            "links": it.get("links") or [],   # [{label, url}]: paper, video, ...
            "version_of": it.get("version_of"),
            "doi": it.get("doi"),
            "added": it.get("added"),
            "thumb": f"thumbs/{it['id']}.jpg" if thumb.exists() else None,
            "thumb_wh": jpeg_size(thumb) if thumb.exists() else None,
            "thumb_sm": f"thumbs/sm/{it['id']}.jpg" if (SRC / "thumbs" / "sm" / f"{it['id']}.jpg").exists() else None,
            "description": it.get("description") or tidy(a.get("short_description")),
            "summary": it.get("summary") or tidy(a.get("summary")),
            "key_points": it.get("key_points") or a.get("key_points") or [],
            "level": it.get("level") or a.get("audience_level"),
            # "draft" = machine-written and not yet reviewed by the author
            "draft": not it.get("summary_reviewed", False) and (curated or bool(a)),
        })
    return {"pdf_base": pdf_base, "repo_url": REPO_URL, "items": items}


def fill_index(path: Path, lib: dict, site_url: str) -> None:
    """Fill the build-time placeholders in index.html: canonical URL, year span,
    stats, shelf counts, and a static list of every deck (a crawl path and the
    no-JS view; app.js replaces it with the interactive grid)."""
    items = lib["items"]
    years = [i["year"] for i in items if i.get("year")]
    slides = sum(i.get("pages") or 0 for i in items)
    rows = "\n".join(
        f'      <li><a href="items/{html.escape(i["id"])}/">{html.escape(i["title"])}</a>'
        f'{" (" + str(i["year"]) + ")" if i.get("year") else ""}</li>'
        for i in sorted(items, key=lambda i: (-(i.get("year") or 0), i["title"])))
    page = path.read_text()
    subs = {"%SITE_URL%": site_url, "%YEARS%": f"{min(years)} → {max(years)}",
            "%N_DECKS%": str(len(items)), "%N_SLIDES%": f"{slides:,}",
            "%N_HOURS%": f"~{round(slides / 60)}", "%THEME_BOOT%": THEME_BOOT, "%STATIC_LIST%": f'    <ul class="static-list">\n{rows}\n    </ul>'}
    for shelf in ("lectures", "research", "notes"):
        subs[f"%COUNT_{shelf}%"] = str(sum(1 for i in items if i.get("shelf") == shelf))
    for k, v in subs.items():
        page = page.replace(k, v)
    path.write_text(page)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--with-pdfs", action="store_true",
                    help="copy PDFs into _site/ and link to them locally")
    ap.add_argument("--pdf-base", default=None,
                    help="URL prefix for PDF links (default: GitHub, or '' "
                         "with --with-pdfs)")
    ap.add_argument("--site-url", default=SITE_URL,
                    help=f"canonical site URL, with trailing slash (default {SITE_URL})")
    ap.add_argument("--serve", action="store_true",
                    help="serve _site/ on http://localhost:8000 after building")
    args = ap.parse_args()

    pdf_base = args.pdf_base
    if pdf_base is None:
        pdf_base = "" if args.with_pdfs else GITHUB_PDF_BASE

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)
    site_url = args.site_url.rstrip("/") + "/"
    lib = build_library(pdf_base)
    lib["site_url"] = site_url
    pdf_abs = site_url if args.with_pdfs else (pdf_base or GITHUB_PDF_BASE)
    keys_path = REPO_ROOT / "tools" / "bibkeys.json"
    locked = json.loads(keys_path.read_text()) if keys_path.exists() else {}
    series, bib_all, keys = assign_citations(lib["items"], site_url, locked)
    if keys != locked:   # new items get frozen keys; commit tools/bibkeys.json
        keys_path.write_text(json.dumps(dict(sorted(keys.items())), indent=1) + "\n")
        print(f"Updated {keys_path.relative_to(REPO_ROOT)} ({len(keys) - len(locked)} new key(s)); commit it.")
    for it in lib["items"]:
        it["page"] = f"items/{it['id']}/"
        page = OUT / "items" / it["id"] / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(item_page(it, site_url, pdf_abs))
    for srs in series:
        page = OUT / "series" / srs["slug"] / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(series_page(srs, site_url))
    fill_index(OUT / "index.html", lib, site_url)
    (OUT / "citations.bib").write_text("\n\n".join(bib_all) + "\n")
    (OUT / "sitemap.xml").write_text(sitemap(lib["items"], series, site_url))
    (OUT / "robots.txt").write_text(robots(site_url))
    (OUT / "feed.xml").write_text(atom_feed(lib["items"], site_url))
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
