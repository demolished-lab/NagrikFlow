import React, { useState } from 'react';

/* Shared NagrikFlow UI kit: top nav, footer, badges, cards, mock catalog. */

export function BrandMark({ size = 34 }: { size?: number }) {
  return <span className="nf-brand-mark" style={{ width: size, height: size, fontSize: size * 0.56 }} aria-hidden="true">N</span>;
}

export type NavTab = 'home' | 'search' | 'showcase' | 'pathways' | 'documents' | 'help' | 'agent' | 'admin' | 'roadmap';

export function TopNav({ active, onNavigate, userName, isAdmin, unread, lang, onLang, onLogin, onRegister, onLogout }: {
  active: string;
  onNavigate: (tab: NavTab) => void;
  userName: string;
  isAdmin: boolean;
  unread: number;
  lang: string;
  onLang: () => void;
  onLogin: () => void;
  onRegister?: () => void;
  onLogout: () => void;
}) {
  const [menu, setMenu] = useState(false);
  const [userMenu, setUserMenu] = useState(false);
  const initials = userName.split(/[\s._-]+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('') || 'C';
  const go = (tab: NavTab) => {
    setMenu(false);
    // Guests have no workspace yet — route them through sign-in first.
    if (!userName && (tab === 'search' || tab === 'documents' || tab === 'pathways')) { onLogin(); return; }
    onNavigate(tab);
  };
  return <header className="nf-topnav">
    <div className="nf-topnav-inner">
      <button className="nf-brand" onClick={() => go('home')} aria-label="NagrikFlow home">
        <BrandMark /><span className="nf-brand-name">Nagrik<span>Flow</span></span>
      </button>
      <nav className={`nf-nav ${menu ? 'is-open' : ''}`} aria-label="Main navigation">
        <button className={active === 'home' ? 'is-active' : ''} onClick={() => go('home')} aria-current={active === 'home' ? 'page' : undefined}>Home</button>
        <button className={active === 'search' ? 'is-active' : ''} onClick={() => go('search')} aria-current={active === 'search' ? 'page' : undefined}>Services</button>
        <button className={active === 'documents' ? 'is-active' : ''} onClick={() => go('documents')} aria-current={active === 'documents' ? 'page' : undefined}>Documents</button>
        <button className={active === 'help' ? 'is-active' : ''} onClick={() => go('help')} aria-current={active === 'help' ? 'page' : undefined}>About</button>
        <button className={active === 'help' ? 'is-active' : ''} onClick={() => go('help')}>Help</button>
        {isAdmin && <button className={active === 'admin' ? 'is-active' : ''} onClick={() => go('admin')}>Admin</button>}
      </nav>
      <div className="nf-top-actions">
        <button className="nf-lang-btn" onClick={onLang} aria-label="Change language">{lang === 'en' ? 'English' : 'हिन्दी'} ⌄</button>
        {userName ? <>
          <button className="nf-icon-btn" onClick={() => go('documents')} aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}>🔔{unread > 0 && <span className="nf-dot" />}</button>
          <span className="nf-user-chip"><button className="nf-avatar-btn" onClick={() => setUserMenu((v) => !v)} aria-label={`Account options for ${userName}`} aria-expanded={userMenu}>{initials}</button><small>{userName}</small></span>
          {userMenu && <div className="nf-user-menu">
            <button onClick={() => { setUserMenu(false); go('pathways'); }}>My pathways</button>
            <button onClick={() => { setUserMenu(false); go('documents'); }}>Documents &amp; progress</button>
            {isAdmin && <button onClick={() => { setUserMenu(false); go('agent'); }}>Research agent</button>}
            <button onClick={() => { setUserMenu(false); onLogout(); }}>Sign out</button>
          </div>}
        </> : <>
          <button className="nf-login-link" onClick={onLogin}>Login</button>
          <button className="nf-btn nf-btn-primary nf-btn-sm" onClick={() => { setMenu(false); (onRegister || onLogin)(); }}>Register</button>
        </>}
        <button className="nf-icon-btn nf-menu-btn" onClick={() => setMenu((v) => !v)} aria-label="Open navigation menu" aria-expanded={menu}>☰</button>
      </div>
    </div>
  </header>;
}

