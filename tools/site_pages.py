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
import re
from urllib.parse import quote

SITE_NAME = "The Quantum Notebook"
AUTHOR = "Zlatko K. Minev"
SHELF_NAME = {"lectures": "Lectures & Tutorials", "research": "Research Talks",
              "notes": "Tech Notes"}
STOP = {"a", "an", "the", "to", "of", "and", "for", "in", "on", "intro"}


def authors(item: dict) -> list[str]:
    """Speaker field ("Minev", "Haoran Liao", "Minev, Thomas G. McConkey") → full names."""
    names = [s.strip() for s in (item.get("speaker") or "Minev").split(",") if s.strip()]
    return [AUTHOR if n == "Minev" else n for n in names] or [AUTHOR]


def pdf_href(item: dict, pdf_base: str) -> str:
    return pdf_base + "/".join(quote(p) for p in item["file"].split("/"))


def kind(item: dict) -> str:
    if item["category"] == "tech-note":
        return "Technical note"
    if item["category"] == "research-talk":
        return "Talk"
    if "tutorial" in item.get("tags", []):
        return "Tutorial"
    return "Lecture"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _words(text: str, n: int) -> str:
    return "".join([w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP][:n])


def _bib_escape(s: str) -> str:
    return re.sub(r"([&%$#_])", r"\\\1", s)


def _entry(key: str, fields: list[tuple[str, str | None]]) -> str:
    body = ",\n".join(f"  {k} = {{{v if k == 'url' else _bib_escape(v)}}}" for k, v in fields if v)
    return f"@misc{{{key},\n{body}\n}}"


# ---------- series ----------

def series_groups(items: list[dict]) -> dict[str, list[dict]]:
    """Series name → its items, for series with at least two items."""
    groups: dict[str, list[dict]] = {}
    for it in items:
        if it.get("series"):
            groups.setdefault(it["series"], []).append(it)
    return {s: its for s, its in groups.items() if len(its) > 1}


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
        ("url", s["url"]),
        ("note", f"Slides, {len(s['items'])} decks" + (f", {span}" if span and "--" in span else "")),
    ])


# ---------- single items ----------

def item_key_base(item: dict) -> str:
    last = re.sub(r"[^a-z]", "", authors(item)[0].split()[-1].lower())
    tail = re.sub(r"[^a-z0-9]", "", item["note_id"].lower()) if item.get("note_id") else _words(item["title"], 2)
    return f"{last}{item.get('year') or 'nd'}{tail}"


def item_bibtex(item: dict, site_url: str, key: str) -> str:
    how = f"Technical note {item['note_id']}" if item.get("note_id") else kind(item)
    if item.get("venue"):
        how += f", {item['venue']}"
    return _entry(key, [
        ("author", " and ".join(authors(item))),
        ("title", "{" + item["title"] + "}"),
        ("howpublished", how),
        ("year", str(item["year"]) if item.get("year") else None),
        ("url", f"{site_url}items/{item['id']}/"),
        ("note", "Slides" if item["category"] != "tech-note" else None),
    ])


def assign_citations(items: list[dict], site_url: str) -> tuple[list[dict], list[str]]:
    """Attach ``bibtex`` (and ``series_page`` for series members) to every item.

    Returns (series infos, all BibTeX entries). Keys are unique: collisions get
    a/b/c suffixes in a stable order.
    """
    groups = series_groups(items)
    series = [series_info(n, its, site_url) for n, its in groups.items()]
    in_series = {i["id"] for s in series for i in s["items"]}

    bases: dict[str, list[tuple[str, str]]] = {}   # base key → [(sort id, owner)]
    for s in series:
        last = re.sub(r"[^a-z]", "", s["authors"][0].split()[-1].lower())
        base = f"{last}{s['years'][-1] if s['years'] else 'nd'}{_words(s['name'], 3)}"
        bases.setdefault(base, []).append(("s:" + s["slug"], "s:" + s["slug"]))
    for it in items:
        if it["id"] not in in_series:
            bases.setdefault(item_key_base(it), []).append((it["id"], it["id"]))
    keys = {}
    for base, owners in bases.items():
        for n, (_, owner) in enumerate(sorted(owners)):
            keys[owner] = base if len(owners) == 1 else base + "abcdefghijklmnopqrstuvwxyz"[n]

    entries = []
    for s in series:
        s["bibtex"] = series_bibtex(s, keys["s:" + s["slug"]])
        entries.append(s["bibtex"])
        for it in s["items"]:
            it["bibtex"] = s["bibtex"]
            it["series_page"] = f"series/{s['slug']}/"
    for it in items:
        if it["id"] not in in_series:
            it["bibtex"] = item_bibtex(it, site_url, keys[it["id"]])
            entries.append(it["bibtex"])
    return series, entries


