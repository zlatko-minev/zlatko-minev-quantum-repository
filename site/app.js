// Zlatko's Quantum Notebook: client-side search, filter and sort over library.json.
// No framework: one state object, one render(). Filters live in the query
// string (?shelf=&q=&tag=&year=&level=&sort=&group=) and an open item in the
// hash (#<id>), so every view is a shareable link.
"use strict";

// The three collections, in display order. Keys match "shelf" in catalog.json;
// the tiles themselves are static markup in index.html.
const SHELVES = [
  { key: "lectures", name: "Lectures & Tutorials" },
  { key: "research", name: "Research Talks" },
  { key: "notes", name: "Tech Notes" },
];
const SHELF = Object.fromEntries(SHELVES.map((s) => [s.key, s]));

// "Start here": short ordered reading paths (ids from catalog.json).
const PATHS = [
  { name: "Superconducting qubits, from scratch", ket: "|0⟩ → transmon", ids: [
    "2025-your-first-superconducting-qubit-intro-to-cqed-part-i",
    "2025-your-first-superconducting-qubit-intro-to-cqed-part-ii",
    "2023-intro-to-quantum-measurements-part-i-ideal-measurements",
    "2020-to-catch-and-reverse-a-quantum-jump-mid-flight",
    "2025-overview-of-quantum-hardware-design-energy-circuits"] },
  { name: "Noise, and what to do about it", ket: "noise → mitigation", ids: [
    "2023-intro-to-quantum-noise-main-lecture",
    "t27-simple-noise-models-and-gate-fidelity",
    "2022-primer-on-pauli-twirling-part-i",
    "2024-introduction-to-noise-and-quantum-error-mitigation-lecture-1",
    "2023-quantum-error-mitigation-lecture-2"] },
  { name: "The pencil-and-paper toolbox", ket: "∑ → ⟨O⟩", ids: [
    "t11-7-pictorial-digital-quantum-circuits",
    "t11-9-concentration-inequalities-and-tail-bounds",
    "t21-estimating-observables-from-sampled-bit-strings",
    "t22-bounding-a-sum-of-operators-a-la-watrous"] },
];

// Subject tags shown as topic filters, in display order; format tags separately.
const TOPICS = {
  "superconducting-qubits": "Superconducting qubits", hardware: "Quantum hardware",
  "qiskit-metal": "Qiskit Metal & EPR", noise: "Quantum noise", "error-mitigation": "Error mitigation",
  pec: "PEC", twirling: "Pauli twirling", measurement: "Measurement", "many-body": "Many-body physics",
  topological: "Topological / anyons", "machine-learning": "Machine learning", sensing: "Sensing",
  math: "Math", estimation: "Estimation", circuits: "Circuits", qiskit: "Qiskit", career: "Career",
  outreach: "Outreach", overview: "Overview",
};
const FORMATS = {
  "summer-school": "Summer school", lecture: "Lecture", tutorial: "Tutorial", keynote: "Keynote",
  reference: "Reference", "cheat-sheet": "Cheat sheet", derivation: "Derivation",
};
const LEVELS = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced" };
// Search synonyms: a query word also matches any of these.
const SYN = {
  decoherence: ["noise", "t1", "dephasing"], dephasing: ["noise"], t1: ["noise", "relaxation"],
  t2: ["noise", "dephasing"], qec: ["error correction", "error-mitigation"], cqed: ["circuit qed", "transmon"],
  qubit: ["transmon"], mitigation: ["pec", "zne", "twirling"], video: ["lecture"], beginner: ["intro"],
};

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const reEsc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

let LIB = null, BY_ID = new Map();
// group: null = default (on: each series collapses to one cover card)
const state = { q: "", shelf: "", tags: new Set(), years: new Set(), levels: new Set(), sort: "new",
  sortChosen: false, group: null, expanded: new Set() };
const grouped = () => (state.group ?? true);

// ---------- URL state ----------
function readURL() {
  let p;
  try { p = new URLSearchParams(location.search); } catch { return; }
  const pick = (v, ok) => new Set((v || "").split(",").filter(ok));
  state.q = p.get("q") || "";
  state.shelf = SHELF[p.get("shelf")] ? p.get("shelf") : "";
  state.tags = pick(p.get("tag"), (k) => TOPICS[k] || FORMATS[k]);
  state.years = pick(p.get("year"), (k) => k === "undated" || LIB.items.some((i) => String(i.year) === k));
  state.levels = pick(p.get("level"), (k) => LEVELS[k]);
  state.sortChosen = Boolean(SORTS[p.get("sort")]);
  state.sort = state.sortChosen ? p.get("sort") : "new";
  const g = p.get("group");
  state.group = g === "1" ? true : g === "0" ? false : null;
}
function writeURL() {
  const p = new URLSearchParams();
  if (state.shelf) p.set("shelf", state.shelf);
  if (state.q) p.set("q", state.q);
  if (state.tags.size) p.set("tag", [...state.tags].join(","));
  if (state.years.size) p.set("year", [...state.years].join(","));
  if (state.levels.size) p.set("level", [...state.levels].join(","));
  if (state.sortChosen) p.set("sort", state.sort);
  if (state.group !== null) p.set("group", state.group ? "1" : "0");
  const qs = p.toString();
  try { history.replaceState(null, "", (qs ? "?" + qs : location.pathname) + location.hash); } catch { /* sandboxed */ }
}