export function Footer({ onNavigate }: { onNavigate: (tab: NavTab) => void }) {
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);
  return <footer className="nf-footer">
    <div className="nf-footer-inner">
      <div className="nf-footer-brand">
        <button className="nf-brand" onClick={() => onNavigate('home')} aria-label="NagrikFlow home">
          <BrandMark /><span className="nf-brand-name" style={{ color: '#fff' }}>Nagrik<span>Flow</span></span>
        </button>
        <p>From government maze to clear next steps. Official source. Verified information. A simpler India.</p>
        <div className="nf-social" aria-label="Social links">
          <a href="https://www.linkedin.com/" target="_blank" rel="noreferrer" aria-label="LinkedIn">in</a>
          <a href="https://t.me/" target="_blank" rel="noreferrer" aria-label="Telegram">✈</a>
          <a href="https://www.youtube.com/" target="_blank" rel="noreferrer" aria-label="YouTube">▶</a>
        </div>
        <div className="nf-store-row">
          <a href="https://play.google.com/" target="_blank" rel="noreferrer">▶ Google Play</a>
          <a href="https://www.apple.com/app-store/" target="_blank" rel="noreferrer">🍎 App Store</a>
        </div>
      </div>
      <div><h4>Quick Links</h4><ul>
        <li><button onClick={() => onNavigate('home')}>Home</button></li>
        <li><button onClick={() => onNavigate('search')}>Services</button></li>
        <li><button onClick={() => onNavigate('help')}>About Us</button></li>
        <li><button onClick={() => onNavigate('help')}>Help</button></li>
        <li><button onClick={() => onNavigate('help')}>Contact</button></li>
      </ul></div>
      <div><h4>Support</h4><ul>
        <li><button onClick={() => onNavigate('help')}>FAQs</button></li>
        <li><button onClick={() => onNavigate('showcase')}>Design System</button></li>
        <li><button onClick={() => onNavigate('help')}>Privacy Policy</button></li>
        <li><button onClick={() => onNavigate('help')}>Terms of Use</button></li>
        <li><button onClick={() => onNavigate('help')}>Accessibility</button></li>
        <li><button onClick={() => onNavigate('help')}>Feedback</button></li>
      </ul></div>
      <div><h4>Stay Updated</h4>
        <p style={{ fontSize: 13, margin: '0 0 4px' }}>Subscribe to get the latest updates on new services and features.</p>
        {subscribed
          ? <p role="status" style={{ color: '#fff', fontWeight: 700 }}>✓ You are subscribed. Welcome aboard!</p>
          : <form className="nf-subscribe" onSubmit={(e) => { e.preventDefault(); if (email.includes('@')) setSubscribed(true); }}>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Enter your email" aria-label="Email for updates" />
            <button type="submit">Subscribe</button>
          </form>}
      </div>
    </div>
    <div className="nf-footer-bottom">
      <span>© 2025 NagrikFlow. All rights reserved. | Built for a better tomorrow.</span>
      <span>Made with <span style={{ color: '#e14b54' }}>❤</span> for every citizen.</span>
    </div>
  </footer>;
}

export function StatusBadge({ status }: { status: string }) {
  const s = (status || '').toLowerCase();
  if (s.includes('complet') || s.includes('verif') || s.includes('reviewed')) return <span className="nf-badge is-done">● Completed</span>;
  if (s.includes('progress') || s.includes('current') || s.includes('ready')) return <span className="nf-badge is-progress">● In Progress</span>;
  if (s.includes('fail') || s.includes('conflict')) return <span className="nf-badge is-error">● Conflict</span>;
  if (s.includes('pending') || s.includes('lock') || s.includes('await')) return <span className="nf-badge is-pending">● Pending</span>;
  return <span className="nf-badge is-info">● {status || 'Draft'}</span>;
}

export function ProgressBar({ percent }: { percent: number }) {
  const p = Math.max(0, Math.min(100, Math.round(percent)));
  return <div><div className="nf-progress-copy"><span>Progress</span><span>{p}%</span></div><div className="nf-progress-track"><span style={{ width: `${p}%` }} /></div></div>;
}

export function Skyline({ height = 120 }: { height?: number }) {
  return <div className="nf-skyline" aria-hidden="true"><svg viewBox="0 0 700 120" style={{ width: '100%', height, display: 'block' }}>
    <g fill="none" stroke="#b9c6e2" strokeWidth="2">
      <path d="M20 110 V60 h18 v-12 h12 v12 h14 v50" />
      <path d="M96 110 V48 q10 -14 22 0 v62" />
      <rect x="132" y="66" width="26" height="44" />
      <path d="M172 110 V40 h10 v-10 h14 v10 h10 v70" />
      <path d="M220 110 V70 h34 V40 h8 v-14 h6 v14 h8 v30 h34 v40" />
      <path d="M330 110 V58 h16 v-8 h12 v8 h14 v52" />
      <path d="M396 110 V30 q12 -16 24 0 v80" />
      <rect x="434" y="64" width="24" height="46" />
      <path d="M472 110 V52 h12 v-12 h10 v12 h12 v58" />
      <path d="M530 110 V66 q14 -10 28 0 v44" />
      <rect x="572" y="58" width="30" height="52" />
      <path d="M616 110 V44 h34 v66" />
      <path d="M8 110 H692" />
    </g>
    <g fill="#cfe0d8">
      <ellipse cx="120" cy="108" rx="26" ry="8" /><ellipse cx="300" cy="108" rx="30" ry="8" /><ellipse cx="480" cy="108" rx="28" ry="8" /><ellipse cx="640" cy="108" rx="26" ry="8" />
    </g>
  </svg></div>;
}

