import { useEffect, useImperativeHandle, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { confetti } from '../lib/confetti.js';
import { EMAIL_RE, inr } from '../lib/format.js';
import { loadScript } from '../lib/loadScript.js';
import { useSite } from '../lib/site.jsx';
import { getUtm } from '../lib/tracking.js';

// Checkout modal. The browser only says WHAT is being bought; the server decides the price, creates the
// Razorpay order and verifies the payment signature. In demo mode a "simulate payment" step replaces Razorpay.
export default function CheckoutDialog({ product: p, ref }) {
  const { payment_mode: mode, mail_on: mailOn, razorpay_script: rzScript } = useSite();
  const dlg = useRef(null);
  const nameRef = useRef(null);
  const [step, setStep] = useState('form'); // form | demo | success
  const [msg, setMsg] = useState({ text: '', error: false });
  const [busy, setBusy] = useState(false);
  const [fields, setFields] = useState({ name: '', email: '', phone: '', website: '' });
  const [couponOpen, setCouponOpen] = useState(false);
  const [coupon, setCoupon] = useState('');
  const [quote, setQuote] = useState(null);
  const [demo, setDemo] = useState({ order: null, busy: false, msg: { text: '', error: false } });

  useEffect(() => setQuote(null), [p.base_paise]); // price changed under us (early access ended)

  const total = quote ? quote.amount_paise : p.base_paise;
  const set = (k) => (e) => setFields((f) => ({ ...f, [k]: e.target.value }));
  const say = (text, error = false) => setMsg({ text, error });

  function open() {
    setStep('form');
    say('');
    const d = dlg.current;
    if (d && !d.open) (typeof d.showModal === 'function' ? d.showModal() : d.setAttribute('open', ''));
    if (!fields.name) nameRef.current?.focus();
  }
  useImperativeHandle(ref, () => ({ open }));

  async function applyCoupon() {
    say('');
    try {
      const r = await api.post('/api/checkout/quote', { slug: p.slug, coupon: coupon.trim() });
      if (!r.ok) return say(r.json.error || 'That code did not work.', true);
      setQuote(r.json);
      return r.json.discount_paise > 0 ? say('Code applied.') : undefined;
    } catch {
      return say('Could not check the code. Try again.', true);
    }
  }

  async function submit(e) {
    e.preventDefault();
    say('');
    const name = fields.name.trim();
    const email = fields.email.trim();
    if (name.length < 2) { nameRef.current?.focus(); return say('Please enter your full name.', true); }
    if (!EMAIL_RE.test(email)) return say('Please enter a valid email address.', true);
    setBusy(true);
    try {
      const r = await api.post('/api/checkout/order', {
        slug: p.slug, name, email, phone: fields.phone.trim(), coupon: coupon.trim(), utm: getUtm(), website: fields.website,
      });
      setBusy(false);
      if (!r.ok) return say(r.json.error || 'Something went wrong. Please try again.', true);
      if (r.json.mode === 'razorpay') return openRazorpay(r.json);
      setDemo({ order: r.json, busy: false, msg: { text: '', error: false } });
      return setStep('demo');
    } catch {
      setBusy(false);
      return say('Network problem. Check your connection and try again.', true);
    }
  }

  async function openRazorpay(o) {
    try {
      await loadScript(rzScript);
    } catch {
      return say('Could not load the payment window. Check your connection and try again.', true);
    }
    const rzp = new window.Razorpay({
      key: o.key_id, amount: o.amount, currency: o.currency, name: o.business, description: o.description,
      order_id: o.rz_order_id, prefill: o.prefill, notes: { order: o.order_id }, theme: { color: o.theme_color },
      handler: (resp) => verify(o, resp, 0),
      modal: { ondismiss: () => { open(); say('Payment was not completed. Nothing was charged. You can try again.', true); } },
    });
    dlg.current?.close(); // an open <dialog> sits above everything, so close it before Razorpay's window
    return rzp.open();
  }

  async function verify(o, resp, attempt) {
    setStep('success');
    say('');
    if (dlg.current && !dlg.current.open && typeof dlg.current.showModal === 'function') dlg.current.showModal();
    try {
      const r = await api.post('/api/checkout/verify', {
        order_id: o.order_id, razorpay_order_id: resp.razorpay_order_id,
        razorpay_payment_id: resp.razorpay_payment_id, razorpay_signature: resp.razorpay_signature,
      });
      if (r.ok) return done(r.json.redirect);
      return failedVerify(o);
    } catch {
      if (attempt < 2) return setTimeout(() => verify(o, resp, attempt + 1), 1500);
      return failedVerify(o);
    }
  }

  function failedVerify(o) {
    setStep('form');
    say(`We could not confirm your payment yet. If money was deducted, your access email will arrive within a few minutes. Quote order ${o.order_id} if you write to us.`, true);
  }

  async function demoPay() {
    setDemo((d) => ({ ...d, busy: true, msg: { text: '', error: false } }));
    try {
      const r = await api.post('/api/checkout/demo-pay', { order_id: demo.order.order_id });
      if (r.ok) return done(r.json.redirect);
      return setDemo((d) => ({ ...d, busy: false, msg: { text: r.json.error || 'Demo payment failed.', error: true } }));
    } catch {
      return setDemo((d) => ({ ...d, busy: false, msg: { text: 'Network problem.', error: true } }));
    }
  }

  function done(redirect) {
    setStep('success');
    confetti();
    setTimeout(() => { window.location.href = redirect; }, 1500);
  }

  return (
    <dialog className="checkout" id="checkout" ref={dlg} aria-labelledby="checkout-title"
      onClick={(e) => { if (e.target === dlg.current) dlg.current.close(); }}>
      <div className="checkout__panel">
        <button className="checkout__close" type="button" aria-label="Close checkout" onClick={() => dlg.current?.close()}>&times;</button>

        {step === 'form' && (
          <div>
            <h2 id="checkout-title">{p.name}</h2>
            <p className="checkout__sub">{mailOn ? 'Your access link is emailed to you right after payment.' : 'You get instant access on the next screen.'}</p>
            <form onSubmit={submit} noValidate>
              <div className="field">
                <label htmlFor="co-name">Full name</label>
                <input id="co-name" name="name" ref={nameRef} autoComplete="name" required maxLength={80} value={fields.name} onChange={set('name')} />
              </div>
              <div className="field">
                <label htmlFor="co-email">Email</label>
                <input id="co-email" name="email" type="email" autoComplete="email" inputMode="email" required maxLength={254} value={fields.email} onChange={set('email')} />
              </div>
              <div className="field">
                <label htmlFor="co-phone">Phone <span className="muted">(optional, helps with payment apps)</span></label>
                <input id="co-phone" name="phone" type="tel" autoComplete="tel" inputMode="tel" maxLength={20} value={fields.phone} onChange={set('phone')} />
              </div>
              <input className="hp" type="text" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" value={fields.website} onChange={set('website')} />

              <button className="link-btn" type="button" aria-expanded={couponOpen} aria-controls="coupon-row" onClick={() => setCouponOpen((o) => !o)}>Have a discount code?</button>
              <div className={`coupon${couponOpen ? ' is-open' : ''}`} id="coupon-row">
                <label className="sr-only" htmlFor="co-coupon">Discount code</label>
                <input id="co-coupon" name="coupon" maxLength={32} autoComplete="off" spellCheck={false} value={coupon}
                  onChange={(e) => setCoupon(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); applyCoupon(); } }} />
                <button className="btn btn--sm btn--dark" type="button" onClick={applyCoupon}>Apply</button>
              </div>

              <dl className="summary" aria-live="polite">
                <div><dt>{p.name}</dt><dd>{inr(quote ? quote.base_paise : p.base_paise)}</dd></div>
                {quote && quote.discount_paise > 0 && (
                  <div className="off"><dt>{quote.coupon} ({quote.coupon_label})</dt><dd>&minus;{quote.discount_text}</dd></div>
                )}
                <div className="total"><dt>You pay</dt><dd>{inr(total)}</dd></div>
              </dl>

              <button className="btn btn--block" type="submit" disabled={busy}>{busy ? 'Starting payment…' : `Pay ${inr(total)}`}</button>
              <p className={`form-msg${msg.error ? ' is-error' : ''}`} role="alert">{msg.text}</p>
              <p className="fine">{mode === 'razorpay' ? 'Secure payment by Razorpay: UPI, cards, netbanking and wallets.' : 'Demo mode: no real payment is taken.'}</p>
            </form>
          </div>
        )}

        {step === 'demo' && demo.order && (
          <div>
            <h2 id="checkout-title">Demo payment</h2>
            <p className="checkout__sub">This stands in for Razorpay until you add your keys to <code>.env</code>. No money moves.</p>
            <div className="demo-box" style={{ marginTop: '1.2rem' }}>
              <p>Amount: <strong>{demo.order.amount_text}</strong></p>
              <button className="btn btn--block" type="button" disabled={demo.busy} onClick={demoPay}>Simulate successful payment</button>
            </div>
            <p className={`form-msg${demo.msg.error ? ' is-error' : ''}`} role="alert">{demo.msg.text}</p>
          </div>
        )}

        {step === 'success' && (
          <div className="success">
            <div className="success__tick" aria-hidden="true" />
            <h2 id="checkout-title">Payment confirmed</h2>
            <p className="checkout__sub">Taking you to your order page&hellip;</p>
          </div>
        )}
      </div>
    </dialog>
  );
}
