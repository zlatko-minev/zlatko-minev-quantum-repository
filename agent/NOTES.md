# Agent Notes — Zlatko Minev Quantum Repository

> Orientation and maintenance guide for any agent (or human) working on this
> repo. Last updated: 2026-10-10.

## What this repo is

A public archive of Zlatko Minev's talks, lectures, tutorials and technical
notes (2011 → today), plus the static website **Zlatko's Quantum Notebook** that browses it.
Content license: CC BY-NC-ND 4.0 (see `LICENSE.md`).

- `content - research talks/` — flat, `YYYY Title (Minev, Venue).pdf`
- `content - educational/` — topic folders (Superconducting Qubits & Hardware,
  Quantum Noise, Error Mitigation, Quantum Measurements, Tutorials (Pauli
  Twirling), Career & Outreach)
- `content - tech notes/` — `T<n> Title (Minev).pdf`
- `catalog.json` — the metadata database (generated; never hand-edit)
- `tools/catalog_overrides.json` — hand-curated metadata merged into the catalog
- `catalog_text.json` — extracted slide text per item (generated)
- `catalog_ai.json` — 2026-06 local-model enrichment; superseded by curated
  summaries in the overrides, kept as a fallback
- `site/` — the website source (plain HTML/CSS/JS); `site/thumbs/` thumbnails
- `tools/` — the pipeline scripts below

## The owner's intent

1. Keep the GitHub repo small: no Git LFS, history squashed to one commit on
   publish (`tools/publish.sh`).
2. PDFs readable but compressed (~150 dpi).
3. One metadata database that drives the website.
4. The website is the main way people find things: clean, a bit playful,
   professional. Links to the homepage, https://zlatko-minev.com.
5. Adding a talk must be a repeatable, checklist-driven process.

## Add a new talk, lecture or note (checklist)

**Fast path:** `python3 tools/add_deck.py NEW.pdf --shelf … --title … --year …`
does steps 1–8 below in one go (convert, file, compress, override with slug and
`added`, catalog, text, thumbnails, site build with frozen key, size guard).
The agent workflow around it (checking the title slide, summary, links,
shipping, DOI) is `.claude/skills/add-deck/SKILL.md`. The manual steps:

1. **Convert.** `.pptx` → PDF: `soffice --headless --convert-to pdf FILE.pptx`
   (LibreOffice); `tools/convert_pptx_to_pdf.py` instead drives PowerPoint on
   macOS for a whole folder.
2. **Place and name.** Drop the PDF into the right content folder using that
   folder's naming pattern (above). The file name sets the item's internal
   `key`; its public id is the `slug` you add in step 5.
3. **Compress.** `python3 tools/process_pdfs.py` (Ghostscript; never enlarges a
   file; safe to re-run on the whole library).
4. **Catalog.** `python3 tools/build_catalog.py` — parses title/year/venue from
   the file name, infers tags, assigns a `shelf`, validates, writes
   `catalog.json`. Read its output for warnings.
5. **Curate in `tools/catalog_overrides.json`** (keyed by `key`; anything here
   overrides the parsed value, `tags` are unioned):
   - `title`, `venue`, `year`, `series` — take them from the PDF's own title
     slide (`pdftotext -l 1 file.pdf -`), not from the file name.
   - `series` groups decks on the site (e.g. `Intro to Quantum Noise (QGSS 2023)`).
     Reuse an existing series name exactly when the deck belongs to one.
   - `shelf` only when the default is wrong (see "Shelves").
   - `note_id` for tech notes (`T27`).
   - `slug`: the permanent public id (see "Item ids and renaming").
   - `speaker` when someone other than Minev presented, or co-presented
     (comma-separated, in title-slide order); `authors` for a co-authored
     poster or abstract whose citation needs the full author list.
   - `tags_remove` to drop a tag inherited from the folder that doesn't fit.
   - `added`: today's date (`"YYYY-MM-DD"`). Drives the Atom feed and the
     "New" badge (120 days).
   - `links`: the deck's own paper / video (see "Links").
   - `version_of`: public id of the original when this is a copy of another
     item (e.g. a tech note handed out as a summer-school bonus).
