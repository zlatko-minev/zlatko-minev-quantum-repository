#!/usr/bin/env python3
"""
ai_enrich.py — Use a LOCAL ollama vision model to read each talk PDF and extract
a description, summary, topics, and suggested tags for the future website.

Design principles
-----------------
* **Additive & non-destructive.** Results are written to ``catalog_ai.json``,
  a SEPARATE file from ``catalog.json``. Each record is keyed by the catalog
  ``id``. An id that already has a record is SKIPPED (unless ``--force``), so
  hand-edits / re-runs never clobber prior analysis.
* **Resumable.** ``catalog_ai.json`` is saved after every item, so the job can
  be interrupted and restarted; it picks up where it left off.
* **Local only.** Talks to ollama at http://localhost:11434 — nothing leaves the
  machine.

What it does per PDF: renders the first N pages to images (pdftoppm), pulls the
first pages of text (pdftotext), and asks the vision model for structured JSON.

Usage
-----
    python3 tools/ai_enrich.py                 # enrich all not-yet-done items
    python3 tools/ai_enrich.py --limit 3       # do 3 (good for a first test)
    python3 tools/ai_enrich.py --ids T27-...    # specific ids
    python3 tools/ai_enrich.py --force          # redo even if already present
    python3 tools/ai_enrich.py --model qwen2.5vl:7b --pages 6

Requires: ollama (with a vision model pulled, e.g. `ollama pull qwen2.5vl:7b`),
and poppler (`pdftoppm`, `pdftotext`).
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG = REPO_ROOT / "catalog.json"
AI_OUT = REPO_ROOT / "catalog_ai.json"
OLLAMA_URL = "http://localhost:11434/api/generate"

CONTROLLED_TAGS = [
    "hardware", "superconducting-qubits", "qiskit-metal", "epr", "noise",
    "error-mitigation", "pec", "zne", "twirling", "machine-learning",
    "measurement", "many-body", "topological", "sensing", "summer-school",
    "tutorial", "lecture", "career", "overview", "circuits", "math",
]

PROMPT = """You are cataloguing a slide deck / technical talk by physicist Dr. Zlatko Minev on quantum computing. You are shown the first pages of the talk (images) and some extracted text.

Return ONLY a JSON object with these fields:
- "short_description": one concise sentence (max 25 words) describing what the talk covers.
- "summary": 2-4 sentences summarizing the content and what a viewer would learn.
- "topics": array of 3-7 specific topic phrases (e.g. "probabilistic error cancellation", "transmon coherence").
- "suggested_tags": array of 3-8 tags. Prefer these controlled tags where they fit: {tags}. You may add a few new lowercase-hyphenated tags if clearly warranted.
- "audience_level": one of "beginner", "intermediate", "advanced".
- "key_points": array of 2-5 short bullet strings of the main takeaways.

Extracted text from the first pages:
---
{text}
---
Respond with the JSON object only, no prose."""


def render_pages(pdf: Path, n: int, tmp: Path) -> list[str]:
    """Render first n pages to JPEGs; return list of base64 strings."""
    out_prefix = tmp / "pg"
    subprocess.run(
        ["pdftoppm", "-jpeg", "-r", "80", "-f", "1", "-l", str(n),
         str(pdf), str(out_prefix)],
        check=True, capture_output=True)
    imgs = sorted(tmp.glob("pg*.jpg"))
    return [base64.b64encode(p.read_bytes()).decode() for p in imgs]


def extract_text(pdf: Path, n: int) -> str:
    try:
        out = subprocess.run(
            ["pdftotext", "-f", "1", "-l", str(n), str(pdf), "-"],
            capture_output=True, text=True, timeout=60)
        return " ".join(out.stdout.split())[:3000]
    except Exception:
        return ""


# ---- reuse the persistent cache from extract_cache.py when available ----
CACHE = REPO_ROOT / "_cache"


def cached_images(iid: str, n: int) -> list[str] | None:
    d = CACHE / "pages" / iid
    if d.is_dir():
        imgs = sorted(d.glob("page*.jpg"))[:n]
        if imgs:
            return [base64.b64encode(p.read_bytes()).decode() for p in imgs]
    return None


def cached_text(iid: str, n: int = 4) -> str | None:
    f = CACHE / "text" / f"{iid}.json"
    if f.is_file():
        try:
            pages = json.loads(f.read_text()).get("pages", [])
            return " ".join(" ".join(p.split()) for p in pages[:n])[:3000] or None
        except Exception:
            return None
    return None


def cached_full_text(iid: str, max_chars: int) -> str | None:
    """Full extracted text for text-model enrichment (front + tail sampled)."""
    f = CACHE / "text" / f"{iid}.json"
    if not f.is_file():
        return None
    try:
        t = " ".join(json.loads(f.read_text()).get("pages", [])).split()
        t = " ".join(t)
        if len(t) <= max_chars:
            return t or None
        head = t[: int(max_chars * 0.7)]
        tail = t[-int(max_chars * 0.3):]
        return f"{head}\n...\n{tail}"
    except Exception:
        return None


def _parse_json_loose(text: str) -> dict:
    """Parse model output as JSON, tolerating minor noise / trailing commas."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)  # grab the outermost object
    if m:
        cleaned = re.sub(r",\s*([}\]])", r"\1", m.group())  # trailing commas
        return json.loads(cleaned)
    raise json.JSONDecodeError("no JSON object found", text, 0)


