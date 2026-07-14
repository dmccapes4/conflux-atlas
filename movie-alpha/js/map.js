import { state, frame } from "./state.js";

/**
 * Real-geography map (PLAN_MOVIE_ALPHA §3.2 / §9).
 * Layers: ocean → out-of-scope land under grey veil → in-scope polities
 * (confidence fill, gamma RGB stroke, velocity pulse) → beacon halos →
 * active migration arcs (draw-on) → labels → diaspora chips → outro fade.
 */

const GROUP_RGB = {
  muslim: [196, 68, 68],
  christian: [74, 168, 120],
  jewish: [72, 140, 200],
  unaffiliated: [120, 130, 140],
  other: [150, 110, 170],
};

// Countries whose polygons are in-frame; US/Canada come from chips.
let chipUV = {}; // polity_id -> [u, v]
let polityCountry = {}; // polity_id -> country record
let arcBirth = {}; // edge id -> first-seen ms (draw-on sweep)

export function indexWorld() {
  const w = state.world;
  if (!w) return;
  polityCountry = {};
  for (const c of w.countries) {
    if (c.polity_id) polityCountry[c.polity_id] = c;
  }
  chipUV = {};
  for (const chip of w.chips || []) chipUV[chip.polity_id] = chip.uv;
}

export function anchorUV(polityId) {
  if (polityCountry[polityId]) return polityCountry[polityId].label_uv;
  return chipUV[polityId] || null;
}

function fit(canvas) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const cw = canvas.clientWidth;
  const ch = canvas.clientHeight;
  if (canvas.width !== Math.floor(cw * dpr) || canvas.height !== Math.floor(ch * dpr)) {
    canvas.width = Math.floor(cw * dpr);
    canvas.height = Math.floor(ch * dpr);
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  // letterbox the frame's true aspect inside the canvas
  const aspect = state.world?.aspect || 1.34;
  let w = cw;
  let h = cw / aspect;
  if (h > ch) {
    h = ch;
    w = ch * aspect;
  }
  const ox = (cw - w) / 2;
  const oy = (ch - h) / 2;
  return { ctx, cw, ch, ox, oy, w, h };
}

function px(uv, m) {
  return [m.ox + uv[0] * m.w, m.oy + uv[1] * m.h];
}

