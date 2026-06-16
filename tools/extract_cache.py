#!/usr/bin/env python3
"""
extract_cache.py — Extract and CACHE the text (and optionally page images) of
every talk PDF, so future processing (LLM enrichment, search index, embeddings,
SEO copy) is fast and never has to re-render / re-OCR.

Why: rendering + OCR is the slow part. Do it once, persist it, reuse forever.

What it writes
--------------
* ``_cache/text/<id>.json`` — per-page text, full text, char counts, which pages
  needed OCR. (in `_cache/`, git-ignored — it's a derived artifact)
* ``catalog_text.json`` — a COMMITTED, consolidated map {id -> {chars, pages,
  has_ocr, text}}. Useful for full-text search / SEO without shipping PDFs.
* ``_cache/pages/<id>/page-NN.jpg`` — rendered page images, only with --images.
  Lets `ai_enrich.py` (and future vision passes) skip re-rendering.

Text strategy: use the PDF text layer (pdftotext) per page; for pages whose text
layer is sparse (image-only slides), render that page and OCR it with tesseract.

    python3 tools/extract_cache.py                 # text (+OCR sparse pages)
    python3 tools/extract_cache.py --no-ocr        # text layer only (fastest)
    python3 tools/extract_cache.py --images 8      # also cache first 8 page imgs
    python3 tools/extract_cache.py --force         # redo cached items

Idempotent & resumable: an id already cached is skipped unless --force.
Requires poppler (pdftotext/pdftoppm); OCR needs tesseract.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

_VOWELS = set("aeiouAEIOU")
_B64_RUN = re.compile(r"[A-Za-z0-9+/]{15,}")


def _is_junk(tok: str) -> bool:
    """True for base64 / binary gibberish that pdftotext scrapes out of embedded
    images and fonts (e.g. 'Rg00402mIqV329TwSEjet...'). Keeps real words,
    acronyms, numbers, math symbols, URLs."""
    t = tok.strip(".,;:!?()[]{}\"'`")
    if len(t) < 12:
        return False  # short tokens (words, acronyms, numbers, symbols) kept
    letters = [c for c in t if c.isalpha()]
    vr = (sum(c in _VOWELS for c in letters) / len(letters)) if letters else 0.0
    has_up, has_lo = any(c.isupper() for c in t), any(c.islower() for c in t)
    has_dig = any(c.isdigit() for c in t)
    # base64-ish run: long, mixed case + digits, vowel-poor
    m = _B64_RUN.search(t)
    if m and len(m.group()) >= 15 and has_up and has_lo and has_dig and vr < 0.38:
        return True
    if len(t) >= 14 and vr < 0.12:   # consonant/symbol soup
        return True
    if len(t) > 34:                  # absurdly long single token
        return True
    return False


def clean_text(s: str) -> str:
    return " ".join(tok for tok in s.split() if not _is_junk(tok))

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "_cache"
TEXT_DIR = CACHE / "text"
PAGES_DIR = CACHE / "pages"
CATALOG = REPO / "catalog.json"
TEXT_OUT = REPO / "catalog_text.json"
OCR_MIN_CHARS = 40   # a page with less text-layer than this is OCR'd


def pdf_text_per_page(pdf: Path) -> list[str]:
    """Text layer per page (form-feed separated). Plain (not -layout) to keep it
    compact — -layout pads whitespace and bloats output ~10x."""
    out = subprocess.run(["pdftotext", str(pdf), "-"],
                         capture_output=True, text=True, timeout=120)
    # collapse whitespace + strip base64/binary junk, keep page boundaries
    return [clean_text(p) for p in out.stdout.split("\f")]


def ocr_page(pdf: Path, page: int, tmp: Path) -> str:
    if not shutil.which("tesseract"):
        return ""
    img = tmp / f"ocr{page}"
    subprocess.run(["pdftoppm", "-png", "-r", "200", "-f", str(page),
                    "-l", str(page), str(pdf), str(img)],
                   capture_output=True)
    pngs = list(tmp.glob(f"ocr{page}*.png"))
    if not pngs:
        return ""
    r = subprocess.run(["tesseract", str(pngs[0]), "-", "--psm", "4"],
                       capture_output=True, text=True)
    return " ".join(r.stdout.split())


def cache_images(pdf: Path, n: int, dst: Path) -> int:
    dst.mkdir(parents=True, exist_ok=True)
    subprocess.run(["pdftoppm", "-jpeg", "-r", "80", "-f", "1", "-l", str(n),
                    str(pdf), str(dst / "page")], capture_output=True)
    return len(list(dst.glob("page*.jpg")))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-ocr", action="store_true", help="skip OCR of sparse pages")
    ap.add_argument("--images", type=int, default=0, help="cache first N page imgs")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    items = json.loads(CATALOG.read_text())["items"]
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    consolidated = json.loads(TEXT_OUT.read_text()) if TEXT_OUT.exists() else {}

    done = ocr_used = 0
    for i, it in enumerate(items, 1):
        iid, pdf = it["id"], REPO / it["file"]
        cache_file = TEXT_DIR / f"{iid}.json"
        if cache_file.exists() and not args.force and iid in consolidated:
            if args.images:  # may still need images
                pass
            else:
                continue
        try:
            pages = pdf_text_per_page(pdf)
            ocr_pages = []
            with tempfile.TemporaryDirectory() as td:
                for pno, ptext in enumerate(pages, 1):
                    if not args.no_ocr and len(ptext.strip()) < OCR_MIN_CHARS:
                        try:
                            o = clean_text(ocr_page(pdf, pno, Path(td)))
                        except Exception:
                            o = ""  # one page's OCR failure must not drop the item
                        if o:
                            pages[pno - 1] = (ptext + "\n" + o).strip()
                            ocr_pages.append(pno)
                if args.images:
                    cache_images(pdf, args.images, PAGES_DIR / iid)
            full = "\n\n".join(p.strip() for p in pages if p.strip())
            rec = {"id": iid, "file": it["file"], "n_pages": len(pages),
                   "chars": len(full), "ocr_pages": ocr_pages, "pages": pages}
            cache_file.write_text(json.dumps(rec, ensure_ascii=False) + "\n")
            consolidated[iid] = {"chars": len(full), "pages": len(pages),
                                 "has_ocr": bool(ocr_pages), "text": full}
            TEXT_OUT.write_text(json.dumps(consolidated, indent=2,
                                           ensure_ascii=False) + "\n")
            done += 1
            ocr_used += 1 if ocr_pages else 0
            print(f"[{i}/{len(items)}] {iid[:55]:55} {len(full):>6}ch "
                  f"{'OCR:'+str(len(ocr_pages)) if ocr_pages else ''}")
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(items)}] ! {iid[:55]} FAILED: {type(e).__name__} {e}")

    print(f"\nCached {done} items ({ocr_used} needed OCR). "
          f"Text -> {TEXT_OUT.name}; per-page -> _cache/text/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
