import { useEffect, useRef } from 'react';
import { cssVar } from '../lib/theme.js';
import { hasIO, reduceMotion } from '../hooks/useMedia.js';

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

// The hero word is sampled into thousands of particles that assemble, repel from the pointer,
// burst on click and disperse as you scroll. Pauses off-screen / in background tabs; static with reduced motion.
export default function ParticleWord({ word, heroRef }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const hero = heroRef.current;
    if (!canvas || !hero || !canvas.getContext) return undefined;
    const ctx = canvas.getContext('2d');
    const text = (word || 'NEW').toUpperCase();
    const inkColor = cssVar('--hero-ink', '#fff');
    const accColor = cssVar('--accent', '#ffd60a');
    let W = 0; let H = 0; let P = []; let rafId = 0; let visible = true; let built = false;
    let disperse = 0; let startTs = 0; let lastTs = 0; let builtW = 0; let builtH = 0;
    let disposed = false;
    const pointer = { x: -1e4, y: -1e4 };

    function build(quick) {
      const r = canvas.getBoundingClientRect();
      W = Math.max(1, Math.floor(r.width));
      H = Math.max(1, Math.floor(r.height));
      builtW = W; builtH = H;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(W * dpr);
      canvas.height = Math.floor(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const off = document.createElement('canvas');
      off.width = W; off.height = H;
      const o = off.getContext('2d', { willReadFrequently: true });
      const fam = '"Display", system-ui, sans-serif';
      o.font = `800 200px ${fam}`;
      const measured = o.measureText(text).width || 1;
      const size = Math.min((200 * (W * 0.94)) / measured, H * 0.66);
      o.font = `800 ${size.toFixed(1)}px ${fam}`;
      o.textAlign = 'center'; o.textBaseline = 'middle'; o.fillStyle = '#000';
      o.fillText(text, W / 2, H / 2 + size * 0.04);
      const data = o.getImageData(0, 0, W, H).data;

      let count = 0;
      for (let y = 0; y < H; y += 3) for (let x = 0; x < W; x += 3) if (data[(y * W + x) * 4 + 3] > 128) count++;
      const maxParticles = W < 520 ? 1100 : 2400;
      const step = Math.max(3, Math.ceil(Math.sqrt((count * 9) / maxParticles)));

      P = [];
      const cx = W / 2; const cy = H / 2; const reach = Math.max(W, H);
      for (let y = 0; y < H; y += step) {
        for (let x = 0; x < W; x += step) {
          if (data[(y * W + x) * 4 + 3] <= 128) continue;
          const bx = x + (Math.random() - 0.5) * step * 0.6;
          const by = y + (Math.random() - 0.5) * step * 0.6;
          const a = Math.random() * Math.PI * 2;
          const rad = reach * (0.6 + Math.random() * 0.5);
          const sa = Math.random() * Math.PI * 2;
          const sr = reach * (0.15 + Math.random() * 0.35);
          P.push({
            x: reduceMotion ? bx : cx + Math.cos(a) * rad, y: reduceMotion ? by : cy + Math.sin(a) * rad * 0.7,
            vx: 0, vy: 0, bx, by, sx: Math.cos(sa) * sr, sy: Math.sin(sa) * sr,
            d: quick ? Math.random() * 0.25 : Math.random() * 0.7 + (bx / W) * 0.5,
            s: step * (0.62 + Math.random() * 0.4), acc: Math.random() < 0.13, ph: Math.random() * 6.283,
          });
        }
      }
      built = true;
      startTs = 0;
    }

    function draw() {
      ctx.clearRect(0, 0, W, H);
      const n = P.length;
      ctx.fillStyle = inkColor;
      for (let i = 0; i < n; i++) { const p = P[i]; if (!p.acc) ctx.fillRect(p.x - p.s / 2, p.y - p.s / 2, p.s, p.s); }
      ctx.fillStyle = accColor;
      for (let i = 0; i < n; i++) { const p = P[i]; if (p.acc) ctx.fillRect(p.x - p.s / 2, p.y - p.s / 2, p.s, p.s); }
    }

    function frame(ts) {
      rafId = 0;
      if (disposed || !visible || document.hidden || !built) return;
      if (!startTs) { startTs = ts; lastTs = ts; }
      const t = (ts - startTs) / 1000;
      const dt = clamp((ts - lastTs) / 16.667, 0.3, 2.5);
      lastTs = ts;

      const hr = hero.getBoundingClientRect();
      const target = clamp(-hr.top / (hr.height * 0.75), 0, 1);
      disperse += (target - disperse) * Math.min(1, 0.14 * dt);

      const R = clamp(W * 0.14, 56, 112); const R2 = R * R;
      const fr = Math.pow(0.86, dt); const n = P.length;
      for (let i = 0; i < n; i++) {
        const p = P[i];
        if (t < p.d) continue;
        const tx = p.bx + p.sx * disperse + Math.sin(t * 1.3 + p.ph) * 1.2;
        const ty = p.by + p.sy * disperse + Math.cos(t * 1.1 + p.ph) * 1.2;
        p.vx += (tx - p.x) * 0.034 * dt;
        p.vy += (ty - p.y) * 0.034 * dt;
        const dx = p.x - pointer.x; const dy = p.y - pointer.y; const d2 = dx * dx + dy * dy;
        if (d2 < R2 && d2 > 0.01) {
          const d = Math.sqrt(d2); let f = 1 - d / R;
          f = f * f * 3.4 * dt;
          p.vx += (dx / d) * f * 3 - (dy / d) * f * 1.3;
          p.vy += (dy / d) * f * 3 + (dx / d) * f * 1.3;
        }
        p.vx *= fr; p.vy *= fr;
        p.x += p.vx * dt; p.y += p.vy * dt;
      }
      draw();
      rafId = requestAnimationFrame(frame);
    }

    const play = () => { if (!reduceMotion && !rafId && visible && !document.hidden && !disposed) rafId = requestAnimationFrame(frame); };
    const pointerPos = (e) => { const r = canvas.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    const onMove = (e) => { const q = pointerPos(e); pointer.x = q.x; pointer.y = q.y; };
    const onLeave = () => { pointer.x = -1e4; pointer.y = -1e4; };
    const onDown = (e) => {
      const q = pointerPos(e);
      if (q.x < 0 || q.y < 0 || q.x > W || q.y > H) return;
      for (let i = 0; i < P.length; i++) {
        const p = P[i]; const dx = p.x - q.x; const dy = p.y - q.y; const d = Math.sqrt(dx * dx + dy * dy) || 1;
        if (d < 280) { const f = (1 - d / 280) * 24; p.vx += (dx / d) * f; p.vy += (dy / d) * f; }
      }
    };
    if (!reduceMotion) {
      hero.addEventListener('pointermove', onMove, { passive: true });
      hero.addEventListener('pointerleave', onLeave);
      hero.addEventListener('pointerdown', onDown, { passive: true });
    }

    let io;
    if (hasIO) {
      io = new IntersectionObserver((entries) => { visible = entries[0].isIntersecting; if (visible) play(); }, { threshold: 0 });
      io.observe(hero);
    }
    document.addEventListener('visibilitychange', play);

    let resizeTimer = 0;
    const onResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        const r = canvas.getBoundingClientRect();
        if (Math.abs(r.width - builtW) > 24 || Math.abs(r.height - builtH) > 70) {
          build(true);
          if (reduceMotion) draw(); else play();
        }
      }, 220);
    };
    let ro;
    if ('ResizeObserver' in window) { ro = new ResizeObserver(onResize); ro.observe(canvas); } else window.addEventListener('resize', onResize);

    const fontReady = document.fonts && document.fonts.load
      ? Promise.race([document.fonts.load('800 100px Display'), new Promise((res) => setTimeout(res, 1500))])
      : Promise.resolve();
    fontReady.then(() => {
      if (disposed) return;
      build(false);
      if (reduceMotion) draw(); else play();
    });

    return () => {
      disposed = true;
      cancelAnimationFrame(rafId);
      clearTimeout(resizeTimer);
      hero.removeEventListener('pointermove', onMove);
      hero.removeEventListener('pointerleave', onLeave);
      hero.removeEventListener('pointerdown', onDown);
      document.removeEventListener('visibilitychange', play);
      window.removeEventListener('resize', onResize);
      if (io) io.disconnect();
      if (ro) ro.disconnect();
    };
  }, [word, heroRef]);

  return <canvas ref={canvasRef} id="hero-canvas" aria-hidden="true" />;
}
