"use client";

import { useEffect, useState } from "react";

const DEFAULT_DURATION_MS = 800;

// Cubic ease-out — classic "land softly" curve.
function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

// Resolved once at module load (browser-only). Set to true on the server so
// SSR renders the final number; the effect doesn't run on the server anyway,
// so this is purely about getting a deterministic initial state for hydration.
const SKIP_ANIMATION =
  typeof window === "undefined" ||
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function useCountUp(
  target: number,
  durationMs: number = DEFAULT_DURATION_MS,
): number {
  // Lazy initial state — when we skip animation we land on `target` directly,
  // so the value never needs to be reassigned synchronously inside the effect
  // (which the react-hooks/set-state-in-effect rule would flag).
  const [value, setValue] = useState(() =>
    SKIP_ANIMATION || target <= 0 ? target : 0,
  );
  // Track target changes during render — if a new target arrives while we're
  // in skip-animation mode, snap to it without an effect.
  const [lastTarget, setLastTarget] = useState(target);
  if (lastTarget !== target) {
    setLastTarget(target);
    if (SKIP_ANIMATION || target <= 0) {
      setValue(target);
    }
  }

  useEffect(() => {
    if (SKIP_ANIMATION || target <= 0) return;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      setValue(Math.round(easeOutCubic(t) * target));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);

  return value;
}