// ---------- search ----------
const isExtra = (it) => it.tags.some((t) => t === "reference" || t === "cheat-sheet" || t === "derivation")
  || /\((bonus|note)\)/.test(it.title);

function kindLabel(it) {
  if (it.note_id) return it.note_id;
  if (it.category === "tech-note") return "Tech note";
  if (it.category === "research-talk") return "Research talk";
  if (it.tags.includes("tutorial")) return "Tutorial";
  if (it.tags.includes("career")) return "Career talk";
  return "Lecture";
}

function index(it) {
  const tagLabels = it.tags.map((t) => TOPICS[t] || FORMATS[t] || t);
  it._title = it.title.toLowerCase();
  it._meta = [it.series, it.venue, it.note_id, ...tagLabels, LEVELS[it.level], kindLabel(it)].join(" ").toLowerCase();
  it._desc = (it.description || "").toLowerCase();
  it._rest = [it.year, it.summary, ...(it.key_points || []), SHELF[it.shelf]?.name].join(" ").toLowerCase();
}
const words = () => state.q.toLowerCase().split(/\s+/).filter(Boolean);
const forms = (w) => [w, ...(SYN[w] || [])];
const hit = (s, w) => forms(w).some((f) => s.includes(f));

function score(it) {
  let n = 0;
  for (const w of words()) {
    if (hit(it._title, w)) n += 4;
    if (hit(it._meta, w)) n += 3;
    if (hit(it._desc, w)) n += 2;
    if (hit(it._rest, w)) n += 1;
  }
  return n;
}

const yearKey = (it) => (it.year ? String(it.year) : "undated");

function matches(it, skip) {
  if (skip !== "shelf" && state.shelf && it.shelf !== state.shelf) return false;
  if (skip !== "tags") for (const t of state.tags) if (!it.tags.includes(t)) return false;
  if (skip !== "years" && state.years.size && !state.years.has(yearKey(it))) return false;
  if (skip !== "levels" && state.levels.size && !state.levels.has(it.level)) return false;
  for (const w of words()) {
    const all = it._title + " " + it._meta + " " + it._desc + " " + it._rest;
    if (!hit(all, w)) return false;
  }
  return true;
}

const byTitle = (a, b) => a.title.localeCompare(b.title, undefined, { numeric: true });
const SORTS = {
  best: (a, b) => b._score - a._score || (b.year || 0) - (a.year || 0) || byTitle(a, b),
  new: (a, b) => (b.year || 0) - (a.year || 0) || byTitle(a, b),
  old: (a, b) => (a.year || 9999) - (b.year || 9999) || byTitle(a, b),
  title: byTitle,
  pages: (a, b) => (b.pages || 0) - (a.pages || 0),
};
// With a query and no explicit sort choice, rank by relevance.
const activeSort = () => (state.q && !state.sortChosen ? "best" : state.sort);

// ---------- rendering ----------
function highlight(text) {
  const s = String(text ?? "");
  const ws = words().filter((w) => w.length > 1);
  if (!ws.length) return esc(s);
  const re = new RegExp("(" + ws.map(reEsc).join("|") + ")", "gi");
  return s.split(re).map((part, i) => (i % 2 ? `<mark>${esc(part)}</mark>` : esc(part))).join("");
}

const pathURL = (file) => file.split("/").map(encodeURIComponent).join("/");
const pdfURL = (it) => LIB.pdf_base + pathURL(it.file);
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

// "New" for 120 days after the date a deck was added to the notebook.
const isNew = (it) => it.added && Date.now() - Date.parse(it.added) < 120 * 864e5;

function card(it, badge = "") {
  if (isNew(it)) badge = `<span class="new-pill">New</span>` + badge;
  const meta = [it.year || "undated", it.pages ? it.pages + " pp" : null, LEVELS[it.level]].filter(Boolean).join(" · ");
  const wh = it.thumb_wh ? ` width="${it.thumb_wh[0]}" height="${it.thumb_wh[1]}"` : "";
  return `<article class="card" data-id="${esc(it.id)}">
    <div class="thumb">${it.thumb ? `<img src="${esc(it.thumb_sm || it.thumb)}"${it.thumb_sm ? ` srcset="${esc(it.thumb_sm)} 360w, ${esc(it.thumb)} 640w" sizes="(min-width: 1240px) 300px, (min-width: 960px) 25vw, (min-width: 600px) 45vw, 92vw"` : ""} alt=""${wh} loading="lazy" decoding="async">` : ""}</div>
    <div class="card-body">
      <div class="kind">${badge}<span class="type k-${esc(it.shelf)}"><span class="dot"></span>${esc(kindLabel(it))}</span><span>${esc(meta)}</span></div>
      <h3><a class="card-link" href="${esc(it.page)}">${highlight(it.title)}</a></h3>
      ${it.venue ? `<p class="venue">${highlight(it.venue)}</p>` : ""}
      ${it.description ? `<p class="desc">${esc(it.description)}</p>` : ""}
    </div>
  </article>`;
}