6. **Text + summary.** `python3 tools/extract_cache.py` to refresh
   `catalog_text.json`, then write `description`, `summary`, `key_points`,
   `level`, `summary_confidence` into the overrides (rules below).
7. **Thumbnail.** `python3 tools/make_thumbnails.py` (renders only missing ones,
   plus the 360 px copy in `site/thumbs/sm/`; needs Pillow).
8. **Check.** `python3 tools/build_catalog.py` again, then
   `python3 tools/check_sizes.py`, then preview with
   `python3 tools/build_site.py --serve` (http://localhost:8000). The build
   freezes a BibTeX key for the new item in `tools/bibkeys.json`: commit it
   (CI fails otherwise).
9. **Log** the source in `../imported_talks.json` (outside the repo).
10. **Publish.** Commit, or `bash tools/publish.sh --push` to squash and
    force-push. CI (`.github/workflows/site.yml`) re-checks sizes, catalog
    freshness, thumbnails and BibTeX keys, then deploys the site from `main`.

## Shelves (the site's three collections)

| shelf | name on site | default rule |
|---|---|---|
| `lectures` | Lectures & Tutorials | `content - educational/` (incl. tutorials and career talks) |
| `research` | Research Talks | `content - research talks/` |
| `notes` | Tech Notes | `content - tech notes/` (written, T-numbered) |

Shelves follow the content folders one-to-one (`default_shelf()` in
`tools/build_catalog.py`); names and blurbs are in `SHELVES` in `site/app.js`.
Decided 2026-10 to keep three: a separate Career & Outreach shelf had only 3
items; career talks are a series inside Lectures, findable with the Career tag.

## Citations

- **Series.** Every series with 2+ decks is cited as ONE work, even when the
  lecture was given at several venues over the years (e.g.
  `Superconducting Qubits 101`, 2020–2026): the versions are near-identical,
  and one record gathers citations (better for impact metrics, and it maps to
  a Zenodo record with versions under one concept DOI). The entry's note lists
  the decks, years and venues. Only `Career & Outreach` (a grouping, not a
  series) is cited deck by deck. Rule: `citable` in `series_info()`,
  `tools/site_pages.py` (decided with the author 2026-10).
- **Copies.** `version_of` items share the original's BibTeX and point their
  canonical URL at it; they carry no Scholar tags.
- **Keys are frozen** in `tools/bibkeys.json` (owner id → key; series owners are
  `s:<slug>`). Existing keys never change, even if a title or year changes; new
  owners get new keys (collisions get a/b/c). Don't hand-edit keys that may
  already be cited.
- Tech notes are `@techreport` (type "Technical Note", number `Txx`,
  institution "Zlatko's Quantum Notebook"); decks are `@misc` with
  `howpublished = {Talk|Lecture|Tutorial, <venue>}` and `note = {Slides}`.
- Pages: `items/<id>/` per item and `series/<slug>/` per series, with Google
  Scholar `citation_*` tags (PDF tag only when the PDF is on the site), JSON-LD
  and OG tags; plus `citations.bib`, `sitemap.xml`, `robots.txt`, `feed.xml`.
- The `series` string is the grouping key for the site and for citations, so
  spell it identically across decks.
- Authors come from `authors`, else `speaker` ("Minev" → "Zlatko K. Minev";
  others comma-separated in title-slide order).
- Citation URLs use the site address: default `SITE_URL` in
  `tools/build_site.py`; CI uses the repository variable `SITE_URL` when set.
  Changing the address changes every citation URL, so set it once.
- Scholar indexing of slides is not guaranteed; tech notes have the best
  chance. DOIs: `.zenodo.json` is ready for the GitHub–Zenodo integration (see
  ROADMAP › Continue here).

## Links: papers, videos, code

Add `links` to an item's override; each renders as a button in the detail view
and on its citation page:

```json
"links": [
  {"label": "Paper (arXiv)", "url": "https://arxiv.org/abs/2307.07552"},
  {"label": "Video", "url": "https://www.youtube.com/watch?v=..."}
]
```

Only add a link you have verified: the talk's *own* paper (in the title or
author block of slide 1, not one it cites; check the arXiv record's title and
authors), or a video the author confirms. A wrong paper link under the author's
name is worse than none (2026-10: an NQI deck briefly linked a paper it only
cited). As of 2026-10, paper links come from arXiv IDs printed on
the title slides; no video links yet (the QGSS lectures have recordings on
YouTube that still need to be matched to decks).

