import { useEffect, useRef, useState } from 'react';
import { Footer, SolidTopbar } from '../components/Chrome.jsx';
import { usePage } from '../hooks/usePage.js';
import { api } from '../lib/api.js';
import { confetti } from '../lib/confetti.js';
import { inr } from '../lib/format.js';
import { useSite } from '../lib/site.jsx';
import { purchaseAlreadySeen, track } from '../lib/tracking.js';
import ErrorPage from './ErrorPage.jsx';

const POLL_MS = 3000;
const MAX_TRIES = 120;

export default function ThanksPage({ id }) {
  const { site, mail_on: mailOn } = useSite();
  const token = new URLSearchParams(window.location.search).get('t') || '';
  const [order, setOrder] = useState(null);
  const [error, setError] = useState(null);
  const celebrated = useRef(false);

  // Load the order; while payment is still confirming, ask again every few seconds.
  useEffect(() => {
    let stop = false;
    let timer = 0;
    let tries = 0;
    const url = `/api/orders/${encodeURIComponent(id)}?t=${encodeURIComponent(token)}`;
    const load = async () => {
      try {
        const r = await api.get(url);
        if (stop) return;
        if (!r.ok) { setError(r.status === 404 ? 404 : 502); return; }
        setOrder(r.json);
        if (!r.json.paid && r.json.status !== 'failed' && ++tries < MAX_TRIES) timer = setTimeout(load, POLL_MS);
      } catch {
        if (!stop && ++tries < MAX_TRIES) timer = setTimeout(load, POLL_MS * 2);
      }
    };
    load();
    return () => { stop = true; clearTimeout(timer); };
  }, [id, token]);

  usePage({ title: `Your order | ${site.name}`, robots: 'noindex,nofollow', theme: order?.product?.theme });

  useEffect(() => {
    if (!order?.paid || celebrated.current) return;
    celebrated.current = true;
    confetti();
    if (!purchaseAlreadySeen(order.public_id)) {
      track('purchase', { slug: order.product?.slug, name: order.product?.name, value: order.value, order_id: order.public_id });
    }
  }, [order]);

  if (error) return <ErrorPage code={error} message={error === 404 ? "We couldn't find that order." : 'Could not load your order. Please refresh.'} />;
  if (!order) return null;

  const p = order.product;
  const mail = <a href={`mailto:${site.support_email}`}>{site.support_email}</a>;
  return (
    <>
      <SolidTopbar />
      <main id="main" className="section">
        <div className="wrap receipt">
          {order.paid ? (
            <>
              <h1 className="display" style={{ fontSize: 'clamp(2.4rem,1.4rem+4vw,4rem)', lineHeight: 1 }}>You're in{p ? `: ${p.name}` : ''}</h1>
              <p className="lede" style={{ marginTop: '1rem' }}>
                Thanks, {order.first_name}. Your payment is confirmed{order.mode === 'demo' ? ' (demo payment, no money moved)' : ''}.{' '}
                {mailOn ? `We've emailed a copy of this page to ${order.email}.` : 'Bookmark this page to come back to your access.'}
              </p>
              {order.links.length > 0 && (
                <>
                  <h2 style={{ fontSize: '1.5rem', marginTop: '2rem' }}>Your downloads</h2>
                  <div className="downloads">
                    {order.links.map((l) => <a className="btn btn--dark" href={l.url} rel="nofollow" key={l.url}>Download: {l.label}</a>)}
                  </div>
                </>
              )}
              {order.access_url ? (
                <>
                  <h2 style={{ fontSize: '1.5rem', marginTop: '2rem' }}>Start here</h2>
                  <p style={{ margin: '.6rem 0 1.2rem' }}>{p?.instructions}</p>
                  <a className="btn" href={order.access_url} rel="noopener noreferrer" target="_blank">Open your access link</a>
                </>
              ) : (p?.instructions && order.links.length === 0 && <p style={{ marginTop: '1.5rem' }}>{p.instructions}</p>)}
              <dl>
                <dt>Order</dt><dd>{order.public_id}</dd>
                <dt>Amount paid</dt><dd>{order.mode === 'demo' ? 'Free (demo)' : inr(order.amount_paise)}</dd>
                <dt>Email</dt><dd>{order.email}</dd>
              </dl>
              <p className="muted">Bookmark this page. Download links refresh every time you open it. Questions? Write to {mail} and quote your order number.</p>
            </>
          ) : (
            <>
              <h1 className="display" style={{ fontSize: 'clamp(2.2rem,1.4rem+3.4vw,3.4rem)', lineHeight: 1 }}>
                {order.status === 'failed' ? 'Payment did not go through' : 'Confirming your payment'}
              </h1>
              <div className="status-wait" style={{ marginTop: '1.5rem' }} role="status">
                {order.status !== 'failed' && <span className="spinner" aria-hidden="true" />}
                <p>{order.status === 'failed' ? 'No money was taken. You can go back and try again.' : 'This usually takes a few seconds. You can keep this page open.'}</p>
              </div>
              <p className="muted" style={{ marginTop: '1rem' }}>
                If money left your account and this page doesn't update within ten minutes, write to {mail} with order {order.public_id}.
              </p>
            </>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
