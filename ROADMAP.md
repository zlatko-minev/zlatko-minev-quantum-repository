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
Goal: a **static** site (no server/DB) that reads `catalog.json` + `catalog_ai.json`
and renders a fast, searchable, filterable archive. Host on GitHub Pages or any
static host; later embed/链 into **zlatko-minev.com**.

- ⏳ **Stack decision.** Recommended: a static generator that consumes the JSON
  directly — e.g. **Astro** or a single-page vanilla JS app (the old Jekyll
  prototype was removed; start fresh). Must run fully client-side so it can be
  dropped under `zlatko-minev.com/talks` or hosted standalone.
- ⏳ **Landing / home page rewrite (priority, do early).** Strong hero, clear value
  prop, "what is this / who is it for", featured talks, and entry points by
  category + topic. Replace the old "UNDER CONSTRUCTION" copy. Draft copy first,
  then design.
- ⏳ **Browse & filter UI.** Facets: category, topic/tag, year, venue, level.
  Full-text search over titles + AI summaries. Per-talk page with embedded PDF
  viewer + download + metadata + AI summary.
- ⏳ **Thumbnails.** Auto-render page-1 of each PDF to a thumbnail (`pdftoppm`)
  at build time → `assets/images/thumbnails/<id>.jpg`.
- 💡 **Integration with zlatko-minev.com.** Decide subpath vs subdomain
  (`talks.zlatko-minev.com`), shared header/footer, consistent branding.

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
