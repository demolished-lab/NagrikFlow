import React, { useEffect, useState } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';

type MapSummary = { title?: string; graph?: { nodes?: { id: string }[] } };

export default function Dashboard() {
  const t = STR[lang()];
  const [d, setD] = useState<any>(null);
  const [brief, setBrief] = useState<any>(null);
  const [map, setMap] = useState<MapSummary | null>(null);
  const [completed, setCompleted] = useState<string[]>([]);
  const [err, setErr] = useState('');

  useEffect(() => {
    Promise.all([api.dashboard(), api.brief(), api.map('udyam-register'), api.progress('udyam-register')])
      .then(([data, briefData, mapData, progressData]) => {
        setD(data);
        setBrief(briefData);
        setMap(mapData);
        setCompleted(progressData.steps || []);
      })
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  if (err) return <p role="alert" className="cv-api-error">{err}</p>;
  if (!d) return <p aria-live="polite">{t.loading}</p>;

  const totalSteps = map?.graph?.nodes?.length || 0;
  const progressPercent = totalSteps ? Math.round((completed.length / totalSteps) * 100) : 0;
  const inProgress = Object.entries(d.in_progress_maps || {}) as [string, number][];

  return <div className="cv-dashboard-view cv-anim-up">
    <div className="cv-welcome-banner"><h1>{d.user?.name ? `Welcome back, ${d.user.name}` : (t.welcomeBack || 'Welcome Back!')}</h1><p className="cv-welcome-sub">{brief?.brief || t.briefDesc || 'Here is your personalized plain-words brief.'}</p></div>

    <section className="cv-progress-summary" aria-label="Personalized roadmap progress"><div className="cv-progress-summary-head"><div><span className="cv-eyebrow">YOUR PERSONAL PROGRESS</span><h2>{map?.title || 'Udyam registration roadmap'}</h2></div><strong>{progressPercent}%</strong></div><div className="cv-progress-track"><span style={{ width: `${progressPercent}%` }} /></div><div className="cv-progress-summary-foot"><span>{completed.length} of {totalSteps || '—'} steps completed</span><span>{inProgress.length ? `${inProgress.length} active path${inProgress.length === 1 ? '' : 's'}` : 'Start a verified path to track progress'}</span></div></section>

    {inProgress.length > 0 && <section className="cv-active-paths" aria-label="Active paths"><h2>Active verified paths</h2><div className="cv-active-path-grid">{inProgress.map(([slug, count]) => <div className="cv-active-path" key={slug}><span className="cv-active-path-icon">⌘</span><div><strong>{slug.replace(/-/g, ' ')}</strong><p>{count} completed step{count === 1 ? '' : 's'} synced to your account</p></div><span className="cv-active-path-arrow">›</span></div>)}</div></section>}

    <div className="cv-dashboard-grid"><div className="cv-section-card"><h2>📋 {t.have || 'What You Hold'}</h2><div className="cv-doc-grid">{d.have.length === 0 && <p className="cv-empty">{t.noDocs || 'No verified documents yet.'}</p>}{d.have.map((doc: string, i: number) => <div key={i} className="cv-doc-card cv-doc-verified"><span className="cv-doc-status">✅</span><span className="cv-doc-title">{doc}</span><span className="cv-badge cv-badge-success">Verified</span></div>)}</div></div><div className="cv-section-card"><h2>🚀 {t.next || 'Easiest Next Wins'}</h2>{d.next_easiest.length === 0 && <p className="cv-empty">{t.none || 'Nothing pending.'}</p>}<div className="cv-next-list">{d.next_easiest.map((n: any, i: number) => <div key={i} className="cv-next-item"><div className="cv-next-header"><strong className="cv-next-title">{n.get}</strong>{n.effort && <span className="cv-next-effort">{n.effort}</span>}</div><p className="cv-next-why">{n.why || ''}</p></div>)}</div></div><div className="cv-section-card"><h2>⚡ {t.quickActions || 'Quick Actions'}</h2><div className="cv-action-buttons"><ConnectDigiLocker /><ConnectTelegram /></div></div></div>
    {brief?.brief && <div className="cv-brief-card"><h2>💡 {t.brief || 'AI Brief'} <small>({brief?.via || ''})</small></h2><p>{brief.brief}</p></div>}
  </div>;
}

function ConnectTelegram() {
  const t = STR[lang()]; const [code, setCode] = useState('');
  return <div className="cv-action-card"><h3>🔔 {t.tgTitle || 'Telegram Alerts'}</h3><p>{t.tgBody || ''}</p><button onClick={async () => { try { const r = await api.telegramLinkCode(); setCode(r.code || ''); } catch (e: any) { setCode(String(e.message || e)); } }} className="cv-btn cv-btn-primary">{t.tgBtn || 'Get Code'}</button>{code && <p className="cv-code-display">Send <b>/start {code}</b> {t.tgSend || ''}</p>}</div>;
}

function ConnectDigiLocker() {
  const t = STR[lang()]; const [url, setUrl] = useState('');
  return <div className="cv-action-card"><h3>🔐 {t.dlTitle || 'Connect DigiLocker'}</h3><p>{t.dlBody || ''}</p><button onClick={async () => { const r = await api.dlConnect(); sessionStorage.setItem('oauth_state', r.state); setUrl(r.authorize_url); }} className="cv-btn cv-btn-indigo">{t.dlBtn || 'Get Consent Link'}</button>{url && <a href={url} target="_blank" rel="noreferrer" className="cv-dl-link">{t.dlOpen || 'Open'} ↗</a>}</div>;
}
