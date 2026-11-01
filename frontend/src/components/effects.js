import { useEffect } from 'react';
import { canHover, reduceMotion } from '../hooks/useMedia.js';

// 3D tilt that follows the pointer (sets --rx/--ry, which the CSS turns into a perspective transform).
export function useTilt(ref) {
  useEffect(() => {
    const el = ref.current;
    if (!el || reduceMotion || !canHover) return undefined;
    const move = (e) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      el.classList.add('is-tilting');
      el.style.setProperty('--rx', `${(-py * 8).toFixed(2)}deg`);
      el.style.setProperty('--ry', `${(px * 10).toFixed(2)}deg`);
    };
    const leave = () => {
      el.classList.remove('is-tilting');
      el.style.setProperty('--rx', '0deg');
      el.style.setProperty('--ry', '0deg');
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerleave', leave);
    return () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerleave', leave);
    };
  }, [ref]);
}

// Button that leans toward the cursor when it is nearby.
export function useMagnetic(ref) {
  useEffect(() => {
    const el = ref.current;
    if (!el || reduceMotion || !canHover) return undefined;
    const reset = () => { el.style.setProperty('--mx', '0px'); el.style.setProperty('--my', '0px'); };
    const move = (e) => {
      const r = el.getBoundingClientRect();
      const dx = e.clientX - (r.left + r.width / 2);
      const dy = e.clientY - (r.top + r.height / 2);
      if (Math.hypot(dx, dy) < Math.max(r.width, 160) * 0.8) {
        el.style.setProperty('--mx', `${(dx * 0.2).toFixed(1)}px`);
        el.style.setProperty('--my', `${(dy * 0.28).toFixed(1)}px`);
      } else {
        reset();
      }
    };
    document.addEventListener('pointermove', move, { passive: true });
    return () => document.removeEventListener('pointermove', move);
  }, [ref]);
}
