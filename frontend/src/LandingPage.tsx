import React, { useRef, useState } from 'react';
import { SERVICE_TYPES } from './types';
import { TopNav, Footer, HeroSkyline, Skyline, POPULAR_SERVICES, type NavTab } from './nf-kit';

interface LandingProps {
  onLogin: () => void;
  onRegister?: () => void;
  onNavigate: (tab: NavTab) => void;
}

const EXAMPLES = ['Register a vehicle', 'Apply for a driving licence', 'Get a birth certificate', 'Pay property tax'];
const EXAMPLE_STEPS = [
  { title: 'Prepare PAN and Aadhaar', detail: 'Keep identity details ready for the applicant and business.' },
  { title: 'Complete Udyam registration', detail: 'Use the official portal to register an eligible MSME.' },
  { title: 'Check GST requirements', detail: 'Register if the business meets the current eligibility criteria.' },
  { title: 'Review state business rules', detail: 'Check the relevant Shops & Establishments requirements.' },
];

const FEATURES = [
  { icon: '🪜', color: '#e9edfd', title: 'Step-by-Step Guidance', desc: 'Understand the exact process, forms and deadlines.' },
  { icon: '🛡️', color: '#efeafd', title: 'Verified Sources', desc: 'Every detail linked to official government websites.' },
  { icon: '📈', color: '#e5f5ec', title: 'Track Progress', desc: 'Keep track of your application status in real time.' },
  { icon: '🌐', color: '#fdf1dc', title: 'Multi-Jurisdiction', desc: 'Support for India\u2019s central, state and local government services.' },
];

