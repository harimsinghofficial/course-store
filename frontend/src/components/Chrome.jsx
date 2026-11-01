import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSite } from '../lib/site.jsx';
import { consent, loadTrackers } from '../lib/tracking.js';

export function Brand() {
  const { site } = useSite();
  return <Link className="brand" to="/" aria-label={`${site.name} home`}>{site.name}</Link>;
}

// Plain top bar used on every page except the product hero (which overlays its own transparent bar).
export function SolidTopbar({ children }) {
  return (
    <header className="topbar topbar--solid">
      <div className="wrap topbar__row"><Brand />{children}</div>
    </header>
  );
}

export function Footer({ pad = false }) {
  const { site } = useSite();
  return (
    <footer className={`footer${pad ? ' footer--pad' : ''}`}>
      <div className="wrap footer__row">
        <p>&copy; {new Date().getFullYear()} {site.legal_name}. Payments are processed securely by Razorpay.</p>
        <nav aria-label="Legal and support">
          <Link to="/legal/terms">Terms</Link>
          <Link to="/legal/privacy">Privacy</Link>
          <Link to="/legal/refund">Refunds</Link>
          <Link to="/legal/contact">Contact</Link>
        </nav>
      </div>
    </footer>
  );
}

// Cookie prompt, only when GA4 / Meta Pixel ids are configured. Trackers load after the visitor says yes.
export function ConsentBanner() {
  const { analytics } = useSite();
  const configured = !!(analytics.ga4 || analytics.meta_pixel);
  const [choice, setChoice] = useState(() => (configured ? consent.get() : 'no'));

  useEffect(() => {
    if (configured && choice === 'yes') loadTrackers(analytics);
  }, [configured, choice, analytics]);

  if (!configured || choice === 'yes' || choice === 'no') return null;
  const pick = (v) => { consent.set(v); setChoice(v); };
  return (
    <div className="consent" role="dialog" aria-label="Cookie choice">
      <p>We use cookies from Google and Meta to see which ads bring people here. Is that okay?</p>
      <div>
        <button className="btn btn--sm" type="button" onClick={() => pick('yes')}>Yes, that is fine</button>
        <button className="btn btn--sm btn--ghost" type="button" onClick={() => pick('no')}>No thanks</button>
      </div>
    </div>
  );
}
