// The Quantum Notebook: client-side search, filter and sort over library.json.
// No framework: one state object, one render(). Filters live in the query
// string (?shelf=&q=&tag=&year=&level=&sort=&group=) and an open item in the
// hash (#<id>), so every view is a shareable link.
"use strict";

// The three collections, in display order. Keys match "shelf" in catalog.json.
const SHELVES = [
  { key: "lectures", kicker: "|learn⟩", name: "Lectures & Tutorials",
    blurb: "Summer schools, courses, tutorials and career talks. Start here if you're new; curiosity is the only prerequisite." },
  { key: "research", kicker: "|discover⟩", name: "Research Talks",
    blurb: "Seminars, keynotes and conference talks, from whispering-gallery modes in 2011 to Fibonacci anyons." },
  { key: "notes", kicker: "|derive⟩", name: "Tech Notes",
    blurb: "Derivations and cheat sheets, numbered like a lab notebook. Pencil recommended." },
];
const SHELF = Object.fromEntries(SHELVES.map((s) => [s.key, s]));

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
// group: null = default (on: each series collapses to one cover card)
const state = { q: "", shelf: "", tags: new Set(), years: new Set(), levels: new Set(), sort: "new", group: null, expanded: new Set() };
const grouped = () => (state.group ?? true);

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
  if (it.category === "research-talk") return "Research talk";
  if (it.tags.includes("tutorial")) return "Tutorial";
  if (it.tags.includes("career")) return "Career talk";
  return "Lecture";
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

// Bonus material (cheat sheets, derivations, short notes) is never a series' cover deck.
const isExtra = (it) => it.tags.some((t) => t === "reference" || t === "cheat-sheet" || t === "derivation")
  || /\((bonus|note)\)/.test(it.title);

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
    const cover = ms.find((m) => !isExtra(m)) || ms[0];
    const open = state.expanded.has(it.series);
    out.push({ it: cover, stack: { series: it.series, n: ms.length, open, years: yearSpan(ms) } });
    if (open) for (const m of ms) if (m !== cover) out.push({ it: m, member: true });
  }
  return out;
}

