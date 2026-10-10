# Roadmap — Zlatko's Quantum Notebook

> Living plan for the archive and its website. Status: ✅ done · ⏳ next · 💡 idea.
> How-to and conventions: `agent/NOTES.md`. Last updated 2026-10-10.

## Continue here

### Owner actions (in this order)
1. ⏳ **Enable GitHub Pages**: Settings → Pages → Source: **GitHub Actions**.
   Do this before merging, so the first deploy on `main` succeeds.
2. ⏳ **Pick the address before people cite it.** Citation URLs embed it.
   - Default: `https://zlatko-minev.github.io/zlatko-minev-quantum-repository/`.
   - Recommended: `talks.zlatko-minev.com`. Steps:
     1. Add a DNS record: `CNAME talks → zlatko-minev.github.io`.
     2. Settings → Pages → Custom domain, and enforce HTTPS.
     3. Settings → Secrets and variables → Actions → Variables: `SITE_URL=https://talks.zlatko-minev.com/`.
     4. Change `SITE_URL` in `tools/build_site.py` to the same address.
3. ⏳ **Merge the website PR** (squash), then check the deployed site and the
   Actions run.
4. ⏳ **Review the 76 machine-drafted summaries.** For each one that is right,
   set `"summary_reviewed": true` on that item in `tools/catalog_overrides.json`;
   this removes its "draft" note.
5. ⏳ **Decide the metadata questions** below.
6. ⏳ **Open web access for agents** (cloud environment → Network access →
   Allowed domains): `zlatko-minev.com`, `youtube.com`, `www.youtube.com`,
   `arxiv.org`, `doi.org`. This unblocks video links, DOI checks and matching
   the site's style to the homepage.
7. ⏳ **DOIs and Scholar**: see "Getting indexed by Google Scholar" below. Log in to zenodo.org with GitHub, switch on this
   repository, then publish a GitHub Release. Zenodo mints a DOI using
   `.zenodo.json`. Add the DOI to `CITATION.cff` (`identifiers`) and the README.
   Optionally deposit individual tech notes for per-note DOIs, and add their
   `doi` links to the overrides.
8. 💡 Add your ORCID to `CITATION.cff` and `.zenodo.json`.

### Getting indexed by Google Scholar (citations that count)
Scholar indexes scholarly records with stable identifiers much more reliably
than personal websites, so the plan has three tracks:

1. ⏳ **Tech notes on arXiv.** This is the strongest route: Scholar indexes
   arXiv fully and counts citations to it.
   - Category: `quant-ph`, or `physics.ed-ph` for pedagogical notes, with a
     comment such as "Technical note T27, Zlatko's Quantum Notebook".
   - arXiv wants the LaTeX source, not just the PDF. Upload T21–T27 from their
     source files.
   - Then add the arXiv link to each note's `links`. Add the `doi` too if you
     also deposit the note on Zenodo.
2. ⏳ **Slides on Zenodo.** Every record gets a DOI from DataCite, and Scholar
   indexes Zenodo. `tools/zenodo_deposit.py` plans 47 records from the catalog:
   - one "lesson" record per lecture series, holding all its decks (later
     years become new versions under the same concept DOI, so citations
     consolidate);
   - a "presentation" record for each standalone talk, and a "poster" for the
     2011 APS poster;
   - a "technical note" record for each tech note.

   Steps:
   1. Create a token: zenodo.org → Applications → Personal access token, with
      scopes `deposit:write` and `deposit:actions`.
   2. Open network access to `zenodo.org` and `sandbox.zenodo.org` for agent
      sessions, or run the script on your own machine.
   3. Rehearse on the sandbox: `ZENODO_SANDBOX_TOKEN=... python3
      tools/zenodo_deposit.py create --sandbox --only t27`, then check the
      draft on sandbox.zenodo.org.
   4. Production: run `create`, review the drafts on zenodo.org, then run
      `publish`. Publishing writes the concept DOIs into the overrides and
      `tools/series.json`. Rebuild and commit, and the site's BibTeX, Scholar
      tags and DOI buttons pick them up.
   5. Give years to T11.7, T11.9, T23 and T25 first. Zenodo needs a
      publication date, so the script skips these until they have one.
   6. Optional: create a Zenodo community "Zlatko's Quantum Notebook" and add the
      records to it.
