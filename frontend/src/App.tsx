import React, { useState } from 'react';
import Roadmap from './Roadmap';
import Dashboard from './Dashboard';
import Admin from './Admin';
import { api } from './api';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('civic_token') || '');
  const [tab, setTab] = useState<'map' | 'me' | 'admin'>('me');
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
        <h2>🗺️ Civic Path Navigator</h2>
        {['email', 'password', 'name', 'city', 'state'].map((k) => (
          <input key={k} type={k === 'password' ? 'password' : 'text'} placeholder={k}
            value={(form as any)[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
            style={{ display: 'block', width: '100%', margin: '6px 0', padding: 8 }} />
        ))}
        <button onClick={() => submit('register')}>Register</button>{' '}
        <button onClick={() => submit('login')}>Login</button>
        {err && <p style={{ color: 'red' }}>{err}</p>}
      </div>
    );
  }
  return (
    <div style={{ padding: 16, fontFamily: 'sans-serif' }}>
      <h2>🗺️ Civic Path Navigator</h2>
      <button onClick={() => setTab('me')}>My Dashboard</button>{' '}
      <button onClick={() => setTab('map')}>Udyam Roadmap</button>{' '}
      <button onClick={() => setTab('admin')}>Admin Desk</button>{' '}
      <button onClick={() => { localStorage.removeItem('civic_token'); setToken(''); }}>Logout</button>
      <hr />
      {tab === 'me' ? <Dashboard /> : tab === 'map' ? <Roadmap slug="udyam-register" /> : <Admin />}
    </div>
  );
}
