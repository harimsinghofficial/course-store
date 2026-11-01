// Remembers the ad that brought the visitor (UTM / click ids) and, only after consent, loads GA4 / Meta Pixel.
const KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'gclid', 'fbclid', 'ref'];
const STORE = 'kiln_utm';

function safeGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function safeSet(key, val) {
  try {
    localStorage.setItem(key, val);
  } catch {
    /* private mode: ignore */
  }
}

export function getUtm() {
  let saved = {};
  try {
    saved = JSON.parse(safeGet(STORE) || '{}') || {};
  } catch {
    saved = {};
  }
  const params = new URLSearchParams(window.location.search);
  let fresh = false;
  KEYS.forEach((k) => {
    const v = params.get(k);
    if (v) {
      saved[k] = v.slice(0, 100);
      fresh = true;
    }
  });
  if (fresh) safeSet(STORE, JSON.stringify(saved));
  return saved;
}

const GA = { view_product: 'view_item', begin_checkout: 'begin_checkout', purchase: 'purchase', lead: 'generate_lead' };
const FB = { view_product: 'ViewContent', begin_checkout: 'InitiateCheckout', purchase: 'Purchase', lead: 'Lead' };

export function track(name, data = {}) {
  try {
    const value = Number(data.value || 0);
    if (typeof window.gtag === 'function') {
      window.gtag('event', GA[name] || name, {
        currency: 'INR', value, transaction_id: data.order_id,
        items: [{ item_id: data.slug, item_name: data.name, price: value }],
      });
    }
    if (typeof window.fbq === 'function') {
      window.fbq('track', FB[name] || name, { currency: 'INR', value, content_name: data.name, content_ids: [data.slug], content_type: 'product' });
    }
  } catch {
    /* tracking must never break the page */
  }
}

export function loadTrackers({ ga4, meta_pixel: px }) {
  if (ga4 && !window.gtag) {
    const s = document.createElement('script');
    s.async = true;
    s.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(ga4)}`;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag() {
      window.dataLayer.push(arguments); // eslint-disable-line prefer-rest-params
    };
    window.gtag('js', new Date());
    window.gtag('config', ga4, { anonymize_ip: true });
  }
  if (px && !window.fbq) {
    const n = (window.fbq = function fbq(...args) {
      if (n.callMethod) n.callMethod(...args);
      else n.queue.push(args);
    });
    if (!window._fbq) window._fbq = n;
    n.push = n;
    n.loaded = true;
    n.version = '2.0';
    n.queue = [];
    const t = document.createElement('script');
    t.async = true;
    t.src = 'https://connect.facebook.net/en_US/fbevents.js';
    document.head.appendChild(t);
    window.fbq('init', px);
    window.fbq('track', 'PageView');
  }
}

export const consent = {
  get: () => safeGet('kiln_consent'),
  set: (v) => safeSet('kiln_consent', v),
};

export function purchaseAlreadySeen(orderId) {
  const key = `kiln_purchased_${orderId}`;
  let seen = false;
  try {
    seen = !!localStorage.getItem(key);
    localStorage.setItem(key, '1');
  } catch {
    /* ignore */
  }
  return seen;
}
