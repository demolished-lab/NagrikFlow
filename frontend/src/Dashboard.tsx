import React, { useEffect, useState } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';

export default function Dashboard() {
  const t = STR[lang()];
  const [d, setD] = useState<any>(null);
  const [brief, setBrief] = useState<any>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    Promise.all([api.dashboard(), api.brief()])
      .then(([data, briefData]) => { setD(data); setBrief(briefData); })
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  if (err) return <p role="alert" style={{ color: 'red' }}>{err}</p>;
  if (!d) return <p aria-live="polite">{t.loading}</p>;

  return (
    <div className="cv-dashboard-view">
      {/* Welcome Banner */}
      <div className="cv-welcome-banner">
        <h1>{t.welcomeBack || 'Welcome Back!'}</h1>
        <p className="cv-welcome-sub">{brief?.brief || t.briefDesc || 'Here is your personalized plain-words brief.'}</p>
      </div>

      <div className="cv-dashboard-grid">
        {/* Documents You Hold */}
        <div className="cv-section-card">
          <h2>📋 {t.have || 'What You Hold'}</h2>
          <div className="cv-doc-grid">
            {d.have.length === 0 && <p className="cv-empty">{t.noDocs || 'No verified documents yet.'}</p>}
            {d.have.map((doc: string, i: number) => (
              <div key={i} className="cv-doc-card cv-doc-verified">
                <span className="cv-doc-status">✅</span>
                <span className="cv-doc-title">{doc}</span>
                <span className="cv-badge cv-badge-success">Verified</span>
              </div>
            ))}
          </div>
        </div>

        {/* Next Easiest Wins */}
        <div className="cv-section-card">
          <h2>🚀 {t.next || 'Easiest Next Wins'}</h2>
          {d.next_easiest.length === 0 && <p className="cv-empty">{t.none || 'Nothing pending.'}</p>}
          <div className="cv-next-list">
            {d.next_easiest.map((n: any, i: number) => (
              <div key={i} className="cv-next-item">
                <div className="cv-next-header">
                  <strong className="cv-next-title">{n.get}</strong>
                  {n.effort && <span className="cv-next-effort">{n.effort}</span>}
                </div>
                <p className="cv-next-why">{n.why || ''}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="cv-section-card">
          <h2>⚡ {t.quickActions || 'Quick Actions'}</h2>
          <div className="cv-action-buttons">
            <ConnectDigiLocker />
            <ConnectTelegram />
          </div>
        </div>
      </div>

      {/* AI Brief */}
      {brief?.brief && (
        <div className="cv-brief-card">
          <h2>💡 {t.brief || 'AI Brief'} <small>({brief?.via || ''})</small></h2>
          <p>{brief.brief}</p>
        </div>
      )}
    </div>
  );
}

function ConnectTelegram() {
  const t = STR[lang()];
  const [code, setCode] = useState('');

  return (
    <div className="cv-action-card">
      <h3>🔔 {t.tgTitle || 'Telegram Alerts'}</h3>
      <p>{t.tgBody || ''}</p>
      <button
        onClick={async () => {
          try {
            const r = await api.telegramLinkCode();
            setCode(r.code || '');
          } catch (e: any) {
            setCode(String(e.message || e));
          }
        }}
        className="cv-btn cv-btn-primary"
      >
        {t.tgBtn || 'Get Code'}
      </button>
      {code && <p className="cv-code-display">Send <b>/start {code}</b> {t.tgSend || ''}</p>}
    </div>
  );
}

function ConnectDigiLocker() {
  const t = STR[lang()];
  const [url, setUrl] = useState('');

  return (
    <div className="cv-action-card">
      <h3>🔐 {t.dlTitle || 'Connect DigiLocker'}</h3>
      <p>{t.dlBody || ''}</p>
      <button
        onClick={async () => {
          const r = await api.dlConnect();
          sessionStorage.setItem('oauth_state', r.state);
          setUrl(r.authorize_url);
        }}
        className="cv-btn cv-btn-indigo"
      >
        {t.dlBtn || 'Get Consent Link'}
      </button>
      {url && <a href={url} target="_blank" rel="noreferrer" className="cv-dl-link">{t.dlOpen || 'Open'} ↗</a>}
    </div>
  );
}
