import React, { useEffect, useState } from 'react';
import { api } from './api';

export default function Dashboard() {
  const [d, setD] = useState<any>(null);
  const [brief, setBrief] = useState<any>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api.dashboard().then(setD).catch((e) => setErr(String(e.message || e)));
    api.brief().then(setBrief).catch(() => setBrief({ brief: 'Brief unavailable.', via: 'none' }));
  }, []);

  if (err) return <p style={{ color: 'red' }}>{err}</p>;
  if (!d) return <p>Loading your civic profile…</p>;
  return (
    <div style={{ display: 'grid', gap: 12, maxWidth: 720 }}>
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        <h3>📋 What you hold</h3>
        <p>{d.have.length ? d.have.join(' • ') : 'No verified documents yet — connect DigiLocker below.'}</p>
      </div>
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        <h3>💡 Your plain-words brief <small>({brief?.via})</small></h3>
        <p>{brief?.brief || '…'}</p>
      </div>
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        <h3>🚀 Easiest next wins</h3>
        {d.next_easiest.length === 0 && <p>Nothing pending — you're all set.</p>}
        {d.next_easiest.map((n: any) => (
          <p key={n.get}><b>{n.get}</b> — {n.effort}<br /><small>{n.why}</small></p>
        ))}
      </div>
      <ConnectDigiLocker />
      <ConnectTelegram />
    </div>
  );
}

function ConnectTelegram() {
  const [code, setCode] = useState('');
  return (
    <div style={{ border: '1px dashed #888', borderRadius: 8, padding: 12 }}>
      <h3>🔔 Telegram alerts</h3>
      <p><small>One bot for everyone; your chat links only to your account via a one-time code.</small></p>
      <button onClick={async () => {
        const r = await fetch('/api/me/telegram/link-code', {
          method: 'POST',
          headers: { Authorization: `Bearer ${localStorage.getItem('civic_token')}` },
        }).then((x) => x.json());
        setCode(r.code || '');
      }}>Get link code</button>
      {code && <p>Send <b>/start {code}</b> to our bot (expires in 15 min, single use).</p>}
    </div>
  );
}
function ConnectDigiLocker() {
  const [url, setUrl] = useState('');
  return (
    <div style={{ border: '1px dashed #888', borderRadius: 8, padding: 12 }}>
      <h3>🔐 Connect DigiLocker</h3>
      <p><small>Consent-based import of your verified documents. You approve on the official site.</small></p>
      <button onClick={async () => {
        const r = await api.dlConnect();
        sessionStorage.setItem('pkce', r.pkce_verifier);
        setUrl(r.authorize_url);
      }}>Get consent link</button>
      {url && <p><a href={url} target="_blank" rel="noreferrer">Open official consent page ↗</a></p>}
    </div>
  );
}
