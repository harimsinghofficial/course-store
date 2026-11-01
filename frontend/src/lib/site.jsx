import { createContext, useContext, useEffect, useState } from 'react';
import { boot } from '../boot.js';
import { api } from './api.js';

const SiteContext = createContext(null);

// Site-wide settings: from the server-embedded boot data, or fetched once when that is missing (dev server).
export function SiteProvider({ children }) {
  const [data, setData] = useState(boot.site ? boot : null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (data) return;
    api.get('/api/site').then((r) => (r.ok ? setData(r.json) : setFailed(true))).catch(() => setFailed(true));
  }, [data]);

  if (failed) return <p style={{ padding: '2rem' }}>Could not load the store. Please refresh.</p>;
  if (!data) return null;
  return <SiteContext.Provider value={data}>{children}</SiteContext.Provider>;
}

export function useSite() {
  return useContext(SiteContext);
}
