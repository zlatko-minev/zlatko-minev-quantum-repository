# Agent Notes — Zlatko Minev Quantum Repository

> Orientation + working notes for any future agent (or human) picking this up.
> Last meaningful update: 2026-06-14.

## ✅ AI enrichment — COMPLETE (2026-06-15)

All 76 talks enriched (`qwen2.5:7b`, text mode over cleaned `catalog_text.json`)
→ `catalog_ai.json` (committed). Per talk: short_description, summary, topics,
suggested_tags, audience_level, key_points. Additive & non-destructive; re-run
`python3 tools/ai_enrich.py` to fill only new talks.

- The vision model (`qwen2.5vl`) was abandoned for bulk use — it HUNG on
  image-dense multi-page decks. Kept available via `--vision` for one-off decks.
- The 9 sparse cheat-sheet decks (`catalog_text.json` chars < 400) were enriched
  fine from their title text; OCR (`extract_cache.py` w/o `--no-ocr`) is available
  if deeper text is ever needed.
- Next quality step (see ROADMAP): manual proofing of AI text + promoting
  `suggested_tags` into the controlled tag vocabulary (some are noisy, e.g.
  `qiskit-metal` mis-applied to a few noise notes).

## What this repo is

A curated public archive of Zlatko Minev's quantum talks, lectures, tutorials,
and technical notes (2011–present), published to GitHub and intended to feed a
future browsable website. Content lives in three top-level folders:

- `content - research talks/` — keynotes, seminars, colloquia (flat, `YYYY Title (Minev, Venue).pdf`)
- `content - educational/` — lectures, summer schools, tutorials, career talks (nested by series/course)
- `content - tech notes/` — short derivations/notes (`T<n> Title (Minev).pdf`)

74 PDFs as of this writing. No `.pptx` currently checked in (source decks live elsewhere).

## The intent (what the owner wants)

1. **Keep the GitHub repo small and clean.** The Hub copy should never carry
   history — always one squashed commit, force-pushed. History was the main
   source of bloat and is not wanted.
2. **PDFs small but readable.** High-enough quality to project/zoom, small
   enough to host and download without LFS quotas.
3. **A metadata database** (`catalog.json`) so files can be tagged
   (hardware / summer-school / lecture / tutorial / career / research / ...) and
   later power a website. Website is NOT being built yet — just the data.
4. **Consistent, descriptive naming** for files/talks.
5. More talks will be added over time — the pipeline must be repeatable.

## Decisions made (2026-06-14)

- **Dropped Git LFS.** LFS ran out of free storage/bandwidth and was clunky.
  Compressed PDFs are small enough to commit as normal git blobs. `.gitattributes`
  LFS filters removed.
- **Single-commit history.** Repo is reset to one orphan commit and force-pushed.
  No history is retained on the remote by design.
- **Compression: balanced ~150 dpi** via Ghostscript (`tools/process_pdfs.py`).
  Net ~34% smaller (415 MB → 274 MB of PDFs) with crisp text. Quality-heavy
  hardware decks shrank most (e.g. Superconducting Qubits 101: 14.9M → 4.3M).
- **Originals preserved locally**, OUTSIDE the repo, at
  `../_BACKUP_quantum_repo_2026-06-14/` (full pre-compression copy incl. old
  `.git`). This is the source-of-truth for pristine quality. Not committed.
- **Old `_web/` Jekyll site is deprecated.** It was a half-built "UNDER
  CONSTRUCTION" Jekyll prototype; the owner wants to rethink the site from
  scratch later. `catalog.json` is the durable interface a new site will consume.

## How far we got

- [x] Full safety backup of repo (incl. history) → `../_BACKUP_quantum_repo_2026-06-14/`
- [x] `tools/process_pdfs.py` — Ghostscript compressor (idempotent, keeps original if no win)
- [x] Compressed all 74 PDFs in place; validated 0 corrupt; report in `tools/compression_report.csv`
- [x] `tools/build_catalog.py` + `catalog.json` — metadata DB with auto tags
- [x] `tools/catalog_overrides.json` — hand-curated tags merged on regen
- [ ] Drop LFS + squash to single commit + force-push  ← final git step
- [ ] (Future) rethink/rebuild the website that consumes `catalog.json`
- [ ] (Future) optional filename normalization pass

## Repeatable workflow — adding new talks

1. **Source/convert.** If the source is a `.pptx`, convert it to PDF first:
   `soffice --headless --convert-to pdf --outdir <out> "<file.pptx>"`
   (LibreOffice; faithful to PowerPoint — verified). Drop the PDF into the right
   `content - ...` topic folder, following `YYYY Title (Minev, Venue).pdf`.
2. **Compress:** `python3 tools/process_pdfs.py` (only shrinks what it can; safe
   to re-run on the whole library).
3. **Rebuild metadata:** `python3 tools/build_catalog.py` (self-validates; aborts
   on dupes/missing files). Tag stragglers via `tools/catalog_overrides.json`.
4. **AI-enrich (optional):** `python3 tools/ai_enrich.py` → `catalog_ai.json`
   (local ollama vision model; additive, never overwrites; resumable).
5. **Log the source** in `../imported_talks.json` (outside the repo).
6. **Publish:** `bash tools/publish.sh --push` (single clean commit, force-push,
   destructive on the remote by design; refuses to push if LFS pointers slip in).

## Layout (as of 2026-06-14)

- `content - educational/` — flattened to 6 **topic** folders (max 2 deep):
  Superconducting Qubits & Hardware · Quantum Noise · Error Mitigation ·
  Quantum Measurements · Tutorials (Pauli Twirling) · Career & Outreach.
  Reorg is reproducible via `tools/reorg_educational.py`.
- `content - research talks/` (flat), `content - tech notes/` (flat).
- `catalog.json` — metadata DB (generated). `catalog_ai.json` — AI enrichment
  (generated, additive). `ROADMAP.md` — site/quality plan.
- `tools/` — `process_pdfs.py`, `build_catalog.py` + `catalog_overrides.json`,
  `ai_enrich.py`, `reorg_educational.py`, `convert_pptx_to_pdf.py`, `publish.sh`.
- Outside the repo: `../imported_talks.json` (import tracking),
  `../_BACKUP_quantum_repo_2026-06-14/` (pristine originals + old history).

> Tag note: tag inference keys off filename + folder path. After the topic reorg,
> files no longer inherit tags from the old umbrella folder name, so
> error-mitigation/noise counts dropped — this is intentional (more accurate).
> AI `suggested_tags` in `catalog_ai.json` augment these.

## Gotchas / notes for the next agent

- Ghostscript `-dSAFER` blocks reading files by absolute path in `-c` snippets;
  `build_catalog.py` uses `-dNOSAFER` only for local page counting.
- `process_pdfs.py` never enlarges a file — if recompression isn't ≥5% smaller it
  keeps the original. So re-running across the library is cheap and lossless to
  already-optimized files.
- Tags are inferred from folder + filename keywords (`TAG_RULES` in
  `build_catalog.py`). Add rules there for systematic tags; use
  `catalog_overrides.json` for one-offs and curation (`featured`, `description`).
- The remote intentionally has NO history. Never rely on `git log` for the
  archive's provenance — the backup folder is the only deep record.
