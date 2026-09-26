import React, { useState } from 'react';
import Roadmap from './Roadmap';
import Dashboard from './Dashboard';
import Admin from './Admin';
import { api } from './api';
import { STR, lang, setLang, Lang } from './i18n';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('civic_token') || '');
  const [tab, setTab] = useState<'map' | 'me' | 'admin'>('me');
  const [lg, setLg] = useState<Lang>(lang());
  const t = STR[lg];
  const [form, setForm] = useState({ email: '', password: '', name: '', city: '', state: '' });
  const [err, setErr] = useState('');

  const submit = async (mode: 'login' | 'register') => {
    try {
      const r = mode === 'login'
        ? await api.login({ email: form.email, password: form.password })
        : await api.register(form);
      localStorage.setItem('civic_token', r.token);
      setToken(r.token);
      setErr('');
    } catch (e: any) { setErr(String(e.message || e)); }
  };

  if (!token) {
    return (
      <div style={{ maxWidth: 420, margin: '40px auto', fontFamily: 'sans-serif' }}>
        <h2>🗺️ {t.appTitle}</h2>
        <label>{t.login === 'Login' ? 'Language' : 'भाषा'}:{' '}
          <select aria-label="language" value={lg} onChange={(e) => { setLang(e.target.value as Lang); setLg(e.target.value as Lang); }}>
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
          </select>
        </label>
        {['email', 'password', 'name', 'city', 'state'].map((k) => (
          <label key={k} style={{ display: 'block', margin: '6px 0' }}>
            <span className="sr-only">{k}</span>
            <input type={k === 'password' ? 'password' : 'text'} placeholder={k} aria-label={k}
              value={(form as any)[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              style={{ display: 'block', width: '100%', padding: 8 }} />
          </label>
        ))}
        <button onClick={() => submit('register')}>{t.register}</button>{' '}
        <button onClick={() => submit('login')}>{t.login}</button>
        {err && <p role="alert" style={{ color: 'red' }}>{err}</p>}
      </div>
    );
  }
  return (
    <div style={{ padding: 16, fontFamily: 'sans-serif' }}>
      <h2>🗺️ {t.appTitle}</h2>
      <button onClick={() => setTab('me')}>{t.myDashboard}</button>{' '}
      <button onClick={() => setTab('map')}>{t.roadmap}</button>{' '}
      <button onClick={() => setTab('admin')}>{t.admin}</button>{' '}
      <button onClick={() => { localStorage.removeItem('civic_token'); setToken(''); }}>{t.logout}</button>{' '}
      <select aria-label="language" value={lg} onChange={(e) => { setLang(e.target.value as Lang); setLg(e.target.value as Lang); }}>
        <option value="en">English</option>
        <option value="hi">हिन्दी</option>
      </select>
      <hr />
      {tab === 'me' ? <Dashboard /> : tab === 'map' ? <Roadmap slug="udyam-register" /> : <Admin />}
    </div>
  );
}
