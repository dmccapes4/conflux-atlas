import { state } from "./state.js";

function shortName(hid) {
  return hid.replace(/^source_trust:/, "").replace(/^definition_gap:/, "gap:");
}

export function renderSources(snapshot = null) {
  const list = document.getElementById("sources-list");
  if (!list || !state.atlas) return;

  const posts = snapshot || deriveSnapshot();
  const entries = Object.entries(posts).sort((a, b) => b[1].mean - a[1].mean);

  list.innerHTML = entries
    .map(([id, p]) => {
      const pct = Math.round(p.mean * 100);
      return `<div class="source-row" data-id="${id}">
        <div class="name">${shortName(id)}</div>
        <div class="bar"><i style="width:${pct}%"></i></div>
        <div>E[θ]=${p.mean.toFixed(3)} · α=${p.alpha} β=${p.beta} · n=${p.trials ?? "—"}</div>
      </div>`;
    })
    .join("");

  drawBeta(posts);
}

function deriveSnapshot() {
  const tape = state.atlas.settlement_tape || [];
  if (state.settlementIndex >= 0 && tape[state.settlementIndex]) {
    return tape[state.settlementIndex].snapshot;
  }
  // Uniform priors — PLAN §3.4: five bars, not a research workstation
  const keys = Object.keys(tape[0]?.snapshot || state.atlas.trust_final || {});
  const out = {};
  for (const k of keys.slice(0, 5)) {
    out[k] = { alpha: 1, beta: 1, mean: 0.5, trials: 0 };
  }
  return out;
}

function drawBeta(posts) {
  const canvas = document.getElementById("beta-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.fillStyle = "#070b10";
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = "#1a2632";
  ctx.beginPath();
  ctx.moveTo(40, h - 30);
  ctx.lineTo(w - 20, h - 30);
  ctx.lineTo(w - 20, 20);
  ctx.stroke();

  const colors = ["#5cb8a8", "#d4a35c", "#c45c5c", "#488cc8", "#a878c8", "#8a9aab"];
  let ci = 0;
  for (const [id, p] of Object.entries(posts)) {
    const a = Math.max(0.5, p.alpha);
    const b = Math.max(0.5, p.beta);
    const col = colors[ci++ % colors.length];
    let maxY = 0;
    const pts = [];
    for (let i = 0; i <= 100; i++) {
      const x = i / 100;
      const y = betaPdf(x, a, b);
      pts.push([x, y]);
      maxY = Math.max(maxY, y);
    }
    ctx.beginPath();
    pts.forEach(([x, y], i) => {
      const px = 40 + x * (w - 70);
      const py = h - 30 - (y / (maxY || 1)) * (h - 60);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.strokeStyle = col;
    ctx.lineWidth = 2;
    ctx.stroke();

    // mean marker
    const mx = 40 + p.mean * (w - 70);
    ctx.fillStyle = col;
    ctx.fillRect(mx - 1, h - 30, 2, 6);
    ctx.font = "11px IBM Plex Mono";
    ctx.fillText(shortName(id).slice(0, 18), mx + 4, 28 + (ci % 5) * 12);
  }

  ctx.fillStyle = "#8a9aab";
  ctx.font = "12px IBM Plex Mono";
  ctx.fillText("θ (trust) →", w / 2 - 30, h - 8);
  ctx.fillText("Beta(α,β) densities", 48, 18);
}

function betaPdf(x, a, b) {
  if (x <= 0 || x >= 1) return 0;
  // unnormalized is fine for shape; use log-gamma approx via Stirling-ish for small ints
  return Math.pow(x, a - 1) * Math.pow(1 - x, b - 1);
}

export function advanceSettlement() {
  const tape = state.atlas?.settlement_tape || [];
  if (!tape.length) return null;
  state.settlementIndex = Math.min(tape.length - 1, state.settlementIndex + 1);
  const step = tape[state.settlementIndex];
  renderSources(step.snapshot);
  const feed = document.getElementById("settle-feed");
  if (feed) {
    const cls = step.success ? "hit" : "miss";
    const line = document.createElement("div");
    line.className = cls;
    line.textContent = `[${step.t}] ${step.success ? "HIT" : "MISS"} w=${step.weight}  ${shortName(step.hypothesis_id)} — ${step.note}`;
    feed.prepend(line);
  }
  const math = document.getElementById("settle-math");
  if (math) {
    math.textContent =
      `Settlement-only update (nakatomi rule):\n` +
      `  success:  α ← α + w\n` +
      `  failure:  β ← β + w\n` +
      `  E[θ] = α/(α+β)\n` +
      `This step: ${step.hypothesis_id}\n` +
      `  α=${step.alpha}  β=${step.beta}  E[θ]=${step.mean}\n` +
      `Claims may be recorded anytime; only settle() moves belief.`;
  }
  return step;
}

export function resetSettlement() {
  state.settlementIndex = -1;
  const feed = document.getElementById("settle-feed");
  if (feed) feed.innerHTML = "";
  renderSources();
  const math = document.getElementById("settle-math");
  if (math) {
    math.textContent =
      `Prior: θ ~ Beta(1,1)  ⇒  E[θ]=0.5\n` +
      `Nothing but a settled outcome may bump a posterior.`;
  }
}