function renderShelves() {
  const counts = {};
  for (const it of LIB.items) if (matches(it, "shelf")) counts[it.shelf] = (counts[it.shelf] || 0) + 1;
  for (const b of document.querySelectorAll("#shelves .shelf")) {
    b.setAttribute("aria-pressed", String(state.shelf === b.dataset.k));
    b.querySelector(".s-count b").textContent = counts[b.dataset.k] || 0;
  }
}

function chipRow(el, dict, selected, field) {
  // Tags combine with AND, so their counts come from the current result.
  // Levels combine with OR, so their counts skip the level filter itself.
  const counts = {};
  for (const it of LIB.items) if (matches(it, field === "level" ? "levels" : undefined)) {
    for (const v of field === "level" ? [it.level] : it.tags) counts[v] = (counts[v] || 0) + 1;
  }
  el.innerHTML = Object.entries(dict)
    .filter(([k]) => counts[k] || selected.has(k))
    .map(([k, label]) => `<button class="chip" type="button" data-k="${k}" aria-pressed="${selected.has(k)}">${esc(label)}<small>${counts[k] || 0}</small></button>`)
    .join("");
}

function renderYears() {
  const all = LIB.items.map((i) => i.year).filter(Boolean);
  const lo = Math.min(...all), hi = Math.max(...all);
  const counts = {};
  for (const it of LIB.items) if (matches(it, "years")) counts[yearKey(it)] = (counts[yearKey(it)] || 0) + 1;
  const max = Math.max(1, ...Object.values(counts));
  const keys = [];
  for (let y = lo; y <= hi; y++) keys.push(String(y));
  const el = $("#years");
  el.style.setProperty("--n", keys.length);
  el.innerHTML = keys.map((y) => {
    const n = counts[y] || 0;
    const on = state.years.has(y);
    return `<button type="button" data-k="${y}" aria-pressed="${on}" ${n || on ? "" : "disabled"} style="--h:${Math.max(4, (n / max) * 100)}%" title="${y}: ${plural(n, "deck")}" aria-label="${y}, ${plural(n, "deck")}"></button>`;
  }).join("");
  $("#years-axis").innerHTML = `<span>${lo}</span><span>${hi}</span>`;
  const u = counts.undated || 0;
  $("#years-undated").innerHTML = u || state.years.has("undated")
    ? `<button class="chip" type="button" data-k="undated" aria-pressed="${state.years.has("undated")}">Undated<small>${u}</small></button>` : "";
}

function yearSpan(its) {
  const ys = its.map((i) => i.year).filter(Boolean);
  if (!ys.length) return "";
  const lo = Math.min(...ys), hi = Math.max(...ys);
  return lo === hi ? String(lo) : `${lo}–${hi}`;
}

// Collapse each series (2+ matching decks) to one cover card, placed where the
// series' best-ranked deck falls in the current sort, so series and standalone
// decks stay interleaved in sort order. Expanded series list all their decks.
function collapse(list) {
  const members = new Map();
  for (const it of list) if (it.series) {
    if (!members.has(it.series)) members.set(it.series, []);
    members.get(it.series).push(it);   // already in sort order
  }
  const out = [], done = new Set();
  for (const it of list) {
    const ms = it.series && members.get(it.series);
    if (!ms || ms.length < 2) { out.push({ it }); continue; }
    if (done.has(it.series)) continue;
    done.add(it.series);
    const ordered = [...ms.filter((m) => !isExtra(m)), ...ms.filter(isExtra)];   // bonus material last
    const cover = ordered.find((m) => m.tags.includes("lecture")) || ordered[0];
    const rest = ordered.filter((m) => m !== cover);
    const open = state.expanded.has(it.series);
    out.push({ it: cover, stack: { series: it.series, n: ms.length, open, years: yearSpan(ms) } });
    if (open) rest.forEach((m, i) => out.push({ it: m, member: `${i + 2}/${ms.length}` }));
  }
  return out;
}

function cell({ it, stack, member }) {
  if (member) return `<div class="cell member">${card(it, `<span class="member-n">${member}</span>`)}</div>`;
  if (!stack) return `<div class="cell">${card(it)}</div>`;
  const label = stack.open ? "Show fewer" : `+${stack.n - 1} more in this series`;
  return `<div class="cell stack${stack.open ? " open" : ""}">
    <div class="stack-cards">${card(it, stack.open ? `<span class="member-n">1/${stack.n}</span>` : "")}</div>
    <button class="stack-more" type="button" data-series="${esc(stack.series)}" aria-expanded="${stack.open}">
      <span class="stack-name">${esc(stack.series)}</span>
      <span class="stack-count">${stack.years ? esc(stack.years) + " · " : ""}${label}</span>
    </button>
  </div>`;
}

// A small fanned stack of first-page thumbnails (paths and shelf tiles).
const fan = (its) => its.filter((it) => it.thumb).slice(0, 3).reverse().map((it) =>
  `<img src="${esc(it.thumb_sm || it.thumb)}" alt="" loading="lazy" decoding="async">`).join("");

