export const DEFAULT_THEME = {
  hero_bg: '#2B2BFF',
  hero_ink: '#FFFFFF',
  accent: '#FFD60A',
  accent_ink: '#12123A',
  paper: '#F4F3FF',
  ink: '#12123A',
  muted: '#54547A',
};

const toVar = (key) => `--${key.replace(/_/g, '-')}`;

// Colours are plain CSS variables on <html>; the server already wrote the same values into <head>,
// this keeps them right when React navigates between products without a page load.
export function applyTheme(theme) {
  const t = { ...DEFAULT_THEME, ...(theme || {}) };
  const root = document.documentElement;
  Object.keys(DEFAULT_THEME).forEach((k) => root.style.setProperty(toVar(k), t[k]));
  setMeta('theme-color', t.hero_bg);
}

export function cssVar(name, fallback) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

export function setMeta(name, content) {
  let el = document.head.querySelector(`meta[name="${name}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute('name', name);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}
