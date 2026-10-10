#!/usr/bin/env python3
"""
zenodo_deposit.py — Give the archive DOIs on Zenodo, so Google Scholar and
DataCite can index and count citations.

What becomes a Zenodo record ("unit")
-------------------------------------
* each tech note .................. publication / technical note
* each lecture series (2+ decks) .. lesson; all its decks in one record
* each other deck ................. presentation (poster if the venue says so)

Copies (``version_of``) are skipped: they cite the original. The record links
back to the deck's page on the site and to its paper (arXiv), carries the
summary as its description, and uses the archive license (CC BY-NC-ND 4.0).

Safety
------
Nothing is published unless you run ``publish``. ``create`` only makes
*drafts* you can inspect and edit on zenodo.org. Try ``--sandbox`` first
(sandbox.zenodo.org, a separate account and token, throwaway DOIs).

Usage
-----
    python3 tools/zenodo_deposit.py plan                     # list units, no network
    python3 tools/zenodo_deposit.py plan --json plan.json    # full metadata to a file
    ZENODO_TOKEN=... python3 tools/zenodo_deposit.py create --sandbox --only t27
    ZENODO_TOKEN=... python3 tools/zenodo_deposit.py publish --sandbox --only t27
    python3 tools/zenodo_deposit.py status [--sandbox]

``--only`` takes unit ids or prefixes (see ``plan``). After ``publish`` the
record's concept DOI (stable across versions) is written to
``tools/catalog_overrides.json`` (``doi`` on the item) or ``tools/series.json``
(series), so the site's BibTeX, Scholar tags and DOI buttons pick it up on the
next build. Deposition state lives in ``tools/zenodo.json``: commit it.

Adding a deck to an already-published series: open the record on zenodo.org,
click "New version", add the PDF, publish. The concept DOI stays the same.

Token: zenodo.org → Account → Applications → Personal access token, scopes
``deposit:write`` and ``deposit:actions``. Requires network access to
zenodo.org (or sandbox.zenodo.org). Written against Zenodo's documented REST
API (/api/deposit/depositions); try it on the sandbox before production.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_pages import authors, series_groups, slug  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG = REPO_ROOT / "catalog.json"
OVERRIDES = REPO_ROOT / "tools" / "catalog_overrides.json"
SERIES_META = REPO_ROOT / "tools" / "series.json"
STATE = REPO_ROOT / "tools" / "zenodo.json"
SITE_URL = "https://zlatko-minev.github.io/zlatko-minev-quantum-repository/"
HOSTS = {"production": "https://zenodo.org", "sandbox": "https://sandbox.zenodo.org"}
LICENSE = "cc-by-nc-nd-4.0"


# ---------- planning (no network) ----------

def creator(name: str) -> dict:
    """'Zlatko K. Minev' → {'name': 'Minev, Zlatko K.'} (Zenodo's 'Family, Given')."""
    parts = name.split()
    return {"name": f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) > 1 else name}


def related(items: list[dict], page: str) -> list[dict]:
    rel = [{"identifier": page, "relation": "isIdenticalTo", "resource_type": "other"}]
    for it in items:
        for link in it.get("links") or []:
            url = link.get("url", "")
            if "arxiv.org/abs/" in url:
                rel.append({"identifier": "arXiv:" + url.rsplit("/abs/", 1)[1],
                            "relation": "isSupplementTo", "resource_type": "publication-article"})
    seen, out = set(), []
    for r in rel:
        if r["identifier"] not in seen:
            seen.add(r["identifier"])
            out.append(r)
    return out


def description(items: list[dict], page: str, series: str | None = None) -> str:
    parts = []
    if series:
        parts.append(f"<p>Slides of the lecture series <b>{series}</b> by Zlatko K. Minev "
                     f"({len(items)} decks).</p><ul>")
        for it in items:
            facts = ", ".join(str(x) for x in [it.get("venue"), it.get("year")] if x)
            parts.append(f"<li>{it['title']}" + (f" ({facts})" if facts else "") + "</li>")
        parts.append("</ul>")
    else:
        it = items[0]
        parts.append(f"<p>{it.get('summary') or it.get('description') or it['title']}</p>")
        if it.get("key_points"):
            parts.append("<ul>" + "".join(f"<li>{p}</li>" for p in it["key_points"]) + "</ul>")
    parts.append(f'<p>Part of <a href="{page}">Zlatko\'s Quantum Notebook</a>, Zlatko K. Minev\'s '
                 "archive of talks, lectures and notes. Reuse beyond the license (e.g. a reworked "
                 "slide in your own talk) is welcome on request.</p>")
    return "".join(parts)


