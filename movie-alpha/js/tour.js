import { state, setYear } from "./state.js";
import { setNarrationUI, speak, stopSpeak } from "./narration.js";
import { switchView, syncChrome, setSpeedUI } from "./chrome.js";
import { resetSettlement, advanceSettlement } from "./sources-view.js";

/**
 * Beat-queue tour (PLAN_MOVIE_ALPHA §3.3 / §9.6).
 * - Scrubbing or "Pause tour" freezes between/inside beats; "Resume tour"
 *   continues from the same beat (state.beatIndex).
 * - Beacons are hard gates: Continue / Replay beacon (rewind ~8y).
 * - A silent watch cannot under-run: five gates require clicks.
 */

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function waitWhilePaused() {
  while (state.tourActive && state.tourPaused) await sleep(140);
}

export function pauseTour() {
  if (!state.tourActive || state.tourPaused) return;
  state.tourPaused = true;
  stopSpeak();
  const btn = document.getElementById("btn-tour-pause");
  if (btn) btn.textContent = "Resume tour";
  setNarrationUI("Paused — free scrub", "Scrub the timeline or switch tabs. <strong>Resume tour</strong> continues from this beat.", null);
}

export function resumeTour() {
  if (!state.tourActive || !state.tourPaused) return;
  state.tourPaused = false;
  const btn = document.getElementById("btn-tour-pause");
  if (btn) btn.textContent = "Pause tour";
}

/** Narrated line; re-speaks after a pause interrupts it. */
async function line(phase, html, voice, math = null, waitMs = 250) {
  while (state.tourActive) {
    await waitWhilePaused();
    if (!state.tourActive) return false;
    setNarrationUI(phase, html, math);
    await speak(voice, { muted: state.muted, rate: 0.94 });
    if (!state.tourPaused) break; // finished uninterrupted
  }
  if (waitMs) await sleep(waitMs / Math.max(0.5, state.speed));
  return state.tourActive;
}

/** Year sweep that respects pause (resumes from wherever the user scrubbed). */
async function animateYears(to, msPerYear) {
  while (state.tourActive && state.year !== to) {
    await waitWhilePaused();
    if (!state.tourActive) return;
    const step = state.year < to ? 1 : -1;
    setYear(state.year + step);
    syncChrome();
    await sleep(msPerYear / Math.max(0.5, state.speed));
  }
}

async function animateGreyout(target, ms) {
  const from = state.greyout;
  const t0 = performance.now();
  while (state.tourActive && performance.now() - t0 < ms) {
    const k = (performance.now() - t0) / ms;
    state.greyout = from + (target - from) * k;
    await sleep(30);
  }
  state.greyout = target;
}

/** Beacon gate: resolves "continue" or "replay". */
function gate() {
  return new Promise((resolve) => {
    const g = document.getElementById("gate");
    const btnC = document.getElementById("btn-continue");
    const btnR = document.getElementById("btn-replay");
    g.classList.remove("hidden");
    const finish = (v) => {
      g.classList.add("hidden");
      btnC.removeEventListener("click", onC);
      btnR.removeEventListener("click", onR);
      window.removeEventListener("keydown", onKey);
      clearInterval(watchdog);
      resolve(v);
    };
    const onC = () => finish("continue");
    const onR = () => finish("replay");
    const onKey = (e) => {
      if (e.key === " ") {
        e.preventDefault();
        finish("continue");
      }
    };
    btnC.addEventListener("click", onC);
    btnR.addEventListener("click", onR);
    window.addEventListener("keydown", onKey);
    const watchdog = setInterval(() => {
      if (!state.tourActive) finish("continue");
    }, 300);
  });
}

