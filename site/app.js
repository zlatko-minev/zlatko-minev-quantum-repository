// Quantum Jumps: client-side search, filter and sort over library.json.
// No framework: one state object, one render(). Filters live in the query
// string (?shelf=&q=&tag=&year=&level=&sort=&group=) and an open item in the
// hash (#<id>), so every view is a shareable link.
"use strict";

// The four collections, in display order. Keys match "shelf" in catalog.json.
const SHELVES = [
  { key: "lectures", kicker: "Learn", name: "Lectures & Summer Schools",
    blurb: "Courses from the Qiskit Global Summer School, Boulder and device workshops. Start here if you're new." },
  { key: "research", kicker: "Discover", name: "Research Talks",
    blurb: "Seminars, keynotes and conference talks, from whispering-gallery modes to Fibonacci anyons." },
  { key: "notes", kicker: "Derive", name: "Tutorials & Tech Notes",
    blurb: "Step-by-step tutorials, derivations and cheat sheets. Pencil recommended." },
  { key: "outreach", kicker: "Explore", name: "Career & Outreach",
    blurb: "Career advice and big-picture talks for students and the quantum-curious." },
];
const SHELF = Object.fromEntries(SHELVES.map((s) => [s.key, s]));
const KIND = { lectures: "Lecture", research: "Research talk", notes: "Tutorial", outreach: "Outreach" };

// Subject tags shown as topic filters, in display order; format tags separately.
const TOPICS = {
  "superconducting-qubits": "Superconducting qubits", hardware: "Quantum hardware",
  "qiskit-metal": "Qiskit Metal & EPR", noise: "Quantum noise", "error-mitigation": "Error mitigation",
  pec: "PEC", twirling: "Pauli twirling", measurement: "Measurement", "many-body": "Many-body physics",
  topological: "Topological / anyons", "machine-learning": "Machine learning", sensing: "Sensing",
  math: "Math", estimation: "Estimation", circuits: "Circuits", career: "Career", outreach: "Outreach",
  overview: "Overview",
};
const FORMATS = {
  "summer-school": "Summer school", lecture: "Lecture", tutorial: "Tutorial", keynote: "Keynote",
  reference: "Reference", "cheat-sheet": "Cheat sheet", derivation: "Derivation",
};
const LEVELS = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced" };

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let LIB = null;
// group: null = automatic (on for lectures and notes, where series matter)
const state = { q: "", shelf: "", tags: new Set(), years: new Set(), levels: new Set(), sort: "new", group: null };
const grouped = () => (state.group ?? (state.shelf === "lectures" || state.shelf === "notes"));

// ---------- URL state ----------
function readURL() {
  let p;
  try { p = new URLSearchParams(location.search); } catch { return; }
  state.q = p.get("q") || "";
  state.shelf = SHELF[p.get("shelf")] ? p.get("shelf") : "";
  state.tags = new Set((p.get("tag") || "").split(",").filter(Boolean));
  state.years = new Set((p.get("year") || "").split(",").filter(Boolean));
  state.levels = new Set((p.get("level") || "").split(",").filter(Boolean));
  state.sort = p.get("sort") || "new";
  state.group = p.has("group") ? p.get("group") === "1" : null;
}
function writeURL() {
  const p = new URLSearchParams();
  if (state.shelf) p.set("shelf", state.shelf);
  if (state.q) p.set("q", state.q);
  if (state.tags.size) p.set("tag", [...state.tags].join(","));
  if (state.years.size) p.set("year", [...state.years].join(","));
  if (state.levels.size) p.set("level", [...state.levels].join(","));
  if (state.sort !== "new") p.set("sort", state.sort);
  if (state.group !== null) p.set("group", state.group ? "1" : "0");
  const qs = p.toString();
  try { history.replaceState(null, "", (qs ? "?" + qs : location.pathname) + location.hash); } catch { /* sandboxed */ }
}

// ---------- filtering ----------
function haystack(it) {
  return [it.title, it.venue, it.series, it.note_id, it.year, it.description, it.summary, SHELF[it.shelf]?.name,
    ...(it.tags || []), ...(it.key_points || [])].join(" ").toLowerCase();
}
const yearKey = (it) => (it.year ? String(it.year) : "undated");

function matches(it, skip) {
  if (skip !== "shelf" && state.shelf && it.shelf !== state.shelf) return false;
  if (skip !== "tags") for (const t of state.tags) if (!it.tags.includes(t)) return false;
  if (skip !== "years" && state.years.size && !state.years.has(yearKey(it))) return false;
  if (skip !== "levels" && state.levels.size && !state.levels.has(it.level)) return false;
  if (state.q) {
    for (const w of state.q.toLowerCase().split(/\s+/).filter(Boolean)) if (!it._h.includes(w)) return false;
  }
  return true;
}

