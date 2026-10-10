# Roadmap — Zlatko Minev Quantum Repository

> Living plan for turning the archive into a polished, browsable, self-hostable
> site. Status legend: ✅ done · 🔄 in progress · ⏳ planned · 💡 idea.
> See `agent/NOTES.md` for the maintenance pipeline and decisions log.

## Now / foundations
- ✅ Compress PDFs (~150 dpi), drop Git LFS, single-commit publish workflow
- ✅ `catalog.json` metadata DB + self-validating generator (`tools/build_catalog.py`)
- ✅ Import tracking outside the repo (`../imported_talks.json`)
- ✅ pptx→pdf import path (LibreOffice headless) + `tools/process_pdfs.py`
- 🔄 **Local AI enrichment** (`tools/ai_enrich.py`, ollama `qwen2.5vl`) → `catalog_ai.json`
  (additive, never overwrites; short description, summary, topics, tags, level)
- ⏳ **Folder reorg** of `content - educational/` to be shallower / topic-first (see below)

## Content quality
- ⏳ **Metadata questions found while summarizing (author to confirm):**
  QGSS 2022 bonus "State Preparation Noise" / "Coherent ZZ Error" and the QGSS
  2023 "Coherent ZZ Error" pages are dated July 2021 (the 2023 one matches the
  2021 file); "Intro to Real Quantum Computers and Noise" is filed as 2022 but
  cites 2024 work and is titled "IBM Quantum Summer Learning Session"; the 2024
  APS deck's title slide reads "A detailed portrait of quantum many-body
  dynamics"; T23 cites the sparse Pauli-Lindblad paper as Nature Physics 16
  (2020).
- ⏳ **DB + text proofing pass (manual).** Build a simple proofing view (an HTML
  table or `tools/proof.py` that dumps `catalog.json` + `catalog_ai.json` side by
  side) to review every title, venue, year, speaker, description, and tags. Fix
  via `tools/catalog_overrides.json` (curation) — never hand-edit `catalog.json`.
- ⏳ **Tag taxonomy.** Promote the AI `suggested_tags` into a controlled vocabulary;
  reconcile with `TAG_RULES` in `build_catalog.py`. One canonical tag list.
- ✅ **Naming: decided not to rename files** (2026-10). Display titles come from
  `catalog_overrides.json`; renames would break existing GitHub links and site
  permalinks. See `agent/NOTES.md`.

## Technical notes (`content - tech notes/`)
The `T*` notes (derivations, cheat-sheets, working notes) are a distinct content
type and deserve first-class treatment, not just being lumped in with talks.
- ⏳ **Import the full set.** Pull the complete technical-notes collection from the
  internal `TALKS/TALKS technical notes/` folder into the repo (8 of N are in so
  far). Convert any non-PDF sources; compress; log in `../imported_talks.json`.
- ⏳ **Structured JSON metadata.** Extend `catalog.json` records for notes with
  note-specific fields (e.g. `note_id` like `T27`, prerequisite notes, related
  talks, equations/result summary). Run `ai_enrich.py` over them too.
- ⏳ **Dedicated tagging.** A tech-note tag vocabulary (`derivation`, `cheat-sheet`,
  `reference`, `bound`, `estimator`, `noise-model`, …) layered on the main tags.
- 💡 **Repo decision.** Decide whether notes stay a section here or graduate into
  their own lightweight repo (e.g. `zlatko-minev-tech-notes`) that the site can
  pull in alongside the talks — keep the catalog the shared interface either way.
- ⏳ Surface notes as their own browsable category + cross-links from related talks.

## Website (lightweight, self-hostable)
Static site in `site/` (plain HTML/CSS/JS, no framework or npm), built by
`tools/build_site.py` into `_site/` and deployed to GitHub Pages by
`.github/workflows/site.yml`. It reads one merged file, `library.json`
(`catalog.json` + `catalog_ai.json`).

- ✅ Browse UI: search (titles, venues, topics, summaries), type tabs, topic /
  format / level chips with live counts, year histogram, sort, group by series,
  detail view with summary, key points, related items, PDF link. Filters live in
  the URL; `#<id>` opens an item, so every view is a shareable link.
- ✅ Thumbnails: page 1 of each PDF via `pdftoppm` → `site/thumbs/<id>.jpg`
  (~40 KB each, committed; CI fails if one is missing).