def _ollama_once(model, prompt, images, timeout) -> dict:
    payload = {
        "model": model, "prompt": prompt, "images": images,
        "stream": False, "format": "json", "keep_alive": "30m",
        # bigger context so several slide images don't overflow 4096 (caused
        # slow/hung inference + HTTP 500s on image-dense decks)
        "options": {"temperature": 0, "num_ctx": 8192},
    }
    req = urllib.request.Request(
        OLLAMA_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read())
    return _parse_json_loose(resp["response"])


def call_ollama(model, prompt, images, timeout, retries=2) -> dict:
    """Call ollama with retries + backoff; on repeated 500s, shrink the image set."""
    last = None
    for attempt in range(retries):
        try:
            imgs = images if attempt < 2 else images[:3]  # fewer imgs on last try
            return _ollama_once(model, prompt, imgs, timeout)
        except Exception as e:  # noqa: BLE001 - transient HTTP 500 / bad JSON
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vision", action="store_true",
                    help="use the vision model on slide images (slow; default is "
                         "the fast text model over cached extracted text)")
    ap.add_argument("--model", default=None,
                    help="override model (default: qwen2.5:7b text / qwen2.5vl:7b vision)")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ids", nargs="*", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--timeout", type=int, default=240)
    args = ap.parse_args()
    model = args.model or ("qwen2.5vl:7b" if args.vision else "qwen2.5:7b")

    items = json.loads(CATALOG.read_text())["items"]
    ai = {"model": model, "items": {}}
    if AI_OUT.exists():
        ai = json.loads(AI_OUT.read_text())
        ai.setdefault("items", {})
        ai["model"] = model
    done = ai["items"]

    todo = []
    for it in items:
        if args.ids and it["id"] not in args.ids:
            continue
        if it["id"] in done and not args.force:
            continue
        todo.append(it)
    if args.limit:
        todo = todo[:args.limit]

    mode = "vision" if args.vision else "text"
    print(f"{len(todo)} item(s) to enrich with {model} ({mode}) "
          f"({len(done)} already done). Output -> {AI_OUT.name}")

    ok = fail = 0
    for i, it in enumerate(todo, 1):
        pdf = REPO_ROOT / it["file"]
        print(f"[{i}/{len(todo)}] {it['id'][:60]} ...", flush=True)
        try:
            with tempfile.TemporaryDirectory() as td:
                if args.vision:
                    imgs = cached_images(it["id"], args.pages) \
                        or render_pages(pdf, args.pages, Path(td))
                    text = cached_text(it["id"]) or extract_text(pdf, min(args.pages, 4))
                else:  # text mode: full extracted text, no images (fast, stable)
                    imgs = []
                    text = (cached_full_text(it["id"], 9000)
                            or extract_text(pdf, 8))
                prompt = PROMPT.format(tags=", ".join(CONTROLLED_TAGS), text=text)
                data = call_ollama(model, prompt, imgs, args.timeout)
            data["_mode"] = mode
            data["_source_pages"] = len(imgs)
            done[it["id"]] = data
            ai["items"] = done
            AI_OUT.write_text(json.dumps(ai, indent=2, ensure_ascii=False) + "\n")
            ok += 1
            print(f"     ✓ {str(data.get('short_description',''))[:80]}")
        except Exception as e:
            fail += 1
            print(f"     ✗ {type(e).__name__}: {str(e)[:160]}", file=sys.stderr)

    print(f"\nDone: {ok} ok, {fail} failed, {len(done)} total in {AI_OUT.name}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