function renderPaths() {
  $("#paths").innerHTML = PATHS.map((p) => {
    const its = p.ids.map((id) => BY_ID.get(id)).filter(Boolean);
    if (!its.length) return "";
    return `<li class="path">
      <a class="path-fan" href="${esc(its[0].page)}" data-id="${esc(its[0].id)}" aria-label="Start with ${esc(its[0].title)}">${fan(its)}</a>
      <p class="path-ket">${esc(p.ket)}</p><h3>${esc(p.name)}</h3>
      <ol>${its.map((it) => `<li><a href="${esc(it.page)}" data-id="${esc(it.id)}">${esc(it.title)}</a> <span>${esc(it.note_id || it.year || "")}</span></li>`).join("")}</ol>
    </li>`;
  }).join("");
}

// Shelf tiles show three covers: featured decks first, then the newest.
function renderShelfFans() {
  for (const b of document.querySelectorAll("#shelves .shelf")) {
    const its = LIB.items.filter((it) => it.shelf === b.dataset.k && it.thumb && !it.version_of)
      .sort((a, c) => (c.featured - a.featured) || (c.year || 0) - (a.year || 0));
    const seen = new Set(), pick = [];
    for (const it of its) if (!it.series || !seen.has(it.series)) { seen.add(it.series); pick.push(it); }
    b.querySelector(".s-fan").innerHTML = fan(pick);
  }
}

// Re-render replaces the controls, so put keyboard focus back where it was.
function focusKey() {
  const a = document.activeElement;
  if (!a || a === document.body) return null;
  const box = a.closest("#shelves, #tags, #formats, #levels, #years, #years-undated, #grid");
  if (!box) return null;
  for (const attr of ["data-k", "data-series", "data-id"]) {
    const el = attr === "data-id" ? a.closest("[data-id]") : a;
    if (el?.hasAttribute(attr)) return { box: box.id, attr, val: el.getAttribute(attr), link: a.classList.contains("card-link") };
  }
  return null;
}
function restoreFocus(f) {
  if (!f) return;
  let el = document.querySelector(`#${f.box} [${f.attr}="${CSS.escape(f.val)}"]`);
  if (el && f.link) el = el.querySelector(".card-link");
  (el || $("#count")).focus({ preventScroll: true });
}

function render() {
  const f = focusKey();
  for (const it of LIB.items) it._score = state.q ? score(it) : 0;
  const sort = activeSort();
  const list = LIB.items.filter((it) => matches(it)).sort(SORTS[sort]);

  renderShelves();
  chipRow($("#tags"), TOPICS, state.tags, "tags");
  chipRow($("#formats"), FORMATS, state.tags, "tags");
  chipRow($("#levels"), LEVELS, state.levels, "level");
  renderYears();
  $("#group").checked = grouped();
  $("#sort").value = sort;
  $("#random").disabled = list.length === 0;

  const filtered = state.q || state.shelf || state.tags.size || state.years.size || state.levels.size;
  $("#reset").hidden = !filtered;
  const cells = grouped() ? collapse(list) : list.map((it) => ({ it }));
  // Grouping folds a series into one card, so say how many cards that makes.
  const stacks = cells.filter((c) => c.stack && !c.stack.open).length;
  const shown = cells.length;
  const where = state.shelf ? ` in <b>${esc(SHELF[state.shelf].name)}</b>` : "";
  $("#count").innerHTML = `<b>${list.length}</b> of ${plural(LIB.items.length, "deck")}${where}` +
    (stacks ? ` · shown as ${plural(shown, "card")} (${stacks} series stacked)` : "") +
    (state.q && sort === "best" ? " · best matches first" : "") +
    (state.shelf ? ` · <button class="linkish" type="button" id="all-shelves">show everything</button>` : "");
  $("#empty").hidden = list.length > 0;
  if (!list.length) $("#empty-q").textContent = state.q ? `“${state.q}”` : "these filters";

  $("#grid").innerHTML = `<div class="grid">${cells.map(cell).join("")}</div>`;
  writeURL();
  restoreFocus(f);
}

// ---------- detail ----------
function seriesOf(it) {
  if (!it.series) return [];
  const ms = LIB.items.filter((o) => o.series === it.series).sort(SORTS.old);
  return [...ms.filter((m) => !isExtra(m)), ...ms.filter(isExtra)];
}
function related(it, exclude) {
  const score = (o) => o.tags.filter((t) => it.tags.includes(t) && TOPICS[t]).length + (o.shelf === it.shelf ? 0.5 : 0);
  return LIB.items.filter((o) => o.id !== it.id && !exclude.has(o.id)).map((o) => [score(o), o]).filter(([s]) => s > 1)
    .sort((a, b) => b[0] - a[0] || (b[1].year || 0) - (a[1].year || 0)).slice(0, 4).map(([, o]) => o);
}
const relLink = (o, cur) => `<li${o === cur ? ' aria-current="true"' : ""}>${o === cur ? `<b>${esc(o.title)}</b>`
  : `<button type="button" data-id="${esc(o.id)}">${esc(o.title)}</button>`}${o.year ? ` <span>(${o.year})</span>` : ""}</li>`;