3. ⏳ **Your Google Scholar profile.**
   - After indexing (weeks to months), check that each record is attributed
     to you.
   - Add missing ones with "Add article manually", using the DOI's metadata.
   - Merge duplicates, e.g. the same series indexed twice.
   - Turn on automatic profile updates for new articles.
4. ✅ **Already on the site:**
   - Scholar `citation_*` tags, with `citation_pdf_url` only when the PDF is on
     the same site and `citation_doi` once a DOI exists.
   - JSON-LD, a sitemap and BibTeX with `doi`.

   Scholar may index the site's tech-note pages directly, but don't count on
   it for slides.

### Agent tasks (next session; prompts you can paste)
- **Video links** (needs web): "Find the YouTube recordings for the QGSS 2020–2023
  and Boulder 2023 lectures in this repo, verify each matches its deck, and add
  them as `links` with label `Video`. Follow agent/NOTES.md › Links."
- **Paper and DOI check** (needs web): "Verify every `links` entry in
  tools/catalog_overrides.json against arXiv/DOI records, and add journal DOIs
  for the quantum-jump (Nature 570, 200) and ML-QEM (Nat. Mach. Intell. 6, 1478)
  talks."
- **Style match** (needs web): "Look at zlatko-minev.com and align the site's
  palette, type and tone with it, keeping the token system in site/style.css."
- **Add new talks**: "Add this deck to the notebook" plus the file. The agent
  follows `.claude/skills/add-deck/SKILL.md`, which runs `tools/add_deck.py`
  (one command: file, compress, slug, thumbnails, frozen BibTeX key, build)
  and then writes the summary, verifies links and opens a PR.
- **Red-team again** after big changes: "Run a multi-persona review (design,
  physics, student, citations, a11y/SEO, skeptic, QA) of the built site and fix
  what's real."

### Metadata questions for the author
- The QGSS 2022 "State Preparation Noise" and "Coherent ZZ Error" bonus pages
  are dated July 2021, and the QGSS 2023 "Coherent ZZ Error" page has the same
  text as the 2021 file. Keep them as re-distributed copies, or link them with
  `version_of`?
- "Intro to Real Quantum Computers and Noise" is filed as 2022, but it cites
  2024 work and its title slide says "IBM Quantum Summer Learning Session".
  What are the correct year and venue?
- The 2024 APS invited talk's title slide reads "A detailed portrait of quantum
  many-body dynamics". The site uses the paper title. Which should it be?
- What years should T11.7, T11.9 and T25 have? They are undated, so their
  BibTeX keys contain `nd`. Keys stay frozen even after a year is added.
- In the PDFs themselves:
  - T23 cites arXiv:2012.09738 as the PEC paper; it should be arXiv:2201.09866.
  - T21–T23 contain a stray "Nature Physics 16, 233 (2020)" line.

## Done (2026-10)

**Repository and pipeline**
- ✅ Compressed PDFs (~150 dpi), no Git LFS, single-commit publishing
  (`tools/publish.sh`).
- ✅ `catalog.json` generator with validation, plus curated
  `tools/catalog_overrides.json` (titles from title slides, series, venues,
  dates, co-presenters, `authors`, `tags_remove`, `links`, `version_of`).
- ✅ Permanent public ids: short frozen slugs, e.g.
  `t27-simple-noise-models-and-gate-fidelity`. Files are never renamed.
- ✅ Size guard `tools/check_sizes.py`, run in CI and `publish.sh`. Lossless PDF
  optimization was measured at 0.8 MB of 297 MB, so further savings would have
  to be lossy or come from moving PDFs out of git.