const SORTS = {
  new: (a, b) => (b.year || 0) - (a.year || 0) || a.title.localeCompare(b.title, undefined, { numeric: true }),
  old: (a, b) => (a.year || 9999) - (b.year || 9999) || a.title.localeCompare(b.title, undefined, { numeric: true }),
  title: (a, b) => a.title.localeCompare(b.title, undefined, { numeric: true }),
  pages: (a, b) => (b.pages || 0) - (a.pages || 0),
};

// ---------- rendering ----------
function highlight(text) {
  const s = esc(text);
  const words = state.q.trim().split(/\s+/).filter((w) => w.length > 1);
  if (!words.length) return s;
  const re = new RegExp("(" + words.map((w) => esc(w).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")", "gi");
  return s.replace(re, "<mark>$1</mark>");
}

const pathURL = (file) => file.split("/").map(encodeURIComponent).join("/");
const pdfURL = (it) => LIB.pdf_base + pathURL(it.file);

function kindLabel(it) {
  if (it.note_id) return it.note_id;
  if (it.category === "tech-note") return "Tech note";
  return KIND[it.shelf] || "Deck";
}

function card(it) {
  const meta = [it.year || "undated", it.pages ? it.pages + " pp" : null].filter(Boolean).join(" · ");
  return `<button class="card" type="button" data-id="${esc(it.id)}">
    <div class="thumb">${it.thumb ? `<img src="${esc(it.thumb)}" alt="" loading="lazy" decoding="async">` : ""}</div>
    <div class="card-body">
      <div class="kind"><span class="type k-${esc(it.shelf)}"><span class="dot"></span>${esc(kindLabel(it))}</span><span>${esc(meta)}</span></div>
      <h3>${highlight(it.title)}</h3>
      ${it.venue ? `<p class="venue">${highlight(it.venue)}</p>` : ""}
      ${it.description ? `<p class="desc">${esc(it.description)}</p>` : ""}
    </div>
  </button>`;
}

function renderShelves() {
  const counts = {};
  for (const it of LIB.items) if (matches(it, "shelf")) counts[it.shelf] = (counts[it.shelf] || 0) + 1;
  $("#shelves").innerHTML = SHELVES.map((s) => `<button class="shelf s-${s.key}" type="button" data-k="${s.key}" aria-pressed="${state.shelf === s.key}">
      <span class="s-top"><span class="s-kicker">${s.kicker}</span><span class="s-count">${counts[s.key] || 0}</span></span>
      <h2>${s.name}</h2><p>${s.blurb}</p></button>`).join("");
}

function chipRow(el, dict, selected, facet, field) {
  const counts = {};
  for (const it of LIB.items) if (matches(it, facet)) {
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
    return `<button type="button" data-k="${y}" aria-pressed="${state.years.has(y)}" style="height:${Math.max(4, (n / max) * 100)}%" title="${y}: ${n}" aria-label="${y}, ${n} items"></button>`;
  }).join("");
  let axis = $("#years-axis");
  if (!axis) { axis = document.createElement("div"); axis.id = "years-axis"; axis.className = "years-axis"; el.after(axis); }
  axis.innerHTML = `<span>${lo}</span><button class="chip" type="button" data-k="undated" aria-pressed="${state.years.has("undated")}">Undated<small>${counts.undated || 0}</small></button><span>${hi}</span>`;
}

function groupsOf(list) {
  const groups = new Map();
  for (const it of list) {
    const g = it.series || (it.category === "tech-note" ? "Tech notes" : "");
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(it);
  }
  // Series with 2+ items first, newest series first; singles pooled at the end.
  const multi = [], singles = [];
  for (const [g, its] of groups) (g && its.length > 1 ? multi.push([g, its]) : singles.push(...its));
  const newest = (its) => Math.max(0, ...its.map((i) => i.year || 0));
  multi.sort((a, b) => newest(b[1]) - newest(a[1]) || a[0].localeCompare(b[0]));
  if (singles.length) multi.push([multi.length ? "More" : "", singles]);
  return multi;
}

function yearSpan(its) {
  const ys = its.map((i) => i.year).filter(Boolean);
  if (!ys.length) return "";
  const lo = Math.min(...ys), hi = Math.max(...ys);
  return lo === hi ? String(lo) : `${lo}–${hi}`;
}