function buildBeats() {
  const beats = [];
  const B = (fn) => beats.push(fn);

  // 1 — problem (map frozen; grey veil breathes in mid-line)
  B(async () => {
    switchView("map");
    setYear(1900);
    syncChrome();
    const veilPromise = (async () => {
      await sleep(1500);
      await animateGreyout(1, 2200);
    })();
    await line(
      "1 · The problem",
      "This is a real map — Morocco to Iran, Europe down to the Sahel. Demographics here get argued endlessly, but almost nobody <em>keeps score</em>. Conflux Atlas tracks religious shares and migrations as claims that can be settled later. Everything outside our desk is fading to grey right now: out of scope, on purpose.",
      "This is a real map — Morocco to Iran, Europe down to the Sahel. Demographics here get argued endlessly, but almost nobody keeps score. Conflux Atlas tracks religious shares and migrations as claims that can be settled later. Everything outside our desk is fading to grey right now: out of scope, on purpose.",
      {
        title: "The problem",
        body: "Sparse cited snapshots ≠ continuous truth.\nYearly view = hold last anchor ≤ Y, uncertainty bleeds between anchors.",
      },
      600
    );
    await veilPromise;
  });

  // 2 — map language
  B(async () => {
    await line(
      "1 · How to read it",
      "Each country's outline mixes <strong>Muslim→red, Christian→green, Jewish→blue</strong> — Egypt reads red with a green trace; Israel reads blue. Fill brightness is <em>confidence</em>: bright means a recent citation, dull means we're holding an old anchor. Arcs are migrations. Two chips on the Atlantic edge stand in for the US and Canada.",
      "Each country's outline mixes Muslim to red, Christian to green, Jewish to blue. Egypt reads red with a green trace; Israel reads blue. Fill brightness is confidence: bright means a recent citation, dull means we are holding an old anchor. Arcs are migrations. Two chips on the Atlantic edge stand in for the United States and Canada.",
      null,
      400
    );
  });

  // 3 — dummy settlement
  B(async () => {
    await line(
      "1 · Keeping score",
      "Before the clock runs, the one mechanism that matters: a source claims “Egypt stays ≥90% Muslim through 2020.” Years later a census band arrives — hit or miss. Only then does that source's trust move. Recording a claim is free; <em>settlement</em> moves belief.",
      "Before the clock runs, the one mechanism that matters. A source claims Egypt stays at least ninety percent Muslim through twenty twenty. Years later a census band arrives — hit or miss. Only then does that source's trust move. Recording a claim is free; settlement moves belief.",
      {
        title: "Beta–Bernoulli trust",
        body: "Prior θ ~ Beta(1,1)\nHit:  α ← α + w\nMiss: β ← β + w\nTrust = E[θ] = α/(α+β)",
      },
      500
    );
  });

  // 4 — engine on
  B(async () => {
    await line(
      "2 · Engine on",
      "Starting the clock at 1900. Watch the fills dim between anchors — that's honesty, not a rendering bug.",
      "Starting the clock at nineteen hundred. Watch the fills dim between anchors — that's honesty, not a rendering bug.",
      null,
      200
    );
    await animateYears(1920, 100);
  });

  // 5 — data detour (one scene)
  B(async () => {
    switchView("data");
    await line(
      "3 · Data desk",
      "Same numbers, no map poetry. Featured polities at the current year: population, confidence, M/C/J shares. Click any card later for histograms and timelines. Cold and honest.",
      "Same numbers, no map poetry. Featured polities at the current year: population, confidence, and Muslim, Christian, Jewish shares. Click any card later for histograms and timelines. Cold and honest.",
      {
        title: "Hold model",
        body: "shares(Y) = shares(latest anchor ≤ Y)\nconfidence decays slowly without new citations",
      },
      900
    );
  });

  // 6 — sources detour (one scene + short tape)
  B(async () => {
    switchView("sources");
    resetSettlement();
    await line(
      "4 · The scorekeeper",
      "This screen is the ledger. Bars are trust posteriors per source. We'll replay a few settlements from the real tape — watch belief move only when outcomes land.",
      "This screen is the ledger. Bars are trust posteriors per source. We'll replay a few settlements from the real tape — watch belief move only when outcomes land.",
      {
        title: "Settlement rule",
        body: "record(claim) → ledger only\nsettle(outcome, w) → posterior bump\nw < 1 when evidence is partial or non-independent",
      },
      300
    );
    for (let i = 0; i < 6 && state.tourActive; i++) {
      await waitWhilePaused();
      const step = advanceSettlement();
      if (!step) break;
      setNarrationUI(
        "4 · Settling",
        `<span class="${step.success ? "hit" : "miss"}">${step.success ? "Hit" : "Miss"}</span> on <code>${step.hypothesis_id}</code> — ${step.note}`,
        { title: "Update", body: `${step.success ? "α" : "β"} ← +${step.weight}\nE[θ] = ${step.mean}` }
      );
      await sleep(1000 / Math.max(0.5, state.speed));
    }
    await line(
      "4 · Ledger",
      "Run this for enough census rounds and you don't just get estimates — you get a calibrated ledger of <em>who to believe</em> about demography.",
      "Run this for enough census rounds and you don't just get estimates — you get a calibrated ledger of who to believe about demography.",
      null,
      400
    );
  });

  // 7 — back to map, announce the walk
  B(async () => {
    switchView("map");
    await line(
      "5 · The beacon walk",
      "Back to the map for the part history remembers: five events, 1923 to 2011. The tour <strong>stops</strong> at each one — press <em>Continue</em> when you're ready, or <em>Replay beacon</em> to watch it again.",
      "Back to the map for the part history remembers: five events, nineteen twenty three to twenty eleven. The tour stops at each one — press Continue when you're ready, or Replay beacon to watch it again.",
      null,
      300
    );
  });

  // 8..12 — beacon gates
  const beacons = state.atlas.tour_beacons || [];
  for (const beat of beacons) {
    B(async () => {
      const approach = async (msPerYear) => {
        await animateYears(Math.max(state.atlas.meta.year_min, beat.year - 8), 60);
        await animateYears(beat.year, msPerYear);
      };
      await approach(170);
      for (;;) {
        if (!state.tourActive) return;
        await line(
          `5 · Beacon · ${beat.year}`,
          `<strong>${beat.title}</strong> — ${beat.blurb}`,
          `${beat.title}. ${beat.blurb}`,
          {
            title: "Event → movement",
            body: "Events open migration_burst edges.\nVolumes rewrite node totals/shares through the window.\nConfidence may reset where the desk goes dark.",
          },
          200
        );
        // linger a few years so the arcs and halo land
        await animateYears(Math.min(beat.year + 4, state.atlas.meta.year_max), 260);
        const verdict = await gate();
        if (verdict !== "replay") break;
        setYear(Math.max(state.atlas.meta.year_min, beat.year - 8));
        syncChrome();
        await approach(220);
      }
    });
  }

  // 13 — catch up
  B(async () => {
    await line(
      "5 · To the present",
      "Rolling forward to the present day.",
      "Rolling forward to the present day.",
      null,
      100
    );
    await animateYears(2020, 35);
  });

  // 14 — outro
  B(async () => {
    const veil = document.getElementById("outro-veil");
    veil?.classList.remove("hidden");
    state.outro = true;
    for (let i = 0; i <= 20 && state.tourActive; i++) {
      state.darken = i / 20;
      veil?.classList.toggle("on", i > 4);
      await sleep(110);
    }
    await line(
      "6 · Findings",
      "Alpha findings, said plainly: the map is a <em>view</em> over sparse citations, not a crystal ball. Shock windows hurt prediction accuracy. Settlement moves trust. Pre-1900 beacons are still library, not desk. And a miss on the 1975 prediction cut is still a result.",
      "Alpha findings, said plainly: the map is a view over sparse citations, not a crystal ball. Shock windows hurt prediction accuracy. Settlement moves trust. Pre-nineteen-hundred beacons are still library, not desk. And a miss on the nineteen seventy five prediction cut is still a result.",
      {
        title: "What held up",
        body: "Event deltas make migration visible.\nUNHCR stocks gave Syria→host edges (stocks ≠ flows).\nPhase 2b: calm hit ≈ 0.67 vs shock ≈ 0.48.\nShare desk still ~92% Pew — scarcity not cured yet.",
      },
      800
    );
    await line(
      "6 · Close",
      "That's the system in miniature. Scrub freely — Map, Data, Source weighting. Thank you for watching.",
      "That's the system in miniature. Scrub freely — Map, Data, and Source weighting. Thank you for watching.",
      null,
      200
    );
  });

  return beats;
}

