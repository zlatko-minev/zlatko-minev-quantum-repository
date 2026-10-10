"""
site_pages.py — Citation support for the website, used by build_site.py.

* One BibTeX entry per **series** (every series with 2+ decks, e.g. a summer
  school's lectures) and one per standalone deck or note.
* ``item_page`` — a static page per item at ``items/<id>/``; ``series_page`` —
  one per series at ``series/<slug>/``. Both carry Google Scholar (Highwire
  Press ``citation_*``) and Open Graph meta tags plus the BibTeX.
* ``sitemap`` / ``robots`` — so crawlers find every page.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import quote

SITE_NAME = "Zlatko's Quantum Notebook"
# Per-series metadata that has no single deck to live on, e.g. the Zenodo DOI
# of a whole lecture series: {"<series name>": {"doi": "10.5281/zenodo.N"}}.
SERIES_META_PATH = Path(__file__).resolve().parent / "series.json"
AUTHOR = "Zlatko K. Minev"
SHELF_NAME = {"lectures": "Lectures & Tutorials", "research": "Research Talks",
              "notes": "Tech Notes"}
STOP = {"a", "an", "the", "to", "of", "and", "for", "in", "on", "intro"}


def authors(item: dict) -> list[str]:
    """Author list: the ``authors`` override (e.g. a co-authored poster), else the
    speaker field ("Minev", "Haoran Liao", "Thomas G. McConkey, Minev")."""
    raw = item.get("authors") or item.get("speaker") or "Minev"
    names = [s.strip() for s in raw.split(",") if s.strip()]
    return [AUTHOR if n == "Minev" else n for n in names] or [AUTHOR]


def pdf_href(item: dict, pdf_base: str) -> str:
    return pdf_base + "/".join(quote(p) for p in item["file"].split("/"))


def kind(item: dict) -> str:
    """Display label; matches kindLabel() in site/app.js."""
    if item["category"] == "tech-note":
        return "Tech note"
    if item["category"] == "research-talk":
        return "Research talk"
    if "tutorial" in item.get("tags", []):
        return "Tutorial"
    if "career" in item.get("tags", []):
        return "Career talk"
    return "Lecture"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _words(text: str, n: int) -> str:
    return "".join([w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP][:n])


def _bib_escape(s: str) -> str:
    return re.sub(r"([&%$#_])", r"\\\1", s)


def _entry(key: str, fields: list[tuple[str, str | None]], kind: str = "misc") -> str:
    body = ",\n".join(f"  {k} = {{{v if k in ('url', 'doi') else _bib_escape(v)}}}" for k, v in fields if v)
    return f"@{kind}{{{key},\n{body}\n}}"


# ---------- series ----------

# Groupings that are not one lecture series; their decks are cited individually.
NOT_CITED_AS_SERIES = {"Career & Outreach"}


def series_groups(items: list[dict]) -> dict[str, list[dict]]:
    """Series name → its items, for series with at least two items."""
    groups: dict[str, list[dict]] = {}
    for it in items:
        if it.get("series"):
            groups.setdefault(it["series"], []).append(it)
    return {s: its for s, its in groups.items() if len(its) > 1}


def _series_meta() -> dict:
    return json.loads(SERIES_META_PATH.read_text()) if SERIES_META_PATH.exists() else {}


def _common(its: list[dict], field: str) -> str | None:
    vals = {i.get(field) for i in its}
    return vals.pop() if len(vals) == 1 else None


def series_info(name: str, its: list[dict], site_url: str) -> dict:
    years = sorted({i["year"] for i in its if i.get("year")})
    names: list[str] = []
    for i in its:
        names += [a for a in authors(i) if a not in names]
    return {
        "name": name,
        "slug": slug(name),
        "items": its,
        "years": years,
        "authors": names,
        "venue": _common(its, "venue"),
        "url": f"{site_url}series/{slug(name)}/",
        # Every real series is cited as ONE work, including a lecture given at
        # several venues over the years: the versions are near-identical, and
        # one record gathers citations (and suits a Zenodo concept DOI). Only
        # groupings that are not a series are cited deck by deck.
        "citable": name not in NOT_CITED_AS_SERIES,
        "doi": _series_meta().get(name, {}).get("doi"),
        "venues": sorted({i["venue"] for i in its if i.get("venue")}),
    }


def series_bibtex(s: dict, key: str) -> str:
    span = (f"{s['years'][0]}--{s['years'][-1]}" if len(s["years"]) > 1
            else (str(s["years"][0]) if s["years"] else None))
    how = "Lecture series" + (f", {s['venue']}" if s["venue"] else "")
    return _entry(key, [
        ("author", " and ".join(s["authors"])),
        ("title", "{" + s["name"] + "}"),
        ("howpublished", how),
        ("year", str(s["years"][-1]) if s["years"] else None),
        ("doi", s.get("doi")),
        ("url", s["url"]),
        ("note", f"Slides, {len(s['items'])} decks" + (f", {span}" if span and "--" in span else "")
                 + (f"; given at {'; '.join(s['venues'])}" if len(s["venues"]) > 1 else "")),
    ])


# ---------- single items ----------

def item_key_base(item: dict) -> str:
    last = re.sub(r"[^a-z]", "", authors(item)[0].split()[-1].lower())
    tail = re.sub(r"[^a-z0-9]", "", item["note_id"].lower()) if item.get("note_id") else _words(item["title"], 2)
    return f"{last}{item.get('year') or 'nd'}{tail}"


def item_bibtex(item: dict, site_url: str, key: str) -> str:
    url = f"{site_url}items/{item['id']}/"
    if item["category"] == "tech-note":
        # Renders as "Technical Note T21 (The Quantum Notebook, 2022)" in APS/IEEE styles.
        return _entry(key, [
            ("author", " and ".join(authors(item))),
            ("title", "{" + item["title"] + "}"),
            ("type", "Technical Note"),
            ("number", item.get("note_id")),
            ("institution", SITE_NAME),
            ("year", str(item["year"]) if item.get("year") else None),
            ("doi", item.get("doi")),
            ("url", url),
        ], "techreport")
    how = {"Research talk": "Talk", "Career talk": "Talk"}.get(kind(item), kind(item))
    if item.get("venue"):
        how += f", {item['venue']}"
    return _entry(key, [
        ("author", " and ".join(authors(item))),
        ("title", "{" + item["title"] + "}"),
        ("howpublished", how),
        ("year", str(item["year"]) if item.get("year") else None),
        ("doi", item.get("doi")),
        ("url", url),
        ("note", "Slides"),
    ])


def assign_citations(items: list[dict], site_url: str,
                     locked: dict[str, str] | None = None) -> tuple[list[dict], list[str], dict[str, str]]:
    """Attach ``bibtex`` (plus ``series_page`` / ``canonical_page``) to every item.

    * Citable series (one event) get one entry that their decks share; other
      decks get their own entry.
    * An item with ``version_of`` (e.g. a cheat sheet handed out at a summer
      school that is also a tech note) shares the original's entry and page.
    * Keys are frozen: ``locked`` (tools/bibkeys.json) maps owner → key, and
      only new owners get new keys (collisions get a/b/c suffixes). Returns
      (series infos, entries, updated key map).
    """
    locked = dict(locked or {})
    by_id = {it["id"]: it for it in items}
    groups = series_groups(items)
    series = [series_info(n, its, site_url) for n, its in groups.items()]
    for s in series:
        for it in s["items"]:
            it["series_page"] = f"series/{s['slug']}/"
    cited_by_series = {i["id"] for s in series if s["citable"] for i in s["items"]}

    owners: list[tuple[str, str]] = []   # (owner, base key)
    for s in series:
        if s["citable"]:
            last = re.sub(r"[^a-z]", "", s["authors"][0].split()[-1].lower())
            owners.append(("s:" + s["slug"], f"{last}{s['years'][-1] if s['years'] else 'nd'}{_words(s['name'], 3)}"))
    for it in items:
        if it["id"] not in cited_by_series and not it.get("version_of"):
            owners.append((it["id"], item_key_base(it)))
    keys = {o: locked[o] for o, _ in owners if o in locked}
    used = set(keys.values())
    for o, base in sorted(owners):
        if o in keys:
            continue
        key, n = base, 0
        while key in used:
            key = base + "abcdefghijklmnopqrstuvwxyz"[n]
            n += 1
        keys[o] = key
        used.add(key)

    entries = []
    for s in series:
        if s["citable"]:
            s["bibtex"] = series_bibtex(s, keys["s:" + s["slug"]])
            entries.append(s["bibtex"])
            for it in s["items"]:
                it["bibtex"] = s["bibtex"]
                it["cited_as_series"] = True
                if s.get("doi"):
                    it["series_doi"] = s["doi"]
    for it in items:
        if it["id"] in keys:
            it["bibtex"] = item_bibtex(it, site_url, keys[it["id"]])
            entries.append(it["bibtex"])
    for it in items:
        orig = by_id.get(it.get("version_of") or "")
        if orig:
            it["bibtex"] = orig["bibtex"]
            it["canonical_page"] = f"items/{orig['id']}/"
            it["cited_as_series"] = False
    locked.update(keys)
    return series, entries, locked


# ---------- pages ----------

def _e(s) -> str:
    return html.escape(str(s or ""), quote=True)


LICENSE_URL = "https://creativecommons.org/licenses/by-nc-nd/4.0/"
# Keep in sync with the "Cite & reuse" section of site/index.html and README.md.
PERMISSIONS_HTML = (
    "<p>Unless a deck says otherwise, the slides and notes here are © Zlatko K. Minev and "
    f"shared under <a href=\"{LICENSE_URL}\">CC BY-NC-ND 4.0</a>: you're welcome to read, "
    "download and share them, unchanged and non-commercially, with credit and a link back. "
    "Commercial use or a reworked slide or figure in your own talk, course or paper needs "
    "permission; please ask, the answer is usually yes. If you use something in teaching or a "
    "publication, I'd love a short note telling me where.</p><p>Some slides include figures, "
    "photos, logos or excerpts from other people and institutions, credited where they appear. "
    "Those aren't mine to license, so please ask the original source. Spotted a missing credit? "
    "<a href=\"https://zlatko-minev.com\">Tell me</a> and I'll fix it.</p>")
DRAFT_NOTE = ("Summary and key points drafted by a language model from the slides, not yet "
              "reviewed by me. The slides are the source.")

# Applies a stored light/dark choice before first paint (site/theme.js does the toggling).
THEME_BOOT = ('document.documentElement.classList.add("js");try{var t=localStorage.getItem("theme");'
              'if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}')

_ICONS = ('<link rel="icon" href="../../favicon.svg" type="image/svg+xml">\n<link rel="icon" href="../../favicon-32.png" sizes="32x32" type="image/png">\n<link rel="apple-touch-icon" href="../../apple-touch-icon.png">')
_FONTS = f'<script>{THEME_BOOT}</script>\n{_ICONS}\n<link rel="preload" href="../../fonts/literata-latin-opsz-normal.woff2" as="font" type="font/woff2" crossorigin>'

_COPY_JS = """<script>
document.getElementById("copy-bib").onclick = async (e) => {
  const t = document.getElementById("bib").textContent;
  try { await navigator.clipboard.writeText(t); e.target.textContent = "Copied"; }
  catch { const r = document.createRange(); r.selectNodeContents(document.getElementById("bib")); getSelection().removeAllRanges(); getSelection().addRange(r); e.target.textContent = "Selected, press Ctrl/⌘-C"; }
  setTimeout(() => { e.target.textContent = "Copy BibTeX"; }, 2500);
};
</script>"""


def _wh(item: dict) -> str:
    wh = item.get("thumb_wh")
    return f' width="{wh[0]}" height="{wh[1]}"' if wh else ""


def _links_html(item: dict) -> str:
    doi = item.get("doi")
    return (f'<a class="btn" href="https://doi.org/{_e(doi)}">DOI {_e(doi)}</a>' if doi else "") + "".join(f'<a class="btn" href="{_e(l["url"])}">{_e(l["label"])}</a>'
                   for l in item.get("links") or [])


def _page(title: str, desc: str, url: str, thumb: str, meta: list, back: str, body: str,
          jsonld: dict | None = None) -> str:
    meta_html = "\n".join(f'<meta name="{k}" content="{_e(v)}">' for k, v in meta if v)
    if jsonld:
        meta_html += ('\n<script type="application/ld+json">'
                      + json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{_e(title)}</title>
<meta name="description" content="{_e(desc)}">
<link rel="canonical" href="{_e(url)}">
<meta property="og:title" content="{_e(title)}">
<meta property="og:description" content="{_e(desc)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{_e(url)}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta name="twitter:card" content="{'summary_large_image' if thumb else 'summary'}">
{f'<meta property="og:image" content="{_e(thumb)}">' if thumb else ''}
{meta_html}
{_FONTS}
<link rel="stylesheet" href="../../style.css">
</head>
<body class="item-page">
<nav class="topbar" aria-label="Site"><div class="wrap topbar-inner">
  <a class="me" href="../../"><svg class="mark" viewBox="0 0 64 64" aria-hidden="true"><rect class="mk-t" width="64" height="64" rx="15"/><path class="mk-d" d="M30 44h24M10 20h14"/><path class="mk-l" d="M10 44h14M40 20h14"/><path class="mk-a" d="M24 44C34 44 30 20 40 20"/></svg>{SITE_NAME}</a>
  <div class="toplinks"><a href="{_e(back)}">Browse everything</a><button class="theme-btn" type="button" data-theme-toggle aria-label="Switch colour theme"></button></div>
</div></nav>
<main class="wrap ip">
{body}
</main>
{_COPY_JS}
<script src="../../theme.js"></script>
</body>
</html>
"""


