import { state, setYear } from "./state.js";
import { drawMap, indexWorld } from "./map.js";
import { closeDetail, toggleShowAll } from "./data-view.js";
import { resetSettlement, advanceSettlement } from "./sources-view.js";
import { initNarration, stopSpeak } from "./narration.js";
import { runTour, stopTour, pauseTour, resumeTour } from "./tour.js";
import { switchView, syncChrome, setSpeedUI, placeEventTicks } from "./chrome.js";

let lastTick = 0;
let acc = 0;

async function boot() {
  initNarration();
  const [atlasRes, worldRes] = await Promise.all([
    fetch("data/atlas.json"),
    fetch("assets/world_frame.json"),
  ]);
  if (!atlasRes.ok) throw new Error("Failed to load data/atlas.json — run: make movie-alpha-export");
  if (!worldRes.ok) throw new Error("Failed to load assets/world_frame.json — run: make movie-alpha-basemap");
  state.atlas = await atlasRes.json();
  state.world = await worldRes.json();
  indexWorld();
  state.year = state.atlas.meta.year_min;

  const slider = document.getElementById("year-slider");
  slider.min = state.atlas.meta.year_min;
  slider.max = state.atlas.meta.year_max;
  slider.value = state.year;
  placeEventTicks();
  syncChrome();
  resetSettlement();

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      if (state.tourActive && !state.tourPaused) pauseTour(); // tab = free scrub
      switchView(tab.dataset.view);
    });
  });

  // Scrub during tour = pause tour, keep it resumable (§9.6)
  slider.addEventListener("input", () => {
    if (state.tourActive && !state.tourPaused) pauseTour();
    setYear(Number(slider.value));
    state.playing = false;
    document.getElementById("btn-play").textContent = "Play";
    syncChrome();
  });

  document.getElementById("btn-play").addEventListener("click", () => {
    if (state.tourActive) return; // transport belongs to the tour while active
    state.playing = !state.playing;
    document.getElementById("btn-play").textContent = state.playing ? "Pause" : "Play";
  });

  document.querySelectorAll(".speed-btn").forEach((b) => {
    b.addEventListener("click", () => setSpeedUI(Number(b.dataset.speed)));
  });

  document.getElementById("btn-mute").addEventListener("click", () => {
    state.muted = !state.muted;
    document.getElementById("btn-mute").textContent = state.muted ? "Voice off" : "Voice on";
    if (state.muted) stopSpeak();
  });

  document.getElementById("btn-tour").addEventListener("click", () => {
    if (state.tourActive) {
      stopTour();
      document.getElementById("btn-tour").textContent = "Start tour";
      return;
    }
    document.getElementById("btn-tour").textContent = "Stop tour";
    runTour().finally(() => {
      document.getElementById("btn-tour").textContent = "Replay tour";
    });
  });

  document.getElementById("btn-tour-pause").addEventListener("click", () => {
    if (!state.tourActive) return;
    if (state.tourPaused) resumeTour();
    else pauseTour();
  });

  document.getElementById("btn-show-all")?.addEventListener("click", toggleShowAll);
  document.getElementById("drawer-close")?.addEventListener("click", closeDetail);

  window.addEventListener("keydown", (e) => {
    if (e.key === " " && !state.tourActive) {
      e.preventDefault();
      state.playing = !state.playing;
      document.getElementById("btn-play").textContent = state.playing ? "Pause" : "Play";
    }
    if (e.key === "n" && state.view === "sources" && !state.tourActive) {
      advanceSettlement();
    }
    if (e.key === "r" && state.view === "sources" && !state.tourActive) {
      resetSettlement();
    }
  });

  requestAnimationFrame(loop);
}

function loop(ts) {
  const dt = lastTick ? ts - lastTick : 16;
  lastTick = ts;

  if (state.playing && !state.tourActive && state.atlas) {
    acc += dt * state.speed * 0.012; // ~years per ms at 1×
    if (acc >= 1) {
      const steps = Math.floor(acc);
      acc -= steps;
      setYear(state.year + steps);
      if (state.year >= state.atlas.meta.year_max) {
        state.playing = false;
        document.getElementById("btn-play").textContent = "Play";
      }
      syncChrome();
    }
  }

  if (state.view === "map") {
    drawMap(document.getElementById("map-canvas"));
  }

  requestAnimationFrame(loop);
}

boot().catch((err) => {
  document.getElementById("narration-text").textContent = String(err);
  console.error(err);
});