let copyTimer;
function flash(btn, text, reset) {
  btn.textContent = text;
  clearTimeout(copyTimer);
  copyTimer = setTimeout(() => { btn.textContent = reset; }, 2500);
}

function openItem(id, push = true) {
  const it = BY_ID.get(id);
  if (!it) return;
  $("#d-img").src = it.thumb || "";
  if (it.thumb_wh) { $("#d-img").width = it.thumb_wh[0]; $("#d-img").height = it.thumb_wh[1]; }
  $("#d-img").alt = it.thumb ? `First page of “${it.title}”` : "";
  $("#d-meta").textContent = [kindLabel(it), it.year || "undated", it.pages && `${it.pages} pages`,
    it.size && `${(it.size / 1e6).toFixed(1)} MB`, LEVELS[it.level]].filter(Boolean).join(" · ");
  $("#d-title").textContent = it.title;
  const who = it.authors || (it.speaker && it.speaker !== "Minev" ? it.speaker : "");
  $("#d-series").innerHTML = [esc(it.venue), it.series ? `Series: <a href="${esc(it.series_page || it.page)}">${esc(it.series)}</a>` : "",
    who ? `With: ${esc(who.replace(/\bMinev\b/, "Zlatko K. Minev"))}` : ""].filter(Boolean).join(" · ");
  const url = pdfURL(it);
  const gh = `${LIB.repo_url}/blob/main/${pathURL(it.file)}`;
  const ms = seriesOf(it);
  const next = ms[ms.indexOf(it) + 1];
  $("#d-actions").innerHTML = `<a class="btn primary" href="${esc(url)}" target="_blank" rel="noopener">Open PDF</a>` +
    (LIB.pdf_base === "" ? `<a class="btn" href="${esc(url)}" download>Download</a>` : "") +
    ((it.doi || it.series_doi) ? `<a class="btn" href="https://doi.org/${esc(it.doi || it.series_doi)}" target="_blank" rel="noopener">DOI</a>` : "") +
    (it.links || []).map((l) => `<a class="btn" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a>`).join("") +
    (next ? `<button class="btn" type="button" id="next" data-id="${esc(next.id)}">Next in series →</button>` : "") +
    `<button class="btn" type="button" id="cite" aria-expanded="false" aria-controls="d-cite">Cite</button>` +
    `<button class="btn" type="button" id="copy">Copy link</button>` +
    (url !== gh ? `<a class="btn quiet" href="${esc(gh)}" target="_blank" rel="noopener">View on GitHub</a>` : "");
  $("#d-cite").hidden = true;
  $("#d-bib").textContent = it.bibtex || "";
  $("#d-citepage").href = it.canonical_page || (it.cited_as_series ? it.series_page : it.page) || "#";
  $("#d-citepage").textContent = it.cited_as_series && !it.canonical_page ? "Series page" : "Citation page";
  $("#d-cite-note").textContent = it.version_of ? "Also published as a tech note; cite that:"
    : it.cited_as_series ? `Part of “${it.series}”, cited as one series:` : "";
  $("#d-summary").textContent = it.summary || it.description || "";
  $("#d-points").innerHTML = (it.key_points || []).map((p) => `<li>${esc(p)}</li>`).join("");
  $("#d-draft").hidden = !it.draft;
  $("#d-tags").innerHTML = it.tags.filter((t) => TOPICS[t] || FORMATS[t]).map((t) => `<span class="chip">${esc(TOPICS[t] || FORMATS[t])}</span>`).join("");
  const inSeries = new Set(ms.map((m) => m.id));
  const rel = related(it, inSeries);
  $("#d-related").innerHTML =
    (ms.length > 1 ? `<h3>In this series (${ms.indexOf(it) + 1} of ${ms.length})</h3><ol>${ms.map((o) => relLink(o, it)).join("")}</ol>` : "") +
    (rel.length ? `<h3>Related</h3><ul>${rel.map((o) => relLink(o, null)).join("")}</ul>` : "");
  $("#cite").onclick = (e) => {
    const box = $("#d-cite");
    box.hidden = !box.hidden;
    e.currentTarget.setAttribute("aria-expanded", String(!box.hidden));
  };
  $("#copy").onclick = async (e) => {
    const btn = e.currentTarget, link = location.href.split("#")[0] + "#" + it.id;
    try { await navigator.clipboard.writeText(link); flash(btn, "Link copied", "Copy link"); }
    catch { flash(btn, "Copy it from the address bar", "Copy link"); }
  };
  const dlg = $("#detail");
  if (!dlg.open) dlg.showModal();
  dlg.querySelector(".detail").scrollTop = 0;
  $("#d-title").focus({ preventScroll: true });
  if (push) try { history.replaceState(null, "", location.pathname + location.search + "#" + it.id); } catch { /* sandboxed */ }
}

