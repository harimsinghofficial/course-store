import { useCallback, useEffect, useState } from 'react';
import { SolidTopbar } from '../components/Chrome.jsx';
import { usePage } from '../hooks/usePage.js';
import { api } from '../lib/api.js';
import { inr } from '../lib/format.js';
import { useSite } from '../lib/site.jsx';

function Login({ onDone }) {
  const [pw, setPw] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMsg('');
    try {
      const r = await api.post('/api/admin/login', { password: pw });
      if (r.ok) onDone();
      else setMsg(r.json.error || 'Could not sign in.');
    } catch {
      setMsg('Network problem. Try again.');
    }
    setBusy(false);
  };
  return (
    <main id="main" className="wrap login">
      <h1 className="display" style={{ fontSize: '2.4rem' }}>Admin sign in</h1>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="pw">Password</label>
          <input id="pw" type="password" autoComplete="current-password" required maxLength={200} autoFocus
            value={pw} onChange={(e) => setPw(e.target.value)} />
        </div>
        {msg && <p className="form-msg is-error" role="alert">{msg}</p>}
        <button className="btn" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
    </main>
  );
}

function Dashboard({ data, onReload, onLogout, notice }) {
  const { stats: s, orders, warnings, names } = data;
  const nameOf = (slug) => names[slug] || slug;
  return (
    <>
      <SolidTopbar><button className="btn btn--sm btn--ghost" type="button" onClick={onLogout}>Sign out</button></SolidTopbar>
      <main id="main" className="wrap admin section">
        <h1 className="display">Dashboard</h1>
        {notice && <p className="admin__warn" style={{ borderColor: '#0b6b3a' }} role="status">{notice}</p>}
        {warnings.map((w, i) => <p className="admin__warn" key={i}>{w}</p>)}

        <div className="admin__cards">
          <div className="admin__card">Revenue<b>{inr(s.revenue_paise)}</b></div>
          <div className="admin__card">Paid orders<b>{s.paid_orders}</b></div>
          <div className="admin__card">Orders started<b>{s.all_orders}</b></div>
          <div className="admin__card">Waitlist<b>{s.leads}</b></div>
        </div>
        <p className="muted">Revenue counts real Razorpay payments only; demo payments are excluded.</p>

        <div className="admin__actions">
          <a className="btn btn--sm btn--dark" href="/admin/export/orders.csv">Export orders (CSV)</a>
          <a className="btn btn--sm btn--dark" href="/admin/export/leads.csv">Export waitlist (CSV)</a>
          <button className="btn btn--sm" type="button" onClick={onReload}>Reload products</button>
        </div>

        <h2 style={{ fontSize: '1.5rem', margin: '2rem 0 .6rem' }}>By product</h2>
        <div className="admin__scroll">
          <table className="admin__table">
            <thead><tr><th>Product</th><th>Paid orders</th><th>Revenue</th></tr></thead>
            <tbody>
              {s.per_product.map((r) => <tr key={r.product_slug}><td>{nameOf(r.product_slug)}</td><td>{r.n}</td><td>{inr(r.rev)}</td></tr>)}
              {s.per_product.length === 0 && <tr><td colSpan={3} className="muted">No paid orders yet.</td></tr>}
            </tbody>
          </table>
        </div>

        <h2 style={{ fontSize: '1.5rem', margin: '2rem 0 .6rem' }}>Where buyers came from</h2>
        <div className="admin__scroll">
          <table className="admin__table">
            <thead><tr><th>utm_source</th><th>Paid orders</th></tr></thead>
            <tbody>
              {s.sources.map(([src, n]) => <tr key={src}><td>{src}</td><td>{n}</td></tr>)}
              {s.sources.length === 0 && <tr><td colSpan={2} className="muted">No data yet.</td></tr>}
            </tbody>
          </table>
        </div>

        <h2 style={{ fontSize: '1.5rem', margin: '2rem 0 .6rem' }}>Latest orders</h2>
        <div className="admin__scroll">
          <table className="admin__table">
            <thead><tr><th>When</th><th>Order</th><th>Product</th><th>Buyer</th><th>Amount</th><th>Status</th></tr></thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.public_id}>
                  <td>{String(o.created_at).slice(0, 16).replace('T', ' ')}</td>
                  <td>{o.public_id}</td>
                  <td>{nameOf(o.product_slug)}</td>
                  <td>{o.name}<br /><span className="muted">{o.email}</span></td>
                  <td>{inr(o.amount_paise)}{o.coupon && <><br /><span className="muted">{o.coupon}</span></>}</td>
                  <td><span className={`badge badge--${o.status}`}>{o.status}</span>{o.mode === 'demo' && <> <span className="badge">demo</span></>}</td>
                </tr>
              ))}
              {orders.length === 0 && <tr><td colSpan={6} className="muted">No orders yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}

export default function AdminPage() {
  const { site } = useSite();
  usePage({ title: `Admin | ${site.name}`, robots: 'noindex,nofollow' });
  const [state, setState] = useState('loading');   // loading | login | ready
  const [data, setData] = useState(null);
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      const r = await api.get('/api/admin/overview');
      if (r.ok) { setData(r.json); setState('ready'); } else setState('login');
    } catch {
      setState('login');
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const reload = async () => {
    const r = await api.post('/api/admin/reload');
    setNotice(r.ok ? (r.json.problems ? `Reloaded. ${r.json.problems} problem(s) found, see warnings.` : 'Products reloaded.') : 'Reload failed.');
    load();
  };
  const logout = async () => { await api.post('/api/admin/logout'); setData(null); setState('login'); };

  if (state === 'loading') return null;
  if (state === 'login') return <><SolidTopbar /><Login onDone={load} /></>;
  return <Dashboard data={data} notice={notice} onReload={reload} onLogout={logout} />;
}
