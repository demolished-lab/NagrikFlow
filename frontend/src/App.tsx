import React, { useEffect, useState } from 'react';
import LandingPage from './LandingPage';
import LoginPanel from './LoginPanel';
import Dashboard from './Dashboard';
import Roadmap from './Roadmap';
import Admin from './Admin';
import AgentPanel from './Agent';
import PerformanceView from './PerformanceView';
import HomeView from './HomeView';
import PathwaysView from './PathwaysView';
import HelpView from './HelpView';
import { STR, lang, setLang, Lang } from './i18n';
import { api } from './api';
import type { UserProfile } from './types';

type Tab = 'home' | 'pathways' | 'documents' | 'help' | 'roadmap' | 'agent' | 'admin' | 'performance';
type BaseTab = Exclude<Tab, 'roadmap'>;
type AuthState = 'landing' | 'login' | 'register' | 'app';
type Route = { tab: Tab; slug?: string };
type Navigate = (tab: BaseTab | 'roadmap', slug?: string) => void;

const MAIN_NAV: { id: BaseTab; icon: string; label: Record<Lang, string> }[] = [
  { id: 'home', icon: 'home', label: { en: 'Home', hi: 'होम' } },
  { id: 'pathways', icon: 'path', label: { en: 'My pathways', hi: 'मेरे रास्ते' } },
  { id: 'documents', icon: 'document', label: { en: 'Documents', hi: 'दस्तावेज़' } },
  { id: 'help', icon: 'help', label: { en: 'Help', hi: 'सहायता' } },
];