async function copyBib(e) {
  const btn = e.currentTarget;
  try { await navigator.clipboard.writeText($("#d-bib").textContent); flash(btn, "Copied", "Copy BibTeX"); }
  catch {
    const r = document.createRange(); r.selectNodeContents($("#d-bib"));
    getSelection().removeAllRanges(); getSelection().addRange(r);
    flash(btn, "Selected, press Ctrl/⌘-C", "Copy BibTeX");
  }
}

// ---------- the quantum-jump trace: a live record ----------
// Bright |G⟩ and dark |D⟩ levels of a three-level atom, as inferred from its
// bright-state clicks. Waiting times are exponential, with long stretches in G
// and shorter stays in D. The record streams right to left; each G→D jump is
// drawn as a smooth arc (the jump caught mid-flight) and the newest is labelled.
// Seeded, so the first screen is the same on every load.
function mulberry32(a) {
  return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
let tracePaused = false;
function initTrace() {
  const W = 1200, N = 400, dx = W / N, lo = 92, hi = 28, RATE = 32;   // samples per second
  const rnd = mulberry32(20190603);   // Nature 570, 200, published 3 June 2019
  const expo = (m) => -m * Math.log(1 - rnd());
  const ys = [], ups = [];            // ups: absolute sample index of each G→D jump
  let level = 0, left = 0, n = 0, frac = 0;
  const step = () => {
    if (left <= 0) {
      if (n) { if (level === 0) ups.push(n); level = 1 - level; }
      left = Math.max(3, Math.round(expo(level ? 14 : 75) + 4));
    }
    left--;
    ys.push((level ? hi : lo) + (rnd() - 0.5) * 8);
    n++;
    if (ys.length > N + 2) ys.shift();
  };
  for (let i = 0; i < N + 2; i++) step();
  // Start on a screen with a jump about two thirds of the way across.
  while (!ups.some((u) => u - (n - ys.length) > N * 0.55 && u - (n - ys.length) < N * 0.8)) step();

  const path = $("#trace-path"), mark = $("#trace-mark"), label = $("#trace-label"), plot = $("#trace-plot");
  const draw = () => {
    const start = n - ys.length;
    const X = (i) => ((i - frac) * dx).toFixed(1);
    path.setAttribute("d", ys.map((y, i) => (i ? "L" : "M") + X(i) + " " + y.toFixed(1)).join(""));
    while (ups.length && ups[0] - start < -4) ups.shift();
    mark.innerHTML = ups.map((u) => {
      const x = (u - start - frac) * dx;
      return `<path class="mark-path" d="M${(x - 9).toFixed(1)} ${lo} C ${(x + 3).toFixed(1)} ${lo}, ${(x - 3).toFixed(1)} ${hi}, ${(x + 9).toFixed(1)} ${hi}"/>`;
    }).join("");
    const last = ups.filter((u) => (u - start) * dx < W - 40).pop();
    label.hidden = last === undefined;
    if (last !== undefined) {   // keep the label inside the plot on narrow screens
    const pw = plot.clientWidth, half = label.offsetWidth / 2;
    label.style.left = Math.min(pw - half, Math.max(half, ((last - start - frac) * dx) / W * pw)).toFixed(1) + "px";
  }
  };

  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const btn = $("#trace-pause");
  let visible = true, running = false, prev = 0;
  const shouldRun = () => visible && !still && !tracePaused && !document.hidden && !$("#detail").open;
  const frame = (now) => {
    if (!shouldRun()) { running = false; return; }
    frac += Math.min(100, now - prev) / 1000 * RATE; prev = now;
    while (frac >= 1) { frac -= 1; step(); }
    draw();
    requestAnimationFrame(frame);
  };
  const kick = () => { if (!running && shouldRun()) { running = true; prev = performance.now(); requestAnimationFrame(frame); } };
  if ("IntersectionObserver" in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; kick(); }).observe(plot);
  document.addEventListener("visibilitychange", kick);
  $("#detail").addEventListener("close", kick);
  const toggle = () => {
    tracePaused = !tracePaused;
    btn.setAttribute("aria-pressed", String(tracePaused));
    btn.textContent = tracePaused ? "Play" : "Pause";
    kick();
  };
  if (still) btn.hidden = true;
  btn.addEventListener("click", toggle);
  plot.addEventListener("click", () => { if (!still) toggle(); });
  draw();
  kick();
}