function render() {
  const list = LIB.items.filter((it) => matches(it)).sort(SORTS[state.sort] || SORTS.new);

  renderShelves();
  chipRow($("#tags"), TOPICS, state.tags, "tags", "tags");
  chipRow($("#formats"), FORMATS, state.tags, "tags", "tags");
  chipRow($("#levels"), LEVELS, state.levels, "levels", "level");
  renderYears();
  $("#group").checked = grouped();

  const filtered = state.q || state.shelf || state.tags.size || state.years.size || state.levels.size;
  $("#reset").hidden = !filtered;
  const where = state.shelf ? ` in <b>${esc(SHELF[state.shelf].name)}</b>` : "";
  $("#count").innerHTML = `<b>${list.length}</b> of ${LIB.items.length} decks${where}` +
    (state.shelf ? ` · <button class="linkish" type="button" id="all-shelves">show everything</button>` : "");
  $("#empty").hidden = list.length > 0;

  let html = "";
  if (grouped()) {
    for (const [g, its] of groupsOf(list)) {
      const head = g ? `<h2 class="group-h">${esc(g)} <span class="yrs">${yearSpan(its)}</span> <small>${its.length} ${its.length === 1 ? "deck" : "decks"}</small></h2>` : "";
      html += `${head}<div class="grid">${its.map(card).join("")}</div>`;
    }
  } else {
    html = `<div class="grid">${list.map(card).join("")}</div>`;
  }
  $("#grid").innerHTML = html;
  writeURL();
}

// ---------- detail ----------
function related(it) {
  const score = (o) => (o.series && o.series === it.series ? 3 : 0) + o.tags.filter((t) => it.tags.includes(t) && TOPICS[t]).length;
  return LIB.items.filter((o) => o.id !== it.id).map((o) => [score(o), o]).filter(([s]) => s > 1)
    .sort((a, b) => b[0] - a[0] || (b[1].year || 0) - (a[1].year || 0)).slice(0, 5).map(([, o]) => o);
}

function openItem(id, push = true) {
  const it = LIB.items.find((i) => i.id === id);
  if (!it) return;
  $("#d-img").src = it.thumb || "";
  $("#d-img").alt = it.thumb ? `First page of “${it.title}”` : "";
  $("#d-meta").textContent = [kindLabel(it), it.year || "undated", it.pages && `${it.pages} pages`,
    it.size && `${(it.size / 1e6).toFixed(1)} MB`, it.level && LEVELS[it.level]].filter(Boolean).join(" · ");
  $("#d-title").textContent = it.title;
  $("#d-series").textContent = [it.venue, it.series && it.series !== it.venue ? `Series: ${it.series}` : null,
    it.speaker && it.speaker !== "Minev" ? `Speaker: ${it.speaker}` : null].filter(Boolean).join(" · ");
  const url = pdfURL(it);
  const gh = `${LIB.repo_url}/blob/main/${pathURL(it.file)}`;
  $("#d-actions").innerHTML = `<a class="btn primary" href="${esc(url)}" target="_blank" rel="noopener">Open PDF</a>` +
    (LIB.pdf_base === "" ? `<a class="btn" href="${esc(url)}" download>Download</a>` : "") +
    (url !== gh ? `<a class="btn" href="${esc(gh)}" target="_blank" rel="noopener">View on GitHub</a>` : "") +
    `<button class="btn" type="button" id="copy">Copy link</button>`;
  const text = it.summary || it.description;
  $("#d-summary").innerHTML = text ? esc(text) + (it.draft ? `<span class="draft" title="Machine-written from the slides; not yet reviewed by the author">draft</span>` : "") : "";
  $("#d-points").innerHTML = (it.key_points || []).map((p) => `<li>${esc(p)}</li>`).join("");
  $("#d-tags").innerHTML = it.tags.filter((t) => TOPICS[t] || FORMATS[t]).map((t) => `<span class="chip">${esc(TOPICS[t] || FORMATS[t])}</span>`).join("");
  const rel = related(it);
  $("#d-related").innerHTML = rel.length ? `<h3>Related</h3><ul>${rel.map((o) => `<li><button type="button" data-id="${esc(o.id)}">${esc(o.title)}${o.year ? ` (${o.year})` : ""}</button></li>`).join("")}</ul>` : "";
  $("#copy").onclick = async (e) => {
    const link = location.href.split("#")[0] + "#" + it.id;
    try { await navigator.clipboard.writeText(link); e.target.textContent = "Link copied"; }
    catch { e.target.textContent = link; }
  };
  const dlg = $("#detail");
  if (!dlg.open) dlg.showModal();
  dlg.querySelector(".detail").scrollTop = 0;
  if (push) try { history.replaceState(null, "", location.pathname + location.search + "#" + it.id); } catch { /* sandboxed */ }
}

