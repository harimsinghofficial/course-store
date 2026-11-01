import { lazy, Suspense, useEffect } from 'react';
import { Route, Routes, useLocation, useParams } from 'react-router-dom';
import { boot } from './boot.js';
import { ConsentBanner } from './components/Chrome.jsx';
import ErrorPage from './pages/ErrorPage.jsx';
import IndexPage from './pages/IndexPage.jsx';
import ProductPage from './pages/ProductPage.jsx';
import ThanksPage from './pages/ThanksPage.jsx';
import { useSite } from './lib/site.jsx';

// Rarely visited pages are split out so the landing page bundle stays small.
const LegalPage = lazy(() => import('./pages/LegalPage.jsx'));
const AdminPage = lazy(() => import('./pages/AdminPage.jsx'));

function ScrollToTop() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) window.scrollTo(0, 0);
  }, [pathname, hash]);
  return null;
}

const ProductRoute = () => <ProductPage slug={useParams().slug} />;
const ThanksRoute = () => <ThanksPage id={useParams().id} />;
const LegalRoute = () => <LegalPage page={useParams().page} />;

function Home() {
  const { site, catalog } = useSite();
  const home = site.home_product;
  if (home && catalog.some((p) => p.slug === home)) return <ProductPage slug={home} />;
  return <IndexPage />;
}

export default function App() {
  const location = useLocation();
  // The server tells us when it rendered an error page for the first URL (404, bad order link, etc.).
  if (boot.error && location.key === 'default') return <ErrorPage code={boot.error.code} message={boot.error.message} />;
  return (
    <>
      <ScrollToTop />
      <Suspense fallback={null}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/p/:slug" element={<ProductRoute />} />
          <Route path="/thanks/:id" element={<ThanksRoute />} />
          <Route path="/legal/:page" element={<LegalRoute />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<ErrorPage />} />
        </Routes>
      </Suspense>
      <ConsentBanner />
    </>
  );
}