// ---------- the hero transmon: isometric chip with live fields ----------
// Two capacitor pads shunting a Josephson junction. A cartoon of the plasma
// oscillation: charge q = cos θ sloshes between the pads, field lines and pad
// tint follow q, and a Cooper pair crosses the junction as the current flows
// (its position follows q). θ advances slowly with time and with scrolling.
let transmonPaused = false;
function initTransmon() {
  const svg = $("#transmon");
  if (!svg) return;
  const NS = "http://www.w3.org/2000/svg", k = 19, C = Math.cos(Math.PI / 6);
  const ox = 142, oy = 58;
  const P = (x, y, z = 0) => [ox + (x - y) * C * k, oy + (x + y) * 0.5 * k - z * k];
  const pts = (arr) => arr.map((p) => P(...p).map((v) => v.toFixed(1)).join(",")).join(" ");
  const el = (tag, attrs, parent = svg) => {
    const e = document.createElementNS(NS, tag);
    for (const [a, v] of Object.entries(attrs)) e.setAttribute(a, v);
    parent.appendChild(e);
    return e;
  };
  // a box's visible faces: top, front-left (y = y1) and front-right (x = x1)
  const box = (x0, x1, y0, y1, z0, z1, cls) => {
    el("polygon", { class: cls + " f-l", points: pts([[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]]) });
    el("polygon", { class: cls + " f-r", points: pts([[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]]) });
    return el("polygon", { class: cls + " f-t", points: pts([[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]) });
  };
  svg.innerHTML = "";
  box(0, 10, 0, 6, -0.7, 0, "sub");
  // readout resonator meander, capacitively coupled across a small gap
  el("polyline", { class: "meander", points: pts([[8.85, 3.0, 0.02], [9.3, 3.0, 0.02], [9.3, 3.7, 0.02], [8.9, 3.7, 0.02], [8.9, 4.3, 0.02], [9.3, 4.3, 0.02], [9.3, 4.9, 0.02], [8.9, 4.9, 0.02], [8.9, 5.5, 0.02], [9.3, 5.5, 0.02], [9.3, 6, 0.02]]) });
  const padA = box(1.4, 4.3, 1.6, 4.4, 0, 0.3, "pad");
  const padB = box(5.7, 8.6, 1.6, 4.4, 0, 0.3, "pad");
  const tintA = el("polygon", { class: "tint", points: padA.getAttribute("points") });
  const tintB = el("polygon", { class: "tint", points: padB.getAttribute("points") });
  box(4.3, 5.7, 2.92, 3.08, 0, 0.12, "lead");
  box(4.88, 5.12, 2.86, 3.14, 0, 0.2, "jj");
  // field lines: arcs from pad A to pad B, nested by height
  const lines = [];
  for (const [d, y, h] of [[0.2, 2.1, 0.9], [0.2, 3.9, 0.9], [0.9, 2.5, 1.7], [0.9, 3.5, 1.7], [1.7, 3.0, 2.6], [2.5, 2.2, 3.2], [2.5, 3.8, 3.2]]) {
    const a = P(4.3 - d, y, 0.3), b = P(5.7 + d, y, 0.3);
    const c1 = P(4.3 - d * 0.6, y, 0.3 + h), c2 = P(5.7 + d * 0.6, y, 0.3 + h);
    lines.push(el("path", { class: "field", d: `M${a} C${c1} ${c2} ${b}` }));
  }
  const pair = [el("circle", { class: "cp", r: 2.6 }), el("circle", { class: "cp", r: 2.6 })];
  const labA = el("text", { class: "chg", x: P(2.85, 3, 1.2)[0], y: P(2.85, 3, 1.2)[1] });
  const labB = el("text", { class: "chg", x: P(7.15, 3, 1.2)[0], y: P(7.15, 3, 1.2)[1] });

  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let visible = true, running = false, last = 0, clock = 0, prev = performance.now();
  const draw = () => {
    const theta = clock / 1400 + window.scrollY / 90;
    const q = Math.cos(theta);            // + on pad A, − on pad B when q > 0
    tintA.style.fill = q >= 0 ? "var(--accent)" : "var(--edu)";
    tintB.style.fill = q >= 0 ? "var(--edu)" : "var(--accent)";
    tintA.style.opacity = tintB.style.opacity = (0.15 + 0.5 * Math.abs(q)).toFixed(2);
    labA.textContent = q >= 0 ? "+" : "−";
    labB.textContent = q >= 0 ? "−" : "+";
    for (const [i, l] of lines.entries()) {
      l.style.opacity = (0.15 + 0.75 * Math.abs(q) * (1 - i * 0.06)).toFixed(2);
      l.style.strokeDashoffset = (-theta * 18 * Math.sign(q || 1)).toFixed(1);   // dashes flow + → −, along E
    }
    // The pair (charge −2e) sits toward the negative pad: pad B when q > 0.
    for (const [i, c] of pair.entries()) {
      const [x, y] = P(5 + 0.9 * q + (i ? 0.1 : -0.1), 3 + (i ? 0.12 : -0.12), 0.45);
      c.setAttribute("cx", x.toFixed(1)); c.setAttribute("cy", y.toFixed(1));
    }
  };
  const shouldRun = () => visible && !still && !transmonPaused && !document.hidden && !$("#detail").open;
  const frame = (now) => {
    if (!shouldRun()) { running = false; return; }
    clock += Math.min(100, now - prev); prev = now;
    if (now - last > 33) { last = now; draw(); }    // ~30 fps is plenty
    requestAnimationFrame(frame);
  };
  const kick = () => { if (!running && shouldRun()) { running = true; prev = performance.now(); requestAnimationFrame(frame); } };
  if ("IntersectionObserver" in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; kick(); }).observe(svg);
  document.addEventListener("visibilitychange", kick);
  $("#detail").addEventListener("close", kick);
  window.addEventListener("scroll", () => { if (!running && visible) draw(); }, { passive: true });
  const btn = $("#tm-pause");
  if (still) btn.hidden = true;
  btn.addEventListener("click", () => {
    transmonPaused = !transmonPaused;
    btn.setAttribute("aria-pressed", String(transmonPaused));
    btn.textContent = transmonPaused ? "Play" : "Pause";
    kick();
  });
  clock = 840;  // a frame with visible charge for the still / first paint
  draw();
  kick();
}

