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
- ⏳ **AI text proofing (needed before promoting the site).** The local 7B model's
  output has factual slips (e.g. the Fibonacci-anyons talk tagged `qiskit-metal`,
  `pec`, `sensing`); the site labels it "auto-summary" and does not use
  `suggested_tags` for filtering. Rewrite or proof the 76 descriptions.
- ⏳ **DB + text proofing pass (manual).** Build a simple proofing view (an HTML
  table or `tools/proof.py` that dumps `catalog.json` + `catalog_ai.json` side by
  side) to review every title, venue, year, speaker, description, and tags. Fix
  via `tools/catalog_overrides.json` (curation) — never hand-edit `catalog.json`.
- ⏳ **Tag taxonomy.** Promote the AI `suggested_tags` into a controlled vocabulary;
  reconcile with `TAG_RULES` in `build_catalog.py`. One canonical tag list.
- ⏳ **Naming normalization.** Optional pass to standardize filenames to
  `YYYY — Title — (Venue).pdf`; only after the catalog is the source of truth so
  nothing breaks (catalog keys off `id`, derived from filename).

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
- ⏳ **Enable Pages**: Settings → Pages → Source: GitHub Actions (one-time, owner).
- ⏳ **Landing copy**: review the masthead text; add 3–5 `featured` picks.
- 💡 Integration with zlatko-minev.com: subpath vs subdomain
  (`talks.zlatko-minev.com` via a Pages CNAME).

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
