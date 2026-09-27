import React, { useState } from 'react';
import { SERVICE_TYPES } from './types';

interface LandingProps {
  onLogin: () => void;
  onRegister?: () => void;
}

const EXAMPLES = ['Apply for a birth certificate', 'Renew a driving licence', 'Register a small business'];
const EXAMPLE_STEPS = [
  { title: 'Prepare PAN and Aadhaar', detail: 'Keep identity details ready for the applicant and business.' },
  { title: 'Complete Udyam registration', detail: 'Use the official portal to register an eligible MSME.' },
  { title: 'Check GST requirements', detail: 'Register if the business meets the current eligibility criteria.' },
  { title: 'Review state business rules', detail: 'Check the relevant Shops & Establishments requirements.' },
];

export default function LandingPage({ onLogin, onRegister }: LandingProps) {
  const [task, setTask] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [serviceType, setServiceType] = useState('');
  const [search, setSearch] = useState('');

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

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    if (!search.trim()) return;
    continueToAuth(search, 'login');
  };

  const openHelp = () => document.getElementById('public-help')?.scrollIntoView({ behavior: 'smooth', block: 'center' });

  return <div className="cv-public-shell">
    <aside className="cv-public-sidebar">
      <button className="cv-public-brand" type="button" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label="Civic Path Navigator home">
        <span className="cv-public-brand-mark" aria-hidden="true"><svg viewBox="0 0 44 44"><path d="M7 26c9-1 18-8 23-20 2 12-4 24-17 28-4 1-7-2-6-8Z" fill="#df8e43"/><path d="M7 32c9-1 17-6 24-16 0 12-6 22-19 24-4 0-7-3-5-8Z" fill="#1b7a68"/></svg></span>
        <span className="cv-public-brand-copy"><strong>Civic Path<br/>Navigator</strong><small>Government services.<br/>Simpler together.</small></span>
      </button>

      <nav className="cv-public-nav" aria-label="Main navigation">
        <span className="cv-public-nav-caption">YOUR SPACE</span>
        <button className="is-active" type="button" aria-current="page"><PublicIcon name="home"/><span>Home</span></button>
        <button type="button" onClick={onLogin}><PublicIcon name="path"/><span>My pathways</span></button>
        <button type="button" onClick={onLogin}><PublicIcon name="document"/><span>Documents</span></button>
        <button type="button" onClick={openHelp}><PublicIcon name="help"/><span>Help</span></button>
      </nav>

      <div className="cv-public-sidebar-bottom">
        <div className="cv-public-sidebar-trust"><span aria-hidden="true">✓</span><p><strong>Clear steps, trusted sources.</strong><br/>Always check the latest requirements on the official site.</p></div>
        <button className="cv-public-signin-link" type="button" onClick={onLogin}>Sign in to save your progress <span aria-hidden="true">→</span></button>
      </div>
    </aside>

    <main className="cv-public-main">
      <header className="cv-public-header">
        <span className="cv-public-promise">Find. Understand. Complete.</span>
        <form className="cv-public-search" role="search" onSubmit={submitSearch}>
          <span aria-hidden="true">⌕</span>
          <input aria-label="Search services" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search services..." />
          <button type="submit" aria-label="Search services">↵</button>
        </form>
        <div className="cv-public-header-actions">
          <button className="cv-public-help-link" type="button" onClick={openHelp}><PublicIcon name="help"/>Help</button>
          <button className="cv-public-login" type="button" onClick={onLogin}>Login</button>
          <button className="cv-public-register" type="button" onClick={() => continueToAuth(undefined, 'register')}>Register</button>
        </div>
      </header>

      <div className="cv-public-content">
        <div className="cv-public-grid">
          <section className="cv-public-primary" aria-label="Civic task navigator">
            <div className="cv-public-intro">
              <span className="cv-public-eyebrow">PUBLIC SERVICES FOR A BRIGHTER TOMORROW</span>
              <h1>What do you need to get done?</h1>
              <p>Tell us what you want to do and we’ll create a personalised pathway with the right steps, documents and official sources.</p>
            </div>

            <form className="cv-public-composer" onSubmit={submitTask}>
              <div className="cv-public-fields">
                <label className="cv-public-task-field"><span>I want to</span><input aria-label="Describe your civic task" value={task} onChange={(event) => setTask(event.target.value)} placeholder="e.g. Register a small business" /></label>
                <label><span>City</span><input aria-label="City" value={city} onChange={(event) => setCity(event.target.value)} placeholder="Hyderabad" /></label>
                <label><span>State</span><input aria-label="State" value={state} onChange={(event) => setState(event.target.value)} placeholder="Telangana" /></label>
                <label><span>Type of service</span><select aria-label="Type of service" value={serviceType} onChange={(event) => setServiceType(event.target.value)}><option value="">Select a service type</option>{SERVICE_TYPES.map((kind) => <option key={kind} value={kind}>{kind}</option>)}</select></label>
                <button className="cv-public-build" type="submit" disabled={!task.trim()}>Build my pathway <span aria-hidden="true">›</span></button>
              </div>
              <div className="cv-public-examples"><span>Examples:</span>{EXAMPLES.map((example, index) => <React.Fragment key={example}><button type="button" onClick={() => setTask(example)}>{example}</button>{index < EXAMPLES.length - 1 && <span className="cv-public-example-divider">|</span>}</React.Fragment>)}</div>
              <p className="cv-public-auth-note">You’ll sign in before a pathway is built or saved.</p>
            </form>

            <section className="cv-public-example-section" aria-labelledby="public-example-title">
              <div className="cv-public-section-heading"><h2 id="public-example-title">Example pathway</h2><button type="button" onClick={() => continueToAuth('Register a small business')}>Create your own <span aria-hidden="true">→</span></button></div>
              <article className="cv-public-path-card">
                <div className="cv-public-path-head">
                  <span className="cv-public-path-icon" aria-hidden="true">⌂</span>
                  <div><h3>Register a small business</h3><p>Example roadmap <span aria-hidden="true">·</span> India</p><small>A sample of how civic steps can be organised.</small></div>
                  <span className="cv-public-preview-pill">Preview only</span>
                </div>
                <div className="cv-public-preview-note"><span aria-hidden="true">i</span><p>This is an illustrative example, not a saved or reviewed pathway. Confirm current rules on the linked official websites.</p></div>
                <ol className="cv-public-step-list">{EXAMPLE_STEPS.map((step, index) => <li key={step.title}><span className="cv-public-step-number">{index + 1}</span><div><strong>{step.title}</strong><small>{step.detail}</small></div><span className="cv-public-step-label">Step {index + 1}</span></li>)}</ol>
                <div className="cv-public-path-footer"><span>4 example steps <span aria-hidden="true">·</span> 2 official links</span><button type="button" onClick={() => continueToAuth('Register a small business')}>Build my pathway</button></div>
              </article>
            </section>
          </section>

          <aside className="cv-public-aside" aria-label="Official sources and support">
            <section className="cv-public-aside-card">
              <div className="cv-public-aside-heading"><div><h2>Official source links</h2><p>Example sources for the pathway preview.</p></div><span aria-hidden="true">i</span></div>
              <a className="cv-public-source" href="https://udyamregistration.gov.in/" target="_blank" rel="noreferrer"><span className="cv-public-source-check" aria-hidden="true">↗</span><span><strong>Udyam Registration Portal</strong><small>Ministry of Micro, Small and Medium Enterprises</small></span><b aria-hidden="true">↗</b></a>
              <a className="cv-public-source" href="https://www.gst.gov.in/" target="_blank" rel="noreferrer"><span className="cv-public-source-check" aria-hidden="true">↗</span><span><strong>Goods and Services Tax Portal</strong><small>Central Board of Indirect Taxes and Customs</small></span><b aria-hidden="true">↗</b></a>
              <div className="cv-public-source-caution"><span aria-hidden="true">i</span><p><strong>Check the official source before applying.</strong><br/>Rules, fees and procedures can change. Verify the latest guidance on the linked site.</p></div>
            </section>

            <section className="cv-public-aside-card cv-public-help-card" id="public-help">
              <h2>Need help?</h2><p>Sign in to access your saved pathways and step-by-step guidance.</p>
              <button type="button" onClick={onLogin}><PublicIcon name="help"/>Sign in for help <span aria-hidden="true">›</span></button>
            </section>

            <div className="cv-public-trust-card"><span aria-hidden="true">✦</span><p><strong>Civic services, made simpler</strong><br/>Clear steps. Official links. Real progress.</p></div>
          </aside>
        </div>
      </div>
    </main>
  </div>;
}

function PublicIcon({ name }: { name: 'home' | 'path' | 'document' | 'help' }) {
  const common = { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const };
  if (name === 'home') return <svg {...common}><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-7h6v7"/></svg>;
  if (name === 'path') return <svg {...common}><circle cx="6" cy="6" r="2.3"/><circle cx="18" cy="18" r="2.3"/><circle cx="18" cy="6" r="2.3"/><path d="M8.3 6H13a5 5 0 0 1 5 5v4.7"/></svg>;
  if (name === 'document') return <svg {...common}><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6M9 16h6"/></svg>;
  return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 1 1 4.3 1.8c-1 .9-1.9 1.2-1.9 2.7M12 17.2h.01"/></svg>;
}
