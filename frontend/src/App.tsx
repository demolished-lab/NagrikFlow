import React, { useEffect, useState } from 'react';
import LandingPage from './LandingPage';
import LoginPanel from './LoginPanel';
import Dashboard from './Dashboard';
import Roadmap from './Roadmap';
import Admin from './Admin';
import AgentPanel from './Agent';
import HomeView from './HomeView';
import { STR, lang, setLang, Lang } from './i18n';
import { api } from './api';

type Tab = 'home' | 'roadmap' | 'civic_twin' | 'agent' | 'admin';
type AuthState = 'landing' | 'login' | 'app';
type Route = { tab: Tab; slug?: string };

const SIDEBAR_ITEMS: { id: Tab; icon: string; label: Record<Lang, string> }[] = [
  { id: 'home', icon: '⌂', label: { en: 'Home', hi: 'होम' } },
  { id: 'roadmap', icon: '⌘', label: { en: 'Path Builder', hi: 'पथ बिल्डर' } },
  { id: 'civic_twin', icon: '▣', label: { en: 'Civic Twin', hi: 'सिविक ट्विन' } },
  { id: 'agent', icon: '◈', label: { en: 'Hermes Agent', hi: 'हर्मीज एजेंट' } },
  { id: 'admin', icon: '⚙', label: { en: 'Admin', hi: 'एडमिन' } },
];

export default function App() {
  const [token] = useState<string>(localStorage.getItem('civic_token') || '');
  const [authState, setAuthState] = useState<AuthState>(token ? 'app' : 'landing');
  const [route, setRoute] = useState<Route>({ tab: 'home' });
  const [lg, setLg] = useState<Lang>(lang());
  const [isAdmin, setIsAdmin] = useState(false);
  const t = STR[lg];

  useEffect(() => {
    if (authState === 'app') {
      api.profile().then((profile) => setIsAdmin(profile.role === 'admin')).catch(() => setIsAdmin(false));
    }
  }, [authState]);

  // Handle hash-based routing
  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.slice(1);
      if (hash.startsWith('/roadmap/')) {
        const slug = hash.replace('/roadmap/', '');
        setRoute({ tab: 'roadmap', slug });
      } else {
        setRoute({ tab: 'home' });
      }
    };
    handleHash();
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  const navigateTo = (tab: Tab, slug?: string) => {
    setRoute({ tab, slug });
    if (tab === 'home' || !slug) {
      window.location.hash = '';
    } else {
      window.location.hash = `/roadmap/${slug}`;
    }
  };

  if (authState === 'landing') return <LandingPage onLogin={() => setAuthState('login')} />;
  if (authState === 'login') return <LoginPanel onLogin={() => setAuthState('app')} />;

  return <div className="cv-app-layout">
    <aside className="cv-sidebar">
      <div className="cv-brand">
        <div className="cv-brand-mark">⌁</div>
        <div>
          <div className="cv-brand-name">Civic Path Navigator</div>
          <div className="cv-brand-sub">Municipal Bureaucracy Path Visualizer</div>
        </div>
        <span className="cv-pswb">PSWB 02</span>
      </div>
      <nav className="cv-nav" aria-label="Main navigation">
        {SIDEBAR_ITEMS.filter((item) => item.id !== 'admin' || isAdmin).map(item => (
          <button
            key={item.id}
            onClick={() => navigateTo(item.id)}
            className={`cv-nav-item ${route.tab === item.id ? 'cv-nav-item-active' : ''}`}
            aria-current={route.tab === item.id ? 'page' : undefined}
          >
            <span className="cv-nav-icon">{item.icon}</span>
            <span>{item.label[lg]}</span>
          </button>
        ))}
      </nav>
      <div className="cv-sidebar-footer">
        <div className="cv-sidebar-callout">
          <strong>Smarter. Simpler.<br />More Connected.</strong>
          <p>One place for your civic needs — powered by verified government sources and your DigiLocker.</p>
        </div>
        <button className="cv-nav-item cv-logout" onClick={() => { localStorage.removeItem('civic_token'); setAuthState('landing'); }}>
          ↪ {t.logout}
        </button>
      </div>
    </aside>
    <main className="cv-main">
      <header className="cv-header">
        <div className="cv-search-bar">
          <span className="cv-search-icon">⌕</span>
          <input
            placeholder="Search for a civic task..."
            aria-label="Search civic tasks"
            className="cv-search-input"
          />
        </div>
        <div className="cv-header-actions">
          <button className="cv-language" onClick={() => { const next = lg === 'en' ? 'hi' : 'en'; setLang(next); setLg(next); }}>
            {lg === 'en' ? 'English / मरaठी' : 'हिन्दी / English'}
          </button>
          <button className="cv-help">? &nbsp;Help</button>
          <button className="cv-profile"><span>●</span> Civic Twin <b>⌄</b></button>
        </div>
      </header>
      <div className="cv-content">
        {route.tab === 'home' && <HomeView />}
        {route.tab === 'roadmap' && <Roadmap slug={route.slug || 'udyam-register'} />}
        {route.tab === 'civic_twin' && <Dashboard />}
        {route.tab === 'agent' && <AgentPanel />}
        {route.tab === 'admin' && <Admin />}
      </div>
    </main>
    <aside className="cv-context-panel"><CivicTwinPanel token={token} isAdmin={isAdmin} /></aside>
  </div>;
}

function CivicTwinPanel({ token, isAdmin }: { token: string; isAdmin: boolean }) {
  const [docs, setDocs] = useState<any[]>([]);
  const [unlocks, setUnlocks] = useState<any[]>([]);
  const [nextWin, setNextWin] = useState<string>('');
  
  useEffect(() => {
    if (!token) return;
    api.brief().then(data => {
      if (data?.documents) setDocs(data.documents);
      if (data?.unlocks) setUnlocks(data.unlocks);
      if (data?.next_win) setNextWin(data.next_win);
    }).catch(() => {});
  }, [token]);
  
  const docList = docs.length > 0 ? docs : [
    { name: 'Identity', status: 'available' },
    { name: 'Address proof', status: 'available' }
  ];
  const unlockList = unlocks.length > 0 ? unlocks : [];
  
  return <div className="cv-twin-panel">
    <div className="cv-twin-heading">
      <span className="cv-twin-avatar">♙</span>
      <div><h2>Your civic twin</h2><p>Your documents, connections and next best step.</p></div>
    </div>
    <div className="cv-twin-section">
      <h3>Your documents</h3>
      {docList.map((doc: any, i: number) => (
        <div key={i} className="cv-twin-doc">
          <span className={`cv-doc-round ${doc.status}`}>{doc.icon || '▤'}</span>
          <strong>{doc.name}</strong>
          <span className={`cv-doc-badge ${doc.status}`}>{doc.status === 'verified' ? 'VERIFIED' : doc.status === 'available' ? 'AVAILABLE' : 'PENDING'}</span>
          <b>›</b>
        </div>
      ))}
    </div>
    {unlockList.length > 0 && <div className="cv-twin-section">
      <h3>What this unlocks</h3>
      {unlockList.map((item: any, i: number) => (
        <div key={i} className="cv-unlock-card">
          <span>▤</span>
          <strong>{item.title || item.name}</strong>
          <b>›</b>
        </div>
      ))}
    </div>}
    {nextWin && <div className="cv-twin-section">
      <div className="cv-next-win">
        <div className="cv-star">★</div>
        <div>
          <strong>Easiest next win</strong>
          <p>{nextWin}</p>
        </div>
        <b>›</b>
      </div>
    </div>}
  </div>;
}
