#!/usr/bin/env python3
"""
check_sizes.py — Size guard for the archive. Run before publishing; CI runs it
on every push and pull request.

Why: the repository is published as a single commit and the website deploys
every PDF to GitHub Pages, so total size is what clones, pushes and the site
pay for. GitHub refuses files over 100 MB and warns over 50 MB; a Pages site
is capped at 1 GB. The budgets below leave headroom under those limits.

Checks
------
* each PDF against a per-file budget (warn / fail)
* total content size against a repository budget (warn / fail)
* thumbnails against a per-file budget
* any other tracked file over 2 MB (catches stray .pptx / .mp4 / .zip)
* every PDF is in ``catalog.json`` and every catalog entry exists on disk

Usage
-----
    python3 tools/check_sizes.py           # report; exit 1 on any failure
    python3 tools/check_sizes.py --top 15  # also list the 15 largest PDFs

Fix an oversized PDF with ``python3 tools/process_pdfs.py`` (Ghostscript,
~150 dpi) or a lower ``--dpi`` for that file.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIRS = ["content - research talks", "content - educational",
                "content - tech notes"]
MB = 1e6

PDF_WARN, PDF_FAIL = 15 * MB, 40 * MB       # per PDF
TOTAL_WARN, TOTAL_FAIL = 600 * MB, 900 * MB  # all content (Pages cap: 1 GB)
THUMB_WARN, THUMB_FAIL = 120e3, 400e3       # per thumbnail
OTHER_FAIL = 2 * MB                          # any other tracked file


def tracked_files() -> list[Path]:
    """Files git would publish (tracked + untracked-but-not-ignored)."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            cwd=REPO_ROOT, capture_output=True, check=True)
        names = [n for n in out.stdout.decode().split("\0") if n]
        return [REPO_ROOT / n for n in names if (REPO_ROOT / n).is_file()]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in REPO_ROOT.rglob("*")
                if p.is_file() and ".git" not in p.parts]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=0,
                    help="list the N largest PDFs")
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    files = tracked_files()
    rel = {p: p.relative_to(REPO_ROOT).as_posix() for p in files}

    pdfs = [p for p in files
            if p.suffix.lower() == ".pdf" and rel[p].split("/")[0] in CONTENT_DIRS]
    thumbs = [p for p in files if rel[p].startswith("site/thumbs/")]
    content_total = sum(p.stat().st_size for p in pdfs)
    repo_total = sum(p.stat().st_size for p in files)

    for p in pdfs:
        s = p.stat().st_size
        if s > PDF_FAIL:
            errors.append(f"PDF {s / MB:.1f} MB > {PDF_FAIL / MB:.0f} MB: {rel[p]}")
        elif s > PDF_WARN:
            warnings.append(f"PDF {s / MB:.1f} MB > {PDF_WARN / MB:.0f} MB: {rel[p]}")

    for p in thumbs:
        s = p.stat().st_size
        if s > THUMB_FAIL:
            errors.append(f"thumbnail {s / 1e3:.0f} KB: {rel[p]}")
        elif s > THUMB_WARN:
            warnings.append(f"thumbnail {s / 1e3:.0f} KB: {rel[p]}")

    for p in set(files) - set(pdfs) - set(thumbs):
        s = p.stat().st_size
        if s > OTHER_FAIL:
            errors.append(f"non-content file {s / MB:.1f} MB: {rel[p]}")

    if content_total > TOTAL_FAIL:
        errors.append(f"content total {content_total / MB:.0f} MB > "
                      f"{TOTAL_FAIL / MB:.0f} MB budget")
    elif content_total > TOTAL_WARN:
        warnings.append(f"content total {content_total / MB:.0f} MB > "
                        f"{TOTAL_WARN / MB:.0f} MB; plan to move PDFs to "
                        f"release assets (see ROADMAP.md)")

    catalog_path = REPO_ROOT / "catalog.json"
    if catalog_path.exists():
        catalogued = {i["file"] for i in json.loads(catalog_path.read_text())["items"]}
        on_disk = {rel[p] for p in pdfs}
        for f in sorted(on_disk - catalogued):
            errors.append(f"PDF not in catalog.json (run build_catalog.py): {f}")
        for f in sorted(catalogued - on_disk):
            errors.append(f"catalog.json entry missing on disk: {f}")

    print(f"{len(pdfs)} PDFs, {content_total / MB:.1f} MB "
          f"(budget {TOTAL_WARN / MB:.0f} warn / {TOTAL_FAIL / MB:.0f} fail); "
          f"{len(thumbs)} thumbnails, "
          f"{sum(p.stat().st_size for p in thumbs) / MB:.1f} MB; "
          f"all published files {repo_total / MB:.1f} MB")
    if args.top:
        print(f"\nLargest {args.top} PDFs:")
        for p in sorted(pdfs, key=lambda p: -p.stat().st_size)[:args.top]:
            print(f"  {p.stat().st_size / MB:6.1f} MB  {rel[p]}")

    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    for w in warnings:
        print(f"  ! {w}")
    for e in errors:
        print(f"  ✗ {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
