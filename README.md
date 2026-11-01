# Course Store

A fast store for selling digital products (courses, ebooks, templates) with Razorpay.
Ad → landing page → early-access pricing → checkout → instant delivery.

- **Frontend:** React 19 + Vite (plain JavaScript), React Router, hand-written CSS. No UI framework, no animation library.
- **Backend:** FastAPI + SQLite. Prices, payment verification, downloads and admin all live on the server.
- **Modular:** every product is one JSON file in `products/`. Add a file, get a new landing page. No code changes.

---

## Contents

1. [Quick start](#1-quick-start)
2. [How it fits together](#2-how-it-fits-together)
3. [Project structure](#3-project-structure)
4. [Day-to-day workflow](#4-day-to-day-workflow)
5. [Sell something new](#5-sell-something-new)
6. [Customize the design](#6-customize-the-design)
7. [Go live with Razorpay](#7-go-live-with-razorpay)
8. [Deploy](#8-deploy)
9. [Security](#9-security)
10. [Speed](#10-speed)
11. [Ad tracking, email, admin](#11-ad-tracking-email-admin)
12. [Configuration reference](#12-configuration-reference)
13. [API reference](#13-api-reference)
14. [Tests](#14-tests)
15. [Launch checklist](#15-launch-checklist)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. Quick start

You need:

| Tool | Version | Get it |
|---|---|---|
| Python | 3.10 or newer | https://www.python.org/downloads/ |
| Node.js | 20 or newer (includes npm) | https://nodejs.org/ |

```bash
git clone <your-private-repo-url> course-store
cd course-store
./run-dev.sh            # macOS / Linux
run-dev.bat             # Windows
```

The script creates a Python virtual environment, installs Python and Node packages, copies `.env.example` to `.env`, builds the React app and starts the server. Open **http://localhost:8000**.

Without Razorpay keys the store runs in **demo mode**: checkout works end to end, but a "Simulate successful payment" button replaces Razorpay and no money moves. Demo mode is blocked automatically when `APP_ENV=production`.

Useful pages to click through:

| URL | What it is |
|---|---|
| `/` | Home. Shows the product named in `config.json` → `site.home_product`, otherwise a product list |
| `/p/ship-saas-30` | Landing page with early-access price, countdown and seat meter |
| `/p/quiet-founder-ebook` | A second product with a different look |
| `/p/ui-kit-pro` | A "coming soon" product: waitlist form instead of a buy button |
| `/admin` | Dashboard. Set `ADMIN_PASSWORD=something` in `.env` for local use |

### Run commands

| Command | What it does |
|---|---|
| `./run-dev.sh` | Build React once, serve everything from FastAPI on `:8000` (auto-reloads Python) |
| `./run-dev.sh hot` | Same, plus the Vite dev server on `:5173` with instant hot reload. **Use this while editing React** |
| `./run-lan.sh` | Like `run-dev.sh`, reachable from phones and laptops on the same Wi-Fi. It prints the address. Local testing only |
| `./start.sh` | Production (gunicorn + uvicorn workers) |

Manual alternative, if you prefer to see each step:

```bash
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # Windows: copy .env.example .env
cd frontend && npm install && npm run build && cd ..
uvicorn main:app --reload
```

---

## 2. How it fits together

```
Browser ──► FastAPI (main.py)
              ├── GET /p/<slug>, /, /thanks/…, /legal/…, /admin
              │      returns frontend/dist/index.html with, injected on the server:
              │        • <title>, description, canonical, Open Graph, JSON-LD   (SEO, link previews, ad crawlers)
              │        • the product's colours as CSS variables                  (no colour flash)
              │        • "boot" JSON with site + product data                    (React paints with no extra request)
              ├── /static/assets/*    hashed JS/CSS/fonts, cached for a year
              └── /api/*, /download/* JSON API, payments, signed downloads
```

React renders the page in the browser from that boot JSON. Everything money-related is decided on the server: the browser only says *which product*, never *how much*.

Why this design:

- **Fast first paint.** The head, theme and data arrive in the HTML itself. Fonts are preloaded. Admin and legal pages are code-split so the landing page loads less JavaScript.
- **Strict security headers still work.** Boot data lives in `<script type="application/json">`, which the Content-Security-Policy (`script-src 'self'`) allows. Values are escaped so they cannot close the tag.
- **No JavaScript? Crawlers?** The server writes the title, description and a `<noscript>` heading and blurb, and the JSON-LD (`Course` / `Product`) structured data.

In development with `./run-dev.sh hot`, Vite serves the React app on `:5173` and proxies `/api`, `/download` and `/admin/export` to FastAPI on `:8000`. Without boot JSON the app fetches `/api/site` and `/api/products/<slug>` instead, so the same code runs in both modes.

---

## 3. Project structure

```
course-store/
├── main.py                  FastAPI app: routes and middleware wiring only
├── config.json              Every non-secret setting (ports, rate limits, site name, home product)
├── .env                     Secrets (Razorpay keys, SECRET_KEY, SMTP). Never commit. Copy from .env.example
├── run-dev.sh / .bat        One-command local run (build + serve)
├── run-lan.sh               Same, reachable from other devices on your Wi-Fi
├── start.sh                 Production start (gunicorn), reads config.json
├── requirements.txt         Python packages
├── scripts/
│   └── build-frontend.sh    Installs Node packages and builds React when needed
│
├── products/                ONE JSON FILE PER PRODUCT. This is where you add things to sell
├── deliverables/            Files buyers download: deliverables/<product-slug>/<file>
├── utility/coupons.json     Discount codes
│
├── library/                 Backend, one module per concern
│   ├── catalog.py           Loads and validates products and coupons (bad JSON never breaks the store)
│   ├── pricing.py           Server-side price, early-access window, coupons, seat counts
│   ├── payments.py          Razorpay orders (REST via httpx) and signature verification
│   ├── security.py          Headers/CSP, rate limiting, signed links, admin auth, validation
│   ├── db.py                SQLite (orders, waitlist)
│   ├── delivery.py          Safe file lookup and signed download links
│   ├── mailer.py            Optional SMTP "your access" email
│   ├── views.py             JSON shapes for React (public data only; never file names or private links)
│   ├── spa.py               Serves the React build and injects SEO tags, theme and boot JSON
│   ├── seo.py               JSON-LD, sitemap, robots
│   ├── config.py            Reads config.json and .env
│   ├── retry.py             Retry helper for outbound calls
│   ├── timing.py            logs/timing.jsonl  (one line per successful order creation)
│   └── error.py             logs/errors.jsonl  (one line per failure)
│
├── frontend/                React app
│   ├── index.html           Shell. Server fills the two <!--SSR:…--> markers
│   ├── vite.config.js       Build (base /static/) and dev proxy
│   └── src/
│       ├── main.jsx         Entry
│       ├── App.jsx          Routes
│       ├── boot.js          Reads the server's boot JSON
│       ├── pages/           ProductPage, IndexPage, ThanksPage, LegalPage, AdminPage, ErrorPage
│       ├── components/      ProductSections (hero, curriculum, pricing…), CheckoutDialog, ParticleWord,
│       │                    Countdown, SeatBar, CountUp, Accordion, WaitlistForm, Chrome (topbar/footer/cookie banner)
│       ├── hooks/           useMedia, usePage
│       ├── lib/             api, format (₹), products (data hook), site, theme, tracking, confetti
│       ├── styles/main.css  All styling, driven by CSS variables
│       └── assets/fonts/    Self-hosted variable fonts
│
├── data/                    SQLite database (created automatically, not in git)
├── logs/                    timing.jsonl, errors.jsonl (not in git)
└── tests/                   pytest suite (backend); frontend/src/**/*.test.js (vitest)
```

---

## 4. Day-to-day workflow

| You want to… | Do this |
|---|---|
| Edit text, prices, colours of a product | Edit `products/<slug>.json`. The server picks it up within ~5 seconds (or click **Reload products** in `/admin`). No rebuild |
| Add a product | See [Sell something new](#5-sell-something-new). No rebuild |
| Change site name, address, support email | Edit `config.json`, restart the server |
| Change layout, animations, components | Edit files in `frontend/src/`. Use `./run-dev.sh hot` and open `:5173` for instant updates |
| Ship a frontend change | `cd frontend && npm run build` (or let `run-dev.sh` / `start.sh` do it). The server detects the new build automatically |
| Change backend behaviour | Edit `library/*.py` or `main.py`. `run-dev.sh` reloads on save |
| Change legal wording | Edit `frontend/src/pages/LegalPage.jsx` and rebuild. Have a lawyer review it |

Rebuilding is only needed for `frontend/src` changes. Product JSON, config and coupons need no build.

---

## 5. Sell something new

1. Copy `products/quiet-founder-ebook.json` to `products/my-new-thing.json`.
2. Change `slug` (lowercase letters, digits, hyphens), `name`, `headline`, prices, colours and content. Delete sections you don't need: an empty `modules`, `testimonials` or `stats` simply hides that section.
3. Put the files buyers receive in `deliverables/my-new-thing/` and list them under `delivery.files`. For a course hosted elsewhere set `delivery.type` to `"link"` and `access_url` to your private community or platform link (`https://` only). Use `"both"` for files plus a link.
4. Reload: click **Reload products** in `/admin`, or wait a few seconds.
5. Your page is live at `/p/my-new-thing`. Point ads at that URL, or set `site.home_product` in `config.json` to serve it at `/`.

### Product fields

| Field | Meaning |
|---|---|
| `slug`, `name`, `tagline` | Identity. `slug` is the URL |
| `status` | `early_access`, `live`, `coming_soon` or `archived` (see below) |
| `type` | `course`, `ebook` or similar. Used for structured data |
| `headline`, `subhead`, `hero_word`, `cta_label` | Hero copy. `hero_word` is the big word the particles form (keep it short) |
| `theme` | Six hex colours: `hero_bg`, `hero_ink`, `accent`, `accent_ink`, `paper`, `ink`, `muted`. The tests check WCAG contrast |
| `pricing` | `list_price`, optional `early_access_price` + `early_access_ends` (ISO time with timezone), optional `seats_total`. Whole rupees |
| `stats`, `outcomes`, `problem`, `modules`, `includes`, `audience`, `instructor`, `testimonials`, `faq`, `guarantee` | Landing page sections |
| `delivery` | `type`, `files[]` (`id`, `label`, `filename`), `access_url`, `instructions` |
| `seo` | `title`, `description` |

### Status

| status | What visitors see |
|---|---|
| `early_access` | Buy button and a countdown to `early_access_ends`. After that moment the price reverts to `list_price` automatically, decided on the server |
| `live` | Buy button at list price (or the early price while its window is open) |
| `coming_soon` | Waitlist form only, no buying |
| `archived` | Hidden (404) |

`seats_total` shows a real seat meter and stops sales when full. The seat count refreshes every 45 seconds while the page is open. Bad JSON never breaks the store: the broken product is skipped and the problem is listed in `/admin`.

### Coupons

`utility/coupons.json`:

```json
{ "code": "WELCOME10", "percent": 10, "products": ["*"], "max_uses": 200, "expires": "2027-03-31T23:59:00+05:30", "active": true }
{ "code": "FRIEND500", "flat_off": 500, "products": ["ship-saas-30"], "max_uses": 50, "active": true }
```

Discounts are applied on the server. A coupon can never push the price below the minimum payable amount (`pricing.min_amount_paise`).

### Real paid files

`deliverables/*` is git-ignored so paid files never reach your repository. The two sample products' files are committed so the demo works. When you replace them with real files, do **not** `git add -f` them. Deploy them to the server by copying (`scp`/`rsync`) or from private storage.

---

## 6. Customize the design

- **Colours per product:** the `theme` block in the product JSON. Nothing else needed.
- **Fonts:** replace the files in `frontend/src/assets/fonts/` (`display.woff2`, `body.woff2`, `rupee.woff2`) and rebuild. The server preloads the display and body fonts automatically.
- **Layout and sections:** `frontend/src/components/ProductSections.jsx` has one component per section (`Hero`, `Curriculum`, `Pricing`, `Faq`, …). Reorder or remove them in `frontend/src/pages/ProductPage.jsx`.
- **Animations:**
  - Particle hero word: `components/ParticleWord.jsx`
  - 3D tilt and magnetic button: `components/effects.js`
  - Curriculum rail that fills as you scroll: `Curriculum` in `ProductSections.jsx`
  - Confetti on purchase: `lib/confetti.js`
  - All animations stop under the OS "reduce motion" setting, and the particle canvas pauses off-screen.
- **Styling:** `frontend/src/styles/main.css`. Colours, spacing and type scale are CSS variables at the top.
- **Link-preview image:** add `<meta property="og:image" content="…">` in `library/spa.py` (inside `render_page`).

---

## 7. Go live with Razorpay

1. Create a Razorpay account and finish KYC. Their review looks at your site's **Terms, Privacy, Refund and Contact pages**. They exist at `/legal/terms`, `/legal/privacy`, `/legal/refund` and `/legal/contact`. Edit `config.json` (`legal_name`, `address`, `support_email`), review the wording in `frontend/src/pages/LegalPage.jsx`, and have a lawyer check it.
2. Dashboard → Settings → API Keys. Start with **Test Mode** keys and put them in `.env`:
   ```
   RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
   RAZORPAY_KEY_SECRET=xxxxxxxx
   ```
3. Dashboard → Settings → Webhooks → Add: URL `https://YOUR-DOMAIN/api/webhooks/razorpay`, events **payment.captured** and **order.paid**, and a secret. Put the same secret in `.env` as `RAZORPAY_WEBHOOK_SECRET`. This is the safety net for buyers who pay and then close the tab.
4. Keep payment capture on **automatic** in the dashboard.
5. Test in Test Mode with Razorpay's test cards and UPI. Then swap in `rzp_live_…` keys.
6. Set `APP_ENV=production`, `BASE_URL`, a long `SECRET_KEY`, `ALLOWED_HOSTS` and an admin password hash.

Webhooks need a public HTTPS URL. For local testing use a tunnel such as `cloudflared` or `ngrok`.

**How a payment is protected.** The browser only says which product. The server computes the amount, creates the Razorpay order for that amount, and marks it paid only after verifying Razorpay's HMAC signature (checkout callback) or the signed webhook. Both paths are idempotent, check the amount, and a payment ID can unlock only one order. The order page re-checks status every few seconds, so a buyer whose webhook arrives late still sees their access appear.

When the checkout opens Razorpay, the app closes its own dialog first so the two overlays never fight.

---

## 8. Deploy

Any Linux server or container host (Render, Railway, a VPS). Node is needed only to build.

```bash
git clone <repo> course-store && cd course-store
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill it in, APP_ENV=production
./start.sh                # builds React if needed, then gunicorn + uvicorn workers
```

Alternatives:

- **Build elsewhere:** run `cd frontend && npm ci && npm run build` in CI and ship `frontend/dist/` with the app. Then the server needs no Node.
- **Docker:** a two-stage build works well: a `node:20` stage runs `npm ci && npm run build`, a `python:3.12-slim` stage installs `requirements.txt`, copies the project and `frontend/dist`, and runs `./start.sh`.

Put **nginx, Caddy or Cloudflare** in front for HTTPS (required for Razorpay live mode and the HSTS header). Pass the real client IP and set `server.forwarded_allow_ips` in `config.json` to your proxy's IP so rate limiting sees visitors, not the proxy. Cloudflare also gives you a CDN, the biggest speed win for visitors far from your server.

Keep `data/` on persistent storage and back it up (`data/store.db` is every order). SQLite is plenty for thousands of orders a day. If you outgrow it, only `library/db.py` needs to change.

Production environment variables (`.env` or your host's settings):

```
APP_ENV=production
BASE_URL=https://learn.example.com
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
ALLOWED_HOSTS=learn.example.com
RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET / RAZORPAY_WEBHOOK_SECRET
ADMIN_PASSWORD_HASH=<python -m library.security hash "your password">
```

---

## 9. Security

- **Server-side pricing.** The browser can't set an amount, and unknown request fields are rejected.
- **Razorpay signatures** verified with constant-time HMAC; webhook amount and currency checked.
- **Strict Content-Security-Policy** (`script-src 'self'`; Razorpay and analytics hosts allowed only when enabled), plus HSTS, `X-Frame-Options`, `nosniff`, referrer and permissions policies.
- **No secrets or private links in public JSON.** Delivery file names and your private access link are returned only for a verified, *paid* order.
- **CSRF protection** for every state-changing request (Origin and Fetch-Metadata check), `SameSite=Strict` admin cookie.
- **Rate limiting** on checkout, quotes, waitlist, downloads, order status and admin login, plus a global per-IP cap.
- **Signed, expiring download links**, a download-count limit, files served only from `deliverables/<slug>/` and only if declared in the product JSON.
- **Order pages need a signed token.** Wrong tokens return 404, so order IDs can't be guessed.
- **React escapes output by default**, boot JSON is escaped against `</script>` breakouts, SQL is parameterised, inputs are validated, honeypot fields catch bots, CSV exports are formula-injection-safe, request sizes are capped, hosts are checked and API docs are off in production.
- **Admin** at `/admin`: scrypt password hash, login rate limit, HttpOnly cookie, all data behind a cookie-checked JSON API.
- Secrets live only in `.env`. IP addresses are stored hashed.

No site can honestly promise "unhackable". Keep dependencies updated (`pip install -U -r requirements.txt`, `npm audit` / `npm update` in `frontend/`), enable Razorpay's own fraud tools, keep the server patched and back up `data/`. Rate limits are per worker process; add nginx or Cloudflare rate limiting for a hard global limit.

---

## 10. Speed

- The landing page ships one JS bundle (about 96 KB gzipped, React included), one CSS file (about 6 KB gzipped) and two preloaded self-hosted fonts.
- Admin and legal pages load their code only when visited.
- Hashed assets are cached for a year; HTML is rendered per request with the data already inside.
- No third-party requests unless you turn on ad pixels. The particle animation pauses when off-screen and respects "reduce motion".

---

## 11. Ad tracking, email, admin

**Ad tracking.** Set `GA4_ID` and/or `META_PIXEL_ID` in `.env`. A small consent prompt appears and trackers load only after the visitor says yes. The store records `utm_*`, `gclid`, `fbclid` and `ref` from the ad click with each order and waitlist signup, and `/admin` shows paid orders by `utm_source`. Events sent: view item, begin checkout, purchase (once per order), lead.

**Email.** Set the `SMTP_*` values in `.env` (Brevo, Amazon SES, a Gmail app password…) and buyers get their order link by email. Without SMTP they still get instant access on the confirmation page, and the page copy adjusts automatically.

**Admin.** Open `/admin`. Create a hash with `python -m library.security hash "your password"` and put it in `.env` as `ADMIN_PASSWORD_HASH`. (`ADMIN_PASSWORD` works only in development.) The dashboard shows revenue, orders, waitlist size, sales by product and by ad source, setup warnings, CSV exports and a **Reload products** button. Revenue counts real Razorpay payments only.

---

## 12. Configuration reference

`config.json` (non-secret, committed):

| Section | Keys |
|---|---|
| `server` | `host`, `port`, `workers`, `timeout`, `forwarded_allow_ips` |
| `site` | `name`, `tagline`, `home_product`, `support_email`, `legal_name`, `address`, `support_phone`, `price_note` |
| `pricing` | `min_amount_paise`, `max_coupon_percent` |
| `security` | `max_body_bytes`, `session_ttl_s`, `download_token_ttl_s`, `max_downloads_per_order`, `hsts_max_age_s`, `rate_limits` |
| `razorpay` | `api_base`, `checkout_script`, `timeout_s`, `retry_times`, `retry_delay_s` |
| `catalog`, `database`, `delivery`, `logs`, `mailer`, `static` | paths and timeouts |

`.env` (secrets, never committed): `APP_ENV`, `BASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `ADMIN_PASSWORD_HASH`, `ADMIN_PASSWORD` (dev only), `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `GA4_ID`, `META_PIXEL_ID`.

---

## 13. API reference

Pages (all return the React shell with server-rendered head tags):

| Path | Purpose |
|---|---|
| `/`, `/p/{slug}` | Home and landing pages. Unknown or archived slugs return a real 404 |
| `/thanks/{order}?t=token` | Order page. Bad token: 404 |
| `/legal/{terms,privacy,refund,contact}` | Legal pages |
| `/admin` | Dashboard shell (data needs a login) |
| `/healthz`, `/robots.txt`, `/sitemap.xml`, `/favicon.svg` | Ops and SEO |

JSON API:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/site` | Site settings, catalog list, payment mode |
| GET | `/api/products/{slug}` | Public product data (no files, no private link) |
| GET | `/api/products/{slug}/status` | Live seats and price |
| POST | `/api/checkout/quote` | `{slug, coupon}` → server price |
| POST | `/api/checkout/order` | `{slug, name, email, phone, coupon, utm, website}` → Razorpay order |
| POST | `/api/checkout/verify` | Verify Razorpay signature, mark paid |
| POST | `/api/checkout/demo-pay` | Demo mode only |
| POST | `/api/webhooks/razorpay` | Razorpay webhook (signature required) |
| POST | `/api/leads` | Waitlist signup |
| GET | `/api/orders/{id}?t=token` | Order details. Download links and access link only once paid |
| GET | `/api/orders/{id}/status?t=token` | Polling endpoint |
| GET | `/download/{token}` | Signed file download |
| POST | `/api/admin/login`, `/api/admin/logout`, `/api/admin/reload` | Admin session and catalog reload |
| GET | `/api/admin/overview` | Dashboard data (401 without session) |
| GET | `/admin/export/{orders,leads}.csv` | CSV export (redirects to `/admin` without session) |

Create-order response (example):

```json
{"order_id":"ord_k3...","rz_order_id":"order_Q1...","mode":"razorpay","key_id":"rzp_test_...",
 "amount":799900,"currency":"INR","amount_text":"₹7,999","business":"Kiln",
 "description":"Ship Your First SaaS","prefill":{"name":"...","email":"...","contact":""},"theme_color":"#2B2BFF"}
```

### Logs

`logs/timing.jsonl` (one line per order created) and `logs/errors.jsonl` (one line per failure):

```json
{"ts":"2026-11-01T12:00:00+00:00","task_id":"…","context":"order:ord_k3…","steps":{"quote_s":0.0,"db_s":0.003,"razorpay_s":0.41},"total_s":0.42}
```

---

## 14. Tests

```bash
python -m pytest -q          # backend: 53 tests
cd frontend && npm test      # frontend unit tests (vitest)
```

The backend suite covers payments, signatures, webhooks, idempotency, tampering, coupons, rate limits, CSRF, security headers, no-inline-script CSP, admin auth, CSV injection, catalog validation, theme contrast, and the React JSON API (no leaked delivery data, boot JSON escaping, order links only when paid). Tests never touch the network: Razorpay is stubbed. The React build is not required to run them.

---

## 15. Launch checklist

- [ ] Replace the sample products' **bio, testimonials and numbers** with your own. Never publish invented testimonials or results: Indian consumer-protection rules treat that as misleading advertising.
- [ ] Replace files in `deliverables/` with your real ones, and the sample `access_url`.
- [ ] Edit `config.json`: site name, `legal_name`, `address`, `support_email`, `price_note` (say "inclusive of GST" only if that's true).
- [ ] Review the legal pages with a lawyer; add GST invoicing if you're registered.
- [ ] Real Razorpay keys and webhook; do a ₹1 live test with a real card and refund it.
- [ ] `APP_ENV=production`, `SECRET_KEY`, `ADMIN_PASSWORD_HASH`, `ALLOWED_HOSTS`, `BASE_URL` set. HTTPS on.
- [ ] Add an Open Graph image if you want rich link previews.
- [ ] Back up `data/` on a schedule.

---

## 16. Troubleshooting

| Symptom | Fix |
|---|---|
| Page says "The React frontend has not been built yet" | `cd frontend && npm install && npm run build`, reload |
| `run-dev.sh` says Node is missing or too old | Install Node 20+ from https://nodejs.org/ |
| My React edit doesn't show on `:8000` | Rebuild (`npm run build`), or use `./run-dev.sh hot` and open `:5173` |
| Checkout button does nothing in `:5173` dev mode | Make sure FastAPI is running on `:8000` (the script starts it) |
| `403` on a POST | The CSRF guard saw a different Origin. Use the same host you opened the page on; for another device use `./run-lan.sh` |
| `400 Invalid host header` | Add the hostname to `ALLOWED_HOSTS` in `.env` |
| "Demo checkout is off" | You set `APP_ENV=production` without Razorpay keys. Add keys |
| Buyer paid but sees "Confirming…" | Webhook not configured or secret mismatch. Check `/admin` warnings and the Razorpay webhook log |
| Product doesn't appear | Check `/admin` warnings; the JSON probably failed validation (the reason is listed) |
| Phone can't reach the LAN address | Same Wi-Fi, no "client isolation" on the router, and allow Python through the firewall |