def _cite_block(bib: str, note: str = "") -> str:
    return (f'<h2 class="ip-h">Cite</h2>{note}<pre class="bib" id="bib">{_e(bib)}</pre>'
            '<button class="btn" type="button" id="copy-bib">Copy BibTeX</button>'
            f'<h2 class="ip-h">Reuse</h2><div class="ip-perm">{PERMISSIONS_HTML}</div>')


def item_page(item: dict, site_url: str, pdf_base_abs: str) -> str:
    url = f"{site_url}{item.get('canonical_page') or 'items/' + item['id'] + '/'}"
    pdf = pdf_href(item, pdf_base_abs)
    thumb = f"{site_url}{item['thumb']}" if item.get("thumb") else ""
    desc = item.get("description") or item["title"]
    # A copy of another item (version_of) carries no Scholar tags: the
    # original's page is the one to index and cite.
    meta = [] if item.get("canonical_page") else [
        ("citation_title", item["title"]),
        *[("citation_author", a) for a in authors(item)],
        ("citation_publication_date", item.get("year")),
        # Scholar only accepts a PDF on the same site as the page.
        ("citation_pdf_url", pdf if pdf.startswith(site_url) else None),
        ("citation_abstract_html_url", url),
        ("citation_technical_report_number", item.get("note_id")),
        ("citation_technical_report_institution", SITE_NAME if item.get("note_id") else None),
        ("citation_doi", item.get("doi")),
        ("citation_language", "en"),
    ]
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Report" if item["category"] == "tech-note" else "PresentationDigitalDocument",
        "name": item["title"], "url": url, "description": desc,
        "author": [{"@type": "Person", "name": a} for a in authors(item)],
        "datePublished": str(item["year"]) if item.get("year") else None,
        "inLanguage": "en", "license": LICENSE_URL,
        "encoding": {"@type": "MediaObject", "contentUrl": pdf, "encodingFormat": "application/pdf"},
        "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": site_url},
        "identifier": f"https://doi.org/{item['doi']}" if item.get("doi") else None,
    }
    jsonld = {k: v for k, v in jsonld.items() if v}
    facts = " · ".join(_e(x) for x in [item.get("note_id") or kind(item), item.get("year") or "undated",
                                        item.get("venue"), item.get("pages") and f"{item['pages']} pages"] if x)
    points = "".join(f"<li>{_e(p)}</li>" for p in item.get("key_points") or [])
    draft = f'<p class="draft-note">{DRAFT_NOTE}</p>' if item.get("draft") else ""
    series_note = ""
    if item.get("series_page"):
        how = ("; cited as one entry below" if item.get("cited_as_series")
               else "" if item.get("canonical_page") else "; each deck is cited on its own")
        series_note = (f'<p class="ip-note">Part of the series <a href="../../{_e(item["series_page"])}">'
                       f'{_e(item["series"])}</a>{how}.</p>')
    elif item.get("series"):
        series_note = f'<p class="ip-note">Series: {_e(item["series"])}</p>'
    if item.get("canonical_page"):
        series_note += (f'<p class="ip-note">Also published as <a href="../../{_e(item["canonical_page"])}">'
                        "a tech note</a>; please cite that.</p>")
    thumb_html = (f'<a class="ip-thumb" href="{_e(pdf)}"><img src="../../{_e(item["thumb"])}" '
                  f'alt="First page of {_e(item["title"])}"{_wh(item)}></a>' if item.get("thumb") else "")
    body = f"""  <p class="eyebrow">{_e(SHELF_NAME.get(item.get('shelf'), ''))}</p>
  <h1 class="ip-title">{_e(item['title'])}</h1>
  <p class="ip-authors">{_e(', '.join(authors(item)))}</p>
  <p class="d-meta">{facts}</p>
  <div class="ip-grid">
    <div class="ip-body">
      <div class="d-actions"><a class="btn primary" href="{_e(pdf)}">Open PDF</a>{_links_html(item)}</div>
      {series_note}
      <p class="d-summary">{_e(item.get('summary') or desc)}</p>
      {f'<ul class="d-points">{points}</ul>' if points else ''}
      {draft}
      {_cite_block(item['bibtex'])}
    </div>
    {thumb_html}
  </div>"""
    return _page(f"{item['title']} · {', '.join(authors(item))}", desc, url, thumb, meta,
                 f"../../#{item['id']}", body, jsonld)