# ---------- pages ----------

def _e(s) -> str:
    return html.escape(str(s or ""), quote=True)


PERMISSIONS_HTML = (
    "<p>These slides and notes are © Zlatko K. Minev and shared under "
    "<a href=\"https://creativecommons.org/licenses/by-nc-nd/4.0/\">CC BY-NC-ND 4.0</a>: "
    "read them, download them, share them with credit. Want to reuse a slide or figure "
    "in your own talk, course or paper? Just ask. The answer is usually yes. "
    "Some slides include figures by other people, credited where they appear; those "
    "stay with their owners, so please ask the original source.</p>")

_FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
          '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
          '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,500;0,7..72,650;1,7..72,500&family=Public+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">')

_COPY_JS = """<script>
document.getElementById("copy-bib").onclick = async (e) => {
  const t = document.getElementById("bib").textContent;
  try { await navigator.clipboard.writeText(t); e.target.textContent = "Copied"; }
  catch { const r = document.createRange(); r.selectNodeContents(document.getElementById("bib")); getSelection().removeAllRanges(); getSelection().addRange(r); }
};
</script>"""


def _links_html(item: dict) -> str:
    return "".join(f'<a class="btn" href="{_e(l["url"])}">{_e(l["label"])}</a>'
                   for l in item.get("links") or [])


def _page(title: str, desc: str, url: str, thumb: str, meta: list, back: str, body: str) -> str:
    meta_html = "\n".join(f'<meta name="{k}" content="{_e(v)}">' for k, v in meta if v)
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
{f'<meta property="og:image" content="{_e(thumb)}">' if thumb else ''}
{meta_html}
{_FONTS}
<link rel="stylesheet" href="../../style.css">
</head>
<body class="item-page">
<nav class="topbar wrap" aria-label="Site">
  <a class="me" href="../../"><span class="mono-mark" aria-hidden="true">|ψ⟩</span>{SITE_NAME}</a>
  <div class="toplinks"><a href="{_e(back)}">Browse everything</a></div>