function cell({ it, stack, member }) {
  if (member) return `<div class="cell member">${card(it)}</div>`;
  if (!stack) return `<div class="cell">${card(it)}</div>`;
  const label = stack.open ? "Show fewer" : `+${stack.n - 1} more in this series`;
  return `<div class="cell stack${stack.open ? " open" : ""}">
    <div class="stack-cards">${card(it)}</div>
    <button class="stack-more" type="button" data-series="${esc(stack.series)}" aria-expanded="${stack.open}">
      <span class="stack-name">${esc(stack.series)}</span>
      <span class="stack-count">${stack.years ? esc(stack.years) + " · " : ""}${label}</span>
    </button>
  </div>`;
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

  const cells = grouped() ? collapse(list) : list.map((it) => ({ it }));
  $("#grid").innerHTML = `<div class="grid">${cells.map(cell).join("")}</div>`;
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
    (it.links || []).map((l) => `<a class="btn" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.label)}</a>`).join("") +
    (url !== gh ? `<a class="btn" href="${esc(gh)}" target="_blank" rel="noopener">View on GitHub</a>` : "") +
    `<button class="btn" type="button" id="cite" aria-expanded="false">Cite</button>` +
    `<button class="btn" type="button" id="copy">Copy link</button>`;
  $("#d-cite").hidden = true;
  $("#d-bib").textContent = it.bibtex || "";
  $("#d-citepage").href = it.series_page || it.page || "#";
  $("#d-citepage").textContent = it.series_page ? "Series page" : "Citation page";
  $("#d-cite-note").textContent = it.series_page ? `Part of “${it.series}”, cited as one series:` : "";
  const text = it.summary || it.description;
  $("#d-summary").innerHTML = text ? esc(text) + (it.draft ? `<span class="draft" title="Machine-written from the slides; not yet reviewed by the author">draft</span>` : "") : "";
  $("#d-points").innerHTML = (it.key_points || []).map((p) => `<li>${esc(p)}</li>`).join("");
  $("#d-tags").innerHTML = it.tags.filter((t) => TOPICS[t] || FORMATS[t]).map((t) => `<span class="chip">${esc(TOPICS[t] || FORMATS[t])}</span>`).join("");
  const rel = related(it);
  $("#d-related").innerHTML = rel.length ? `<h3>Related</h3><ul>${rel.map((o) => `<li><button type="button" data-id="${esc(o.id)}">${esc(o.title)}${o.year ? ` (${o.year})` : ""}</button></li>`).join("")}</ul>` : "";
  $("#cite").onclick = (e) => {
    const box = $("#d-cite");
    box.hidden = !box.hidden;
    e.target.setAttribute("aria-expanded", String(!box.hidden));
  };
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

async function copyBib(e) {
  try { await navigator.clipboard.writeText($("#d-bib").textContent); e.target.textContent = "Copied"; }
  catch {
    const r = document.createRange(); r.selectNodeContents($("#d-bib"));
    getSelection().removeAllRanges(); getSelection().addRange(r);
    e.target.textContent = "Selected, press Ctrl/⌘-C";
  }
  setTimeout(() => { e.target.textContent = "Copy BibTeX"; }, 2000);
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

// ---------- the hero transmon: isometric chip with live fields ----------
// Two capacitor pads joined by a Josephson junction on a substrate. Charge q
// sloshes between the pads (q = cos φ); field lines and pad tint follow q,
// and a Cooper pair hops across the junction. φ advances slowly with time and
// faster with scrolling.
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
  // readout resonator meander leaving the right pad
  el("polyline", { class: "meander", points: pts([[8.5, 3.0, 0.02], [9.3, 3.0, 0.02], [9.3, 3.7, 0.02], [8.9, 3.7, 0.02], [8.9, 4.3, 0.02], [9.3, 4.3, 0.02], [9.3, 4.9, 0.02], [8.9, 4.9, 0.02], [8.9, 5.5, 0.02], [9.3, 5.5, 0.02], [9.3, 6, 0.02]]) });
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
  let visible = true, t0 = performance.now();
  const frame = (now) => {
    const phi = (still ? 0.6 : (now - t0) / 1400) + window.scrollY / 90;
    const q = Math.cos(phi);
    tintA.style.fill = q >= 0 ? "var(--accent)" : "var(--edu)";
    tintB.style.fill = q >= 0 ? "var(--edu)" : "var(--accent)";
    tintA.style.opacity = tintB.style.opacity = (0.15 + 0.5 * Math.abs(q)).toFixed(2);
    labA.textContent = q >= 0 ? "+" : "−";
    labB.textContent = q >= 0 ? "−" : "+";
    for (const [i, l] of lines.entries()) {
      l.style.opacity = (0.15 + 0.75 * Math.abs(q) * (1 - i * 0.06)).toFixed(2);
      l.style.strokeDashoffset = (phi * 18 * Math.sign(q || 1)).toFixed(1);
    }
    const s = Math.sin(phi);  // current ∝ dq/dt: the pair crosses as q changes sign
    for (const [i, c] of pair.entries()) {
      const [x, y] = P(5 + 0.9 * s + (i ? 0.25 : -0.25) * 0.4, 3 + (i ? 0.12 : -0.12), 0.45);
      c.setAttribute("cx", x.toFixed(1)); c.setAttribute("cy", y.toFixed(1));
    }
    if (visible && !still) requestAnimationFrame(frame);
  };
  if (!still && "IntersectionObserver" in window) {
    new IntersectionObserver(([e]) => { const was = visible; visible = e.isIntersecting; if (visible && !was) requestAnimationFrame(frame); }).observe(svg);
  }
  if (still) window.addEventListener("scroll", () => frame(0), { passive: true });
  requestAnimationFrame(frame);
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
  $("#grid").addEventListener("click", (e) => {
    const more = e.target.closest(".stack-more");
    if (more) { toggle(state.expanded, more.dataset.series); render(); return; }
    const c = e.target.closest(".card");
    if (c) openItem(c.dataset.id);
  });
  $("#d-related").addEventListener("click", (e) => { const b = e.target.closest("button[data-id]"); if (b) openItem(b.dataset.id); });
  const dlg = $("#detail");
  $("#close").addEventListener("click", () => dlg.close());
  $("#copy-bib").addEventListener("click", copyBib);
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
  try { initTransmon(); } catch (e) { console.error(e); }
  const res = await fetch("library.json");
  LIB = await res.json();
  for (const it of LIB.items) it._h = haystack(it);
  const ys = LIB.items.map((i) => i.year).filter(Boolean);
  $("#span-years").textContent = `${Math.min(...ys)} → ${Math.max(...ys)}`;
  const slides = LIB.items.reduce((n, i) => n + (i.pages || 0), 0);
  $("#fun-stats").innerHTML = `<b>${LIB.items.length}</b> decks · <b>${slides.toLocaleString("en-US")}</b> slides · ` +
    `about <b>${Math.round(slides / 60)}</b> hours of talking, at a minute a slide (optimistic)`;
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