def series_page(s: dict, site_url: str) -> str:
    extra = {"reference", "cheat-sheet", "derivation"}   # bonus material after the lectures
    its = sorted(s["items"], key=lambda i: (bool(extra & set(i.get("tags", []))) or "(bonus)" in i["title"]
                                              or "(note)" in i["title"], -(i.get("year") or 0), i["title"]))
    span = (f"{s['years'][0]}–{s['years'][-1]}" if len(s["years"]) > 1
            else (str(s["years"][0]) if s["years"] else "undated"))
    desc = f"{s['name']}: {len(its)} decks ({span}) by {', '.join(s['authors'])}."
    meta = []   # no citation_* tags: a series page has no PDF of its own
    rows = ""
    for i in its:
        facts = " · ".join(str(x) for x in [i.get("year") or "undated", i.get("venue"),
                                            i.get("pages") and f"{i['pages']} pp"] if x)
        thumb_i = (f'<a class="ip-row-thumb" href="../../items/{_e(i["id"])}/" tabindex="-1" aria-hidden="true">'
                   f'<img src="../../{_e(i["thumb"])}" alt="" loading="lazy"{_wh(i)}></a>') if i.get("thumb") else ""
        rows += (f'<li>{thumb_i}<a href="../../items/{_e(i["id"])}/">{_e(i["title"])}</a>'
                 f'<span class="ip-row-meta">{_e(facts)}</span>'
                 + (f'<span>{_e(i["description"])}</span>' if i.get("description") else "") + "</li>")
    thumb = next((f"{site_url}{i['thumb']}" for i in its if i.get("thumb")), "")
    body = f"""  <p class="eyebrow">Series · {len(its)} decks · {_e(span)}</p>
  <h1 class="ip-title">{_e(s['name'])}</h1>
  <p class="ip-authors">{_e(', '.join(s['authors']))}</p>
  <div class="ip-grid ip-grid-single">
    <div class="ip-body">
      <ol class="ip-list">{rows}</ol>
      {_cite_block(s['bibtex']) if s.get('bibtex') else '<h2 class="ip-h">Cite</h2><p class="ip-note">These decks were given at different events, so each is cited on its own: open a deck for its BibTeX.</p><h2 class="ip-h">Reuse</h2><div class="ip-perm">' + PERMISSIONS_HTML + '</div>'}
    </div>
  </div>"""
    return _page(f"{s['name']} · {SITE_NAME}", desc, s["url"], thumb, meta, "../../", body)


