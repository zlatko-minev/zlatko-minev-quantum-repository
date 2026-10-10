// Light/dark toggle. The page follows the system theme until someone picks
// one; the choice is remembered in this browser. Picking the theme the system
// already uses clears the choice, so the page follows the system again.
// (The inline snippet in <head> applies a stored choice before first paint.)
"use strict";
(() => {
  const root = document.documentElement, KEY = "theme";
  const sys = matchMedia("(prefers-color-scheme: dark)");
  const SUN = '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="3.6"/><path d="M10 1.8v2.4M10 15.8v2.4M1.8 10h2.4M15.8 10h2.4M4.2 4.2l1.7 1.7M14.1 14.1l1.7 1.7M4.2 15.8l1.7-1.7M14.1 5.9l1.7-1.7"/></svg>';
  const MOON = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M16.5 12.6A7 7 0 0 1 7.4 3.5a7 7 0 1 0 9.1 9.1z"/></svg>';
  const effective = () => root.dataset.theme || (sys.matches ? "dark" : "light");
  const paint = () => {
    const dark = effective() === "dark";
    for (const b of document.querySelectorAll("[data-theme-toggle]")) {
      b.innerHTML = dark ? SUN : MOON;
      b.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
      b.title = b.getAttribute("aria-label");
    }
  };
  document.addEventListener("click", (e) => {
    if (!e.target.closest("[data-theme-toggle]")) return;
    const next = effective() === "dark" ? "light" : "dark";
    const follow = next === (sys.matches ? "dark" : "light");
    if (follow) delete root.dataset.theme; else root.dataset.theme = next;
    try { follow ? localStorage.removeItem(KEY) : localStorage.setItem(KEY, next); } catch { /* storage off */ }
    paint();
  });
  sys.addEventListener?.("change", paint);
  paint();
})();
