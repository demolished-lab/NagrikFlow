import React, { useState } from 'react';
import LandingPage from './LandingPage';
import LoginPanel from './LoginPanel';
import Dashboard from './Dashboard';
import Roadmap from './Roadmap';
import Admin from './Admin';
import AgentPanel from './Agent';
import HomeView from './HomeView';
import { STR, lang, setLang, Lang } from './i18n';

type Tab = 'home' | 'roadmap' | 'civic_twin' | 'agent' | 'admin';
type AuthState = 'landing' | 'login' | 'app';

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
  const [tab, setTab] = useState<Tab>('home');
  const [lg, setLg] = useState<Lang>(lang());
  const t = STR[lg];
  if (authState === 'landing') return <LandingPage onLogin={() => setAuthState('login')} />;
  if (authState === 'login') return <LoginPanel onLogin={() => setAuthState('app')} />;

  return <div className="cv-app-layout">
    <aside className="cv-sidebar">
      <div className="cv-brand"><div className="cv-brand-mark">⌁</div><div><div className="cv-brand-name">Civic Path Navigator</div><div className="cv-brand-sub">Municipal Bureaucracy Path Visualizer</div></div><span className="cv-pswb">PSWB 02</span></div>
      <nav className="cv-nav" aria-label="Main navigation">{SIDEBAR_ITEMS.map(item => <button key={item.id} onClick={() => setTab(item.id)} className={`cv-nav-item ${tab === item.id ? 'cv-nav-item-active' : ''}`} aria-current={tab === item.id ? 'page' : undefined}><span className="cv-nav-icon">{item.icon}</span><span>{item.label[lg]}</span></button>)}</nav>
      <div className="cv-sidebar-footer"><div className="cv-sidebar-callout"><strong>Smarter. Simpler.<br />More Connected.</strong><p>One place for your civic needs — powered by verified government sources and your DigiLocker.</p></div><button className="cv-nav-item cv-logout" onClick={() => { localStorage.removeItem('civic_token'); setAuthState('landing'); }}>↪ {t.logout}</button></div>
    </aside>
    <main className="cv-main">
      <header className="cv-header"><div className="cv-search-bar"><span className="cv-search-icon">⌕</span><input placeholder="Search for a civic task (e.g., water connection, birth certificate, property tax...)" aria-label="Search civic tasks" /></div><div className="cv-header-actions"><button className="cv-language" onClick={() => { const next = lg === 'en' ? 'hi' : 'en'; setLang(next); setLg(next); }}>{lg === 'en' ? 'English / मराठी' : 'हिन्दी / English'}</button><button className="cv-help">? &nbsp;Help</button><button className="cv-profile"><span>●</span> Civic Twin <b>⌄</b></button></div></header>
      <div className="cv-content">{tab === 'home' && <HomeView />}{tab === 'roadmap' && <Roadmap slug="udyam-register" />}{tab === 'civic_twin' && <Dashboard />}{tab === 'agent' && <AgentPanel />}{tab === 'admin' && <Admin />}</div>
    </main>
    <aside className="cv-context-panel"><CivicTwinPanel /></aside>
  </div>;
}

function CivicTwinPanel() {
  return <div className="cv-twin-panel"><div className="cv-twin-heading"><span className="cv-twin-avatar">♙</span><div><h2>Your civic twin</h2><p>Your documents, connections and next best step.</p></div></div><div className="cv-twin-section"><h3>Your documents</h3>{[['♙','Identity','VERIFIED','verified'],['▤','Property tax receipt','VERIFIED','verified'],['◉','Address proof','AVAILABLE','available'],['▥','Water bill','MISSING','missing']].map(([icon, name, status, kind]) => <div className="cv-twin-doc" key={name}><span className={`cv-doc-round ${kind}`}>{icon}</span><strong>{name}</strong><span className={`cv-doc-badge ${kind}`}>{status}</span><b>›</b></div>)}</div><div className="cv-twin-section"><h3>⌕ &nbsp;What this unlocks</h3><div className="cv-unlock-card"><span>▤</span><strong>Property tax receipt&nbsp; →<br />water connection application</strong><b>›</b></div></div><div className="cv-twin-section"><div className="cv-next-win"><div className="cv-star">★</div><div><strong>Easiest next win</strong><p>Upload latest occupancy proof</p><small>This will unlock the application step<br />and save 2–3 days.</small></div><b>›</b></div></div><div className="cv-digilocker"><span>▣</span><div><strong>DigiLocker connected · consent active</strong><small>You control what gets shared.</small></div><a href="#manage">Manage access</a></div></div>;
}
