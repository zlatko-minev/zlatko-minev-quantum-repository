---
name: add-deck
description: Add a new slide deck, lecture or tech note to Zlatko's Quantum Notebook archive and website — file it, compress it, give it a permanent id, metadata from its title slide, a summary, links, thumbnail and citation, and ship it. Use when the owner hands over a new PDF/PPTX ("add this talk", "new lecture", "here's my latest deck", "new tech note T28").
---

# Add a deck to Zlatko's Quantum Notebook

Read `agent/NOTES.md` first if you haven't this session; it holds the rules this
skill applies. Everything committed is public: keep commits factual.

## 1. Gather the facts (from the deck, not the file name)

```bash
pdftotext -l 2 NEW.pdf - | head -60      # title slide (PPTX: convert first, or read it)
```

Decide, from the title slide and the owner's message:
- **shelf**: `lectures` (taught: schools, courses, tutorials, career talks),
  `research` (seminars, conference talks), `notes` (written T-notes).
- **folder** (lectures only): `python3 tools/add_deck.py x --shelf lectures --folder ? --title x --year 1`
  lists them. Don't invent a new topic folder unless the owner agrees.
- **title** exactly as on the title slide (sentence or title case as printed),
  **year**, **venue** (official event name), **speaker** if not only Minev
  (title-slide order, comma-separated), **note id** for notes (`T28`).
- **series**: if it is another lecture of an existing series, reuse the exact
  name (`grep '"series"' tools/catalog_overrides.json | sort -u`). A new
  school/course with 2+ decks gets a new series name like
  `Intro to Quantum Noise (QGSS 2027)`. A recurring lecture given again
  (e.g. Superconducting Qubits 101) joins its existing series.
- Is it a **copy** of an existing item (e.g. a tech note handed out at a
  school)? Then it still gets added, with `version_of` (step 4).

Ask the owner only for what the deck and message don't settle (usually venue
name or year).

## 2. Run the pipeline

```bash
python3 tools/add_deck.py NEW.pdf --shelf research --title "…" --year 2027 --venue "…" --dry-run
python3 tools/add_deck.py NEW.pdf --shelf research --title "…" --year 2027 --venue "…"
```

It converts (LibreOffice), files the PDF under the house naming pattern,
compresses it (Ghostscript), writes the override (permanent `slug`, metadata,
`added` = today), rebuilds the catalog, extracts text, renders thumbnails,
builds the site (freezing the BibTeX key in `tools/bibkeys.json`) and runs the
size guard. Read its output: the size guard must say 0 errors; a PDF over
15 MB should be compressed harder (`tools/process_pdfs.py` logic, lower dpi)
after checking equation legibility.

## 3. Write the summary

Text: `catalog_text.json["<key>"]["text"]` (key printed by the script). In
`tools/catalog_overrides.json` under that key add `description` (≤150 chars),
`summary` (2–3 sentences), `key_points` (3–4), `level`
(beginner/intermediate/advanced), `summary_confidence`. Rules (NOTES ›
Writing summaries): only what the slides support; subject-first, no
"Dr. Minev…"; no hype; spell out acronyms in beginner/intermediate
descriptions; never describe the extraction. Leave `summary_reviewed` unset:
the owner sets it after reading.

## 4. Links, copies, tags

- `links`: the talk's **own** paper (arXiv ID in the title/author block of
  slide 1, verified against the arXiv record's title and authors) and a
  video only if the owner confirms it. Never a paper the deck merely cites.
- `version_of`: public id of the original, if this is a copy.
- `tags` / `tags_remove` if the folder-inferred tags are wrong (check the
  item's `tags` in `catalog.json`).
- "Start here" paths (`PATHS` in `site/app.js`): add the deck only if it is a
  clearly better entry point than what's there.

## 5. Check and look

```bash
python3 tools/build_catalog.py && python3 tools/check_sizes.py
python3 tools/build_site.py --serve        # http://localhost:8000/#<id>
```

Open the deck's dialog and its page `items/<id>/` (or `series/<slug>/`):
title, venue, year, thumbnail, summary, Cite. If you can run Playwright,
screenshot both at 1280 and 390 px.

## 6. Ship

Commit the PDF, `catalog.json`, `catalog_text.json`,
`tools/catalog_overrides.json`, `tools/bibkeys.json`, `site/thumbs/<id>.jpg`
and `site/thumbs/sm/<id>.jpg` together, e.g. "Add 2027 APS talk: <title>".
Open a PR (or push to main if the owner works that way); CI re-checks size,
catalog, thumbnails and keys, and deploys on main.

## 7. DOI (when Zenodo is set up)

- New standalone deck or note: `python3 tools/zenodo_deposit.py create --only <id>`,
  owner reviews the draft, then `publish --only <id>`; commit the DOI changes.
- New deck in a series already on Zenodo: on zenodo.org open the series
  record → **New version** → add the PDF → publish (concept DOI unchanged).

## Don'ts

- Don't rename existing PDFs or change an existing `slug` or BibTeX key.
- Don't hand-edit `catalog.json`; edit the overrides and rebuild.
- Don't mark summaries reviewed, and don't publish to Zenodo, without the owner.
