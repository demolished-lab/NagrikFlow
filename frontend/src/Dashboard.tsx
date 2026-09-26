import React, { useEffect, useState } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';

export default function Dashboard() {
  const t = STR[lang()];
  const [d, setD] = useState<any>(null);
  const [brief, setBrief] = useState<any>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api.dashboard().then(setD).catch((e) => setErr(String(e.message || e)));
    api.brief().then(setBrief).catch(() => setBrief({ brief: 'Brief unavailable.', via: 'none' }));
  }, []);

  if (err) return <p role="alert" style={{ color: 'red' }}>{err}</p>;
  if (!d) return <p aria-live="polite">{t.loading}</p>;
  return (
    <div aria-live="polite" style={{ display: 'grid', gap: 12, maxWidth: 720 }}>
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        <h3>📋 {t.have}</h3>
        <p>{d.have.length ? d.have.join(' • ') : t.noDocs}</p>
      </div>
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        <h3>💡 {t.brief} <small>({brief?.via})</small></h3>
        <p>{brief?.brief || '…'}</p>
      </div>
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        <h3>🚀 {t.next}</h3>
        {d.next_easiest.length === 0 && <p>{t.none}</p>}
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
  const t = STR[lang()];
  const [code, setCode] = useState('');
  return (
    <div style={{ border: '1px dashed #888', borderRadius: 8, padding: 12 }}>
      <h3>🔔 {t.tgTitle}</h3>
      <p><small>{t.tgBody}</small></p>
      <button onClick={async () => {
        const r = await fetch('/api/me/telegram/link-code', {
          method: 'POST',
          headers: { Authorization: `Bearer ${localStorage.getItem('civic_token')}` },
        }).then((x) => x.json());
        setCode(r.code || '');
      }}>{t.tgBtn}</button>
      {code && <p>Send <b>/start {code}</b> {t.tgSend}</p>}
    </div>
  );
}
function ConnectDigiLocker() {
  const t = STR[lang()];
  const [url, setUrl] = useState('');
  return (
    <div style={{ border: '1px dashed #888', borderRadius: 8, padding: 12 }}>
      <h3>🔐 {t.dlTitle}</h3>
      <p><small>{t.dlBody}</small></p>
      <button onClick={async () => {
        const r = await api.dlConnect();
        sessionStorage.setItem('oauth_state', r.state);
        setUrl(r.authorize_url);
      }}>{t.dlBtn}</button>
      {url && <p><a href={url} target="_blank" rel="noreferrer">{t.dlOpen} ↗</a></p>}
    </div>
  );
}