// ---------- wiring ----------
function toggle(set, k) { set.has(k) ? set.delete(k) : set.add(k); }
function resetAll() {
  Object.assign(state, { q: "", shelf: "", tags: new Set(), years: new Set(), levels: new Set(), expanded: new Set() });
  $("#q").value = "";
  render();
}
const onButton = (sel, fn) => $(sel).addEventListener("click", (e) => { const b = e.target.closest("button[data-k]"); if (b) { fn(b.dataset.k); render(); } });

function wire() {
  let t;
  $("#q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); render(); }, 120); });
  onButton("#shelves", (k) => { state.shelf = state.shelf === k ? "" : k; });
  onButton("#tags", (k) => toggle(state.tags, k));
  onButton("#formats", (k) => toggle(state.tags, k));
  onButton("#levels", (k) => toggle(state.levels, k));
  onButton("#years", (k) => toggle(state.years, k));
  onButton("#years-undated", (k) => toggle(state.years, k));
  $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; state.sortChosen = e.target.value !== "best"; render(); });
  $("#group").addEventListener("change", (e) => { state.group = e.target.checked; render(); });
  $("#reset").addEventListener("click", resetAll);
  $("#reset2").addEventListener("click", resetAll);
  $("#count").addEventListener("click", (e) => { if (e.target.id === "all-shelves") { state.shelf = ""; render(); } });
  $("#random").addEventListener("click", () => {
    const pool = LIB.items.filter((it) => matches(it));
    if (pool.length) openItem(pool[Math.floor(Math.random() * pool.length)].id);
  });
  $("#start-link").addEventListener("click", () => { $("#start").open = true; });
  // Choosing a shelf takes you down to the results.
  $("#shelves").addEventListener("click", (e) => {
    if (e.target.closest(".shelf") && state.shelf) $("#browse").scrollIntoView({ behavior: smooth(), block: "start" });
  });
  // Cards are links to their citation pages (for crawlers, new tabs and
  // no-JS); a plain click opens the in-page dialog instead.
  const plain = (e) => !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button === 1);
  $("#grid").addEventListener("click", (e) => {
    const more = e.target.closest(".stack-more");
    if (more) { toggle(state.expanded, more.dataset.series); render(); return; }
    const c = e.target.closest(".card");
    if (c && plain(e)) { e.preventDefault(); openItem(c.dataset.id); }
  });
  $("#paths").addEventListener("click", (e) => {
    const a = e.target.closest("a[data-id]");
    if (a && plain(e)) { e.preventDefault(); openItem(a.dataset.id); }
  });
  $("#d-related").addEventListener("click", (e) => { const b = e.target.closest("button[data-id]"); if (b) openItem(b.dataset.id); });
  $("#d-actions").addEventListener("click", (e) => { if (e.target.id === "next") openItem(e.target.dataset.id); });
  const dlg = $("#detail");
  $("#close").addEventListener("click", () => dlg.close());
  $("#copy-bib").addEventListener("click", copyBib);
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener("close", () => { try { history.replaceState(null, "", location.pathname + location.search); } catch { /* sandboxed */ } });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== $("#q") && !dlg.open) { e.preventDefault(); $("#q").focus(); }
  });
  window.addEventListener("hashchange", () => {
    const id = location.hash.slice(1);
    if (BY_ID.has(id)) openItem(id, false);
    else if (!id && dlg.open) dlg.close();
  });
}

const smooth = () => (matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");

// Sections fade up once as they scroll into view (not with reduced motion).
function initReveal() {
  const els = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const io = new IntersectionObserver((es) => {
    for (const e of es) if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
  }, { rootMargin: "0px 0px -8% 0px" });
  for (const el of els) { el.classList.add("pre"); io.observe(el); }
}

// Filters start open on wide screens, collapsed on phones.
function syncFilterBox() {
  try { $("#filters-box").open = matchMedia("(min-width: 960px)").matches; } catch { $("#filters-box").open = true; }
}

async function boot() {
  try { initTrace(); } catch (e) { console.error(e); }
  try { initTransmon(); } catch (e) { console.error(e); }
  initReveal();
  const res = await fetch("library.json");
  if (!res.ok) throw new Error(`library.json: HTTP ${res.status}`);
  LIB = await res.json();
  for (const it of LIB.items) { index(it); BY_ID.set(it.id, it); }
  readURL();
  $("#q").value = state.q;
  syncFilterBox();
  renderPaths();
  renderShelfFans();
  wire();
  render();
  const id = location.hash.slice(1);
  if (BY_ID.has(id)) openItem(id, false);
}

boot().catch((err) => {
  $("#count").innerHTML = 'The catalog didn\'t load, so search and filters are off. Every deck is still listed below and in the <a href="sitemap.xml">sitemap</a>.';
  console.error(err);
});
