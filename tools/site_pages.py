"""
site_pages.py — Citation support for the website, used by build_site.py.

* ``bibtex(item, site_url)`` — a BibTeX entry per deck or note.
* ``item_page(...)`` — a static landing page per item at ``items/<id>/``, with
  Google Scholar (Highwire Press ``citation_*``) and Open Graph meta tags, the
  summary, a PDF link and the BibTeX. Search engines and Scholar index these;
  the single-page browser stays the main way to explore.
* ``sitemap(...)`` / ``ROBOTS`` — so crawlers find every item page.
"""
from __future__ import annotations

import html
import re
from urllib.parse import quote

AUTHOR = "Zlatko K. Minev"
SHELF_NAME = {"lectures": "Lectures & Tutorials", "research": "Research Talks",
              "notes": "Tech Notes"}


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


def _bib_escape(s: str) -> str:
    return re.sub(r"([&%$#_])", r"\\\1", s)


def bib_key(item: dict) -> str:
    last = re.sub(r"[^a-z]", "", authors(item)[0].split()[-1].lower())
    if item.get("note_id"):
        tail = re.sub(r"[^a-z0-9]", "", item["note_id"].lower())
    else:
        words = [w for w in re.findall(r"[a-z0-9]+", item["title"].lower())
                 if w not in {"a", "an", "the", "to", "of", "and", "for", "in", "on", "intro"}]
        tail = "".join(words[:2])
    return f"{last}{item.get('year') or 'nd'}{tail}"


def unique_keys(items: list[dict]) -> dict[str, str]:
    """id → BibTeX key; colliding keys get a/b/c suffixes in id order (stable)."""
    groups: dict[str, list[str]] = {}
    for it in items:
        groups.setdefault(bib_key(it), []).append(it["id"])
    out = {}
    for key, ids in groups.items():
        for n, i in enumerate(sorted(ids)):
            out[i] = key if len(ids) == 1 else key + "abcdefghijklmnopqrstuvwxyz"[n]
    return out


def bibtex(item: dict, site_url: str, key: str | None = None) -> str:
    venue = item.get("venue")
    how = kind(item)
    if item.get("note_id"):
        how = f"Technical note {item['note_id']}"
    if venue:
        how += f", {venue}"
    fields = [
        ("author", " and ".join(authors(item))),
        ("title", "{" + item["title"] + "}"),
        ("howpublished", how),
        ("year", str(item["year"]) if item.get("year") else None),
        ("url", f"{site_url}items/{item['id']}/"),
        ("note", "Slides" if item["category"] != "tech-note" else None),
    ]
    body = ",\n".join(f"  {k} = {{{_bib_escape(v) if k not in ('url',) else v}}}"
                      for k, v in fields if v)
    return f"@misc{{{key or bib_key(item)},\n{body}\n}}"


def _e(s) -> str:
    return html.escape(str(s or ""), quote=True)


PERMISSIONS_HTML = (
    "<p>These slides and notes are © Zlatko K. Minev and shared under "
    "<a href=\"https://creativecommons.org/licenses/by-nc-nd/4.0/\">CC BY-NC-ND 4.0</a>: "
    "read them, download them, share them with credit. Want to reuse a slide or figure "
    "in your own talk, course or paper? Just ask. The answer is usually yes. "
    "Some slides include figures by other people, credited where they appear; those "
    "stay with their owners, so please ask the original source.</p>")


def item_page(item: dict, site_url: str, pdf_base_abs: str, key: str | None = None) -> str:
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
    meta_html = "\n".join(f'<meta name="{k}" content="{_e(v)}">' for k, v in meta if v)
    facts = " · ".join(_e(x) for x in [kind(item) if not item.get("note_id") else item["note_id"],
                                        item.get("year") or "undated", item.get("venue"),
                                        item.get("pages") and f"{item['pages']} pages"] if x)
    points = "".join(f"<li>{_e(p)}</li>" for p in item.get("key_points") or [])
    draft = (' <span class="draft" title="Machine-written from the slides; not yet reviewed by the author">draft</span>'
             if item.get("draft") else "")
    bib = bibtex(item, site_url, key)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{_e(item['title'])} · {_e(', '.join(authors(item)))}</title>
<meta name="description" content="{_e(desc)}">
<link rel="canonical" href="{_e(url)}">
<meta property="og:title" content="{_e(item['title'])}">
<meta property="og:description" content="{_e(desc)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{_e(url)}">
{f'<meta property="og:image" content="{_e(thumb)}">' if thumb else ''}
{meta_html}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,500;0,7..72,650;1,7..72,500&family=Public+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="../../style.css">
</head>
<body class="item-page">
<nav class="topbar wrap" aria-label="Site">
  <a class="me" href="../../"><span class="mono-mark" aria-hidden="true">|ψ⟩</span>Quantum Jumps</a>
  <div class="toplinks"><a href="../../#{_e(item['id'])}">Browse the archive</a></div>
</nav>
<main class="wrap ip">
  <p class="eyebrow">{_e(SHELF_NAME.get(item.get('shelf'), ''))}</p>
  <h1 class="ip-title">{_e(item['title'])}</h1>
  <p class="ip-authors">{_e(', '.join(authors(item)))}</p>
  <p class="d-meta">{facts}</p>
  <div class="ip-grid">
    <div class="ip-body">
      <div class="d-actions"><a class="btn primary" href="{_e(pdf)}">Open PDF</a></div>
      <p class="d-summary">{_e(item.get('summary') or desc)}{draft}</p>
      {f'<ul class="d-points">{points}</ul>' if points else ''}
      <h2 class="ip-h">Cite</h2>
      <pre class="bib" id="bib">{_e(bib)}</pre>
      <button class="btn" type="button" id="copy-bib">Copy BibTeX</button>
      <h2 class="ip-h">Reuse</h2>
      <div class="ip-perm">{PERMISSIONS_HTML}</div>
    </div>
    {f'<a class="ip-thumb" href="{_e(pdf)}"><img src="../../{_e(item["thumb"])}" alt="First page of {_e(item["title"])}"></a>' if item.get('thumb') else ''}
  </div>
</main>
<script>
document.getElementById("copy-bib").onclick = async (e) => {{
  const t = document.getElementById("bib").textContent;
  try {{ await navigator.clipboard.writeText(t); e.target.textContent = "Copied"; }}
  catch {{ const r = document.createRange(); r.selectNodeContents(document.getElementById("bib")); getSelection().removeAllRanges(); getSelection().addRange(r); }}
}};
</script>
</body>
</html>
"""


def sitemap(items: list[dict], site_url: str) -> str:
    urls = [site_url] + [f"{site_url}items/{i['id']}/" for i in items]
    body = "\n".join(f"  <url><loc>{html.escape(u)}</loc></url>" for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}\n</urlset>\n")


def robots(site_url: str) -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {site_url}sitemap.xml\n"