export async function runTour() {
  stopSpeak();
  state.tourActive = true;
  state.tourPaused = false;
  state.beatIndex = 0;
  state.playing = false;
  state.outro = false;
  state.darken = 0;
  state.greyout = 0;
  document.getElementById("outro-veil")?.classList.add("hidden");
  document.getElementById("outro-veil")?.classList.remove("on");
  document.getElementById("btn-tour-pause")?.classList.remove("hidden");
  const speedBefore = state.speed;
  resetSettlement();

  const beats = buildBeats();
  while (state.tourActive && state.beatIndex < beats.length) {
    await waitWhilePaused();
    if (!state.tourActive) break;
    await beats[state.beatIndex]();
    state.beatIndex++;
  }

  state.tourActive = false;
  state.tourPaused = false;
  state.outro = false;
  state.darken = 0;
  state.speed = speedBefore;
  setSpeedUI(speedBefore);
  document.getElementById("outro-veil")?.classList.add("hidden");
  document.getElementById("outro-veil")?.classList.remove("on");
  document.getElementById("btn-tour-pause")?.classList.add("hidden");
  document.getElementById("gate")?.classList.add("hidden");
}

export function stopTour() {
  state.tourActive = false;
  state.tourPaused = false;
  stopSpeak();
  document.getElementById("btn-tour-pause")?.classList.add("hidden");
  document.getElementById("gate")?.classList.add("hidden");
}
