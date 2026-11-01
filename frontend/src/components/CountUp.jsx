import { useEffect, useRef, useState } from 'react';
import { hasIO, reduceMotion } from '../hooks/useMedia.js';

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

// Number that counts up from 0 the first time it scrolls into view.
export default function CountUp({ value }) {
  const ref = useRef(null);
  const decimals = (String(value).split('.')[1] || '').length;
  const fmt = (n) => n.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  const [text, setText] = useState(fmt(Number(value)));

  useEffect(() => {
    if (reduceMotion || !hasIO || !ref.current) return undefined;
    let raf = 0;
    let cancelled = false;
    setText('0');
    const run = () => {
      const to = Number(value);
      let t0 = 0;
      const step = (ts) => {
        if (cancelled) return;
        if (!t0) t0 = ts;
        const p = clamp((ts - t0) / 1100, 0, 1);
        setText(fmt(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    };
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) { io.disconnect(); run(); }
    }, { threshold: 0.6 });
    io.observe(ref.current);
    return () => { cancelled = true; cancelAnimationFrame(raf); io.disconnect(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return <span ref={ref}>{text}</span>;
}
