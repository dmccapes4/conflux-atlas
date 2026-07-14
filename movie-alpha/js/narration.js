/** Lightweight Feynman-style narration via Web Speech API (prefer male voice). */

let current = null;
let preferredVoice = null;

function pickVoice() {
  const voices = speechSynthesis.getVoices();
  if (!voices.length) return null;
  const prefer = [
    /daniel/i,
    /google uk english male/i,
    /microsoft (david|mark|guy)/i,
    /male/i,
    /en-gb/i,
    /en-us/i,
  ];
  for (const re of prefer) {
    const v = voices.find((x) => re.test(x.name) || re.test(x.lang));
    if (v) return v;
  }
  return voices.find((v) => v.lang.startsWith("en")) || voices[0];
}

export function initNarration() {
  if (!("speechSynthesis" in window)) return;
  preferredVoice = pickVoice();
  speechSynthesis.onvoiceschanged = () => {
    preferredVoice = pickVoice();
  };
}

export function speak(text, { muted = false, rate = 0.95 } = {}) {
  stopSpeak();
  if (muted || !text || !("speechSynthesis" in window)) return Promise.resolve();
  return new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(text);
    u.rate = rate;
    u.pitch = 0.9;
    u.volume = 1;
    if (preferredVoice) u.voice = preferredVoice;
    u.onend = () => {
      current = null;
      resolve();
    };
    u.onerror = () => {
      current = null;
      resolve();
    };
    current = u;
    speechSynthesis.speak(u);
  });
}

export function stopSpeak() {
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  current = null;
}

export function setNarrationUI(phase, text, math = null) {
  const phaseEl = document.getElementById("phase-label");
  const textEl = document.getElementById("narration-text");
  const panel = document.getElementById("math-panel");
  const title = document.getElementById("math-title");
  const body = document.getElementById("math-body");
  if (phaseEl) phaseEl.textContent = phase;
  if (textEl) textEl.innerHTML = text;
  if (math && panel) {
    panel.classList.remove("hidden");
    title.textContent = math.title || "Math";
    body.textContent = math.body || "";
  } else if (panel) {
    panel.classList.add("hidden");
  }
}