def sitemap(items: list[dict], series: list[dict], site_url: str) -> str:
    urls = ([site_url] + [f"{site_url}items/{i['id']}/" for i in items]
            + [s["url"] for s in series])
    body = "\n".join(f"  <url><loc>{html.escape(u)}</loc></url>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}\n</urlset>\n")


def atom_feed(items: list[dict], site_url: str, limit: int = 40) -> str:
    """Atom feed, newest first by ``added`` date (else year). Dates come from
    the data, never the clock, so builds stay deterministic."""
    def when(i: dict) -> str:
        return i.get("added") or (f"{i['year']}-01-01" if i.get("year") else "2011-01-01")
    its = sorted((i for i in items if not i.get("version_of")), key=lambda i: (when(i), i["id"]), reverse=True)[:limit]
    updated = when(its[0]) if its else "2011-01-01"
    entries = "".join(
        f"""  <entry>
    <title>{_e(i['title'])}</title>
    <id>{_e(site_url)}items/{_e(i['id'])}/</id>
    <link href="{_e(site_url)}items/{_e(i['id'])}/"/>
    <updated>{when(i)}T00:00:00Z</updated>
    {''.join(f'<author><name>{_e(a)}</name></author>' for a in authors(i))}
    <summary>{_e(i.get('description') or i['title'])}</summary>
  </entry>
""" for i in its)
    return ('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n'
            f"  <title>{SITE_NAME}</title>\n  <subtitle>New talks, lectures and notes by Zlatko K. Minev</subtitle>\n"
            f'  <link href="{_e(site_url)}"/>\n  <link rel="self" href="{_e(site_url)}feed.xml"/>\n'
            f"  <id>{_e(site_url)}</id>\n  <updated>{updated}T00:00:00Z</updated>\n{entries}</feed>\n")


def robots(site_url: str) -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {site_url}sitemap.xml\n"
