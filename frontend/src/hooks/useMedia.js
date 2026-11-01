import { useEffect, useState } from 'react';

// Read once at start-up; these do not change during a visit in practice.
export const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
export const canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
export const hasIO = 'IntersectionObserver' in window;

// True while the element is on screen. With `once`, stays true after the first time it is seen.
export function useInView(ref, { threshold = 0, once = false, initial = false } = {}) {
  const [inView, setInView] = useState(initial || !hasIO);
  useEffect(() => {
    const el = ref.current;
    if (!el || !hasIO) return undefined;
    const io = new IntersectionObserver(
      (entries) => {
        const seen = entries[entries.length - 1].isIntersecting;
        if (seen) {
          setInView(true);
          if (once) io.disconnect();
        } else if (!once) {
          setInView(false);
        }
      },
      { threshold },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [ref, threshold, once]);
  return inView;
}
