/** Shared movie state. */
export const state = {
  atlas: null,
  world: null, // basemap slice (assets/world_frame.json)
  year: 1900,
  playing: false,
  speed: 1, // presets: 0.5 / 1 / 2 / 4
  view: "map",
  muted: false,
  tourActive: false,
  tourPaused: false, // free-scrub: tour frozen at current beat, resumable
  beatIndex: 0,
  selectedPolity: null,
  settlementIndex: -1,
  outro: false,
  darken: 0,
  greyout: 0, // 0 = world lit, 1 = out-of-scope fully veiled (breathes in)
  showAllData: false,
};

export function frame() {
  const a = state.atlas;
  if (!a) return null;
  return a.frames[String(state.year)] || null;
}

export function setYear(y) {
  const a = state.atlas;
  if (!a) return;
  state.year = Math.max(a.meta.year_min, Math.min(a.meta.year_max, Math.round(y)));
}
