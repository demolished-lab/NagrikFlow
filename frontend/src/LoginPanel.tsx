import React, { useEffect, useState } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';

interface LoginPanelProps {
  onLogin: (email: string) => void;
  initialMode?: 'login' | 'register';
}

export default function LoginPanel({ onLogin, initialMode = 'login' }: LoginPanelProps) {
  const t = STR[lang()];
  const [isLogin, setIsLogin] = useState(initialMode === 'login');
  const [form, setForm] = useState({ email: '', password: '', name: '', city: '', state: '' });
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr('');
    
    try {
      let result;
      if (isLogin) {
        result = await api.login({ email: form.email, password: form.password });
      } else {
        result = await api.register(form);
      }
      
      localStorage.setItem('civic_token', result.token);
      onLogin(form.email);
    } catch (error: any) {
      setErr(error.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="cv-anim-up" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-6)' }}>
      {/* Decorative tricolor bar at top */}
      <div className="tricolor-bar" style={{ position: 'fixed', top: 0, left: 0, right: 0 }} />
      
      <div className="cv-card" style={{ 
        width: '100%', 
        maxWidth: 420,
        padding: 'var(--space-8)',
        marginTop: 'var(--space-8)',
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-6)' }}>
          <div className="tricolor-bar-thin" style={{ width: 60, margin: '0 auto var(--space-3)' }} />
          <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--color-indigo)' }}>
            {t.appTitle}
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 14, marginTop: 'var(--space-2)' }}>
            {isLogin ? t.login : t.register}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <FormField label="Name" id="name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required={!isLogin} />
          )}
          <FormField 
            label="Email" 
            id="email" 
            type="email" 
            value={form.email} 
            onChange={(v) => setForm({ ...form, email: v })} 
            required 
          />
          {!isLogin && (
            <>
              <FormField label="City" id="city" value={form.city} onChange={(v) => setForm({ ...form, city: v })} />
              <FormField label="State" id="state" value={form.state} onChange={(v) => setForm({ ...form, state: v })} placeholder="TS" />
            </>
          )}
          <FormField 
            label="Password" 
            id="password" 
            type="password" 
            value={form.password} 
            onChange={(v) => setForm({ ...form, password: v })} 
            required
            minLength={8}
          />

          {err && (
            <div role="alert" style={{ 
              background: 'var(--danger-soft)', 
              color: 'var(--danger)', 
              padding: 'var(--space-3)', 
              borderRadius: 'var(--radius-md)',
              marginBottom: 'var(--space-4)',
              fontSize: 14,
            }}>
              {err}
            </div>
          )}

          <button 
            type="submit" 
            className="btn btn-primary" 
            style={{ width: '100%', marginBottom: 'var(--space-4)' }}
            disabled={loading}
          >
            {loading ? 'Please wait...' : (isLogin ? t.login : t.register)}
          </button>
        </form>

        {/* Toggle */}
        <div style={{ textAlign: 'center', fontSize: 14, color: 'var(--color-text-secondary)' }}>
          {isLogin ? "Don't have an account?" : 'Already have an account?'}{' '}
          <button 
            className="btn btn-ghost" 
            style={{ padding: 'var(--space-1) var(--space-2)', fontSize: 13 }}
            onClick={() => { setIsLogin(!isLogin); setErr(''); }}
          >
            {isLogin ? t.register : t.login}
          </button>
        </div>

        {/* Footer info */}
        <div style={{ marginTop: 'var(--space-6)', textAlign: 'center', fontSize: 12, color: 'var(--color-text-muted)' }}>
          <div className="tricolor-bar-thin" style={{ width: 40, margin: '0 auto var(--space-2)' }} />
          <p>By continuing, you agree to our Terms of Service</p>
          <p>and Privacy Policy</p>
        </div>
      </div>
    </div>
  );
}

function FormField({ 
  label, 
  id, 
  type = 'text', 
  value, 
  onChange, 
  required, 
  minLength,
  placeholder,
}: { 
  label: string; 
  id: string; 
  type?: string; 
  value: string; 
  onChange: (v: string) => void; 
  required?: boolean;
  minLength?: number;
  placeholder?: string;
}) {
  return (
    <div style={{ marginBottom: 'var(--space-4)' }}>
      <label htmlFor={id} className="label">{label}</label>
      <input
        id={id}
        type={type}
        className="cv-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        minLength={minLength}
        placeholder={placeholder}
      />
    </div>
  );
}