## DOIs and Zenodo

- `doi` on an item (override) or `tools/series.json` (`{"<series>": {"doi": ...}}`)
  flows into BibTeX (`doi`), Scholar (`citation_doi`), JSON-LD and a DOI button.
  Use the Zenodo *concept* DOI (stable across versions).
- `tools/zenodo_deposit.py plan|create|publish|status` (see its docstring):
  units are tech notes, lecture series (one record, all decks) and standalone
  decks; copies (`version_of`) and Career & Outreach grouping are handled like
  the citations. `create` makes drafts only; `publish` is explicit and writes
  DOIs back. State in `tools/zenodo.json` (commit it). Rehearse with
  `--sandbox`. Needs network access to zenodo.org.
- A new deck in an already-published series: "New version" on the Zenodo
  record (UI), add the PDF, publish; the concept DOI is unchanged.

## License and reuse

Content is CC BY-NC-ND 4.0 (`LICENSE.md`), not MIT. Agreed wording (2026-10):
read, download and share unchanged and non-commercially with credit and a link
back; commercial use or reworked slides/figures need permission ("please ask,
the answer is usually yes"); a non-binding request to send a note when the
material is used in teaching or a publication; third-party figures, photos and
logos stay with their owners. Keep the texts in sync: `site/index.html`
(footer), `PERMISSIONS_HTML` in `tools/site_pages.py`, README, LICENSE.md.
Code and site source are covered by the same file today; the fonts in
`site/fonts/` are SIL OFL (licenses alongside).

## Writing summaries

Summaries are public, under the author's name. Accuracy first.

- Read the deck's text (`catalog_text.json`, or `pdftotext`). State only what the
  slides support: no invented results, numbers, collaborators or affiliations.
- `description`: one sentence, ≤ 150 characters, for the card.
  `summary`: 2–3 sentences. `key_points`: 3–4 concrete bullets.
  `level`: `beginner` / `intermediate` / `advanced`.
- Subject-first; never open with "Dr. Minev…" or "This talk by…". No hype words.
  Don't describe the extraction process ("the extracted text…").
- `summary_confidence`: `high` / `medium` / `low` (low = mostly handwritten or
  image-only pages; keep it generic).
- The site labels every summary "draft" until the author approves it: set
  `"summary_reviewed": true` on that item in the overrides.

## Item ids and renaming

- Each item has a public, permanent `id` (its URL `items/<id>/`, the `#<id>`
  permalink, thumbnail name and BibTeX URL). It is the frozen `slug` in the
  item's override, e.g. `t27-simple-noise-models-and-gate-fidelity`. Give
  every new item a short slug (`YYYY-short-title`, or `tNN-short-title` for
  notes) when you add it, and never change it afterwards: people cite these.
- The override itself is keyed by `key`, the slug of the file name (also the
  key of `catalog_ai.json` / `catalog_text.json`). Renaming a PDF changes its
  `key`, so move its override entry to the new key in the same commit; the
  public `id` is unaffected.
- Display titles come from the overrides, so a file rarely needs renaming.
  Renames also break GitHub file links that other pages may use.

## Repository size

- `python3 tools/check_sizes.py` enforces budgets: per PDF 15 MB warn / 40 MB
  fail; all content 600 MB warn / 900 MB fail (Pages caps a site at 1 GB);
  other files > 2 MB fail.
- Lossless re-optimization of these PDFs gains nothing (measured 0.8 MB of
  297 MB, 2026-10); they are mostly JPEG slide images. Real savings are lossy
  (`process_pdfs.py` with a lower dpi) or moving PDFs to Release assets (the
  plan once content passes 600 MB; `build_site.py --pdf-base` repoints links).
- Every `publish.sh` squash re-uploads the whole library. Plain commits are
  cheaper for additions; squash after replacing or deleting files.

## Website

- Layout (2026-10 redesign, Apple-product-page style): one idea per band,
  centred headings, lots of space, little text. Order: hero (title, one-line
  lede, two buttons, transmon) → stats → quantum-jump band → three shelf tiles
  (with fanned cover thumbnails) → "New here? Three ways in" (a collapsed
  `<details>`) → browse (sticky toolbar, filters, grid) → footer (reuse,
  others' work, about). Add new text to the footer or a deck page, not the
  hero; if a band needs more than two sentences, it's probably two bands.
- "Start here" reading paths: `PATHS` at the top of `site/app.js` (item ids).
  Keep them short (4–5 decks) and beginner-first. They render as cards with
  the first three decks' covers fanned out.
- Light/dark: follows the system; the top-bar button (`site/theme.js`, on
  every page) overrides it per browser. `THEME_BOOT` in `tools/site_pages.py`
  is inlined in each `<head>` to apply the choice before first paint.
- The results count says how many cards the decks fold into when series are
  stacked ("41 decks … shown as 10 cards (8 series stacked)").
- Machine-written summaries show a one-line disclosure until
  `summary_reviewed: true`; review notes from the 2026-10 red team are in
  ROADMAP.md.

- Source: `site/index.html`, `site/style.css`, `site/app.js`. No build step
  beyond `tools/build_site.py`, which writes `_site/library.json` (catalog +
  fallback AI fields) and copies the site.
- State lives in the URL (`?shelf=&q=&tag=&year=&level=&sort=&group=`, item as
  `#<id>`). By default each series collapses to one cover card (its first
  non-bonus deck in the current sort) with "+N more in this series"; series
  and standalone decks stay interleaved in sort order.
- Hero: the isometric transmon (`initTransmon()` in `site/app.js`, scroll- and
  time-driven, paused off-screen, static under reduced motion). The
  quantum-jump band (`initTrace()`) streams a seeded simulated record right to
  left, arcs each G→D jump in copper and labels the newest; it has a Pause
  button (and click-to-pause) and is static under reduced motion.
- Sections marked `.reveal` fade up once on scroll, only when JS runs
  (`html.js`) and motion is allowed; content is never hidden otherwise.
- Deploy: GitHub Pages via Actions on push to `main`.
- Fonts are self-hosted (`site/fonts/`, latin + greek subsets from Fontsource);
  no third-party requests. Cards load `thumbs/sm/` (360 px) with `srcset`.
- `index.html` has build-time placeholders (`%SITE_URL%`, `%YEARS%`,
  `%N_DECKS%`, `%N_SLIDES%`, `%N_HOURS%`, `%THEME_BOOT%`, `%COUNT_<shelf>%`,
  `%STATIC_LIST%`) filled by
  `fill_index()` in `tools/build_site.py`.
- Logo (chosen 2026-10, option C "caught mid-flight"): two energy levels and
  the copper arc of a jump in progress. Inline SVG `.mark` in the top bar of
  every page (themed via CSS tokens; the arc redraws on hover). Favicon is
  the bolder `site/favicon.svg` (no dotted guides, fixed dark tile) plus
  `favicon-32.png` and `apple-touch-icon.png` rendered from it.
- Social image: `site/og.png` (1200×630, a screenshot of the hero); regenerate
  if the hero changes.
- Tone: lighthearted, not self-serious, still professional: ket-notation shelf
  labels, the transmon and quantum-jump trace in the hero, the "Surprise me" button, the
  slide-count joke, the empty state and footer. Keep jokes short, and never in
  summaries or citations. The homepage link stays low-key (top bar + footer).

## Gotchas

- Ghostscript `-dSAFER` blocks reading files by absolute path; page counting uses
  `-dNOSAFER` locally and falls back to `pdfinfo`.
- `process_pdfs.py` keeps the original unless recompression is ≥ 5 % smaller.
- Tag inference keys off folder and file name (`TAG_RULES` in
  `build_catalog.py`); use overrides for one-offs.
- The remote has no history by design; pristine originals and the old history
  are in a local backup outside the repo.