- ✅ Curated display titles / series / venues / tech-note dates in
  `tools/catalog_overrides.json` (from the PDFs' own title pages).
- ✅ Named **The Quantum Notebook**; three shelves (Lectures & Tutorials, Research
  Talks, Tech Notes) with series grouping; low-key links to zlatko-minev.com.
- ✅ Citations: one BibTeX entry per series or standalone deck; item and series
  pages with Google Scholar meta tags; `citations.bib`, sitemap, `CITATION.cff`;
  "Cite & reuse" notice.
- ✅ Paper links (arXiv IDs from title slides) via `links` in the overrides.
- ⏳ **Video links**: match QGSS and other recorded lectures to their YouTube
  videos (`links` with label "Video"); needs web access or the author's list.
- 💡 Zenodo DOIs for the tech notes (needs the owner's Zenodo account); add
  `doi` to BibTeX once they exist.
- ✅ Summaries rewritten from each deck's text (2026-10), shown as "draft" until
  the author sets `summary_reviewed: true`.
- ⏳ **Enable Pages**: Settings → Pages → Source: GitHub Actions (one-time, owner).
- ⏳ **Address**: recommended `talks.zlatko-minev.com` (DNS CNAME `talks` →
  `zlatko-minev.github.io`, then Settings → Pages → Custom domain, enforce HTTPS).
- ⏳ **Author review** of summaries and of the metadata questions below.
- ⏳ Add 3–5 `featured` picks.

## Repository size
Facts (2026-10): 76 PDFs, 297 MB; git pack 211 MB; history is already a single
commit. ~75% of PDF bytes are JPEG images at ~150 dpi; a lossless re-optimization
pass (pikepdf, object streams + recompressed Flate) saves 0.8 MB total. So
further shrinking is either lossy or moves files out of git.

- ✅ `tools/check_sizes.py` size guard, run by CI and `publish.sh`: per-PDF
  15 MB warn / 40 MB fail; content total 600 MB warn / 900 MB fail (Pages cap is
  1 GB); stray non-content binaries > 2 MB fail; catalog ↔ disk consistency.
- Note: every `publish.sh` squash re-uploads the whole library (the new root
  commit shares no history with the remote). Squashing only frees space when
  files were replaced or removed; plain commits are cheaper for additions.
- 💡 **Decision rule:** when content passes the 600 MB warning, move PDFs to a
  GitHub Release ("library" tag, 2 GB per file, no repo quota) and have CI pull
  them into the Pages build. The site already takes a `--pdf-base`, so links
  change in one place.
- 💡 Lossy pass on the 10 decks over 10 MB (e.g. 120 dpi) if clone size matters
  before then. Check text legibility on equation slides first.

## Discoverability
- ⏳ **SEO.** Per-page `<title>`/meta description (seed from AI `short_description`),
  Open Graph + Twitter cards (thumbnail), JSON-LD structured data
  (`ScholarlyArticle` / `PresentationDigitalDocument`), `sitemap.xml`, `robots.txt`,
  canonical URLs, descriptive slugs (already have stable `id`s).
- 💡 Optional: RSS/Atom feed of new talks; "cite this talk" snippets.

## Critical review (multi-agent)
Before launch, run the site + copy through a panel of role-played reviewers and
collect findings:
- ⏳ **Student** — is it understandable? can I find learning material by topic/level?
- ⏳ **Colleague / researcher** — is it accurate, credible, properly attributed?
- ⏳ **Dev-rel / community** — is it shareable, embeddable, well-tagged, useful?
- ⏳ **Journalist / science writer** — is the story clear, quotable, citable?
- ⏳ **Skeptic / critic** — what's confusing, missing, over-claimed, or broken?
- ⏳ **Web/dev reviewer** — performance, accessibility (a11y), mobile, SEO, links.
  (Implement as a workflow/agents pass over the built site + `catalog.json`.)

## Backlog / ideas
- 💡 Per-series landing pages (e.g. the QGSS noise course as one unit)
- 💡 "Collections" / playlists curated across categories
- 💡 Analytics (privacy-respecting) to see what's downloaded
- 💡 Versioning note per talk (which event/year variants exist)

## Maintenance loop (adding talks) — see `agent/NOTES.md`
1. Drop/convert source into the right `content - …` folder
2. `python3 tools/process_pdfs.py` → compress
3. `python3 tools/build_catalog.py` → catalog + validation
4. `python3 tools/ai_enrich.py` → AI enrichment (additive)
5. Log the source in `../imported_talks.json`
6. `bash tools/publish.sh --push` → single clean commit