// ---------- the hero trace: a telegraph signal of quantum jumps ----------
// Seeded so the page looks the same on every load until someone clicks.
function mulberry32(a) {
  return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
function drawTrace(seed) {
  const rnd = mulberry32(seed), W = 1200, N = 600, lo = 78, hi = 18;
  let level = 0, x = 0;
  const pts = [], jumps = [];
  while (x < W) {
    const dwell = 25 + rnd() * (level ? 70 : 160);   // ground dwells longer than excited
    const end = Math.min(W, x + dwell);
    for (; x < end; x += W / N) pts.push([x, (level ? hi : lo) + (rnd() - .5) * 7]);
    if (x < W) { jumps.push([x, level]); level = 1 - level; }
  }
  const d = pts.map(([px, py], i) => (i ? "L" : "M") + px.toFixed(1) + " " + py.toFixed(1)).join("");
  $("#trace-path").setAttribute("d", d);
  // Mark one upward jump past the middle as "caught mid-flight".
  const up = jumps.filter(([jx, from]) => from === 0 && jx > 420 && jx < 900)[0];
  const g = $("#trace-mark"), label = $("#trace-label");
  label.hidden = !up;
  if (!up) { g.innerHTML = ""; return; }
  const jx = up[0];
  g.innerHTML = `<path class="mark-path" d="M${jx - 6} ${lo} C ${jx + 4} ${lo}, ${jx - 4} ${hi}, ${jx + 6} ${hi}"/>`;
  label.style.left = (jx / W * 100).toFixed(2) + "%";
}

// ---------- wiring ----------
function toggle(set, k) { set.has(k) ? set.delete(k) : set.add(k); }
function resetAll() {
  Object.assign(state, { q: "", shelf: "", tags: new Set(), years: new Set(), levels: new Set(), group: null });
  $("#q").value = "";
  render();
}
const onButton = (sel, fn) => $(sel).addEventListener("click", (e) => { const b = e.target.closest("button[data-k]"); if (b) { fn(b.dataset.k); render(); } });

function wire() {
  let t;
  $("#q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); render(); }, 120); });
  onButton("#shelves", (k) => { state.shelf = state.shelf === k ? "" : k; state.group = null; });
  onButton("#tags", (k) => toggle(state.tags, k));
  onButton("#formats", (k) => toggle(state.tags, k));
  onButton("#levels", (k) => toggle(state.levels, k));
  $("#years").parentElement.addEventListener("click", (e) => { const b = e.target.closest("button[data-k]"); if (b) { toggle(state.years, b.dataset.k); render(); } });
  $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; render(); });
  $("#group").addEventListener("change", (e) => { state.group = e.target.checked; render(); });
  $("#reset").addEventListener("click", resetAll);
  $("#reset2").addEventListener("click", resetAll);
  $("#count").addEventListener("click", (e) => { if (e.target.id === "all-shelves") { state.shelf = ""; state.group = null; render(); } });
  $("#random").addEventListener("click", () => {
    const pool = LIB.items.filter((it) => matches(it));
    const pick = (pool.length ? pool : LIB.items)[Math.floor(Math.random() * (pool.length || LIB.items.length))];
    openItem(pick.id);
  });
  $("#trace").addEventListener("click", () => drawTrace((Math.random() * 1e9) | 0));
  $("#grid").addEventListener("click", (e) => { const c = e.target.closest(".card"); if (c) openItem(c.dataset.id); });
  $("#d-related").addEventListener("click", (e) => { const b = e.target.closest("button[data-id]"); if (b) openItem(b.dataset.id); });
  const dlg = $("#detail");
  $("#close").addEventListener("click", () => dlg.close());
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener("close", () => { try { history.replaceState(null, "", location.pathname + location.search); } catch { /* sandboxed */ } });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== $("#q") && !dlg.open) { e.preventDefault(); $("#q").focus(); }
  });
  window.addEventListener("hashchange", () => { const id = location.hash.slice(1); if (id) openItem(id, false); });
}

// Filters start open on wide screens, collapsed on phones.
function syncFilterBox() {
  try { $("#filters-box").open = matchMedia("(min-width: 960px)").matches; } catch { $("#filters-box").open = true; }
}

async function boot() {
  drawTrace(20190603);   // Nature, 3 June 2019
  const res = await fetch("library.json");
  LIB = await res.json();
  for (const it of LIB.items) it._h = haystack(it);
  const ys = LIB.items.map((i) => i.year).filter(Boolean);
  $("#span-years").textContent = `${Math.min(...ys)} → ${Math.max(...ys)}`;
  readURL();
  $("#q").value = state.q;
  $("#sort").value = state.sort;
  syncFilterBox();
  wire();
  render();
  const id = location.hash.slice(1);
  if (id) openItem(id, false);
}

boot().catch((err) => {
  $("#count").textContent = "Couldn't load the catalog (library.json). If you opened this file directly, run: python3 tools/build_site.py --serve";
  console.error(err);
});