def plan(catalog: list[dict]) -> list[dict]:
    """One unit per Zenodo record, with full deposition metadata and files."""
    items = [i for i in catalog if not i.get("version_of")]
    groups = {n: its for n, its in series_groups(items).items() if n != "Career & Outreach"}
    in_series = {i["id"] for its in groups.values() for i in its}
    units = []

    for name, its in sorted(groups.items()):
        its = sorted(its, key=lambda i: (i.get("year") or 0, i["title"]))
        years = [i["year"] for i in its if i.get("year")]
        names = []
        for i in its:
            names += [a for a in authors(i) if a not in names]
        page = f"{SITE_URL}series/{slug(name)}/"
        units.append({
            "id": f"series-{slug(name)}", "kind": "series", "series": name,
            "files": [i["file"] for i in its],
            "metadata": {
                "title": f"{name}: lecture slides",
                "upload_type": "lesson",
                "description": description(its, page, series=name),
                "creators": [creator(n) for n in names],
                "publication_date": f"{max(years)}-01-01" if years else None,
                "keywords": sorted({t for i in its for t in i.get("tags", [])}),
                "related_identifiers": related(its, page),
                "notes": "Years: " + ", ".join(str(y) for y in sorted(set(years))) if years else None,
            }})

    for it in items:
        if it["id"] in in_series:
            continue
        page = f"{SITE_URL}items/{it['id']}/"
        md = {
            "title": it["title"],
            "description": description([it], page),
            "creators": [creator(n) for n in authors(it)],
            "publication_date": f"{it['year']}-01-01" if it.get("year") else None,
            "keywords": sorted(it.get("tags", [])),
            "related_identifiers": related([it], page),
        }
        if it["category"] == "tech-note":
            md.update(upload_type="publication", publication_type="technicalnote",
                      title=f"{it['note_id']}: {it['title']}" if it.get("note_id") else it["title"])
        elif "poster" in (it.get("venue") or "").lower():
            md.update(upload_type="poster")
        else:
            md.update(upload_type="presentation")
        if it["category"] == "research-talk" and it.get("venue"):
            md["conference_title"] = it["venue"]
        units.append({"id": it["id"], "kind": "item", "key": it.get("key", it["id"]),
                      "files": [it["file"]], "metadata": md})

    for u in units:
        md = u["metadata"]
        md.update(access_right="open", license=LICENSE, language="eng")
        u["metadata"] = {k: v for k, v in md.items() if v}
    return units


# ---------- Zenodo REST API ----------

class Zenodo:
    def __init__(self, env: str):
        self.base = HOSTS[env]
        self.token = os.environ.get("ZENODO_SANDBOX_TOKEN" if env == "sandbox" else "ZENODO_TOKEN") \
            or os.environ.get("ZENODO_TOKEN")
        if not self.token:
            sys.exit("Set ZENODO_TOKEN (or ZENODO_SANDBOX_TOKEN for --sandbox).")

    def call(self, method: str, url: str, body=None, data=None, ctype="application/json"):
        if not url.startswith("http"):
            url = self.base + url
        headers = {"Authorization": f"Bearer {self.token}"}
        if body is not None:
            data = json.dumps(body).encode()
        if data is not None:
            headers["Content-Type"] = ctype
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            sys.exit(f"Zenodo {method} {url} → HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")
        except urllib.error.URLError as e:
            sys.exit(f"Can't reach {self.base} ({e.reason}). Is network access to Zenodo allowed?")

    def upload(self, bucket: str, path: Path) -> None:
        url = f"{bucket}/{urllib.parse.quote(path.name)}"
        with path.open("rb") as f:
            req = urllib.request.Request(url, data=f, method="PUT", headers={
                "Authorization": f"Bearer {self.token}", "Content-Type": "application/octet-stream",
                "Content-Length": str(path.stat().st_size)})
            try:
                urllib.request.urlopen(req, timeout=3600).read()
            except urllib.error.HTTPError as e:
                sys.exit(f"Upload {path.name} → HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {"production": {}, "sandbox": {}}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")