- ✅ One-command intake for new decks: `tools/add_deck.py` plus the agent skill
  `.claude/skills/add-deck/SKILL.md`.
- ✅ CI (`.github/workflows/site.yml`) checks size, catalog freshness,
  thumbnails and frozen BibTeX keys, then builds and deploys to Pages from
  `main`.

**Website ("Zlatko's Quantum Notebook")**
- ✅ Three shelves: Lectures & Tutorials, Research Talks, Tech Notes.
- ✅ Each series collapses to a cover card with "+N more"; the chosen sort order
  is kept.
- ✅ "Start here" reading paths.
- ✅ Search ranks best matches first and expands synonyms; filters by topic,
  format, level and year; all state lives in the URL.
- ✅ Detail view: summary, key points, in-series navigation, related decks,
  paper links, Cite panel.
- ✅ Hero: animated isometric transmon and a quantum-jump trace, both checked
  for physics.
- ✅ Accessibility: focus is kept across re-renders, status-only live region,
  skip link, pause control, reduced motion respected.
- ✅ SEO: crawlable card links, static deck list without JS, JSON-LD,
  OG/Twitter cards, social image, sitemap, robots, Atom feed (`feed.xml`) with
  "New" badges.
- ✅ Performance: self-hosted fonts (SIL OFL), 360 px thumbnails with `srcset`,
  no layout shift from late-loading content.
- ✅ All 76 summaries drafted from the slide text and checked by a physics
  reviewer. They are labelled as drafts until the author reviews them.

**Citations**
- ✅ Per-item pages (`items/<id>/`) and per-series pages (`series/<slug>/`).
- ✅ BibTeX: tech notes are `@techreport`. Each lecture series is cited as one
  work (its note lists years and venues), so citations consolidate; only
  Career & Outreach decks are cited individually.
- ✅ Summer-school copies of tech notes cite the note (`version_of`).
- ✅ Keys are frozen in `tools/bibkeys.json`.
- ✅ Google Scholar tags follow its rules: the PDF tag appears only when the
  PDF is hosted on the site, and copies carry no tags.
- ✅ `citations.bib`, `CITATION.cff`, `.zenodo.json`.

**License and reuse**
- ✅ License is CC BY-NC-ND 4.0, with a copyright line.
- ✅ Commercial use and adapted versions need permission.
- ✅ A non-binding request to tell the author when the material is used in
  teaching or publications.
- ✅ Third-party material stays with its owners.
- ✅ The same wording appears on the site, the citation pages, the README and
  LICENSE.md.

**Reviews**
- ✅ Seven-persona red team (2026-10): design, physics, student, citations,
  a11y/performance/SEO, skeptic/journalist, QA. All findings were fixed except
  the items listed under "Next".

## Next
- ⏳ **Video links**: needs web access, or a list from the author.
- ⏳ **Import the remaining tech notes** from the internal `TALKS technical notes/`
  folder. 8 of N are in the repo so far.
- ⏳ **Featured picks**: 3–5 decks, using `tags: ["featured"]`. Show them in the
  hero or under "Start here".
- ⏳ **Tag taxonomy**: one controlled vocabulary, reconciling `TAG_RULES` with the
  curated tags.
- ⏳ **Reading paths**: revisit `PATHS` in `site/app.js` as new decks arrive.
- 💡 Per-deck "versions" note, e.g. Superconducting Qubits 101 given at five
  venues.
- 💡 Privacy-respecting analytics (e.g. GoatCounter) to see which decks are read.
- 💡 A lossy pass on the decks over 10 MB if clone size starts to matter. Check
  equation legibility first.
- 💡 **Storage decision rule**: when content passes 600 MB, move PDFs to a GitHub
  Release and pull them into the Pages build. `--pdf-base` already supports this.

## Repository size facts
76 PDFs, 297 MB; git pack 211 MB; a single commit. About 75% of PDF bytes are
JPEG images. Each `publish.sh` squash re-uploads the whole library: plain commits
are cheaper for additions, and squashing only pays after replacing or deleting
files.
