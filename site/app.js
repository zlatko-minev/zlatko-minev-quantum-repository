// Quantum Archive — client-side search, filter and sort over library.json.
// No framework: one state object, one render(). Filters live in the query
// string (?q=&type=&tag=&year=&level=&sort=&group=) and an open item in the
// hash (#<id>), so every view is a shareable link.
"use strict";

const TYPES = [
  ["all", "All"],
  ["educational", "Lectures & tutorials"],
  ["research-talk", "Research talks"],
  ["tech-note", "Technical notes"],
];
const TYPE_LABEL = { educational: "Lecture", "research-talk": "Research talk", "tech-note": "Tech note" };

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
const state = { q: "", type: "all", tags: new Set(), years: new Set(), levels: new Set(), sort: "new", group: false };

// ---------- URL state ----------
function readURL() {
  let p;
  try { p = new URLSearchParams(location.search); } catch { return; }
  state.q = p.get("q") || "";
  state.type = TYPES.some(([k]) => k === p.get("type")) ? p.get("type") : "all";
  state.tags = new Set((p.get("tag") || "").split(",").filter(Boolean));
  state.years = new Set((p.get("year") || "").split(",").filter(Boolean));
  state.levels = new Set((p.get("level") || "").split(",").filter(Boolean));
  state.sort = p.get("sort") || "new";
  state.group = p.get("group") === "1";
}
function writeURL() {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.type !== "all") p.set("type", state.type);
  if (state.tags.size) p.set("tag", [...state.tags].join(","));
  if (state.years.size) p.set("year", [...state.years].join(","));
  if (state.levels.size) p.set("level", [...state.levels].join(","));
  if (state.sort !== "new") p.set("sort", state.sort);
  if (state.group) p.set("group", "1");
  const qs = p.toString();
  try { history.replaceState(null, "", (qs ? "?" + qs : location.pathname) + location.hash); } catch { /* sandboxed */ }
}

// ---------- filtering ----------
function haystack(it) {
  return [it.title, it.venue, it.series, it.note_id, it.year, it.description, it.summary,
    ...(it.tags || []), ...(it.topics || []), ...(it.key_points || [])].join(" ").toLowerCase();
}
const yearKey = (it) => (it.year ? String(it.year) : "undated");

function matches(it, skip) {
  if (skip !== "type" && state.type !== "all" && it.category !== state.type) return false;
  if (skip !== "tags") for (const t of state.tags) if (!it.tags.includes(t)) return false;
  if (skip !== "years" && state.years.size && !state.years.has(yearKey(it))) return false;
  if (skip !== "levels" && state.levels.size && !state.levels.has(it.level)) return false;
  if (state.q) {
    const h = it._h;
    for (const w of state.q.toLowerCase().split(/\s+/).filter(Boolean)) if (!h.includes(w)) return false;
  }
  return true;
}

