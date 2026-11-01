import { Link } from 'react-router-dom';
import { Footer, SolidTopbar } from '../components/Chrome.jsx';
import { usePage } from '../hooks/usePage.js';
import { inr } from '../lib/format.js';
import { useSite } from '../lib/site.jsx';

// Shown at "/" when no home product is configured: a simple list of everything for sale.
export default function IndexPage() {
  const { site, catalog } = useSite();
  usePage({ title: `${site.name}: ${site.tagline}`, description: site.tagline });
  return (
    <>
      <SolidTopbar />
      <main id="main" className="section">
        <div className="wrap">
          <h1 className="display" style={{ fontSize: 'clamp(2.6rem,1.4rem + 5vw,5rem)', lineHeight: 0.98 }}>{site.tagline}</h1>
          <div className="catalog">
            {catalog.map((p) => (
              <Link className="catalog__row" to={`/p/${p.slug}`} key={p.slug} style={{ '--row-accent': p.color }}>
                <div>
                  <h2>{p.name}</h2>
                  <p className="muted">{p.tagline}{p.status === 'coming_soon' ? '. Opening soon.' : ''}</p>
                </div>
                <span className="catalog__price">{p.status === 'coming_soon' ? 'Waitlist' : inr(p.price_paise)}</span>
              </Link>
            ))}
            {catalog.length === 0 && (
              <p className="lede" style={{ paddingTop: '2rem' }}>No products yet. Add a JSON file to the <code>products/</code> folder.</p>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
