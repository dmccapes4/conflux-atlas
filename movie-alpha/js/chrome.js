import { state, frame } from "./state.js";
import { renderDataGrid } from "./data-view.js";
import { renderSources } from "./sources-view.js";

export function switchView(name) {
  state.view = name;
  document.querySelectorAll(".tab").forEach((t) => {
    const on = t.dataset.view === name;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", on ? "true" : "false");
  });
  document.querySelectorAll(".view").forEach((v) => {
    v.classList.toggle("active", v.dataset.view === name);
  });
  if (name === "data") renderDataGrid();
  if (name === "sources") renderSources();
}

export function setSpeedUI(speed) {
  state.speed = speed;
  document.querySelectorAll(".speed-btn").forEach((b) => {
    b.classList.toggle("active", Number(b.dataset.speed) === speed);
  });
}

export function syncChrome() {
  const slider = document.getElementById("year-slider");
  const readout = document.getElementById("year-readout");
  if (slider) slider.value = String(state.year);
  if (readout) readout.textContent = String(state.year);
  if (state.view === "data") renderDataGrid();
  if (state.selectedPolity && state.view === "data") {
    // refresh open drawer numbers
    const n = frame()?.nodes[state.selectedPolity];
    if (n) {
      document.getElementById("detail-blurb").textContent =
        `Cold readout at ${state.year}. Shares held from last cited anchor ≤ year; population may overlay WPP/OWID. ` +
        `Sources: ${(n.sources || []).join(", ") || "—"}.`;
    }
  }
}

export function placeEventTicks() {
  const ticks = document.getElementById("event-ticks");
  const a = state.atlas;
  if (!ticks || !a) return;
  const ymin = a.meta.year_min;
  const ymax = a.meta.year_max;
  ticks.innerHTML = (a.events || [])
    .map((e) => {
      const pct = ((e.year - ymin) / (ymax - ymin)) * 100;
      return `<div class="tick" style="left:${pct}%" title="${e.year}: ${e.title}"></div>`;
    })
    .join("");
}
