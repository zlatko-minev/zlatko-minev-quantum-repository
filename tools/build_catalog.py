#!/usr/bin/env python3
"""
build_catalog.py — Scan the content folders and (re)generate ``catalog.json``,
the metadata database for every talk / lecture / note.

Each PDF becomes one JSON record with parsed fields (title, year, venue,
category, auto-inferred tags) plus a stable ``id``. A future website (or you)
can read ``catalog.json`` to list, filter, and tag the library.

Manual tags are preserved
-------------------------
Auto-inferred tags are a starting point. Any hand-curated metadata you put in
``tools/catalog_overrides.json`` (keyed by item ``id``) is merged on top every
time you regenerate, so re-running this after adding new talks never clobbers
your curation. Example override file::

    {
      "2024-fibonacci-anyons-realizing-string-net-condensation": {
        "tags": ["topological", "many-body", "featured"],
        "featured": true,
        "description": "CIFAR talk on Fibonacci anyon braiding."
      }
    }

Usage
-----
    python3 tools/build_catalog.py            # writes catalog.json
    python3 tools/build_catalog.py --check    # print summary, don't write
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OVERRIDES = REPO_ROOT / "tools" / "catalog_overrides.json"
OUT = REPO_ROOT / "catalog.json"

CATEGORY_BY_DIR = {
    "content - research talks": "research-talk",
    "content - educational": "educational",
    "content - tech notes": "tech-note",
}

# keyword (lowercased, matched against folder+filename) -> tags to add
TAG_RULES = {
    "superconducting qubit": ["hardware", "superconducting-qubits"],
    "cqed": ["hardware", "superconducting-qubits"],
    "epr": ["hardware", "qiskit-metal"],
    "qiskit metal": ["hardware", "qiskit-metal"],
    "hardware design": ["hardware"],
    "whispering gallery": ["hardware"],
    "josephson": ["hardware"],
    "transmon": ["hardware"],
    "parametric amplifier": ["hardware"],
    "drawbridge": ["hardware"],
    "circuit quantum electrodynamics": ["hardware", "superconducting-qubits"],
    "noise": ["noise"],
    "error mitigation": ["error-mitigation"],
    "mitigation": ["error-mitigation"],
    "pec": ["error-mitigation", "pec"],
    "probabilistic error cancelation": ["error-mitigation", "pec"],
    "twirling": ["error-mitigation", "twirling"],
    "ml-qem": ["error-mitigation", "machine-learning"],
    "machine learning": ["machine-learning"],
    "summer school": ["summer-school"],
    "qiskit global summer school": ["summer-school", "qiskit"],
    "boulder summer school": ["summer-school"],
    "tutorial": ["tutorial"],
    "career": ["career"],
    "lecture": ["lecture"],
    "keynote": ["keynote"],
    "many-body": ["many-body"],
    "integrability": ["many-body"],
    "fibonacci": ["many-body", "topological"],
    "anyon": ["many-body", "topological"],
    "spin model": ["many-body"],
    "measurement": ["measurement"],
    "quantum jump": ["measurement"],
    "sensing": ["sensing"],
    "prelude to practical": ["overview"],
    "overview": ["overview"],
}

YEAR_RE = re.compile(r"(19|20)\d{2}")
PAREN_RE = re.compile(r"\(([^)]*)\)")
# the consecutive run of parentheticals immediately before .pdf (venue/speaker)
TRAILING_PARENS_RE = re.compile(r"((?:\([^)]*\)\s*)+)\.pdf$", re.IGNORECASE)
SLUG_MAX = 110
# parenthetical contents that are descriptors, not venues
NON_VENUE = {"minev", "tutorial", "ph.d.", "phd"}


def slugify(text: str) -> str:
    text = re.sub(r"\.pdf$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return re.sub(r"-+", "-", text)[:SLUG_MAX].strip("-")


def parse_year(name: str, parts: list[str]) -> int | None:
    for blob in [name] + parts:
        m = YEAR_RE.search(blob)
        if m:
            return int(m.group())
    return None


def _clean_venue_fragment(inside: str) -> str | None:
    """Turn a parenthetical's contents into a venue string, or None.

    Drops the speaker token ('Minev'), bare year tokens, and pure descriptors;
    strips a trailing year so venues are consistent (year lives in its own field).
    """
    bits = [b.strip() for b in inside.split(",")]
    bits = [b for b in bits
            if b.lower() not in NON_VENUE and not YEAR_RE.fullmatch(b)]
    v = ", ".join(bits).strip()
    v = re.sub(r"[\s,]*(19|20)\d{2}\s*$", "", v).strip(" ,")  # trailing year
    return v or None


def parse_venue(name: str, parts: list[str]) -> str | None:
    """Venue from the filename's TRAILING parentheticals, falling back to folder.

    Only the run of parentheticals immediately before '.pdf' is considered, so
    mid-title abbreviations like '(EPR)' or '(cQED)' are never mistaken for a
    venue. Handles '(Venue Year) (Minev)' and '(Minev, Venue, Year)' by taking
    the last trailing parenthetical that yields a real venue.
    """
    m = TRAILING_PARENS_RE.search(name)
    if m:
        for inside in reversed(PAREN_RE.findall(m.group(1))):
            v = _clean_venue_fragment(inside)
            if v:
                return v
    # fall back to a series-folder parenthetical e.g. '... (Qiskit GSS 2021)'
    for folder in reversed(parts):
        for inside in PAREN_RE.findall(folder):
            v = _clean_venue_fragment(inside)
            if v:
                return v
    return None


def clean_title(name: str) -> str:
    t = re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE).strip()
    # strip trailing speaker/venue parentheticals (phrase-like: has space, comma,
    # year, or 'Minev'); keep short acronyms like '(ML-QEM)' / '(EPR)'.
    while True:
        m = re.search(r"\s*\(([^)]*)\)\s*$", t)
        if not m:
            break
        inside = m.group(1)
        if ("," in inside or " " in inside or YEAR_RE.search(inside)
                or "minev" in inside.lower()):
            t = t[:m.start()].rstrip()
        else:
            break
    t = re.sub(r"^(19|20)\d{2}\s+", "", t)  # leading year (research talks)
    return t.strip(" -,")


def infer_tags(haystack: str) -> list[str]:
    h = haystack.lower()
    tags: list[str] = []
    for kw, ts in TAG_RULES.items():
        if kw in h:
            tags.extend(ts)
    return sorted(set(tags))


def page_count(path: Path) -> int | None:
    try:
        out = subprocess.run(
            ["gs", "-q", "-dNODISPLAY", "-dNOSAFER", "-c",
             f"({path}) (r) file runpdfbegin pdfpagecount = quit"],
            capture_output=True, text=True, timeout=60)
        return int(out.stdout.strip())
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="summarize without writing catalog.json")
    ap.add_argument("--no-pages", action="store_true",
                    help="skip page-count extraction (faster)")
    args = ap.parse_args()

    overrides = {}
    if OVERRIDES.exists():
        overrides = json.loads(OVERRIDES.read_text())

    items = []
    seen_ids: set[str] = set()
    for cdir, category in CATEGORY_BY_DIR.items():
        base = REPO_ROOT / cdir
        if not base.exists():
            continue
        for pdf in sorted(base.rglob("*.pdf")):
            rel = pdf.relative_to(REPO_ROOT)
            name = pdf.name
            parts = list(rel.parts[1:-1])  # subfolders between content dir & file
            # subcategory: top grouping folder; series: immediate folder
            subcat = None
            series = None
            if parts:
                series = parts[-1].lstrip("- ").strip()
                subcat = parts[0].lstrip("- ").strip()
            # stable, unique id (guard against slug collisions)
            item_id = slugify(name)
            if item_id in seen_ids:
                n = 2
                while f"{item_id}-{n}" in seen_ids:
                    n += 1
                item_id = f"{item_id}-{n}"
            seen_ids.add(item_id)
            haystack = str(rel)
            rec = {
                "id": item_id,
                "title": clean_title(name),
                "file": str(rel),
                "category": category,
                "subcategory": subcat,
                "series": series,
                "year": parse_year(name, parts),
                "venue": parse_venue(name, parts),
                "speaker": "Minev",
                "tags": infer_tags(haystack),
                "size_bytes": pdf.stat().st_size,
                "pages": None if args.no_pages else page_count(pdf),
            }
            ov = overrides.get(item_id, {})
            if "tags" in ov:  # union auto + manual
                rec["tags"] = sorted(set(rec["tags"]) | set(ov["tags"]))
            for k, v in ov.items():
                if k != "tags":
                    rec[k] = v
            items.append(rec)

    items.sort(key=lambda r: (r["category"], -(r["year"] or 0), r["title"]))
    catalog = {"count": len(items), "items": items}

    # summary
    from collections import Counter
    cat_counts = Counter(i["category"] for i in items)
    tag_counts = Counter(t for i in items for t in i["tags"])
    print(f"{len(items)} items: " +
          ", ".join(f"{c}={n}" for c, n in cat_counts.items()))
    print("top tags: " +
          ", ".join(f"{t}({n})" for t, n in tag_counts.most_common(12)))
    untagged = [i["id"] for i in items if not i["tags"]]
    if untagged:
        print(f"{len(untagged)} untagged (add tags in catalog_overrides.json):")
        for u in untagged:
            print(f"  - {u}")

    # ---- self-validation: fail loudly on systematic problems ----
    errors, warnings = [], []
    ids = [i["id"] for i in items]
    dupes = [k for k, n in Counter(ids).items() if n > 1]
    if dupes:
        errors.append(f"duplicate ids: {dupes}")
    for i in items:
        if not (REPO_ROOT / i["file"]).exists():
            errors.append(f"file missing on disk: {i['file']}")
        if not i["title"]:
            errors.append(f"empty title: {i['id']}")
        if i["year"] is not None and not (2008 <= i["year"] <= 2026):
            errors.append(f"year out of range ({i['year']}): {i['id']}")
        if not args.no_pages and not i.get("pages"):
            warnings.append(f"no page count: {i['id']}")
    no_year = [i["id"] for i in items if i["year"] is None]
    if no_year:
        warnings.append(f"{len(no_year)} items without a year (undated notes/"
                        f"tutorials): {', '.join(no_year[:3])}...")

    print(f"\nvalidation: {len(errors)} error(s), {len(warnings)} warning(s)")
    for w in warnings:
        print(f"  ! {w}")
    for e in errors:
        print(f"  ✗ {e}")
    if errors:
        print("ABORTED — fix errors above; catalog.json not written.")
        return 1

    if not args.check:
        OUT.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
        print(f"Wrote {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
