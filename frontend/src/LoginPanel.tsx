import React, { useState } from 'react';
import { api } from './api';

interface LoginPanelProps {
  onLogin: (email: string) => void;
  onBack: () => void;
  initialMode?: 'login' | 'register';
}

export default function LoginPanel({ onLogin, onBack, initialMode = 'login' }: LoginPanelProps) {
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

  return <div className="cv-auth-shell">
    <div className="nf-card nf-auth-card">
      <button className="nf-text-link" type="button" onClick={onBack} style={{ marginBottom: 12 }}>← Back to services</button>
      <span className="nf-eyebrow">Your civic services account</span>
      <h1>{isLogin ? 'Welcome back.' : 'A clearer path starts here.'}</h1>
      <p>{isLogin ? 'Sign in to pick up where you left off and keep your saved pathways and progress together.' : 'Create an account to save your civic pathways and keep track of each step.'}</p>
      <form onSubmit={handleSubmit} aria-busy={loading}>
        {!isLogin && <div className="nf-field"><span>Name</span><input id="name" name="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoComplete="name" aria-label="Name" /></div>}
        <div className="nf-field"><span>Email</span><input id="email" name="email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required autoComplete="email" aria-label="Email" /></div>
        {!isLogin && <div className="nf-auth-grid2">
          <div className="nf-field"><span>City</span><input id="city" name="city" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} autoComplete="address-level2" placeholder="e.g. Hyderabad" aria-label="City" /></div>
          <div className="nf-field"><span>State</span><input id="state" name="state" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} autoComplete="address-level1" placeholder="e.g. Telangana" aria-label="State" /></div>
        </div>}
        <div className="nf-field"><span>Password</span><input id="password" name="password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={8} autoComplete={isLogin ? 'current-password' : 'new-password'} aria-label="Password" /></div>
        {err && <div className="nf-auth-error" role="alert">{err}</div>}
        <button type="submit" className="nf-btn nf-btn-primary nf-btn-block" disabled={loading}>{loading ? 'Please wait…' : isLogin ? 'Login ›' : 'Register ›'}</button>
      </form>
      <div className="nf-auth-switch">{isLogin ? "Don't have an account?" : 'Already have an account?'} <button type="button" className="nf-link-btn" onClick={() => { setIsLogin((v) => !v); setErr(''); }}>{isLogin ? 'Register' : 'Login'}</button></div>
      <div className="nf-auth-links">
        <h2 style={{ fontSize: 14, margin: '14px 0 6px' }}>Official service links</h2>
        <a href="https://udyamregistration.gov.in/" target="_blank" rel="noreferrer">Udyam Registration Portal ↗</a>
        {' · '}<a href="https://www.gst.gov.in/" target="_blank" rel="noreferrer">GST Portal ↗</a>
        <p style={{ margin: '10px 0 0' }}>NagrikFlow is a guide. You submit forms through the linked official services.</p>
      </div>
    </div>
  </div>;
}
