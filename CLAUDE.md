# CLAUDE.md

Archive of Zlatko Minev's talks, lectures and notes, plus the static website
"Zlatko's Quantum Notebook" (`site/`) that browses it.

Read `agent/NOTES.md` before changing anything. It has the add-a-talk
checklist, the summary-writing rules, the shelf (collection) definitions, the
size budgets, and why files are not renamed.

Quick reference:

```bash
python3 tools/add_deck.py NEW.pdf --shelf research --title "…" --year 2027 --venue "…"
                                     # add a new deck end to end (skill: .claude/skills/add-deck)
python3 tools/build_catalog.py       # regenerate catalog.json (never hand-edit it)
python3 tools/make_thumbnails.py     # thumbnails for new items
python3 tools/check_sizes.py         # size guard (CI runs it too)
python3 tools/build_site.py --serve  # preview on :8000 (commit tools/bibkeys.json if it changes)
```

Curated metadata (titles, series, summaries) goes in
`tools/catalog_overrides.json`. Everything committed is public: keep commits and
notes factual.
