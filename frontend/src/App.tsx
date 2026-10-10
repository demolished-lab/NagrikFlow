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
import SearchView from './SearchView';
import ShowcaseView from './ShowcaseView';
import { Footer, TopNav, type NavTab } from './nf-kit';
import { lang, setLang, type Lang } from './i18n';
import { api } from './api';
import type { UserProfile } from './types';

type Tab = NavTab | 'performance';
type BaseTab = Exclude<Tab, 'roadmap'>;
type AuthState = 'landing' | 'login' | 'register' | 'app';
type Route = { tab: Tab; slug?: string };
type Navigate = (tab: BaseTab | 'roadmap', slug?: string) => void;

function routeFromHash(): Route {
  const hash = window.location.hash.slice(1);
  const match = hash.match(/^\/roadmap\/([^/?#]+)/);
  if (match) {
    try { return { tab: 'roadmap', slug: decodeURIComponent(match[1]) }; }
    catch { return { tab: 'home' }; }
  }
  const allowed: BaseTab[] = ['home', 'search', 'showcase', 'pathways', 'documents', 'help', 'agent', 'admin', 'performance'];
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
    if (window.location.hash.slice(1) !== next) window.location.hash = next;
  };

  const onLogin = () => {
    setToken(localStorage.getItem('civic_token') || '');
    setAuthState('app');
  };

  const logout = () => {
    localStorage.removeItem('civic_token');
    setToken('');
    setProfile(null);
    setProfileLoaded(false);
    setIsAdmin(false);
    navigateTo('home');
    setAuthState('landing');
  };

  const toggleLanguage = () => {
    const next = lg === 'en' ? 'hi' : 'en';
    setLang(next);
    setLg(next);
  };

  if (authState === 'landing') {
    return <LandingPage onLogin={() => setAuthState('login')} onRegister={() => setAuthState('register')} onNavigate={(tab) => navigateTo(tab)} />;
  }
  if (authState === 'login' || authState === 'register') {
    return <LoginPanel key={authState} initialMode={authState === 'register' ? 'register' : 'login'} onLogin={onLogin} onBack={() => setAuthState('landing')} />;
  }

  const profileName = profile?.name || profile?.email?.split('@')[0] || 'Citizen';
  const nav = (tab: NavTab) => navigateTo(tab);
  const onRequireAuth = (task: string) => {
    sessionStorage.setItem('civic_task_prefill', task);
    setAuthState('login');
  };
  const onBuildService = (service: { task: string }) => {
    sessionStorage.setItem('civic_task_prefill', service.task);
    navigateTo('home');
  };

  return <div className="nf-shell">
    <TopNav active={route.tab} onNavigate={nav} userName={profileName} isAdmin={isAdmin} unread={0} lang={lg} onLang={toggleLanguage} onLogin={() => setAuthState('login')} onRegister={() => setAuthState('register')} onLogout={logout} />
    <main className="nf-main nf-main-wide" id="main-content">
      {route.tab === 'home' && <HomeView profile={profile} onNavigate={navigateTo} />}
      {route.tab === 'search' && <SearchView authed onRequireAuth={onRequireAuth} onBuildService={onBuildService} />}
      {route.tab === 'showcase' && <ShowcaseView guest={false} userName={profileName} isAdmin={isAdmin} lang={lg} onLang={toggleLanguage} onLogin={() => setAuthState('login')} onRegister={() => setAuthState('register')} onLogout={logout} onNavigate={nav} />}
      {route.tab === 'pathways' && <PathwaysView onOpenPath={(slug) => navigateTo('roadmap', slug)} />}
      {route.tab === 'roadmap' && <Roadmap slug={route.slug || ''} onBack={() => navigateTo('pathways')} />}
      {route.tab === 'documents' && <Dashboard onNavigate={(tab, slug) => navigateTo(tab, slug)} />}
      {route.tab === 'help' && <HelpView onBuildPath={() => navigateTo('home')} />}
      {route.tab === 'agent' && (isAdmin ? <AgentPanel /> : <RestrictedView label="Research agent" loaded={profileLoaded} onHome={() => navigateTo('home')} />)}
      {route.tab === 'admin' && (isAdmin ? <Admin /> : <RestrictedView label="Review desk" loaded={profileLoaded} onHome={() => navigateTo('home')} />)}
      {route.tab === 'performance' && (isAdmin ? <PerformanceView /> : <RestrictedView label="Performance monitoring" loaded={profileLoaded} onHome={() => navigateTo('home')} />)}
    </main>
    {(route.tab === 'home' || route.tab === 'showcase') && <Footer onNavigate={nav} />}
  </div>;
}

function RestrictedView({ label, loaded, onHome }: { label: string; loaded: boolean; onHome: () => void }) {
  if (!loaded) return <div className="nf-card" role="status" style={{ padding: 24 }}>Checking your access…</div>;
  return <div className="nf-card" role="alert" style={{ padding: 24 }}>
    <span className="nf-badge is-error">403</span>
    <h2>Administrator access required</h2>
    <p>{label} is limited to administrator accounts, and your account does not have access.</p>
    <button className="nf-btn nf-btn-primary" onClick={onHome}>Back to home</button>
  </div>;
}
