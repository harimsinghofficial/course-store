import { Link } from 'react-router-dom';
import { Footer, SolidTopbar } from '../components/Chrome.jsx';
import { usePage } from '../hooks/usePage.js';
import { useSite } from '../lib/site.jsx';

export default function ErrorPage({ code = 404, message = "That page doesn't exist." }) {
  const { site } = useSite();
  usePage({ title: `${code} | ${site.name}`, robots: 'noindex,nofollow' });
  return (
    <>
      <SolidTopbar />
      <main id="main" className="wrap errorpage">
        <p className="code">{code}</p>
        <h1 className="display" style={{ fontSize: 'clamp(1.6rem,1.2rem + 1.6vw,2.4rem)' }}>{message}</h1>
        <p><Link className="btn" to="/">Back to the home page</Link></p>
      </main>
      <Footer />
    </>
  );
}
