import { useState } from 'react';
import { api } from '../lib/api.js';
import { EMAIL_RE } from '../lib/format.js';
import { getUtm, track } from '../lib/tracking.js';

// Email capture for coming-soon / sold-out products. `website` is a honeypot that real users never fill.
export default function WaitlistForm({ slug, name, id, label = 'Join the waitlist' }) {
  const [email, setEmail] = useState('');
  const [website, setWebsite] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState({ text: '', error: false });

  async function submit(e) {
    e.preventDefault();
    const value = email.trim();
    if (!EMAIL_RE.test(value)) return setMsg({ text: 'Please enter a valid email address.', error: true });
    setBusy(true);
    setMsg({ text: '', error: false });
    try {
      const r = await api.post('/api/leads', { slug, email: value, utm: getUtm(), website });
      if (r.ok) {
        setMsg({ text: r.json.message || 'You are on the list.', error: false });
        setEmail('');
        track('lead', { slug, name });
      } else {
        setMsg({ text: r.json.error || 'Something went wrong.', error: true });
      }
    } catch {
      setMsg({ text: 'Network problem. Please try again.', error: true });
    }
    setBusy(false);
    return undefined;
  }

  return (
    <form className="inline-form" onSubmit={submit} noValidate>
      <label className="sr-only" htmlFor={id}>Email address</label>
      <input id={id} type="email" name="email" placeholder="you@example.com" autoComplete="email" required
        value={email} onChange={(e) => setEmail(e.target.value)} />
      <input className="hp" type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true"
        value={website} onChange={(e) => setWebsite(e.target.value)} />
      <button className="btn" type="submit" disabled={busy}>{label}</button>
      <p className={`form-msg${msg.error ? ' is-error' : ''}`} role="status" aria-live="polite">{msg.text}</p>
    </form>
  );
}
