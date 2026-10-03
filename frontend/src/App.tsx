import React, { useEffect, useState } from 'react';
import LandingPage from './LandingPage';
import LoginPanel from './LoginPanel';
import Dashboard from './Dashboard';
import Roadmap from './Roadmap';
import Admin from './Admin';
import AgentPanel from './Agent';
import HomeView from './HomeView';
import PathwaysView from './PathwaysView';
import HelpView from './HelpView';
import SearchView from './SearchView';
import ShowcaseView from './ShowcaseView';
import { TopNav, Footer, type NavTab, type CatalogService } from './nf-kit';
import { lang, setLang, Lang } from './i18n';
import { api } from './api';
import type { UserProfile } from './types';

type Tab = 'home' | 'search' | 'showcase' | 'pathways' | 'documents' | 'help' | 'roadmap' | 'agent' | 'admin';
type BaseTab = Exclude<Tab, 'roadmap'>;
type AuthState = 'landing' | 'login' | 'register' | 'app';
type Route = { tab: Tab; slug?: string; searchKey?: string };
type Navigate = (tab: BaseTab | 'roadmap', slug?: string) => void;

const ALLOWED: BaseTab[] = ['home', 'search', 'showcase', 'pathways', 'documents', 'help', 'agent', 'admin'];

function routeFromHash(): Route {
  const raw = window.location.hash.slice(1);
  const match = raw.match(/^\/roadmap\/([^/?#]+)/);
  if (match) {
    try { return { tab: 'roadmap', slug: decodeURIComponent(match[1]) }; }
    catch { return { tab: 'home' }; }
  }
  const [path] = raw.split('?');
  const tab = path.replace(/^\//, '') as BaseTab;
  if (tab === 'search') return { tab, searchKey: raw };
  return ALLOWED.includes(tab) ? { tab } : { tab: 'home' };
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
  const [unread, setUnread] = useState(0);
  const [profileMenu, setProfileMenu] = useState(false);

  useEffect(() => {
    const handleHash = () => { setRoute(routeFromHash()); setProfileMenu(false); };
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
    api.notifications().then((n) => setUnread(n.unread || 0)).catch(() => setUnread(0));
  }, [authState, token]);

  const navigateTo: Navigate = (tab, slug) => {
    if (tab === 'roadmap' && !slug) return;
    const next = hashForRoute(tab, slug);
    setRoute(tab === 'roadmap' ? { tab, slug } : { tab, searchKey: next });
    const current = window.location.hash.slice(1);
    if (current !== next) window.location.hash = next;
    window.scrollTo({ top: 0 });
  };

  const navFromKit = (tab: NavTab) => {
    if (tab === 'roadmap') return;
    navigateTo(tab as BaseTab);
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
    setUnread(0);
    setProfileMenu(false);
    navigateTo('home');
    setAuthState('landing');
  };

  const buildService = (service: CatalogService) => {
    sessionStorage.setItem('civic_task_prefill', service.task);
    sessionStorage.setItem('civic_location_prefill', JSON.stringify({ city: service.location, state: '', serviceType: '' }));
    sessionStorage.setItem('civic_autobuild', '1');
    navigateTo('home');
  };

  if (route.tab === 'showcase') return <ShowcaseView
    guest={authState !== 'app'}
    userName={profile?.name || profile?.email?.split('@')[0] || ''}
    isAdmin={isAdmin}
    lang={lg}
    onLang={() => { const next = lg === 'en' ? 'hi' : 'en'; setLang(next); setLg(next); }}
    onLogin={() => setAuthState('login')}
    onRegister={() => setAuthState('register')}
    onLogout={logout}
    onNavigate={navFromKit}
  />;
  if (authState === 'landing') return <LandingPage onLogin={() => setAuthState('login')} onRegister={() => setAuthState('register')} onNavigate={navFromKit} />;
  if (authState === 'login' || authState === 'register') return <LoginPanel key={authState} initialMode={authState === 'register' ? 'register' : 'login'} onLogin={onLogin} onBack={() => setAuthState('landing')} />;

  const profileName = profile?.name || profile?.email?.split('@')[0] || 'Your account';
  void profileMenu;

  return <div className="nf-shell">
    <TopNav
      active={route.tab}
      onNavigate={navFromKit}
      userName={profileName}
      isAdmin={isAdmin}
      unread={unread}
      lang={lg}
      onLang={() => { const next = lg === 'en' ? 'hi' : 'en'; setLang(next); setLg(next); }}
      onLogin={() => {}}
      onLogout={logout}
    />
    <main className="nf-main" id="main-content">
      {route.tab === 'home' && <HomeView profile={profile} onNavigate={navigateTo} />}
      {route.tab === 'search' && <SearchView key={route.searchKey || 'search'} authed={true} onRequireAuth={() => {}} onBuildService={buildService} />}
      {route.tab === 'pathways' && <PathwaysView onOpenPath={(slug) => navigateTo('roadmap', slug)} />}
      {route.tab === 'roadmap' && <Roadmap slug={route.slug || ''} onBack={() => navigateTo('pathways')} />}
      {route.tab === 'documents' && <Dashboard onNavigate={(tab, slug) => navigateTo(tab as BaseTab, slug)} />}
      {route.tab === 'help' && <HelpView onBuildPath={() => navigateTo('home')} />}
      {route.tab === 'agent' && (isAdmin
        ? <AgentPanel />
        : <RestrictedView label="Research agent" loaded={profileLoaded} onHome={() => navigateTo('home')} />)}
      {route.tab === 'admin' && (isAdmin
        ? <Admin />
        : <RestrictedView label="Review desk" loaded={profileLoaded} onHome={() => navigateTo('home')} />)}
    </main>
    <Footer onNavigate={navFromKit} />
  </div>;
}

function RestrictedView({ label, loaded, onHome }: { label: string; loaded: boolean; onHome: () => void }) {
  if (!loaded) return <div className="nf-card" style={{ padding: 24 }} role="status"><p className="nf-muted">Checking your access…</p></div>;
  return <div className="nf-card" style={{ padding: 28, textAlign: 'center' }} role="alert">
    <h2>Administrator access required</h2>
    <p className="nf-muted">{label} is limited to administrator accounts, and your account does not have access. If you think this is a mistake, ask an administrator to update your role.</p>
    <button className="nf-btn nf-btn-primary nf-btn-sm" onClick={onHome}>Back to home</button>
  </div>;
}