def select(units: list[dict], only: list[str] | None) -> list[dict]:
    if not only:
        return units
    return [u for u in units if any(u["id"] == o or u["id"].startswith(o) for o in only)]


def record_doi(unit: dict, doi: str) -> None:
    """Write the concept DOI where the site build reads it."""
    if unit["kind"] == "series":
        meta = json.loads(SERIES_META.read_text()) if SERIES_META.exists() else {}
        meta.setdefault(unit["series"], {})["doi"] = doi
        SERIES_META.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    else:
        ov = json.loads(OVERRIDES.read_text())
        ov.setdefault(unit["key"], {})["doi"] = doi
        OVERRIDES.write_text(json.dumps(ov, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["plan", "create", "publish", "status"])
    ap.add_argument("--sandbox", action="store_true", help="use sandbox.zenodo.org")
    ap.add_argument("--only", nargs="*", help="unit ids or prefixes")
    ap.add_argument("--json", help="plan: write full metadata to this file")
    args = ap.parse_args()

    units = select(plan(json.loads(CATALOG.read_text())["items"]), args.only)
    env = "sandbox" if args.sandbox else "production"
    state = load_state()
    st = state.setdefault(env, {})

    if args.command == "plan":
        for u in units:
            size = sum((REPO_ROOT / f).stat().st_size for f in u["files"]) / 1e6
            flag = "" if "publication_date" in u["metadata"] else "   (needs a year)"
            print(f"{u['metadata']['upload_type']:<12} {len(u['files']):>2} file(s) {size:6.1f} MB  {u['id']}{flag}"
                  + (f"   [{st[u['id']].get('doi') or 'draft'}]" if u["id"] in st else ""))
        print(f"\n{len(units)} unit(s). Nothing was sent.")
        if args.json:
            Path(args.json).write_text(json.dumps(units, indent=1, ensure_ascii=False))
            print(f"Metadata written to {args.json}")
        return 0

    if args.command == "status":
        for uid, s in sorted(st.items()):
            print(f"{s.get('doi') or 'draft':<28} {uid}  {s.get('html', '')}")
        return 0

    z = Zenodo(env)
    for u in units:
        s = st.get(u["id"], {})
        if args.command == "create":
            if s.get("id"):
                print(f"skip (exists)  {u['id']}")
                continue
            if "publication_date" not in u["metadata"]:
                print(f"skip (no year: set \"year\" in tools/catalog_overrides.json)  {u['id']}")
                continue
            dep = z.call("POST", "/api/deposit/depositions", body={})
            for f in u["files"]:
                z.upload(dep["links"]["bucket"], REPO_ROOT / f)
            dep = z.call("PUT", f"/api/deposit/depositions/{dep['id']}", body={"metadata": u["metadata"]})
            st[u["id"]] = {"id": dep["id"], "html": dep["links"].get("html"), "doi": None}
            save_state(state)
            print(f"draft created  {u['id']}  {dep['links'].get('html')}")
        elif args.command == "publish":
            if not s.get("id"):
                print(f"skip (no draft; run create first)  {u['id']}")
                continue
            if s.get("doi"):
                print(f"skip (published {s['doi']})  {u['id']}")
                continue
            dep = z.call("POST", f"/api/deposit/depositions/{s['id']}/actions/publish")
            concept = dep.get("conceptdoi") or dep.get("doi")
            s.update(doi=concept, version_doi=dep.get("doi"), html=dep["links"].get("html"))
            save_state(state)
            if env == "production":
                record_doi(u, concept)
            print(f"published {concept}  {u['id']}")
    if args.command == "publish" and env == "production":
        print("\nDOIs written to tools/catalog_overrides.json / tools/series.json. Next: "
              "python3 tools/build_catalog.py && python3 tools/build_site.py, then commit "
              "tools/zenodo.json and the updated files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