function tracePath(ctx, rings, m) {
  ctx.beginPath();
  for (const ring of rings) {
    ring.forEach((uv, i) => {
      const [x, y] = px(uv, m);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
  }
}

function activeEvent() {
  return (state.atlas.events || []).find(
    (e) => state.year >= e.year && state.year <= (e.year_end || e.year + 3)
  );
}

export function drawMap(canvas) {
  if (!state.atlas || !state.world) return;
  const m = fit(canvas);
  const { ctx, cw, ch } = m;
  const fr = frame();
  if (!fr) return;
  const now = performance.now();
  const greyout = state.greyout; // 0 → world lit; 1 → out-of-scope dimmed
  const fade = state.outro ? Math.max(0.06, 1 - state.darken) : 1;

  // Ocean
  ctx.fillStyle = "#0a1118";
  ctx.fillRect(0, 0, cw, ch);

  // Out-of-scope land (under the grey veil)
  const dim = 0.42 - 0.3 * greyout;
  for (const c of state.world.countries) {
    if (c.polity_id) continue;
    tracePath(ctx, c.rings, m);
    ctx.fillStyle = `rgba(52, 62, 70, ${dim * fade})`;
    ctx.fill();
    ctx.strokeStyle = `rgba(70, 82, 92, ${(0.25 - 0.15 * greyout) * fade})`;
    ctx.lineWidth = 0.6;
    ctx.stroke();
  }

  const ev = activeEvent();
  const evPolities = new Set(ev ? ev.polities || [] : []);

  // In-scope polities
  for (const [id, c] of Object.entries(polityCountry)) {
    const n = fr.nodes[id];
    tracePath(ctx, c.rings, m);
    if (!n) {
      ctx.fillStyle = `rgba(60, 72, 82, ${0.35 * fade})`;
      ctx.fill();
      continue;
    }
    const conf = Math.max(0.2, n.confidence);
    const [r, g, b] = n.rgb.map((v) => Math.round(v * 255));

    // Beacon halo first (under the fill's own stroke)
    if (evPolities.has(id)) {
      const halo = 0.5 + 0.5 * Math.sin(now * 0.005);
      ctx.save();
      ctx.shadowColor = `rgba(226, 184, 106, ${0.85 * halo * fade})`;
      ctx.shadowBlur = 18;
      ctx.strokeStyle = `rgba(226, 184, 106, ${0.55 * halo * fade})`;
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.restore();
      tracePath(ctx, c.rings, m);
    }

    // Fill: RGB mix, opacity ∝ confidence (outro desaturates to charcoal)
    if (state.outro) {
      const k = state.darken;
      ctx.fillStyle = `rgba(${Math.round(r * (1 - k) + 40 * k)}, ${Math.round(
        g * (1 - k) + 44 * k
      )}, ${Math.round(b * (1 - k) + 48 * k)}, ${0.1 + 0.24 * conf})`;
    } else {
      ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${(0.1 + 0.24 * conf) * fade})`;
    }
    ctx.fill();

    // Stroke: gamma RGB; width breathes with velocity + |net migration|
    const pulse =
      1 +
      Math.min(0.9, n.velocity * 14 + Math.min(0.45, Math.abs(n.net_migration) / 8e5)) *
        (0.5 + 0.5 * Math.sin(now * 0.004 + id.length));
    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${(0.55 + 0.4 * conf) * fade})`;
    ctx.lineWidth = 1.1 * pulse + 0.4;
    ctx.stroke();
  }

  // Active migration arcs (draw-on when the edge first activates)
  const liveIds = new Set();
  for (const e of fr.edges) {
    if (e.alpha < 0.05) continue;
    const a = anchorUV(e.from);
    const b = anchorUV(e.to);
    if (!a || !b) continue;
    liveIds.add(e.id);
    if (!(e.id in arcBirth)) arcBirth[e.id] = now;
    const sweep = Math.min(1, (now - arcBirth[e.id]) / 900);

    const [ax, ay] = px(a, m);
    const [bx, by] = px(b, m);
    const mx = (ax + bx) / 2;
    const my = (ay + by) / 2 - 26 - Math.min(70, Math.log10(e.volume + 10) * 10);
    const col = GROUP_RGB[e.group] || [180, 180, 180];

    ctx.beginPath();
    const steps = 32;
    const tEnd = sweep;
    for (let i = 0; i <= steps; i++) {
      const t = (i / steps) * tEnd;
      const x = (1 - t) * (1 - t) * ax + 2 * (1 - t) * t * mx + t * t * bx;
      const y = (1 - t) * (1 - t) * ay + 2 * (1 - t) * t * my + t * t * by;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = `rgba(${col[0]}, ${col[1]}, ${col[2]}, ${(0.2 + 0.5 * e.alpha) * fade})`;
    ctx.lineWidth = 1 + Math.min(5, Math.log10(e.volume + 10) - 1);
    ctx.stroke();

    // moving head dot while sweeping
    if (sweep < 1) {
      const t = tEnd;
      const x = (1 - t) * (1 - t) * ax + 2 * (1 - t) * t * mx + t * t * bx;
      const y = (1 - t) * (1 - t) * ay + 2 * (1 - t) * t * my + t * t * by;
      ctx.beginPath();
      ctx.arc(x, y, 2.6, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${col[0]}, ${col[1]}, ${col[2]}, ${0.9 * fade})`;
      ctx.fill();
    }
  }
  for (const id of Object.keys(arcBirth)) {
    if (!liveIds.has(id)) delete arcBirth[id];
  }

  // Labels (population-scaled, in-scope only)
  const maxPop = Math.max(...Object.values(fr.nodes).map((n) => n.pop), 1);
  ctx.textAlign = "center";
  for (const [id, c] of Object.entries(polityCountry)) {
    const n = fr.nodes[id];
    if (!n) continue;
    const [x, y] = px(c.label_uv, m);
    const size = Math.max(8.5, Math.min(14, 8 + 7 * Math.sqrt(n.pop / maxPop)));
    ctx.font = `600 ${size}px Syne, sans-serif`;
    ctx.fillStyle = `rgba(10, 14, 18, 0.55)`;
    ctx.fillText(n.name, x + 1, y + 1);
    ctx.fillStyle = `rgba(232, 238, 244, ${0.85 * fade})`;
    ctx.fillText(n.name, x, y);
  }

  // Diaspora chips (off-frame nodes: US, Canada)
  for (const chip of state.world.chips || []) {
    const n = fr.nodes[chip.polity_id];
    if (!n) continue;
    const [x, y] = px(chip.uv, m);
    const [r, g, b] = n.rgb.map((v) => Math.round(v * 255));
    ctx.fillStyle = `rgba(16, 24, 32, ${0.85 * fade})`;
    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${0.9 * fade})`;
    ctx.lineWidth = 1.4;
    const cwd = 92;
    ctx.beginPath();
    ctx.roundRect(x - 10, y - 13, cwd, 26, 6);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(x + 2, y, 3.4, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${0.95 * fade})`;
    ctx.fill();
    ctx.textAlign = "left";
    ctx.font = "600 10px Syne, sans-serif";
    ctx.fillStyle = `rgba(232, 238, 244, ${0.9 * fade})`;
    ctx.fillText(chip.name, x + 10, y + 3.5);
    ctx.textAlign = "center";
  }

  // Attribution (tiny, honest)
  ctx.textAlign = "left";
  ctx.font = "9px IBM Plex Mono, monospace";
  ctx.fillStyle = "rgba(138, 154, 171, 0.45)";
  ctx.fillText("Basemap: Natural Earth (public domain)", 10, ch - 8);
  ctx.textAlign = "center";

  // HUD
  const hudYear = document.getElementById("hud-year");
  const hudEvent = document.getElementById("hud-event");
  if (hudYear) hudYear.textContent = String(state.year);
  if (hudEvent) hudEvent.textContent = ev ? ev.title : "steady hold · no active event window";
}