function routeFromHash(): Route {
  const hash = window.location.hash.slice(1);
  const match = hash.match(/^\/roadmap\/([^/?#]+)/);
  if (match) {
    try { return { tab: 'roadmap', slug: decodeURIComponent(match[1]) }; }
    catch { return { tab: 'home' }; }
  }
  const allowed: BaseTab[] = ['home', 'pathways', 'documents', 'help', 'agent', 'admin', 'performance'];
  const tab = hash.replace(/^\//, '') as BaseTab;
  return allowed.includes(tab) ? { tab } : { tab: 'home' };
}

function hashForRoute(tab: Tab, slug?: string): string {
  if (tab === 'roadmap' && slug) return `/roadmap/${encodeURIComponent(slug)}`;
  return tab === 'home' ? '' : `/${tab}`;
}

export default function App() {
  const [token, setToken] = useState<string>(localStorage.getItem('civic_token') || '');
  const [authState, setAuthState] = useState<AuthState>(token ? 'app' : 'landing');
  const [route, setRoute] = useState<Route>(() => routeFromHash());
  const [lg, setLg] = useState<Lang>(lang());
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [search, setSearch] = useState('');
  const [profileMenu, setProfileMenu] = useState(false);
  const t = STR[lg];

  useEffect(() => {
    const handleHash = () => setRoute(routeFromHash());
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  useEffect(() => {
    if (authState !== 'app' || !token) return;
    api.profile().then((data: UserProfile) => {
      setProfile(data);
      setIsAdmin(data.role === 'admin');
    }).catch(() => {
      setProfile(null);
      setIsAdmin(false);
    }).finally(() => setProfileLoaded(true));
  }, [authState, token]);

  const navigateTo: Navigate = (tab, slug) => {
    if (tab === 'roadmap' && !slug) return;
    const next = hashForRoute(tab, slug);
    setRoute(tab === 'roadmap' ? { tab, slug } : { tab });
    const current = window.location.hash.slice(1);
    if (current !== next) window.location.hash = next;
  };

  const onLogin = () => {
    const savedToken = localStorage.getItem('civic_token') || '';
    setToken(savedToken);
    setAuthState('app');
  };

  const logout = () => {
    localStorage.removeItem('civic_token');
    setToken('');
    setProfile(null);
    setProfileLoaded(false);
    setIsAdmin(false);
    setProfileMenu(false);
    navigateTo('home');
    setAuthState('landing');
  };

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    const value = search.trim();
    if (!value) return;
    sessionStorage.setItem('civic_task_prefill', value);
    navigateTo('home');
    window.dispatchEvent(new CustomEvent('civic:search-task', { detail: value }));
    setSearch('');
  };

  if (authState === 'landing') return <LandingPage onLogin={() => setAuthState('login')} onRegister={() => setAuthState('register')} />;
  if (authState === 'login' || authState === 'register') return <LoginPanel key={authState} initialMode={authState === 'register' ? 'register' : 'login'} onLogin={onLogin} onBack={() => setAuthState('landing')} />;

  const profileName = profile?.name || profile?.email?.split('@')[0] || 'Your account';
  const initials = profileName.split(/[\s._-]+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('') || 'C';

  return <div className="cv-app-layout">
    <aside className="cv-sidebar">
      <button className="cv-brand" onClick={() => navigateTo('home')} aria-label="Civic Path Navigator home">
        <span className="cv-brand-mark" aria-hidden="true">
          <svg viewBox="0 0 44 44" role="img"><path d="M7 26c9-1 18-8 23-20 2 12-4 24-17 28-4 1-7-2-6-8Z" fill="#df8e43"/><path d="M7 32c9-1 17-6 24-16 0 12-6 22-19 24-4 0-7-3-5-8Z" fill="#1b7a68"/></svg>
        </span>
        <span className="cv-brand-copy"><strong>Civic Path<br />Navigator</strong><small>Government services.<br />Simpler together.</small></span>
      </button>
      <nav className="cv-nav" aria-label="Main navigation">
        <span className="cv-nav-caption">YOUR SPACE</span>
        {MAIN_NAV.map((item) => <button
          key={item.id}
          onClick={() => navigateTo(item.id)}
          className={`cv-nav-item ${((route.tab === item.id) || (route.tab === 'roadmap' && item.id === 'pathways')) ? 'cv-nav-item-active' : ''}`}
          aria-current={((route.tab === item.id) || (route.tab === 'roadmap' && item.id === 'pathways')) ? 'page' : undefined}
        ><NavIcon name={item.icon} /><span>{item.label[lg]}</span></button>)}
        {isAdmin && <>
          <span className="cv-nav-caption cv-nav-caption-secondary">ADMIN TOOLS</span>
          <button className={`cv-nav-item ${route.tab === 'agent' ? 'cv-nav-item-active' : ''}`} onClick={() => navigateTo('agent')} aria-current={route.tab === 'agent' ? 'page' : undefined}><NavIcon name="spark" /><span>Research agent</span></button>
          <button className={`cv-nav-item ${route.tab === 'admin' ? 'cv-nav-item-active' : ''}`} onClick={() => navigateTo('admin')} aria-current={route.tab === 'admin' ? 'page' : undefined}><NavIcon name="settings" /><span>Review desk</span></button>
          <button className={`cv-nav-item ${route.tab === 'performance' ? 'cv-nav-item-active' : ''}`} onClick={() => navigateTo('performance')} aria-current={route.tab === 'performance' ? 'page' : undefined}><NavIcon name="chart" /><span>Performance</span></button>
        </>}
      </nav>
      <div className="cv-sidebar-bottom">
        <div className="cv-sidebar-trust"><span className="cv-trust-mark">✓</span><p><strong>Clear steps, trusted sources.</strong><br />Always confirm details on the official site before applying.</p></div>
        <div className="cv-sidebar-user"><span className="cv-user-avatar">{initials}</span><span className="cv-user-name"><strong>{profileName}</strong><small>{[profile?.city, profile?.state].filter(Boolean).join(', ') || 'Citizen account'}</small></span><button className="cv-user-menu-btn" onClick={() => setProfileMenu((open) => !open)} aria-label="Account options" aria-expanded={profileMenu}>⋯</button></div>
        {profileMenu && <div className="cv-user-menu"><button onClick={() => navigateTo('documents')}>Documents & progress</button><button onClick={logout}>Sign out</button></div>}
      </div>
    </aside>

    <main className="cv-main">
      <header className="cv-header">
        <div className="cv-header-promise">Find. Understand. Complete.</div>
        <form className="cv-search-bar" onSubmit={submitSearch} role="search">
          <span className="cv-search-icon" aria-hidden="true">⌕</span>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search services..." aria-label="Search civic services" className="cv-search-input" />
          <button type="submit" className="cv-search-submit" aria-label="Search">↵</button>
        </form>
        <div className="cv-header-actions">
          <button className="cv-language" onClick={() => { const next = lg === 'en' ? 'hi' : 'en'; setLang(next); setLg(next); }} aria-label="Change language">{lg === 'en' ? 'English' : 'हिन्दी'} <span>⌄</span></button>
          <button className="cv-help" onClick={() => navigateTo('help')}><NavIcon name="help" /> <span>Help</span></button>
          <button className="cv-header-profile" onClick={() => navigateTo('documents')} aria-label={`Open documents and progress for ${profileName}`}><span className="cv-user-avatar">{initials}</span><span className="cv-header-name">{profileName}</span><b>⌄</b></button>
        </div>
      </header>
      <div className="cv-content" id="main-content">
        {route.tab === 'home' && <HomeView profile={profile} onNavigate={navigateTo} />}
        {route.tab === 'pathways' && <PathwaysView onOpenPath={(slug) => navigateTo('roadmap', slug)} />}
        {route.tab === 'roadmap' && <Roadmap slug={route.slug || ''} onBack={() => navigateTo('pathways')} />}
        {route.tab === 'documents' && <Dashboard />}
        {route.tab === 'help' && <HelpView onBuildPath={() => navigateTo('home')} />}
        {route.tab === 'agent' && (isAdmin
          ? <AgentPanel />
          : <RestrictedView label="Research agent" loaded={profileLoaded} onHome={() => navigateTo('home')} />)}
        {route.tab === 'admin' && (isAdmin
          ? <Admin />
          : <RestrictedView label="Review desk" loaded={profileLoaded} onHome={() => navigateTo('home')} />)}
        {route.tab === 'performance' && (isAdmin
          ? <PerformanceView />
          : <RestrictedView label="Performance monitoring" loaded={profileLoaded} onHome={() => navigateTo('home')} />)}
      </div>
    </main>
  </div>;
}

function RestrictedView({ label, loaded, onHome }: { label: string; loaded: boolean; onHome: () => void }) {
  if (!loaded) return <div className="cv-page-state" role="status">Checking your access…</div>;
  return <div className="cv-empty-card" role="alert">
    <span className="cv-empty-icon" aria-hidden="true">403</span>
    <h2>Administrator access required</h2>
    <p>{label} is limited to administrator accounts, and your account does not have access. If you think this is a mistake, ask an administrator to update your role.</p>
    <button className="cv-btn cv-btn-indigo" onClick={onHome}>Back to home</button>
  </div>;
}

function NavIcon({ name }: { name: string }) {
  const common = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const };
  switch (name) {
    case 'home': return <svg {...common}><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-7h6v7"/></svg>;
    case 'path': return <svg {...common}><circle cx="6" cy="6" r="2.3"/><circle cx="18" cy="18" r="2.3"/><circle cx="18" cy="6" r="2.3"/><path d="M8.3 6H13a5 5 0 0 1 5 5v4.7"/></svg>;
    case 'document': return <svg {...common}><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6M9 16h6"/></svg>;
    case 'help': return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 1 1 4.3 1.8c-1 .9-1.9 1.2-1.9 2.7M12 17.2h.01"/></svg>;
    case 'spark': return <svg {...common}><path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z"/><path d="m19 16 .9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9L19 16Z"/></svg>;
    case 'chart': return <svg {...common}><path d="M4 19V5M4 19h17"/><path d="m7 15 3-4 3 2 5-6"/><circle cx="7" cy="15" r="1"/><circle cx="10" cy="11" r="1"/><circle cx="13" cy="13" r="1"/><circle cx="18" cy="7" r="1"/></svg>;
    default: return <svg {...common}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.8 1.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5v.2h-2.6v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1-1.8-1.8.1-.1A1.7 1.7 0 0 0 8 15a1.7 1.7 0 0 0-1.5-1H6.3v-2.6h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1 1.8-1.8.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.5v-.2H15v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.8 1.8-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.2V14h-.2a1.7 1.7 0 0 0-1.5 1Z"/></svg>;
  }
}
