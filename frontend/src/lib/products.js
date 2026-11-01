import { useCallback, useEffect, useReducer, useState } from 'react';
import { boot } from '../boot.js';
import { api } from './api.js';

const FRESH_MS = 30_000;
const cache = new Map(); // slug -> { data, at }
if (boot.product) cache.set(boot.product.slug, { data: boot.product, at: Date.now() });

// Product data for a landing page: instant from the boot data / cache, refreshed in the background.
export function useProduct(slug) {
  const [, rerender] = useReducer((x) => x + 1, 0);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const r = await api.get(`/api/products/${encodeURIComponent(slug)}`);
      if (r.ok) {
        cache.set(slug, { data: r.json, at: Date.now() });
        setError(null);
      } else {
        setError(r.status === 404 ? 'notfound' : 'error');
      }
    } catch {
      setError('error');
    }
    rerender();
  }, [slug]);

  useEffect(() => {
    const hit = cache.get(slug);
    if (!hit || Date.now() - hit.at > FRESH_MS) refresh();
  }, [slug, refresh]);

  return { product: cache.get(slug)?.data ?? null, error, refresh };
}
