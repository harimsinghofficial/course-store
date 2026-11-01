import { useCallback, useEffect, useRef, useState } from 'react';
import { BuyContext } from '../components/buy.jsx';
import CheckoutDialog from '../components/CheckoutDialog.jsx';
import { Footer } from '../components/Chrome.jsx';
import {
  Audience, BuyBar, Closer, Curriculum, Faq, Hero, Includes, Instructor, Marquee, Pricing, Problem, Stats,
  Testimonials, Topbar,
} from '../components/ProductSections.jsx';
import { usePage } from '../hooks/usePage.js';
import { api } from '../lib/api.js';
import { useProduct } from '../lib/products.js';
import { track } from '../lib/tracking.js';
import ErrorPage from './ErrorPage.jsx';

const SEATS_POLL_MS = 45_000;

// Keeps the seat counter honest while the page is open; reloads product data if sales close.
function useLiveSeats(p, refresh) {
  const [left, setLeft] = useState(null);
  useEffect(() => {
    if (!p.seats_total) return undefined;
    setLeft(null);
    const id = setInterval(async () => {
      if (document.hidden) return;
      try {
        const r = await api.get(`/api/products/${encodeURIComponent(p.slug)}/status`);
        if (!r.ok || r.json.seats_total == null) return;
        if (r.json.seats_left === 0 || !r.json.can_buy) refresh();
        else setLeft(r.json.seats_left);
      } catch { /* offline: keep what we have */ }
    }, SEATS_POLL_MS);
    return () => clearInterval(id);
  }, [p.slug, p.seats_total, refresh]);
  return left;
}

function ProductView({ product, refresh }) {
  const heroRef = useRef(null);
  const pricingRef = useRef(null);
  const checkoutRef = useRef(null);
  const liveLeft = useLiveSeats(product, refresh);
  const p = liveLeft == null ? product : { ...product, seats_left: liveLeft };

  usePage({ title: p.seo.title, description: p.seo.description, theme: p.theme });
  useEffect(() => {
    track('view_product', { slug: p.slug, name: p.name, value: (p.base_paise / 100).toFixed(2) });
  }, [p.slug]); // eslint-disable-line react-hooks/exhaustive-deps

  const openCheckout = useCallback(() => {
    checkoutRef.current?.open();
    track('begin_checkout', { slug: p.slug, name: p.name, value: (p.base_paise / 100).toFixed(2) });
  }, [p.slug, p.name, p.base_paise]);

  return (
    <BuyContext.Provider value={openCheckout}>
      <Topbar p={p} />
      <main id="main">
        <Hero p={p} heroRef={heroRef} />
        <Marquee items={p.outcomes} />
        <Stats stats={p.stats} />
        <Problem problem={p.problem} />
        <Curriculum modules={p.modules} />
        <Includes items={p.includes} />
        <Audience audience={p.audience} />
        <Instructor person={p.instructor} />
        <Testimonials items={p.testimonials} />
        <Pricing p={p} sectionRef={pricingRef} onExpire={refresh} />
        <Faq items={p.faq} />
        <Closer p={p} />
      </main>
      <Footer pad={p.can_buy} />
      {p.can_buy && (
        <>
          <BuyBar p={p} heroRef={heroRef} pricingRef={pricingRef} />
          <CheckoutDialog ref={checkoutRef} product={p} />
        </>
      )}
    </BuyContext.Provider>
  );
}

export default function ProductPage({ slug }) {
  const { product, error, refresh } = useProduct(slug);
  if (!product && error === 'notfound') return <ErrorPage code={404} message="That page doesn't exist." />;
  if (!product) return error ? <ErrorPage code={502} message="Could not load this page. Please refresh." /> : null;
  return <ProductView key={product.slug} product={product} refresh={refresh} />;
}