export default function LandingPage({ onLogin, onRegister, onNavigate }: LandingProps) {
  const [task, setTask] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [serviceType, setServiceType] = useState('');
  const [heroQuery, setHeroQuery] = useState('');
  const composerRef = useRef<HTMLDivElement>(null);

  const continueToAuth = (intent?: string, mode: 'login' | 'register' = 'login') => {
    const cleanIntent = intent?.trim();
    if (cleanIntent) {
      sessionStorage.setItem('civic_task_prefill', cleanIntent);
      sessionStorage.setItem('civic_location_prefill', JSON.stringify({
        city: city.trim(), state: state.trim(), serviceType: serviceType.trim(),
      }));
    }
    if (mode === 'register') onRegister?.();
    else onLogin();
  };

  const submitTask = (event: React.FormEvent) => {
    event.preventDefault();
    if (task.trim()) continueToAuth(task, 'login');
  };

  const submitHeroSearch = (event: React.FormEvent) => {
    event.preventDefault();
    if (!heroQuery.trim()) return;
    setTask(heroQuery.trim());
    composerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  const pickPopular = (popularTask: string) => {
    setTask(popularTask);
    composerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  return <div className="nf-shell">
    <TopNav active="home" onNavigate={onNavigate} userName="" isAdmin={false} unread={0} lang="en" onLang={() => {}} onLogin={onLogin} onRegister={() => onRegister?.()} onLogout={() => {}} />
    <main className="nf-main nf-main-wide" id="main-content">
      {/* Panel 1 — hero */}
      <section className="nf-hero" aria-label="Welcome to NagrikFlow">
        <HeroSkyline />
        <div className="nf-hero-inner">
          <h1>Your Guide to Government Services</h1>
          <p className="nf-hero-sub">From complex procedures to clear next steps.</p>
          <p className="nf-hero-desc">NagrikFlow helps you understand, complete and track government processes with a powerful platform, verified information and step-by-step guidance.</p>
          <form className="nf-hero-search" role="search" onSubmit={submitHeroSearch}>
            <input value={heroQuery} onChange={(e) => setHeroQuery(e.target.value)} placeholder="What civic task do you need help with? (e.g. Register a small business)" aria-label="Search civic tasks" />
            <button type="submit">Search</button>
          </form>
        </div>
      </section>

      {/* Panel 1 — features */}
      <section className="nf-section" aria-label="Why NagrikFlow">
        <div className="nf-feature-grid">
          {FEATURES.map((f) => <div className="nf-feature" key={f.title}>
            <span className="nf-feature-icon" style={{ background: f.color }} aria-hidden="true">{f.icon}</span>
            <h3>{f.title}</h3><p>{f.desc}</p>
          </div>)}
        </div>
      </section>

      {/* Panel 1 — popular services */}
      <section className="nf-section" aria-labelledby="popular-title">
        <div className="nf-section-head"><h2 id="popular-title">Popular Civic Services</h2><button className="nf-text-link" onClick={() => continueToAuth(undefined, 'login')}>View all services →</button></div>
        <div className="nf-service-grid">
          {POPULAR_SERVICES.map((s) => <div className="nf-service-card" key={s.title}>
            <span className="nf-svc-icon" style={{ background: s.color }} aria-hidden="true">{s.icon}</span>
            <h3>{s.title}</h3><p>{s.desc}</p>
            <button onClick={() => pickPopular(s.task)}>Start →</button>
          </div>)}
        </div>
      </section>

      {/* Panel 2 — task composer */}
      <section className="nf-section" aria-label="Task composer" ref={composerRef}>
        <div className="nf-card nf-task-card">
          <span className="nf-eyebrow">Public services for a brighter tomorrow</span>
          <h2>What do you need to get done?</h2>
          <p>Tell us what you need to do, and we&rsquo;ll find the right government process, forms, and steps for you.</p>
          <form onSubmit={submitTask}>
            <div className="nf-task-main">
              <span className="nf-q" aria-hidden="true">⌕</span>
              <input value={task} onChange={(e) => setTask(e.target.value)} placeholder="I want to register a small business" aria-label="Describe your civic task" />
            </div>
            <div className="nf-task-row nf-task-row-3">
              <div className="nf-field"><label htmlFor="nf-loc">Location</label><input id="nf-loc" value={city} onChange={(e) => setCity(e.target.value)} placeholder="📍 Mumbai" aria-label="City" /></div>
              <div className="nf-field"><label htmlFor="nf-state">State</label><input id="nf-state" value={state} onChange={(e) => setState(e.target.value)} placeholder="Maharashtra" aria-label="State" /></div>
              <div className="nf-field"><label htmlFor="nf-svc">Service Type</label><select id="nf-svc" value={serviceType} onChange={(e) => setServiceType(e.target.value)} aria-label="Type of service"><option value="">Small Business</option>{SERVICE_TYPES.map((k) => <option key={k} value={k}>{k}</option>)}</select></div>
            </div>
            <button className="nf-btn nf-btn-primary nf-find-btn cv-public-build" type="submit" disabled={!task.trim()}>Build my pathway →</button>
          </form>
          <div className="nf-examples"><span>Try these examples</span>{EXAMPLES.map((ex) => <button key={ex} type="button" onClick={() => setTask(ex)}>{ex}</button>)}</div>
          <p className="nf-auth-note">You&rsquo;ll sign in before a pathway is built or saved.</p>
          <Skyline />
        </div>
        <div className="nf-trust-strip">
          <p>Trusted by 1M+ citizens across India</p>
          <div className="nf-trust-logos"><span>🏛 Central Govt</span><span>🏫 State Govt</span><span>🏙 Municipalities</span><span>📁 Departments</span></div>
        </div>
      </section>

      {/* Example pathway + sources */}
      <section className="nf-section" aria-label="Example pathway and sources">
        <div className="nf-two-col">
          <div className="nf-card nf-example-card">
            <div className="nf-example-head">
              <div><h2>Example pathway</h2><p>Register a small business · Example roadmap · India</p></div>
              <span className="nf-badge is-info" style={{ marginLeft: 'auto' }}>Preview only</span>
            </div>
            <p className="nf-muted" style={{ fontSize: 13, margin: '0 0 8px' }}>This is an illustrative example, not a saved or reviewed pathway. Confirm current rules on the linked official websites.</p>
            <ol className="nf-step-rows">
              {EXAMPLE_STEPS.map((s, i) => <li key={s.title}><span className="nf-tl-marker">{i + 1}</span><div><strong style={{ fontSize: 14 }}>{s.title}</strong><br /><small className="nf-muted">{s.detail}</small></div></li>)}
            </ol>
            <div className="nf-example-foot"><span>4 example steps · 2 official links</span><button className="nf-btn nf-btn-outline nf-btn-sm" onClick={() => continueToAuth('Register a small business')}>Build my pathway</button></div>
          </div>
          <div className="nf-side-stack">
            <div className="nf-card nf-side-card">
              <h2>Official source links</h2><p className="nf-sub">Example sources for the pathway preview.</p>
              <div className="nf-source-row"><div><strong>Udyam Registration Portal</strong><small>Ministry of Micro, Small and Medium Enterprises</small></div><a href="https://udyamregistration.gov.in/" target="_blank" rel="noreferrer" aria-label="Open Udyam Registration Portal">↗</a></div>
              <div className="nf-source-row"><div><strong>Goods and Services Tax Portal</strong><small>Central Board of Indirect Taxes and Customs</small></div><a href="https://www.gst.gov.in/" target="_blank" rel="noreferrer" aria-label="Open Goods and Services Tax Portal">↗</a></div>
              <div className="nf-caution"><span aria-hidden="true">ⓘ</span><p><strong>Check the official source before applying.</strong> Rules, fees and procedures can change.</p></div>
            </div>
            <div className="nf-card nf-side-card nf-help-card">
              <h2>Need help?</h2><p className="nf-sub">Sign in to access saved pathways and step-by-step guidance.</p>
              <button className="nf-btn nf-btn-primary nf-btn-sm" onClick={onLogin}>Sign in for help ›</button>
            </div>
          </div>
        </div>
      </section>
    </main>
    <Footer onNavigate={onNavigate} />
  </div>;
}
