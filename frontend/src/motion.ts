import { useEffect, useRef, useState, type CSSProperties } from "react";

export const reducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Stagger helper for the `.rise` entrance animation. */
export const delay = (ms: number) => ({ "--d": `${ms}ms` }) as CSSProperties;

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/** Animate a number from its previous value (0 at first) to `target`. */
export function useCountUp(target: number, duration = 900): number {
  const [value, setValue] = useState(() => (reducedMotion() ? target : 0));
  const current = useRef(value);
  useEffect(() => {
    const from = current.current;
    const start = performance.now();
    const instant = reducedMotion();
    let raf = requestAnimationFrame(function tick(now) {
      const t = instant ? 1 : Math.min(1, (now - start) / duration);
      current.current = from + (target - from) * easeOut(t);
      setValue(current.current);
      if (t < 1) raf = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return value;
}

/** False on the first frame, true after: lets CSS transitions animate from an initial state. */
export function useMounted(): boolean {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const raf = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(raf);
  }, []);
  return mounted;
}
