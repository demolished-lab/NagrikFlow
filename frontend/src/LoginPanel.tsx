import React, { useState } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';

interface LoginPanelProps {
  onLogin: (email: string) => void;
  onBack: () => void;
  initialMode?: 'login' | 'register';
}

type FieldProps = {
  label: string;
  id: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  minLength?: number;
  placeholder?: string;
  autoComplete?: string;
};

export default function LoginPanel({ onLogin, onBack, initialMode = 'login' }: LoginPanelProps) {
  const t = STR[lang()];
  const [isLogin, setIsLogin] = useState(initialMode === 'login');
  const [form, setForm] = useState({ email: '', password: '', name: '', city: '', state: '' });
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setErr('');
    try {
      const result = isLogin
        ? await api.login({ email: form.email, password: form.password })
        : await api.register(form);
      localStorage.setItem('civic_token', result.token);
      onLogin(form.email);
    } catch (error: any) {
      setErr(error.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setIsLogin((current) => !current);
    setErr('');
  };

  return <div className="cv-public-shell cv-auth-shell cv-anim-up">
    <aside className="cv-public-sidebar">
      <button className="cv-public-brand" type="button" onClick={onBack} aria-label="Civic Path Navigator home">
        <span className="cv-public-brand-mark" aria-hidden="true"><svg viewBox="0 0 44 44"><path d="M7 26c9-1 18-8 23-20 2 12-4 24-17 28-4 1-7-2-6-8Z" fill="#df8e43"/><path d="M7 32c9-1 17-6 24-16 0 12-6 22-19 24-4 0-7-3-5-8Z" fill="#1b7a68"/></svg></span>
        <span className="cv-public-brand-copy"><strong>Civic Path<br/>Navigator</strong><small>Government services.<br/>Simpler together.</small></span>
      </button>

      <nav className="cv-public-nav" aria-label="Account navigation">
        <span className="cv-public-nav-caption">YOUR SPACE</span>
        <button type="button" onClick={onBack}><AuthIcon name="home"/><span>Home</span></button>
        <button className="is-active" type="button" aria-current="page"><AuthIcon name="account"/><span>{isLogin ? 'Sign in' : 'Create account'}</span></button>
        <button type="button" onClick={onBack}><AuthIcon name="help"/><span>Help</span></button>
      </nav>

      <div className="cv-public-sidebar-bottom">
        <div className="cv-public-sidebar-trust"><span aria-hidden="true">✓</span><p><strong>A guide, not a government office.</strong><br/>Applications are completed on official government websites.</p></div>
        <button className="cv-public-signin-link" type="button" onClick={onBack}>Back to the service guide <span aria-hidden="true">→</span></button>
      </div>
    </aside>

    <main className="cv-public-main">
      <header className="cv-public-header">
        <span className="cv-public-promise">Find. Understand. Complete.</span>
        <div className="cv-public-header-actions">
          <button className="cv-public-help-link" type="button" onClick={onBack}><AuthIcon name="help"/>Help</button>
          <button className="cv-public-login" type="button" onClick={onBack}>Back to services</button>
        </div>
      </header>

      <div className="cv-public-content cv-auth-content">
        <div className="cv-public-grid cv-auth-grid">
          <section className="cv-public-primary cv-auth-primary" aria-label={isLogin ? 'Sign in to your account' : 'Create your account'}>
            <div className="cv-public-intro cv-auth-intro">
              <span className="cv-public-eyebrow">YOUR CIVIC SERVICES ACCOUNT</span>
              <h1>{isLogin ? 'Welcome back.' : 'A clearer path starts here.'}</h1>
              <p>{isLogin ? 'Sign in to pick up where you left off and keep your saved pathways and progress together.' : 'Create an account to save your civic pathways and keep track of each step.'}</p>
            </div>

            <section className="cv-auth-card" aria-labelledby="auth-form-title">
              <div className="cv-auth-card-heading">
                <span className="cv-auth-mark" aria-hidden="true"><AuthIcon name="account"/></span>
                <div><h2 id="auth-form-title">{isLogin ? 'Sign in to Civic Path' : 'Create your account'}</h2><p>{isLogin ? 'Your saved pathways are waiting for you.' : 'It only takes a moment to get started.'}</p></div>
              </div>

              <form onSubmit={handleSubmit} aria-busy={loading}>
                {!isLogin && <FormField label="Name" id="name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required autoComplete="name" />}
                <FormField label="Email" id="email" type="email" value={form.email} onChange={(value) => setForm({ ...form, email: value })} required autoComplete="email" />
                {!isLogin && <div className="cv-auth-location-grid">
                  <FormField label="City" id="city" value={form.city} onChange={(value) => setForm({ ...form, city: value })} autoComplete="address-level2" placeholder="e.g. Hyderabad" />
                  <FormField label="State" id="state" value={form.state} onChange={(value) => setForm({ ...form, state: value })} autoComplete="address-level1" placeholder="e.g. Telangana" />
                </div>}
                <FormField label="Password" id="password" type="password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} required minLength={8} autoComplete={isLogin ? 'current-password' : 'new-password'} />

                {err && <div className="cv-auth-error" role="alert">{err}</div>}
                <button type="submit" className="cv-auth-submit" disabled={loading}>
                  {loading ? <><span className="cv-button-spinner" aria-hidden="true"/>Please wait…</> : <>{isLogin ? t.login : t.register}<span aria-hidden="true">›</span></>}
                </button>
              </form>

              <div className="cv-auth-switch">{isLogin ? "Don't have an account?" : 'Already have an account?'} <button type="button" onClick={switchMode}>{isLogin ? t.register : t.login}</button></div>
              <p className="cv-auth-disclaimer">Civic Path Navigator is a guide. You submit forms and applications through the linked official services.</p>
            </section>
          </section>

          <aside className="cv-public-aside cv-auth-aside" aria-label="Official services and support">
            <section className="cv-public-aside-card">
              <div className="cv-public-aside-heading"><div><h2>Official service links</h2><p>Continue on the government portal when you’re ready.</p></div><span aria-hidden="true">i</span></div>
              <a className="cv-public-source" href="https://udyamregistration.gov.in/" target="_blank" rel="noreferrer"><span className="cv-public-source-check" aria-hidden="true">↗</span><span><strong>Udyam Registration Portal</strong><small>Ministry of Micro, Small and Medium Enterprises</small></span><b aria-hidden="true">↗</b></a>
              <a className="cv-public-source" href="https://www.gst.gov.in/" target="_blank" rel="noreferrer"><span className="cv-public-source-check" aria-hidden="true">↗</span><span><strong>Goods and Services Tax Portal</strong><small>Government of India</small></span><b aria-hidden="true">↗</b></a>
              <div className="cv-public-source-caution"><span aria-hidden="true">i</span><p><strong>Check requirements before applying.</strong><br/>Rules, fees and procedures can change. Verify current guidance on the linked site.</p></div>
            </section>

            <section className="cv-public-aside-card cv-public-help-card">
              <h2>Need help?</h2><p>Return to the service guide for examples and answers about how Civic Path works.</p>
              <button type="button" onClick={onBack}><AuthIcon name="help"/>Visit the service guide <span aria-hidden="true">›</span></button>
            </section>

            <div className="cv-public-trust-card"><span aria-hidden="true">✦</span><p><strong>Your progress, in one place</strong><br/>Sign in to keep saved pathways connected to your account.</p></div>
          </aside>
        </div>
      </div>
    </main>
  </div>;
}

function FormField({ label, id, type = 'text', value, onChange, required, minLength, placeholder, autoComplete }: FieldProps) {
  return <label className="cv-auth-field" htmlFor={id}>
    <span>{label}{required && <b aria-hidden="true">*</b>}</span>
    <input id={id} name={id} type={type} value={value} onChange={(event) => onChange(event.target.value)} required={required} minLength={minLength} placeholder={placeholder} autoComplete={autoComplete} />
  </label>;
}

function AuthIcon({ name }: { name: 'home' | 'account' | 'help' }) {
  const common = { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const };
  if (name === 'home') return <svg {...common}><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-7h6v7"/></svg>;
  if (name === 'account') return <svg {...common}><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>;
  return <svg {...common}><circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 1 1 4.3 1.8c-1 .9-1.9 1.2-1.9 2.7M12 17.2h.01"/></svg>;
}
