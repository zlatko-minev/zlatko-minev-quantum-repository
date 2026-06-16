#!/usr/bin/env python3
"""
process_pdfs.py — Compress the slide/PDF library to a web-friendly size while
keeping text crisp.

Strategy
--------
For every PDF under the ``content - *`` folders we run Ghostscript with a tuned
"balanced ~150 dpi" profile (images downsampled to ~150 dpi, JPEG encoded, mono
art kept sharp at ~450 dpi). We only replace the original if the compressed
version is meaningfully smaller AND still valid; otherwise the original is kept
untouched. Nothing is ever deleted in place — see ``--backup-dir``.

This script is idempotent: re-running it on already-compressed files is a no-op
(the recompressed copy won't be smaller, so the original is kept).

Usage
-----
    python3 tools/process_pdfs.py --dry-run          # report only, change nothing
    python3 tools/process_pdfs.py                     # compress in place
    python3 tools/process_pdfs.py --dpi 110           # smaller / softer
    python3 tools/process_pdfs.py --report report.csv # write a CSV report

Requires Ghostscript (`gs`). Install with `brew install ghostscript`.
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIRS = [
    "content - research talks",
    "content - educational",
    "content - tech notes",
]
# Only replace the original if we save at least this fraction of the size.
MIN_SAVING = 0.05


def human(n: int) -> str:
    for unit in ("B", "K", "M", "G"):
        if n < 1024 or unit == "G":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}G"


def gs_compress(src: Path, dst: Path, dpi: int) -> bool:
    """Run Ghostscript. Return True on success (dst written)."""
    mono = dpi * 3  # keep line art / text-as-image crisp
    cmd = [
        "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6",
        "-dNOPAUSE", "-dQUIET", "-dBATCH", "-dSAFER",
        "-dDetectDuplicateImages=true",
        "-dDownsampleColorImages=true", f"-dColorImageResolution={dpi}",
        "-dColorImageDownsampleThreshold=1.0",
        "-dDownsampleGrayImages=true", f"-dGrayImageResolution={dpi}",
        "-dGrayImageDownsampleThreshold=1.0",
        "-dDownsampleMonoImages=true", f"-dMonoImageResolution={mono}",
        "-dColorImageFilter=/DCTEncode", "-dGrayImageFilter=/DCTEncode",
        "-dAutoFilterColorImages=false", "-dAutoFilterGrayImages=false",
        f"-sOutputFile={dst}", str(src),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"  ! gs failed: {e.stderr.decode()[:200]}", file=sys.stderr)
        return False
    return dst.exists() and dst.stat().st_size > 0


def find_pdfs() -> list[Path]:
    out: list[Path] = []
    for d in CONTENT_DIRS:
        base = REPO_ROOT / d
        if base.exists():
            out.extend(sorted(base.rglob("*.pdf")))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dpi", type=int, default=150,
                    help="target image resolution (default 150 = balanced)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report projected savings without changing files")
    ap.add_argument("--backup-dir", type=Path, default=None,
                    help="if set, copy each original here before replacing")
    ap.add_argument("--report", type=Path, default=None,
                    help="write a per-file CSV report to this path")
    args = ap.parse_args()

    if not shutil.which("gs"):
        print("ERROR: Ghostscript (gs) not found. brew install ghostscript",
              file=sys.stderr)
        return 1

    pdfs = find_pdfs()
    print(f"Found {len(pdfs)} PDFs. dpi={args.dpi} "
          f"{'(DRY RUN)' if args.dry_run else ''}\n")

    rows = []
    tot_before = tot_after = 0
    changed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, src in enumerate(pdfs, 1):
            before = src.stat().st_size
            tot_before += before
            rel = src.relative_to(REPO_ROOT)
            tmp_out = Path(tmp) / f"c{i}.pdf"
            ok = gs_compress(src, tmp_out, args.dpi)
            after = tmp_out.stat().st_size if ok else before
            saved = before - after
            keep_compressed = ok and saved > before * MIN_SAVING
            status = "compress" if keep_compressed else "keep-orig"

            if keep_compressed and not args.dry_run:
                if args.backup_dir:
                    bdst = args.backup_dir / rel
                    bdst.parent.mkdir(parents=True, exist_ok=True)
                    if not bdst.exists():
                        shutil.copy2(src, bdst)
                shutil.move(str(tmp_out), str(src))
                changed += 1
            final = after if keep_compressed else before
            tot_after += final

            pct = (saved / before * 100) if before else 0
            print(f"[{i:>2}/{len(pdfs)}] {human(before):>7} -> "
                  f"{human(final):>7} ({pct:4.0f}%) {status}  {rel.name[:60]}")
            rows.append({
                "path": str(rel), "before": before, "after": final,
                "saved_pct": round(pct, 1), "action": status,
            })

    print(f"\nTotal: {human(tot_before)} -> {human(tot_after)} "
          f"({(tot_before - tot_after) / tot_before * 100:.0f}% smaller), "
          f"{changed} files compressed"
          f"{' (dry run, nothing written)' if args.dry_run else ''}")

    if args.report:
        with open(args.report, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["path", "before", "after",
                                              "saved_pct", "action"])
            w.writeheader()
            w.writerows(rows)
        print(f"Report written to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
