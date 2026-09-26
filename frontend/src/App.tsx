import React, { useState } from 'react';
import LandingPage from './LandingPage';
import LoginPanel from './LoginPanel';
import Dashboard from './Dashboard';
import Roadmap from './Roadmap';
import Admin from './Admin';
import AgentPanel from './Agent';
import { api } from './api';
import { STR, lang, setLang, Lang } from './i18n';

type Tab = 'me' | 'roadmap' | 'agent' | 'admin';
type AuthState = 'landing' | 'login' | 'app';

export default function App() {
  const [token] = useState<string>(localStorage.getItem('civic_token') || '');
  const [authState, setAuthState] = useState<AuthState>(token ? 'app' : 'landing');
  const [tab, setTab] = useState<Tab>('me');
  const [lg, setLg] = useState<Lang>(lang());
  const t = STR[lg];

  const handleLogin = () => setAuthState('app');

  if (authState === 'landing') {
    return <LandingPage onLogin={() => setAuthState('login')} />;
  }

  if (authState === 'login') {
    return <LoginPanel onLogin={handleLogin} />;
  }

  // App is authenticated — show main UI
  return (
    <div style={{ minHeight: '100vh', background: 'var(--paper-2)' }}>
      {/* Tricolor top bar */}
      <div className="tricolor-bar" style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100 }} />

      {/* Header Navigation */}
      <header style={{
        background: 'rgba(255,255,255,0.95)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--line)',
        padding: '16px 24px',
        position: 'sticky',
        top: 4,
        zIndex: 99,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--indigo)', margin: 0 }}>
            🗺️ {t.appTitle}
          </h1>

          {/* Navigation Tabs */}
          <nav style={{ display: 'flex', gap: 4, marginLeft: 16, borderTop: '1px solid var(--line)', paddingLeft: 16 }}>
            {([['me', t.myDashboard], ['roadmap', t.roadmap], ['agent', t.agent], ['admin', t.admin]] as [Tab, string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                style={{
                  padding: '8px 12px',
                  borderRadius: '8px 8px 0 0',
                  border: 'none',
                  borderBottom: tab === key ? '2px solid var(--saffron)' : '2px solid transparent',
                  background: tab === key ? 'rgba(249,115,22,0.1)' : 'transparent',
                  color: tab === key ? 'var(--saffron)' : 'var(--ink-2)',
                  fontWeight: tab === key ? 600 : 500,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  fontSize: 14,
                }}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Language Switcher */}
          <select aria-label="language" value={lg} onChange={(e) => { setLang(e.target.value as Lang); setLg(e.target.value as Lang); }}
            style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid var(--line)', fontSize: 13 }}>
            <option value="en">English</option>
            <option value="hi">हिंदी</option>
          </select>

          <button
            className="cv-btn cv-btn-ghost"
            style={{ padding: '6px 12px', fontSize: 12 }}
            onClick={() => {
              if (confirm('Export all your data?')) {
                api.dashboard().then(data => {
                  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `civic-data-${new Date().toISOString().split('T')[0]}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }).catch(() => alert('Export failed'));
              }
            }}
          >
            📥 Export
          </button>

          <button className="cv-btn cv-btn-ghost" onClick={() => { localStorage.removeItem('civic_token'); setAuthState('landing'); }}>
            {t.logout}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main id="main-content" style={{ maxWidth: 1200, margin: '0 auto', padding: '24px' }}>
        {tab === 'me' && <Dashboard />}
        {tab === 'roadmap' && <Roadmap slug="udyam-register" />}
        {tab === 'agent' && <AgentPanel />}
        {tab === 'admin' && <Admin />}
      </main>

      {/* Footer */}
      <footer style={{
        background: 'var(--paper)',
        borderTop: '1px solid var(--line)',
        padding: '24px',
        marginTop: 48,
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', textAlign: 'center' }}>
          <div className="tricolor" style={{ width: 80, margin: '0 auto 16px' }} />
          <p style={{ color: 'var(--ink-3)', fontSize: 13 }}>
            An initiative supporting Digital India. DPDP Act compliant.
          </p>
          <p style={{ color: 'var(--ink-4)', fontSize: 11, marginTop: 8 }}>
            Informational purposes only. Verify with official government sources.
          </p>
        </div>
      </footer>
    </div>
  );
}