const SORTS = {
  new: (a, b) => (b.year || 0) - (a.year || 0) || a.title.localeCompare(b.title),
  old: (a, b) => (a.year || 9999) - (b.year || 9999) || a.title.localeCompare(b.title),
  title: (a, b) => a.title.localeCompare(b.title),
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

function pdfURL(it) { return LIB.pdf_base + it.file.split("/").map(encodeURIComponent).join("/"); }

function card(it) {
  const meta = [it.year || "undated", it.pages ? it.pages + " pp" : null].filter(Boolean).join(" · ");
  return `<button class="card" type="button" data-id="${esc(it.id)}">
    <div class="thumb">${it.thumb ? `<img src="${esc(it.thumb)}" alt="" loading="lazy" decoding="async">` : ""}</div>
    <div class="card-body">
      <div class="kind"><span class="type k-${it.category}"><span class="dot"></span>${esc(it.note_id || TYPE_LABEL[it.category])}</span><span>${esc(meta)}</span></div>
      <h3>${highlight(it.title)}</h3>
      ${it.venue ? `<p class="venue">${highlight(it.venue)}</p>` : ""}
      ${it.description ? `<p class="desc">${esc(it.description)}</p>` : ""}
    </div>
  </button>`;
}

function chipRow(el, dict, selected, facet, field) {
  const counts = {};
  for (const it of LIB.items) if (matches(it, facet)) {
    const vals = field === "level" ? [it.level] : it.tags;
    for (const v of vals) counts[v] = (counts[v] || 0) + 1;
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
  const undated = counts.undated || 0;
  let axis = $("#years-axis");
  if (!axis) { axis = document.createElement("div"); axis.id = "years-axis"; el.after(axis); }
  axis.className = "years-axis";
  axis.innerHTML = `<span>${lo}</span><button class="chip" type="button" data-k="undated" aria-pressed="${state.years.has("undated")}">Undated<small>${undated}</small></button><span>${hi}</span>`;
}

function render() {
  const list = LIB.items.filter((it) => matches(it)).sort(SORTS[state.sort] || SORTS.new);

  $("#types").innerHTML = TYPES.map(([k, label]) =>
    `<button type="button" data-k="${k}" aria-pressed="${state.type === k}">${label}</button>`).join("");
  chipRow($("#tags"), TOPICS, state.tags, "tags", "tags");
  chipRow($("#formats"), FORMATS, state.tags, "tags", "tags");
  chipRow($("#levels"), LEVELS, state.levels, "levels", "level");
  renderYears();

  const filtered = state.q || state.type !== "all" || state.tags.size || state.years.size || state.levels.size;
  $("#reset").hidden = !filtered;
  $("#count").innerHTML = `<b>${list.length}</b> of ${LIB.items.length} items`;
  $("#empty").hidden = list.length > 0;

  let html = "";
  if (state.group) {
    const groups = new Map();
    for (const it of list) {
      const g = it.series || (it.category === "tech-note" ? "Technical notes" : "Standalone talks");
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g).push(it);
    }
    const order = [...groups].sort((a, b) => (b[1].length > 1) - (a[1].length > 1) || b[1].length - a[1].length);
    for (const [g, its] of order) html += `<h2 class="group-h">${esc(g)} <small>${its.length}</small></h2><div class="grid">${its.map(card).join("")}</div>`;
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
  $("#d-img").alt = it.thumb ? `First slide of “${it.title}”` : "";
  $("#d-meta").textContent = [it.note_id || TYPE_LABEL[it.category], it.year || "undated", it.pages && `${it.pages} pages`,
    it.size && `${(it.size / 1e6).toFixed(1)} MB`, it.level && LEVELS[it.level]].filter(Boolean).join(" · ");
  $("#d-title").textContent = it.title;
  $("#d-series").textContent = [it.venue, it.series && it.series !== it.venue ? `Series: ${it.series}` : null,
    it.speaker && it.speaker !== "Minev" ? `Speaker: ${it.speaker}` : null].filter(Boolean).join(" · ");
  const url = pdfURL(it);
  const gh = `${LIB.repo_url}/blob/main/${it.file.split("/").map(encodeURIComponent).join("/")}`;
  $("#d-actions").innerHTML = `<a class="btn primary" href="${esc(url)}" target="_blank" rel="noopener">Open PDF</a>` +
    (LIB.pdf_base === "" ? `<a class="btn" href="${esc(url)}" download>Download</a>` : "") +
    (url !== gh ? `<a class="btn" href="${esc(gh)}" target="_blank" rel="noopener">View on GitHub</a>` : "") +
    `<button class="btn" type="button" id="copy">Copy link</button>`;
  const text = it.summary || it.description;
  $("#d-summary").innerHTML = text ? esc(text) + (it.ai ? `<span class="ai" title="Generated by a language model from the slides; may contain errors">auto-summary</span>` : "") : "";
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

function closeItem() {
  $("#detail").close();
}

// ---------- wiring ----------
function toggle(set, k) { set.has(k) ? set.delete(k) : set.add(k); }
function resetAll() {
  Object.assign(state, { q: "", type: "all", tags: new Set(), years: new Set(), levels: new Set() });
  $("#q").value = "";
  render();
}

function wire() {
  let t;
  $("#q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); render(); }, 120); });
  $("#types").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { state.type = b.dataset.k; render(); } });
  for (const id of ["#tags", "#formats"]) $(id).addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { toggle(state.tags, b.dataset.k); render(); } });
  $("#levels").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { toggle(state.levels, b.dataset.k); render(); } });
  $("#years").parentElement.addEventListener("click", (e) => { const b = e.target.closest("button[data-k]"); if (b) { toggle(state.years, b.dataset.k); render(); } });
  $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; render(); });
  $("#group").addEventListener("change", (e) => { state.group = e.target.checked; render(); });
  $("#reset").addEventListener("click", resetAll);
  $("#reset2").addEventListener("click", resetAll);
  $("#grid").addEventListener("click", (e) => { const c = e.target.closest(".card"); if (c) openItem(c.dataset.id); });
  $("#d-related").addEventListener("click", (e) => { const b = e.target.closest("button[data-id]"); if (b) openItem(b.dataset.id); });
  $("#close").addEventListener("click", closeItem);
  const dlg = $("#detail");
  dlg.addEventListener("click", (e) => { if (e.target === dlg) closeItem(); });
  dlg.addEventListener("close", () => { try { history.replaceState(null, "", location.pathname + location.search); } catch { /* sandboxed */ } });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== $("#q") && !dlg.open) { e.preventDefault(); $("#q").focus(); }
  });
  window.addEventListener("hashchange", () => { const id = location.hash.slice(1); if (id) openItem(id, false); });
}

function renderStats() {
  const items = LIB.items;
  const n = (c) => items.filter((i) => i.category === c).length;
  const pages = items.reduce((s, i) => s + (i.pages || 0), 0);
  const stats = [[n("educational"), "lectures"], [n("research-talk"), "talks"], [n("tech-note"), "notes"], [pages.toLocaleString("en-US"), "slides & pages"]];
  $("#stats").innerHTML = stats.map(([v, l]) => `<div><dt>${l}</dt><dd>${v}</dd></div>`).join("");
}

// Filters start open on wide screens, collapsed on phones.
function syncFilterBox() {
  try { $("#filters-box").open = matchMedia("(min-width: 960px)").matches || $("#filters-box").open; } catch { $("#filters-box").open = true; }
}

async function boot() {
  const res = await fetch("library.json");
  LIB = await res.json();
  for (const it of LIB.items) it._h = haystack(it);
  readURL();
  $("#q").value = state.q;
  $("#sort").value = state.sort;
  $("#group").checked = state.group;
  syncFilterBox();
  renderStats();
  wire();
  render();
  const id = location.hash.slice(1);
  if (id) openItem(id, false);
}

boot().catch((err) => {
  $("#count").textContent = "Could not load the catalog (library.json). If you opened this file directly, run: python3 tools/build_site.py --serve";
  console.error(err);
});