export function HeroSkyline() {
  return <div className="nf-hero-bg" aria-hidden="true"><svg viewBox="0 0 800 300" preserveAspectRatio="xMidYMax slice">
    <rect width="800" height="300" fill="none" />
    <g fill="#ffffff" opacity="0.16">
      <rect x="40" y="150" width="60" height="150" /><rect x="120" y="110" width="44" height="190" />
      <rect x="185" y="170" width="70" height="130" /><rect x="275" y="90" width="52" height="210" />
      <rect x="350" y="140" width="66" height="160" /><rect x="436" y="60" width="48" height="240" />
      <rect x="505" y="130" width="72" height="170" /><rect x="598" y="100" width="50" height="200" />
      <rect x="668" y="150" width="62" height="150" />
    </g>
    <g fill="#ffd98a" opacity="0.5">
      {Array.from({ length: 40 }).map((_, i) => <rect key={i} x={45 + (i * 53) % 700} y={120 + (i * 37) % 150} width="7" height="9" />)}
    </g>
  </svg></div>;
}

/* ---------- mock service catalog for discovery (panel 3) ---------- */
export type CatalogService = {
  id: string;
  title: string;
  department: string;
  description: string;
  category: 'Business' | 'Licences' | 'Certificates' | 'Other';
  tags: string[];
  location: string;
  icon: string;
  color: string;
  task: string;
};

export const SERVICE_CATALOG: CatalogService[] = [
  { id: 'shop', title: 'Shop & Establishments Registration', department: 'Municipal Corporation of Greater Mumbai (MCGM)', description: 'Register your shop, office or commercial establishment under the Shops & Establishments Act.', category: 'Business', tags: ['Business', 'Licence', 'Mumbai'], location: 'Mumbai, Maharashtra', icon: '🏪', color: '#e5f5ec', task: 'Register a small business' },
  { id: 'trade', title: 'Trade Licence', department: 'Municipal Corporation of Greater Mumbai (MCGM)', description: 'Obtain a trade licence for your business activity.', category: 'Licences', tags: ['Business', 'Licence', 'Mumbai'], location: 'Mumbai, Maharashtra', icon: '📋', color: '#e5f5ec', task: 'Apply for a trade licence' },
  { id: 'udyam', title: 'Udyog Aadhaar (MSME Registration)', department: 'Ministry of MSME, Government of India', description: 'Register as a Micro, Small or Medium Enterprise to access schemes and credit.', category: 'Certificates', tags: ['Business', 'Certificate', 'Pan-India'], location: 'Pan-India', icon: '🏭', color: '#e9edfd', task: 'Register for Udyam MSME registration' },
  { id: 'gst', title: 'GST Registration', department: 'Goods and Services Tax Network', description: 'Register for GST to legally operate your business.', category: 'Certificates', tags: ['Business', 'Tax', 'Pan-India'], location: 'Pan-India', icon: '🧾', color: '#e9edfd', task: 'Register for GST' },
  { id: 'driving', title: 'Apply for a Driving Licence', department: 'Regional Transport Office (RTO)', description: 'Start your driving licence application process.', category: 'Licences', tags: ['Transport', 'Licence', 'Pan-India'], location: 'Pan-India', icon: '🚗', color: '#e7f1fd', task: 'Apply for a driving licence' },
  { id: 'birth', title: 'Get Birth Certificate', department: 'Municipal Corporation / Registrar of Births', description: 'Apply for a birth certificate online or offline.', category: 'Certificates', tags: ['Records', 'Certificate', 'Pan-India'], location: 'Pan-India', icon: '📄', color: '#efeafd', task: 'Apply for a birth certificate' },
  { id: 'property', title: 'Property Registration', department: 'Sub-Registrar Office / State Stamps & Registration', description: 'Register your property with the government.', category: 'Other', tags: ['Property', 'Registration'], location: 'Pan-India', icon: '🏠', color: '#fdf1dc', task: 'Register a property' },
  { id: 'property-tax', title: 'Pay Property Tax', department: 'Municipal Corporation', description: 'Pay your annual property tax online.', category: 'Other', tags: ['Tax', 'Payment'], location: 'Mumbai, Maharashtra', icon: '💰', color: '#fdf1dc', task: 'Pay property tax' },
];

export const POPULAR_SERVICES = [
  { icon: '🏪', color: '#e5f5ec', title: 'Register a Small Business', desc: 'Get your business legally registered in India.', task: 'Register a small business' },
  { icon: '🚗', color: '#e7f1fd', title: 'Apply for a Driving Licence', desc: 'Start your driving licence application process.', task: 'Apply for a driving licence' },
  { icon: '🏠', color: '#fdf1dc', title: 'Property Registration', desc: 'Register your property with the government.', task: 'Register a property' },
  { icon: '📄', color: '#efeafd', title: 'Get Birth Certificate', desc: 'Apply for a birth certificate online or offline.', task: 'Apply for a birth certificate' },
];
