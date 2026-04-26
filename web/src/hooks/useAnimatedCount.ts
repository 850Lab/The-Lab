import { useEffect, useState } from "react";

const easeOutQuad = (t: number) => 1 - (1 - t) * (1 - t);

/**
 * Animates from 0 toward `target` over `durationMs`. Subtle, for stat lines only.
 */
export function useAnimatedCount(
  target: number,
  durationMs = 650,
  run: boolean = true,
): number {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!run) {
      setValue(target);
      return;
    }
    if (target <= 0) {
      setValue(0);
      return;
    }
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const n = Math.round(easeOutQuad(t) * target);
      setValue(n);
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        setValue(target);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs, run]);

  return value;
}
