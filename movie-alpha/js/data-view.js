import { state, frame } from "./state.js";

const COLORS = {
  muslim: "#c44444",
  christian: "#4aa878",
  jewish: "#488cc8",
  rest: "#6a7580",
};

// PLAN §3.4: starve the data view — featured cards, "show all" on demand.
const FEATURED = [
  "egypt", "turkey", "iran", "israel", "lebanon", "syria", "saudi_arabia", "iraq",
];

export function toggleShowAll() {
  state.showAllData = !state.showAllData;
  const btn = document.getElementById("btn-show-all");
  if (btn) btn.textContent = state.showAllData ? "Featured only" : "Show all 28";
  renderDataGrid();
}

export function renderDataGrid() {
  const grid = document.getElementById("data-grid");
  const fr = frame();
  if (!grid || !fr) return;
  let nodes = Object.values(fr.nodes).sort((a, b) => b.pop - a.pop);
  if (!state.showAllData) {
    nodes = nodes.filter((n) => FEATURED.includes(n.id));
  }
  grid.innerHTML = nodes
    .map((n) => {
      const m = (n.shares.muslim || 0) * 100;
      const c = (n.shares.christian || 0) * 100;
      const j = (n.shares.jewish || 0) * 100;
      const r = Math.max(0, 100 - m - c - j);
      return `<article class="data-card" data-id="${n.id}">
        <h3>${n.name}</h3>
        <div class="meta">pop ${(n.pop / 1e6).toFixed(1)}M · conf ${n.confidence.toFixed(2)} · anchor ${n.anchor_year}</div>
        <div class="meta">M ${m.toFixed(1)}% · C ${c.toFixed(1)}% · J ${j.toFixed(1)}%</div>
        <div class="bar-row">
          <span style="width:${m}%;background:${COLORS.muslim}"></span>
          <span style="width:${c}%;background:${COLORS.christian}"></span>
          <span style="width:${j}%;background:${COLORS.jewish}"></span>
          <span style="width:${r}%;background:${COLORS.rest}"></span>
        </div>
      </article>`;
    })
    .join("");

  grid.querySelectorAll(".data-card").forEach((el) => {
    el.addEventListener("click", () => openDetail(el.dataset.id));
  });
}

export function openDetail(polityId) {
  state.selectedPolity = polityId;
  const drawer = document.getElementById("detail-drawer");
  const n = frame()?.nodes[polityId];
  if (!drawer || !n || !state.atlas) return;
  drawer.classList.remove("hidden");
  document.getElementById("detail-title").textContent = n.name;
  document.getElementById("detail-blurb").textContent =
    `Cold readout at ${state.year}. Shares held from last cited anchor ≤ year; population may overlay WPP/OWID. ` +
    `Sources: ${(n.sources || []).join(", ") || "—"}.`;

  const hist = document.getElementById("hist-canvas");
  const tl = document.getElementById("tl-canvas");
  drawShareBars(hist, n);
  drawTimeline(tl, polityId);
  document.getElementById("detail-math").textContent =
    `hold(shares, Y) = shares(anchor*) where anchor* = max { A : A.year ≤ Y }\n` +
    `confidence_bleed ≈ max(floor, conf₀ − ${0.004} · (Y − anchor_year))\n` +
    `outline_rgb = normalize( (m^γ, c^γ, j^γ) ), γ = 0.55\n` +
    `velocity = ‖Δshares‖₂ vs previous year frame`;
}

function drawShareBars(canvas, n) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.fillStyle = "#070b10";
  ctx.fillRect(0, 0, w, h);
  const keys = ["muslim", "christian", "jewish", "unaffiliated", "other"];
  const labels = { muslim: "Muslim", christian: "Christian", jewish: "Jewish", unaffiliated: "Unaff.", other: "Other" };
  keys.forEach((k, i) => {
    const v = n.shares[k] || 0;
    const y = 28 + i * 48;
    ctx.fillStyle = "#8a9aab";
    ctx.font = "14px IBM Plex Mono";
    ctx.fillText(labels[k], 16, y);
    ctx.fillStyle = "#1a2632";
    ctx.fillRect(120, y - 14, w - 150, 18);
    ctx.fillStyle = COLORS[k] || COLORS.rest;
    ctx.fillRect(120, y - 14, (w - 150) * v, 18);
    ctx.fillStyle = "#e8eef4";
    ctx.fillText(`${(v * 100).toFixed(2)}%`, w - 90, y);
  });
}

function drawTimeline(canvas, polityId) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.fillStyle = "#070b10";
  ctx.fillRect(0, 0, w, h);
  const ymin = state.atlas.meta.year_min;
  const ymax = state.atlas.meta.year_max;
  const series = [];
  for (let y = ymin; y <= ymax; y += 2) {
    const node = state.atlas.frames[String(y)]?.nodes[polityId];
    if (!node) continue;
    series.push({
      y,
      m: node.shares.muslim || 0,
      c: node.shares.christian || 0,
      j: node.shares.jewish || 0,
    });
  }
  const plot = (key, color) => {
    ctx.beginPath();
    series.forEach((p, i) => {
      const x = 40 + ((p.y - ymin) / (ymax - ymin)) * (w - 60);
      const yy = h - 30 - p[key] * (h - 50);
      if (i === 0) ctx.moveTo(x, yy);
      else ctx.lineTo(x, yy);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();
  };
  plot("m", COLORS.muslim);
  plot("c", COLORS.christian);
  plot("j", COLORS.jewish);

  // year cursor
  const cx = 40 + ((state.year - ymin) / (ymax - ymin)) * (w - 60);
  ctx.strokeStyle = "rgba(212,163,92,0.8)";
  ctx.beginPath();
  ctx.moveTo(cx, 10);
  ctx.lineTo(cx, h - 20);
  ctx.stroke();

  ctx.fillStyle = "#8a9aab";
  ctx.font = "12px IBM Plex Mono";
  ctx.fillText(`${ymin}`, 40, h - 8);
  ctx.fillText(`${ymax}`, w - 40, h - 8);
  ctx.fillText("share timelines (M/C/J)", 40, 16);
}

export function closeDetail() {
  document.getElementById("detail-drawer")?.classList.add("hidden");
  state.selectedPolity = null;
}
