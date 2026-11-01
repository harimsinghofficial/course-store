import { useEffect, useRef, useState } from 'react';
import { inr } from '../lib/format.js';
import { useSite } from '../lib/site.jsx';
import Accordion from './Accordion.jsx';
import { useBuy } from './buy.jsx';
import Countdown from './Countdown.jsx';
import CountUp from './CountUp.jsx';
import { useMagnetic, useTilt } from './effects.js';
import ParticleWord from './ParticleWord.jsx';
import SeatBar from './SeatBar.jsx';
import WaitlistForm from './WaitlistForm.jsx';
import { SolidTopbar } from './Chrome.jsx';
import { Link } from 'react-router-dom';
import { hasIO } from '../hooks/useMedia.js';

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

function heroNote(p) {
  if (p.early) return `Early-access price until ${p.ends_text}`;
  if (p.sold_out) return 'Every seat is taken. Join the waitlist for the next round.';
  if (p.pstatus === 'coming_soon') return 'Opening soon. Waitlist members hear first.';
  if (!p.can_buy) return 'Enrolment is paused right now.';
  return 'Instant access after payment';
}

export function Topbar({ p }) {
  const { site } = useSite();
  return (
    <header className="topbar">
      <div className="wrap topbar__row">
        <Link className="brand" to="/" aria-label={`${site.name} home`}>{site.name}</Link>
        <nav className="topbar__nav" aria-label="Page sections">
          {p.modules.length > 0 && <a href="#curriculum">What's inside</a>}
          {p.faq.length > 0 && <a href="#faq">Questions</a>}
          <a className="btn btn--sm" href="#pricing">{p.can_buy ? 'Enroll' : 'Waitlist'}</a>
        </nav>
      </div>
    </header>
  );
}

export function Hero({ p, heroRef }) {
  const buy = useBuy();
  const btnRef = useRef(null);
  useMagnetic(btnRef);
  const words = p.headline.split(' ');
  return (
    <section className="hero" ref={heroRef}>
      <div className="wrap hero__inner">
        <div className="hero__copy">
          <p className="hero__note">{heroNote(p)}</p>
          <h1 className="hero__title">
            {words.map((w, i) => (
              <span key={i}><span className="w"><span style={{ '--i': i }}>{w}</span></span>{' '}</span>
            ))}
          </h1>
          <p className="hero__sub">{p.subhead}</p>
          <div className="hero__actions">
            {p.can_buy ? (
              <button className="btn" type="button" ref={btnRef} onClick={buy}>{p.cta_label} for {inr(p.base_paise)}</button>
            ) : (
              <WaitlistForm slug={p.slug} name={p.name} id="wl-hero" label="Join the waitlist" />
            )}
            {p.modules.length > 0 && <a className="btn btn--ghost" href="#curriculum">See what's inside</a>}
          </div>
          {p.can_buy && (
            <p className="hero__fine">
              {p.seats_total ? <span>{p.seats_left} of {p.seats_total} seats left. </span> : null}
              {p.guarantee.days ? `Full refund within ${p.guarantee.days} days.` : null}
            </p>
          )}
        </div>
        <div className="hero__stage"><ParticleWord word={p.hero_word} heroRef={heroRef} /></div>
      </div>
    </section>
  );
}

export function Marquee({ items }) {
  if (!items.length) return null;
  const reps = Math.floor(6 / items.length) + 1;
  return (
    <div className="marquee" aria-label="What you walk away with">
      <div className="marquee__track">
        {[0, 1].map((g) => (
          <ul className="marquee__group" key={g} aria-hidden={g === 1 ? 'true' : undefined}>
            {Array.from({ length: reps }, (_, r) => items.map((o, i) => <li className="marquee__item" key={`${r}-${i}`}>{o}</li>))}
          </ul>
        ))}
      </div>
    </div>
  );
}

export function Stats({ stats }) {
  if (!stats.length) return null;
  return (
    <section className="section" aria-label="At a glance">
      <div className="wrap">
        <dl className="stats__list" style={{ '--cols': stats.length }}>
          {stats.map((s, i) => (
            <div className="stat" key={i}>
              <dt>{s.label}</dt>
              <dd><CountUp value={s.value} />{s.suffix}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

export function Problem({ problem }) {
  if (!problem.title) return null;
  return (
    <section className="section section--tint">
      <div className="wrap split split--wide-left">
        <h2 className="title">{problem.title}</h2>
        <p className="lede">{problem.body}</p>
      </div>
    </section>
  );
}

// Curriculum on a vertical "rail" that fills with colour as you scroll past each module.
export function Curriculum({ modules }) {
  const ref = useRef(null);
  const [passed, setPassed] = useState(0);

  useEffect(() => {
    const rail = ref.current;
    if (!rail) return undefined;
    let queued = false;
    const update = () => {
      queued = false;
      const r = rail.getBoundingClientRect();
      const mid = window.innerHeight * 0.55;
      rail.style.setProperty('--prog', clamp((mid - r.top) / r.height, 0, 1).toFixed(3));
      let n = 0;
      rail.querySelectorAll('.rail__marker').forEach((m, i) => {
        const b = m.getBoundingClientRect();
        if (b.top + b.height / 2 < mid) n = i + 1;
      });
      setPassed(n);
    };
    const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(update); } };
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    const ro = 'ResizeObserver' in window ? new ResizeObserver(schedule) : null;
    if (ro) ro.observe(rail);
    update();
    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (ro) ro.disconnect();
    };
  }, [modules]);

  if (!modules.length) return null;
  return (
    <section className="section" id="curriculum">
      <div className="wrap">
        <h2 className="title">What's inside</h2>
        <ol className="rail" ref={ref}>
          {modules.map((m, i) => (
            <Accordion key={i} as="li" className={`rail__item${i < passed ? ' is-passed' : ''}`} defaultOpen={i === 0}
              meta={m.duration} title={m.title} marker={<span className="rail__marker" aria-hidden="true">{i + 1}</span>}>
              <p>{m.summary}</p>
              {m.lessons.length > 0 && <ul className="lessons">{m.lessons.map((l, j) => <li key={j}>{l}</li>)}</ul>}
            </Accordion>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function Includes({ items }) {
  if (!items.length) return null;
  return (
    <section className="section section--tint">
      <div className="wrap">
        <h2 className="title">Everything you get</h2>
        <ul className="includes">
          {items.map((it, i) => <li className="includes__item" key={i}><h3>{it.title}</h3><p>{it.detail}</p></li>)}
        </ul>
      </div>
    </section>
  );
}

export function Audience({ audience }) {
  if (!audience.for.length && !audience.not_for.length) return null;
  return (
    <section className="section">
      <div className="wrap">
        <h2 className="title">Is this for you?</h2>
        <div className="audience">
          {audience.for.length > 0 && (
            <div><h3>It's a good fit if you are</h3><ul className="mark-list">{audience.for.map((a, i) => <li key={i}>{a}</li>)}</ul></div>
          )}
          {audience.not_for.length > 0 && (
            <div><h3>Skip it if you are</h3><ul className="mark-list mark-list--no">{audience.not_for.map((a, i) => <li key={i}>{a}</li>)}</ul></div>
          )}
        </div>
      </div>
    </section>
  );
}

export function Instructor({ person }) {
  if (!person.name) return null;
  return (
    <section className="section section--tint">
      <div className="wrap person">
        <div className="person__mark" aria-hidden="true">{person.initials || person.name.slice(0, 2)}</div>
        <div className="measure">
          <h2 className="person__name">{person.name}</h2>
          <p className="person__role">{person.role}</p>
          <p>{person.bio}</p>
        </div>
      </div>
    </section>
  );
}

export function Testimonials({ items }) {
  if (!items.length) return null;
  return (
    <section className="section" aria-label="What students say">
      <div className="wrap">
        <h2 className="title">What students say</h2>
        <div className="quotes" role="list" tabIndex={0}>
          {items.map((t, i) => (
            <figure className="quote" role="listitem" key={i}>
              <blockquote>{t.quote}</blockquote>
              <figcaption>{t.name}<span>{t.role}</span></figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

// The ticket: price, countdown, seat meter and the buy button.
export function Pricing({ p, sectionRef, onExpire }) {
  const buy = useBuy();
  const { site, mail_on: mailOn } = useSite();
  const ticketRef = useRef(null);
  useTilt(ticketRef);
  const title = p.can_buy ? (p.seats_total ? 'Reserve your seat' : 'Get instant access') : 'Be first in line';
  const third = p.delivery.type === 'link' ? 'Join straight away' : 'Download and start';
  return (
    <section className="section section--tint" id="pricing" ref={sectionRef}>
      <div className="wrap pricing">
        <div>
          <h2 className="title">{title}</h2>
          {p.can_buy ? (
            <ol className="steps">
              <li><strong>Pay securely</strong>UPI, cards, netbanking or wallets, through Razorpay.</li>
              <li>
                <strong>{mailOn ? 'Check your email' : 'Land on your order page'}</strong>
                {mailOn ? 'Your receipt and order link arrive in a minute.' : 'Your access appears the moment payment is confirmed.'}
              </li>
              <li><strong>{third}</strong>{p.delivery.instructions || 'Everything is on your order page.'}</li>
            </ol>
          ) : (
            <p className="lede" style={{ marginTop: '1.2rem' }}>Leave your email and we'll write the moment this opens, with launch pricing for the first people in.</p>
          )}
          {p.guarantee.days > 0 && <p className="guarantee"><strong>{p.guarantee.days}-day refund.</strong> {p.guarantee.text}</p>}
        </div>

        <div className="ticket" ref={ticketRef}>
          <div className="ticket__top">
            <p className="ticket__name">{p.name}</p>
            {p.can_buy ? (
              <>
                <div className="ticket__price">
                  <span className="ticket__amount">{inr(p.base_paise)}</span>
                  {p.base_paise < p.list_paise && <span className="ticket__was"><span className="sr-only">Regular price </span>{inr(p.list_paise)}</span>}
                </div>
                <p className="ticket__tax">{site.price_note}</p>
                {p.early && <Countdown endIso={p.ends_iso} onExpire={onExpire} />}
              </>
            ) : (
              <>
                <p className="ticket__price"><span className="ticket__amount" style={{ fontSize: '2.6rem' }}>{p.sold_out ? 'Sold out' : 'Soon'}</span></p>
                <p className="ticket__tax">{p.early || p.pstatus === 'coming_soon' ? `Launch price: ${inr(p.launch_price_paise)}` : ''}</p>
              </>
            )}
          </div>
          <div className="ticket__bottom">
            {p.seats_total && p.can_buy ? (
              <div className="seats">
                <div className="seats__line"><span>{p.seats_left} of {p.seats_total} seats left</span></div>
                <SeatBar total={p.seats_total} left={p.seats_left} />
              </div>
            ) : null}
            {p.can_buy ? (
              <>
                <button className="btn btn--block ticket__cta" type="button" onClick={buy}>{p.cta_label} for {inr(p.base_paise)}</button>
                <p className="ticket__fine">Secure checkout. {p.guarantee.days ? `Refundable for ${p.guarantee.days} days.` : ''}</p>
              </>
            ) : (
              <WaitlistForm slug={p.slug} name={p.name} id="wl-ticket" label="Notify me" />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export function Faq({ items }) {
  if (!items.length) return null;
  return (
    <section className="section" id="faq">
      <div className="wrap">
        <h2 className="title">Questions</h2>
        <div className="faq">
          {items.map((f, i) => <Accordion key={i} title={f.q}><p>{f.a}</p></Accordion>)}
        </div>
      </div>
    </section>
  );
}

export function Closer({ p }) {
  const buy = useBuy();
  return (
    <section className="closer">
      <div className="wrap">
        <h2>{p.headline}</h2>
        <p>{p.can_buy ? p.subhead : "We'll email you the day it opens."}</p>
        {p.can_buy ? (
          <button className="btn" type="button" onClick={buy}>{p.cta_label} for {inr(p.base_paise)}</button>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <WaitlistForm slug={p.slug} name={p.name} id="wl-closer" label="Join the waitlist" />
          </div>
        )}
      </div>
    </section>
  );
}

// Sticky buy bar for small screens: shown once the hero and pricing section are both off screen.
export function BuyBar({ p, heroRef, pricingRef }) {
  const buy = useBuy();
  const [seen, setSeen] = useState({ hero: true, pricing: false });

  useEffect(() => {
    if (!hasIO) return undefined;
    const watch = [['hero', heroRef.current], ['pricing', pricingRef.current]];
    const observers = watch.map(([key, el]) => {
      if (!el) return null;
      const io = new IntersectionObserver((es) => setSeen((s) => ({ ...s, [key]: es[es.length - 1].isIntersecting })));
      io.observe(el);
      return io;
    });
    return () => observers.forEach((io) => io && io.disconnect());
  }, [heroRef, pricingRef]);

  const show = hasIO && !seen.hero && !seen.pricing;
  return (
    <div className={`buybar${show ? ' is-visible' : ''}`} inert={!show}>
      <div><b>{inr(p.base_paise)}</b><span>{p.name}</span></div>
      <button className="btn btn--sm" type="button" onClick={buy}>{p.cta_label}</button>
    </div>
  );
}

export { SolidTopbar };
