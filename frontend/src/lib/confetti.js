import { cssVar } from './theme.js';
import { reduceMotion } from '../hooks/useMedia.js';

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

// One-shot celebratory burst on a throwaway full-screen canvas.
export function confetti() {
  if (reduceMotion) return;
  const c = document.createElement('canvas');
  c.className = 'confetti';
  c.setAttribute('aria-hidden', 'true');
  document.body.appendChild(c);
  const ctx = c.getContext('2d');
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = (c.width = Math.floor(window.innerWidth * dpr));
  const h = (c.height = Math.floor(window.innerHeight * dpr));
  const colors = [cssVar('--accent', '#ffd60a'), cssVar('--hero-bg', '#2b2bff'), cssVar('--ink', '#12123a'), '#ffffff'];
  const bits = [];
  for (let i = 0; i < 160; i++) {
    const a = -Math.PI / 2 + (Math.random() - 0.5) * 1.5;
    const sp = (9 + Math.random() * 13) * dpr;
    bits.push({
      x: w / 2, y: h * 0.62, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, r: Math.random() * 6.28,
      vr: (Math.random() - 0.5) * 0.4, w: (6 + Math.random() * 8) * dpr, h: (3 + Math.random() * 5) * dpr, c: colors[i % colors.length],
    });
  }
  let t0 = 0;
  const loop = (ts) => {
    if (!t0) t0 = ts;
    const age = (ts - t0) / 1000;
    ctx.clearRect(0, 0, w, h);
    bits.forEach((b) => {
      b.vy += 0.38 * dpr;
      b.vx *= 0.992;
      b.x += b.vx;
      b.y += b.vy;
      b.r += b.vr;
      ctx.save();
      ctx.translate(b.x, b.y);
      ctx.rotate(b.r);
      ctx.globalAlpha = clamp(1 - (age - 1.6) / 1.2, 0, 1);
      ctx.fillStyle = b.c;
      ctx.fillRect(-b.w / 2, -b.h / 2, b.w, b.h);
      ctx.restore();
    });
    if (age < 2.9) requestAnimationFrame(loop);
    else c.remove();
  };
  requestAnimationFrame(loop);
}
