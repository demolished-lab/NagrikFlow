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
  { id: 'home', icon: '\U0001f3e0', label: { en: 'Home', hi: 'होम' } },
  { id: 'roadmap', icon: '\U0001f5fa\ufe0f', label: { en: 'Path Builder', hi: 'पथ बिल्डर' } },
  { id: 'civic_twin', icon: '\U0001f464', label: { en: 'Civic Twin', hi: 'सिविक ट्विन' } },
  { id: 'agent', icon: '\U0001f916', label: { en: 'Hermes Agent', hi: 'हर्मीज एजेंट' } },
  { id: 'admin', icon: '\u2699\ufe0f', label: { en: 'Admin', hi: 'एडमिन' } },
];

export default function App() {
  const [token] = useState<string>(localStorage.getItem('civic_token') || '');
  const [authState, setAuthState] = useState<AuthState>(token ? 'app' : 'landing');
  const [tab, setTab] = useState<Tab>('home');
  const [lg, setLg] = useState<Lang>(lang());
  const t = STR[lg];

  const handleLogin = () => setAuthState('app');

  if (authState === 'landing') {
    return <LandingPage onLogin={() => setAuthState('login')} />;
  }

  if (authState === 'login') {
    return <LoginPanel onLogin={handleLogin} />;
  }

  return (
    <div className="cv-app-layout">
      <aside className="cv-sidebar">
        <div className="cv-sidebar-header">
          <div className="cv-logo">
            <span className="cv-logo-icon">{'\U0001f5fa\ufe0f'}</span>
            <span className="cv-logo-text">{t.appTitle}</span>
          </div>
          <p className="cv-tagline">{t.appSubtitle}</p>
        </div>
        <nav className="cv-nav" role="navigation" aria-label="Main navigation">
          {SIDEBAR_ITEMS.map(item => (
            <button
              key={item.id}
              onClick={() => setTab(item.id)}
              className={`cv-nav-item ${tab === item.id ? 'cv-nav-item-active' : ''}`}
              aria-current={tab === item.id ? 'page' : undefined}
            >
              <span className="cv-nav-icon">{item.icon}</span>
              <span className="cv-nav-label">{item.label[lg]}</span>
            </button>
          ))}
        </nav>
        <div className="cv-sidebar-footer">
          <p className="cv-slogan">{t.tagline}</p>
          <div className="cv-lang-switch">
            <select
              value={lg}
              onChange={(e) => { setLang(e.target.value as Lang); setLg(e.target.value as Lang); }}
              aria-label="Select language"
              className="cv-select"
            >
              <option value="en">English</option>
              <option value="hi">हिन्दी</option>
            </select>
          </div>
          <button
            onClick={() => { localStorage.removeItem('civic_token'); setAuthState('landing'); }}
            className="cv-btn cv-btn-ghost cv-btn-sm"
            style={{ width: '100%' }}
          >
            {'\U0001f6aa'} {t.logout}
          </button>
        </div>
      </aside>

      <main className="cv-main">
        <header className="cv-header">
          <div className="cv-search-bar">
            <span className="cv-search-icon">{'\U0001f50d'}</span>
            <input
              type="text"
              placeholder={t.appSubtitle}
              className="cv-search-input"
              aria-label={t.appSubtitle}
            />
          </div>
          <div className="cv-user-pill">
            <span className="cv-user-avatar">{'\U0001f464'}</span>
            <span className="cv-user-name">{t.civicTwin || 'Civic Twin'}</span>
          </div>
        </header>
        <div className="cv-content">
          {tab === 'home' && <HomeView />}
          {tab === 'roadmap' && <Roadmap slug="udyam-register" />}
          {tab === 'civic_twin' && <Dashboard />}
          {tab === 'agent' && <AgentPanel />}
          {tab === 'admin' && <Admin />}
        </div>
      </main>

      <aside className="cv-context-panel">
        {tab === 'roadmap' && <ContextualRoadmap />}
        {tab === 'civic_twin' && <ContextualDashboard />}
        {tab === 'home' && <ContextualHome />}
        {tab !== 'roadmap' && tab !== 'civic_twin' && tab !== 'home' && (
          <div className="cv-empty-panel">
            <p>{t.rightPanelHint || 'Select a path to see context'}</p>
          </div>
        )}
      </aside>

      <footer className="cv-footer">
        <div className="cv-tricolor-line" />
        <p className="cv-footer-text">{t.footer}</p>
        <p className="cv-disclaimer">{t.disclaimer}</p>
      </footer>
    </div>
  );
}

function ContextualRoadmap() {
  const t = STR[lang()];
  return (
    <div className="cv-context-section">
      <h3>{'\U0001f50d'} {t.sourcesChecked || 'Sources Checked'}</h3>
      <div className="cv-source-list">
        {[
          { name: 'National Government Services Portal', verified: true },
          { name: 'Municipal Corporation portal', verified: true },
          { name: 'DigiLocker', verified: true },
        ].map((src, i) => (
          <div key={i} className={`cv-source-item ${src.verified ? 'cv-verified' : ''}`}>
            <span className="cv-source-dot" />
            <span className="cv-source-name">{src.name}</span>
            {src.verified && <span className="cv-badge cv-badge-success">Verified</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function ContextualDashboard() {
  const t = STR[lang()];
  return (
    <div className="cv-context-section">
      <h3>{'\U0001f4c4'} {t.yourDocuments || 'Your Documents'}</h3>
      <div className="cv-doc-list">
        <div className="cv-doc-item cv-doc-verified">
          <span className="cv-doc-status">{'\u2705'}</span>
          <span className="cv-doc-title">{t.have || 'What you hold'}</span>
          <span className="cv-badge cv-badge-success">Verified</span>
        </div>
        <div className="cv-doc-item" style={{ borderStyle: 'dashed' }}>
          <span className="cv-doc-icon">{'\u2795'}</span>
          <span className="cv-doc-name">{t.addDoc || '+ Add Document'}</span>
        </div>
      </div>
      <h3 style={{ marginTop: 24 }}>{'\U0001f3af'} {t.next || 'Easiest Next Win'}</h3>
      <div className="cv-win-card">
        <p className="cv-win-text">{t.welcomeBack || 'Welcome Back!'}</p>
        <span className="cv-badge cv-badge-info">Save 2\u20133 days</span>
      </div>
      <h3 style={{ marginTop: 24 }}>{'\U0001f680'} {t.whatUnlocks || 'What This Unlocks'}</h3>
      <ul className="cv-unlock-list">
        <li><strong>{t.rnBuildPath || 'Build Path'}</strong> \u2014 Get verified step-by-step roadmap</li>
        <li><strong>{t.dlTitle || 'Connect DigiLocker'}</strong> \u2014 Import your verified documents</li>
      </ul>
    </div>
  );
}

function ContextualHome() {
  const t = STR[lang()];
  return (
    <div className="cv-context-section">
      <h3>{'\u2139\ufe0f'} {t.aboutCivic || 'About this platform'}</h3>
      <p className="cv-about-text">{t.appDesc || 'A civic task navigator...'}</p>
      <div className="cv-trust-badges">
        {[
          { icon: '\U0001f512', text: 'DPDP Act Compliant' },
          { icon: '\U0001f1ee\U0001f1f3', text: 'Digital India' },
          { icon: '\u267f', text: 'WCAG 2.1 AA' },
        ].map((b, i) => (
          <div key={i} className="cv-trust-badge">
            <span>{b.icon}</span>
            <span>{b.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
