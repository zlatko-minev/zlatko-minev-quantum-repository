#!/usr/bin/env python3
"""
add_deck.py — Add a new slide deck or tech note to the archive in one step.

It does the mechanical part of the checklist in agent/NOTES.md:

 1. converts .pptx/.ppt/.key/.odp to PDF (LibreOffice, if installed)
 2. files it under the right content folder with the house naming pattern
 3. compresses that one PDF (Ghostscript, ~150 dpi; keeps the original unless
    it saves ≥5%)
 4. writes its override entry: permanent slug, title, venue, year, series,
    note id, speaker, and today's date as ``added`` (feed + "New" badge)
 5. rebuilds the catalog, extracts its text, renders thumbnails, builds the
    site (which freezes its BibTeX key) and runs the size guard

What it does NOT do (judgment; see .claude/skills/add-deck/SKILL.md): check
the metadata against the title slide, write the summary, verify paper/video
links, update "Start here" paths, Zenodo, commit.

Usage
-----
    python3 tools/add_deck.py NEW.pdf --shelf research \\
        --title "OTOC-NMR Experiment" --year 2026 --venue "APS March Meeting"

    python3 tools/add_deck.py NEW.pptx --shelf lectures --folder "Quantum Noise" \\
        --title "Intro to Quantum Noise (main lecture)" --year 2027 \\
        --venue "Qiskit Global Summer School" --series "Intro to Quantum Noise (QGSS 2027)"

    python3 tools/add_deck.py T28.pdf --shelf notes --note-id T28 \\
        --title "Readout error mitigation" --year 2027

    add --dry-run to see what would happen without changing anything.

Shelves: lectures (content - educational/<folder>), research (content -
research talks), notes (content - tech notes). Existing lecture folders are
listed by ``--folder ?``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
from build_catalog import slugify  # noqa: E402

OVERRIDES = TOOLS / "catalog_overrides.json"
CATALOG = REPO_ROOT / "catalog.json"
SHELF_DIRS = {"research": "content - research talks", "notes": "content - tech notes",
              "lectures": "content - educational"}
CONVERTIBLE = {".pptx", ".ppt", ".key", ".odp"}


def run(cmd: list[str], dry: bool, check: bool = True) -> int:
    print("  $ " + " ".join(cmd))
    if dry:
        return 0
    r = subprocess.run(cmd, cwd=REPO_ROOT)
    if check and r.returncode:
        sys.exit(f"Step failed: {' '.join(cmd)}")
    return r.returncode


def safe(text: str) -> str:
    """Make a title safe for a file name (no path separators or colons)."""
    return re.sub(r"\s+", " ", re.sub(r'[/\\:*?"<>|]', " - ", text)).strip(" -")


def file_name(a: argparse.Namespace) -> str:
    t = safe(a.title)
    if a.shelf == "research":
        return f"{a.year} {t} (Minev{', ' + safe(a.venue) if a.venue else ''}).pdf"
    if a.shelf == "notes":
        return f"{a.note_id} {t} (Minev).pdf"
    bits = ", ".join(x for x in ["Minev", safe(a.venue) if a.venue else None, str(a.year) if a.year else None] if x)
    return f"{t} ({bits}).pdf"


def make_slug(a: argparse.Namespace, taken: set[str]) -> str:
    if a.slug:
        s = a.slug
    else:
        base = re.sub(r"[^a-z0-9]+", "-", a.title.lower().replace("&", "and")).strip("-")
        head = re.sub(r"[^a-z0-9]+", "-", a.note_id.lower()) if a.note_id else str(a.year or "nd")
        s = f"{head}-{base}"
        if len(s) > 60:
            s = s[:60].rsplit("-", 1)[0]
    if s in taken:
        sys.exit(f"Slug '{s}' is already used; pass a different --slug.")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", s):
        sys.exit(f"Slug '{s}' must be lowercase letters, digits and single hyphens.")
    return s


def to_pdf(src: Path, tmp: Path, dry: bool) -> Path:
    if src.suffix.lower() == ".pdf":
        return src
    if src.suffix.lower() not in CONVERTIBLE:
        sys.exit(f"Unsupported file type: {src.suffix}")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        sys.exit("No LibreOffice (soffice) found. Export the deck to PDF first "
                 "(PowerPoint/Keynote: File → Export → PDF) and pass the PDF.")
    run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(src)], dry)
    return tmp / (src.stem + ".pdf")


def compress(pdf: Path, dry: bool) -> None:
    if not shutil.which("gs"):
        print("  ! Ghostscript (gs) not found: PDF left uncompressed. Install it and run "
              "tools/process_pdfs.py later, or check its size with check_sizes.py.")
        return
    from process_pdfs import MIN_SAVING, gs_compress
    if dry:
        print(f"  (would compress {pdf.name})")
        return
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "c.pdf"
        before = pdf.stat().st_size
        if gs_compress(pdf, out, 150) and out.stat().st_size < before * (1 - MIN_SAVING):
            shutil.move(str(out), str(pdf))
            print(f"  compressed {before / 1e6:.1f} → {pdf.stat().st_size / 1e6:.1f} MB")
        else:
            print(f"  kept original ({before / 1e6:.1f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="the new PDF (or .pptx/.ppt/.key/.odp)")
    ap.add_argument("--shelf", required=True, choices=sorted(SHELF_DIRS))
    ap.add_argument("--folder", help="lectures only: topic folder under content - educational/ ('?' lists them)")
    ap.add_argument("--title", required=True, help="from the title slide")
    ap.add_argument("--year", type=int)
    ap.add_argument("--venue")
    ap.add_argument("--series", help="exact name of an existing series, or a new one")
    ap.add_argument("--note-id", help="notes only, e.g. T28")
    ap.add_argument("--speaker", help="if not (only) Minev, e.g. 'Thomas G. McConkey, Minev'")
    ap.add_argument("--slug", help="permanent public id (default: YEAR-short-title / tNN-short-title)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    edu = REPO_ROOT / SHELF_DIRS["lectures"]
    folders = sorted(p.name for p in edu.iterdir() if p.is_dir())
    if a.shelf == "lectures":
        if not a.folder or a.folder == "?":
            print("Lecture folders:\n  " + "\n  ".join(folders))
            return 0 if a.folder == "?" else 1
        if a.folder not in folders:
            sys.exit(f"Unknown folder '{a.folder}'. Existing: {', '.join(folders)} "
                     "(create the folder first if a new topic is really needed).")
    if a.shelf == "notes" and not a.note_id:
        sys.exit("--note-id is required for tech notes (e.g. T28).")
    if a.shelf != "notes" and not a.year:
        sys.exit("--year is required for talks and lectures.")
    if not a.source.exists():
        sys.exit(f"Not found: {a.source}")

    dest_dir = REPO_ROOT / SHELF_DIRS[a.shelf] / (a.folder if a.shelf == "lectures" else "")
    dest = dest_dir / file_name(a)
    if dest.exists():
        sys.exit(f"Already exists: {dest.relative_to(REPO_ROOT)}")
    key = slugify(dest.name)
    ov = json.loads(OVERRIDES.read_text())
    taken = {o.get("slug") for o in ov.values() if isinstance(o, dict)}
    if CATALOG.exists():
        taken |= {i["id"] for i in json.loads(CATALOG.read_text())["items"]}
    slug = make_slug(a, taken)

    print(f"New item\n  file : {dest.relative_to(REPO_ROOT)}\n  key  : {key}\n  id   : {slug}")
    entry = {"slug": slug, "title": a.title, "added": dt.date.today().isoformat()}
    for field, val in [("year", a.year), ("venue", a.venue), ("series", a.series),
                       ("note_id", a.note_id), ("speaker", a.speaker)]:
        if val:
            entry[field] = val
    print("  override: " + json.dumps(entry, ensure_ascii=False))
    if a.series:
        known = {o.get("series") for o in ov.values() if isinstance(o, dict)}
        print(f"  series : {'joins existing' if a.series in known else 'NEW series'} '{a.series}'")

    with tempfile.TemporaryDirectory() as tmp:
        pdf = to_pdf(a.source.resolve(), Path(tmp), a.dry_run)
        if not a.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf, dest)
    compress(dest, a.dry_run)

    if not a.dry_run:
        ov[key] = {**ov.get(key, {}), **entry}
        OVERRIDES.write_text(json.dumps(ov, indent=2, ensure_ascii=False) + "\n")

    py = sys.executable
    run([py, "tools/build_catalog.py"], a.dry_run)
    ocr = [] if shutil.which("tesseract") else ["--no-ocr"]
    run([py, "tools/extract_cache.py", *ocr], a.dry_run, check=False)
    run([py, "tools/make_thumbnails.py"], a.dry_run)
    run([py, "tools/build_site.py"], a.dry_run)
    run([py, "tools/check_sizes.py"], a.dry_run, check=False)

    if a.dry_run:
        print("\nDry run: nothing changed.")
        return 0
    try:
        first = subprocess.run(["pdftotext", "-l", "1", str(dest), "-"], capture_output=True,
                               text=True).stdout.strip()
    except FileNotFoundError:
        first = "(pdftotext not installed)"
    print(f"""
Added {slug}. Title slide text, to check the metadata against:
----
{first[:700]}
----
Next (see .claude/skills/add-deck/SKILL.md):
  1. Check title / venue / year / speaker above; fix in tools/catalog_overrides.json under "{key}".
  2. Write description, summary, key_points, level, summary_confidence (text: catalog_text.json["{key}"]).
  3. Add verified "links" (own paper / video), "version_of" if it's a copy.
  4. python3 tools/build_catalog.py && python3 tools/build_site.py --serve   (look at it)
  5. Commit everything, incl. the PDF, thumbnails, catalog_text.json and tools/bibkeys.json.
  6. Zenodo: new record, or "New version" of the series record (ROADMAP › Scholar).""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
