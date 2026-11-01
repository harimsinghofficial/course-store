import { Link } from 'react-router-dom';
import { Footer, SolidTopbar } from '../components/Chrome.jsx';
import { usePage } from '../hooks/usePage.js';
import { useSite } from '../lib/site.jsx';
import ErrorPage from './ErrorPage.jsx';

const TITLES = { terms: 'Terms of sale', privacy: 'Privacy policy', refund: 'Refund and cancellation', contact: 'Contact' };

function Mail({ site }) {
  return <a href={`mailto:${site.support_email}`}>{site.support_email}</a>;
}

function Terms({ site }) {
  return (
    <>
      <p>These terms govern your purchase and use of digital products (courses, ebooks, templates and similar) sold by {site.legal_name} ("we", "us") through this website.</p>
      <h2>Digital products</h2>
      <p>Everything we sell is delivered digitally. After your payment is confirmed you receive access through your order page and by email. No physical goods are shipped.</p>
      <h2>Licence</h2>
      <p>When you buy a product you receive a personal, non-transferable licence to use it for yourself. You may not resell, share, publish or redistribute the product or its files, including through download links.</p>
      <h2>Prices and payment</h2>
      <p>Prices are shown in Indian rupees. {site.price_note} Payments are processed by Razorpay; we never see or store your card, UPI or bank details. Early-access prices and discount codes apply only until the date shown and may be withdrawn after that.</p>
      <h2>Access and downloads</h2>
      <p>Download links are personal to your order, expire after a day and can be refreshed from your order page. Each order has a fair-use download limit.</p>
      <h2>Refunds</h2>
      <p>See our <Link to="/legal/refund">refund and cancellation policy</Link>.</p>
      <h2>Liability</h2>
      <p>Products are provided for educational and informational purposes. Results depend on your effort and circumstances and are not guaranteed. To the extent allowed by law, our liability is limited to the amount you paid for the product.</p>
      <h2>Governing law</h2>
      <p>These terms are governed by the laws of India. Disputes are subject to the courts at the location of our registered office.</p>
      <h2>Contact</h2>
      <p>{site.legal_name}, {site.address}. Email <Mail site={site} />.</p>
    </>
  );
}

function Privacy({ site }) {
  return (
    <>
      <p>This policy explains what personal information {site.legal_name} collects when you use this site and why.</p>
      <h2>What we collect</h2>
      <ul>
        <li>Your name, email address and optional phone number when you buy or join a waitlist.</li>
        <li>Order details: product, amount, discount code, time of purchase and payment reference.</li>
        <li>Which ad or link brought you here (for example UTM tags), so we can see which campaigns work.</li>
        <li>A one-way hashed form of your IP address, used to spot abuse. We do not store your raw IP address with orders.</li>
      </ul>
      <h2>What we do not collect</h2>
      <p>Card numbers, UPI IDs, bank details or passwords. Payments are handled entirely by Razorpay.</p>
      <h2>How we use it</h2>
      <p>To deliver your purchase, send your receipt and access links, answer support requests, prevent fraud and, if you joined a waitlist, tell you when a product opens. We do not sell your data.</p>
      <h2>Who we share it with</h2>
      <p>Razorpay (payment processing), our email provider (delivering your emails) and our hosting provider. If analytics or advertising cookies are enabled you will be asked for consent first, and your choice is remembered in your browser.</p>
      <h2>Keeping it</h2>
      <p>We keep order records for as long as tax and accounting law requires. Waitlist emails are kept until you ask us to remove them.</p>
      <h2>Your rights</h2>
      <p>You can ask to see, correct or delete your personal data by writing to <Mail site={site} />.</p>
    </>
  );
}

function Refund({ site, catalog }) {
  return (
    <>
      <p>We want you to be happy with what you buy. Because products are digital and delivered instantly, our refund windows are set per product.</p>
      <h2>Refund windows</h2>
      <ul>
        {catalog.filter((p) => p.guarantee_days).map((p) => (
          <li key={p.slug}><strong>{p.name}:</strong> full refund within {p.guarantee_days} days of purchase.</li>
        ))}
      </ul>
      <h2>How to ask</h2>
      <p>Email <Mail site={site} /> from the address you purchased with and include your order number. We reply within two working days.</p>
      <h2>When refunds are paid</h2>
      <p>Approved refunds go back to the original payment method through Razorpay. Banks usually take 5 to 7 working days to show the credit.</p>
      <h2>Cancellation</h2>
      <p>An order can't be cancelled once payment is confirmed and access has been delivered, but you can request a refund within the window above. If a payment is taken but you receive no access, contact us and we will fix it or refund you in full.</p>
    </>
  );
}

function Contact({ site }) {
  return (
    <>
      <p>Questions about an order, access or a refund? We read every message.</p>
      <h2>Email</h2>
      <p><Mail site={site} /></p>
      {site.support_phone && (<><h2>Phone</h2><p>{site.support_phone}</p></>)}
      <h2>Registered business</h2>
      <p>{site.legal_name}<br />{site.address}</p>
      <h2>Order help</h2>
      <p>Include the order number from your confirmation email. It starts with <code>ord_</code>.</p>
    </>
  );
}

export default function LegalPage({ page }) {
  const { site, catalog } = useSite();
  const title = TITLES[page];
  usePage({ title: `${title || 'Not found'} | ${site.name}`, description: title ? `${title} for ${site.name}.` : undefined });
  if (!title) return <ErrorPage code={404} message="That page doesn't exist." />;
  return (
    <>
      <SolidTopbar />
      <main id="main" className="section">
        <article className="wrap prose">
          <h1 className="display">{title}</h1>
          {page === 'terms' && <Terms site={site} />}
          {page === 'privacy' && <Privacy site={site} />}
          {page === 'refund' && <Refund site={site} catalog={catalog} />}
          {page === 'contact' && <Contact site={site} />}
        </article>
      </main>
      <Footer />
    </>
  );
}