</nav>
<main class="wrap ip">
{body}
</main>
{_COPY_JS}
</body>
</html>
"""


def _cite_block(bib: str, note: str = "") -> str:
    return (f'<h2 class="ip-h">Cite</h2>{note}<pre class="bib" id="bib">{_e(bib)}</pre>'
            '<button class="btn" type="button" id="copy-bib">Copy BibTeX</button>'
            f'<h2 class="ip-h">Reuse</h2><div class="ip-perm">{PERMISSIONS_HTML}</div>')


def item_page(item: dict, site_url: str, pdf_base_abs: str) -> str:
    url = f"{site_url}items/{item['id']}/"
    pdf = pdf_href(item, pdf_base_abs)
    thumb = f"{site_url}{item['thumb']}" if item.get("thumb") else ""
    desc = item.get("description") or item["title"]
    meta = [
        ("citation_title", item["title"]),
        *[("citation_author", a) for a in authors(item)],
        ("citation_publication_date", item.get("year")),
        ("citation_pdf_url", pdf),
        ("citation_abstract_html_url", url),
        ("citation_technical_report_number", item.get("note_id")),
        ("citation_conference_title", item.get("venue") if item["category"] != "tech-note" else None),
        ("citation_language", "en"),
    ]
    facts = " · ".join(_e(x) for x in [item.get("note_id") or kind(item), item.get("year") or "undated",
                                        item.get("venue"), item.get("pages") and f"{item['pages']} pages"] if x)
    points = "".join(f"<li>{_e(p)}</li>" for p in item.get("key_points") or [])
    draft = (' <span class="draft" title="Machine-written from the slides; not yet reviewed by the author">draft</span>'
             if item.get("draft") else "")
    series_note = ""
    if item.get("series_page"):
        series_note = (f'<p class="ip-note">Part of <a href="../../{_e(item["series_page"])}">{_e(item["series"])}</a>; '
                       "cite the series as a whole.</p>")
    elif item.get("series"):
        series_note = f'<p class="ip-note">Series: {_e(item["series"])}</p>'
    thumb_html = (f'<a class="ip-thumb" href="{_e(pdf)}"><img src="../../{_e(item["thumb"])}" '
                  f'alt="First page of {_e(item["title"])}"></a>' if item.get("thumb") else "")
    body = f"""  <p class="eyebrow">{_e(SHELF_NAME.get(item.get('shelf'), ''))}</p>
  <h1 class="ip-title">{_e(item['title'])}</h1>
  <p class="ip-authors">{_e(', '.join(authors(item)))}</p>
  <p class="d-meta">{facts}</p>
  <div class="ip-grid">
    <div class="ip-body">
      <div class="d-actions"><a class="btn primary" href="{_e(pdf)}">Open PDF</a>{_links_html(item)}</div>
      {series_note}
      <p class="d-summary">{_e(item.get('summary') or desc)}{draft}</p>
      {f'<ul class="d-points">{points}</ul>' if points else ''}
      {_cite_block(item['bibtex'])}
    </div>
    {thumb_html}
  </div>"""
    return _page(f"{item['title']} · {', '.join(authors(item))}", desc, url, thumb, meta,
                 f"../../#{item['id']}", body)


def series_page(s: dict, site_url: str) -> str:
    extra = {"reference", "cheat-sheet", "derivation"}   # bonus material after the lectures
    its = sorted(s["items"], key=lambda i: (bool(extra & set(i.get("tags", []))) or "(bonus)" in i["title"]
                                              or "(note)" in i["title"], -(i.get("year") or 0), i["title"]))
    span = (f"{s['years'][0]}–{s['years'][-1]}" if len(s["years"]) > 1
            else (str(s["years"][0]) if s["years"] else "undated"))
    desc = f"{s['name']}: {len(its)} decks ({span}) by {', '.join(s['authors'])}."
    meta = [("citation_title", s["name"]), *[("citation_author", a) for a in s["authors"]],
            ("citation_publication_date", s["years"][-1] if s["years"] else None),
            ("citation_abstract_html_url", s["url"]), ("citation_language", "en")]
    rows = ""
    for i in its:
        facts = " · ".join(str(x) for x in [i.get("year") or "undated", i.get("venue"),
                                            i.get("pages") and f"{i['pages']} pp"] if x)
        rows += (f'<li><a href="../../items/{_e(i["id"])}/">{_e(i["title"])}</a>'
                 f'<span class="ip-row-meta">{_e(facts)}</span>'
                 + (f'<span>{_e(i["description"])}</span>' if i.get("description") else "") + "</li>")
    thumb = next((f"{site_url}{i['thumb']}" for i in its if i.get("thumb")), "")
    body = f"""  <p class="eyebrow">Series · {len(its)} decks · {_e(span)}</p>
  <h1 class="ip-title">{_e(s['name'])}</h1>
  <p class="ip-authors">{_e(', '.join(s['authors']))}</p>
  <div class="ip-grid">
    <div class="ip-body">
      <ol class="ip-list">{rows}</ol>
      {_cite_block(s['bibtex'])}
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


def robots(site_url: str) -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {site_url}sitemap.xml\n"
