#!/usr/bin/env python3
"""
reorg_educational.py — Flatten 'content - educational/' into 6 topic-first
folders (max 2 levels deep). Filenames are unchanged, so catalog ids (and thus
catalog_ai.json keys) stay stable.

    python3 tools/reorg_educational.py --dry-run   # show the plan, change nothing
    python3 tools/reorg_educational.py             # do the moves (uses git mv)

After running: regenerate the catalog (`python3 tools/build_catalog.py`).
"""
from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EDU = REPO / "content - educational"

# Topic folders (ordered, specific first). Each entry: (folder, [keywords]).
# A PDF is matched against the lowercased text of its full relative path.
RULES = [
    ("Superconducting Qubits & Hardware", ["superconducting qubits"]),
    ("Tutorials (Pauli Twirling)",        ["pauli twirling"]),
    ("Career & Outreach",                 ["career talk", "prelude to practical"]),
    ("Quantum Measurements",              ["quantum measurements"]),
    ("Error Mitigation",                  ["error mitigation", "noise mitigation"]),
    ("Quantum Noise",                     ["quantum noise", "real quantum computers and noise"]),
]


def topic_for(rel_lower: str) -> str | None:
    for folder, kws in RULES:
        if any(k in rel_lower for k in kws):
            return folder
    return None


def git_mv(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git", "-C", str(REPO), "mv", str(src), str(dst)],
                       capture_output=True, text=True)
    if r.returncode != 0:  # fall back to plain move (publish rebuilds from tree)
        shutil.move(str(src), str(dst))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pdfs = sorted(EDU.rglob("*.pdf"))
    plan, unmatched = [], []
    for pdf in pdfs:
        rel = pdf.relative_to(REPO)
        topic = topic_for(str(rel).lower())
        if not topic:
            unmatched.append(rel)
            continue
        dst = EDU / topic / pdf.name
        if pdf.resolve() != dst.resolve():
            plan.append((pdf, dst, topic))

    from collections import Counter
    counts = Counter(t for _, _, t in plan)
    already = len(pdfs) - len(plan) - len(unmatched)
    print(f"{len(pdfs)} educational PDFs | {len(plan)} to move | "
          f"{already} already placed | {len(unmatched)} UNMATCHED")
    for folder in [r[0] for r in RULES]:
        print(f"  {counts.get(folder,0):2}  -> {folder}")
    if unmatched:
        print("\nUNMATCHED (need a rule):")
        for u in unmatched:
            print(f"  ! {u}")
        print("Aborting — fix RULES first.")
        return 1

    print()
    for src, dst, topic in plan:
        print(f"  {src.relative_to(EDU)}\n     -> {topic}/{dst.name}")
        if not args.dry_run:
            git_mv(src, dst)

    if not args.dry_run:
        # remove now-empty leftover directories
        for d in sorted(EDU.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        print(f"\nMoved {len(plan)} files. Now run: python3 tools/build_catalog.py")
    else:
        print(f"\nDRY RUN — nothing moved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
