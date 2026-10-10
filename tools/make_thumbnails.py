#!/usr/bin/env python3
"""
make_thumbnails.py — Render page 1 of every catalogued PDF to a small JPEG
thumbnail for the website: ``site/thumbs/<id>.jpg``.

Only missing thumbnails are rendered (``--force`` redraws all), and thumbnails
whose id is no longer in ``catalog.json`` are reported (``--prune`` deletes
them). Thumbnails are committed: they are small (~20-60 KB each) and make the
site work without a render step.

Usage
-----
    python3 tools/make_thumbnails.py            # render missing
    python3 tools/make_thumbnails.py --force    # re-render all
    python3 tools/make_thumbnails.py --prune    # also delete orphans

Requires poppler (``pdftoppm``); Pillow for the 360 px copies in ``sm/``.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG = REPO_ROOT / "catalog.json"
OUT_DIR = REPO_ROOT / "site" / "thumbs"
WIDTH = 640      # px; cards display at ~320 px, so this is crisp on 2x screens
QUALITY = 72     # JPEG quality
SMALL = 360      # px; site/thumbs/sm/<id>.jpg for 1x screens (srcset)


def render(pdf: Path, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / "p"
        subprocess.run(
            ["pdftoppm", "-f", "1", "-l", "1", "-singlefile",
             "-scale-to-x", str(WIDTH), "-scale-to-y", "-1",
             "-jpeg", "-jpegopt", f"quality={QUALITY},optimize=y",
             str(pdf), str(stem)],
            check=True, capture_output=True, timeout=120)
        Path(f"{stem}.jpg").replace(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="re-render all")
    ap.add_argument("--prune", action="store_true", help="delete orphans")
    args = ap.parse_args()

    items = json.loads(CATALOG.read_text())["items"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    made = 0
    for it in items:
        out = OUT_DIR / f"{it['id']}.jpg"
        if out.exists() and not args.force:
            continue
        render(REPO_ROOT / it["file"], out)
        made += 1
        print(f"  {out.stat().st_size / 1e3:5.0f} KB  {out.name}")

    # 1x-screen copies, downscaled from the full thumbnail (needs Pillow).
    try:
        from PIL import Image
    except ImportError:
        Image = None
        print("  (Pillow not installed: skipping small thumbnails)")
    if Image:
        (OUT_DIR / "sm").mkdir(exist_ok=True)
        for it in items:
            src, dst = OUT_DIR / f"{it['id']}.jpg", OUT_DIR / "sm" / f"{it['id']}.jpg"
            if src.exists() and (args.force or not dst.exists()):
                im = Image.open(src)
                im.resize((SMALL, round(im.height * SMALL / im.width)), Image.LANCZOS).save(
                    dst, quality=QUALITY, optimize=True, progressive=True)
                made += 1

    ids = {it["id"] for it in items}
    orphans = [p for p in [*OUT_DIR.glob("*.jpg"), *OUT_DIR.glob("sm/*.jpg")] if p.stem not in ids]
    for p in orphans:
        if args.prune:
            p.unlink()
        print(f"  {'deleted' if args.prune else 'orphan '}  {p.name}")

    total = sum(p.stat().st_size for p in OUT_DIR.rglob("*.jpg"))
    print(f"{made} rendered, {len(orphans)} orphan(s); "
          f"{total / 1e6:.1f} MB in {OUT_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
