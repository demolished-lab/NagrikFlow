import React, { useEffect, useState } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';
import type { PathwaySummary } from './types';

type MapSummary = { title?: string; graph?: { nodes?: { id: string }[] } };

export default function Dashboard() {
  const t = STR[lang()];
  const [d, setD] = useState<any>(null);
  const [brief, setBrief] = useState<any>(null);
  const [map, setMap] = useState<MapSummary | null>(null);
  const [completed, setCompleted] = useState<string[]>([]);
  const [milestones, setMilestones] = useState<any[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unread, setUnread] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [err, setErr] = useState('');
  const [pathways, setPathways] = useState<PathwaySummary[]>([]);
  const [slug, setSlug] = useState('');
  const [slugChosen, setSlugChosen] = useState(false);
  const [mapErr, setMapErr] = useState('');

  useEffect(() => {
    Promise.all([api.dashboard(), api.brief(), api.notifications()])
      .then(([data, briefData, notificationData]) => {
        setD(data);
        setBrief(briefData);
        setNotifications(notificationData.notifications || []);
        setUnread(notificationData.unread || 0);
      })
      .catch((error) => setErr(String(error.message || error)));
    // the tracked pathway comes from the citizen's own saved pathways —
    // never a hard-coded map slug
    api.myPathways()
      .then((pathwayData: PathwaySummary[]) => {
        const list = pathwayData || [];
        setPathways(list);
        const first = list.find((p) => p.slug && p.status !== 'failed');
        if (first) setSlug(first.slug);
        setSlugChosen(true);
      })
      .catch(() => {
        setPathways([]);
        setSlugChosen(true);
      });
  }, []);

  useEffect(() => {
    if (!slugChosen || !slug) return;
    setMapErr('');
    Promise.all([api.map(slug), api.progress(slug), api.milestones(slug)])
      .then(([mapData, progressData, milestoneData]) => {
        setMap(mapData);
        setCompleted(progressData.steps || []);
        setMilestones(milestoneData.milestones || []);
      })
      .catch((error) => {
        setMap(null);
        setCompleted([]);
        setMilestones([]);
        setMapErr(String(error.message || error));
      });
  }, [slug, slugChosen]);

  if (err) return <div className="cv-api-error" role="alert">{err}</div>;
  if (!d || !slugChosen) return <div className="cv-page-state" aria-live="polite">{t.loading}</div>;

  const totalSteps = map?.graph?.nodes?.length || 0;
  const progressPercent = totalSteps ? Math.round((completed.length / totalSteps) * 100) : 0;
  const inProgress = Object.entries(d.in_progress_maps || {}) as [string, number][];
  const documents = d.have || [];
  const nextActions = d.next_easiest || [];

  const downloadReport = async () => {
    setExporting(true);
    try {
      const response = await api.progressReport();
      if (!response.ok) throw new Error('Could not create the progress report');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'civic-progress-report.pdf';
      link.click();
      URL.revokeObjectURL(url);
    } catch (error: any) {
      setErr(String(error.message || error));
    }
    setExporting(false);
  };

  const markRead = async (id: number) => {
    await api.readNotification(id);
    setNotifications((items) => items.map((item) => item.id === id ? { ...item, read: true } : item));
    setUnread((count) => Math.max(0, count - 1));
  };

  return <div className="cv-dashboard-view cv-anim-up">
    <header className="cv-welcome-banner"><span className="cv-eyebrow">YOUR CIVIC ACCOUNT</span><h1>{d.user?.name ? `Welcome back, ${d.user.name}` : (t.welcomeBack || 'Welcome back')}</h1><p className="cv-welcome-sub">{brief?.brief || t.briefDesc || 'Here is your personalized plain-words brief.'}</p></header>

    {slugChosen && !slug ? (
      <section className="cv-progress-summary" aria-label="Personalized roadmap progress">
        <div className="cv-progress-summary-head"><div><span className="cv-eyebrow">YOUR PERSONAL PROGRESS</span><h2>No pathway yet</h2></div></div>
        <p className="cv-empty">Describe a civic task and we will build your pathway — its steps, sources and progress will appear here.</p>
        <button className="cv-btn cv-btn-indigo" type="button" onClick={() => { window.location.hash = ''; }}>Build your first pathway</button>
      </section>
    ) : (
      <section className="cv-progress-summary" aria-label="Personalized roadmap progress">
        <div className="cv-progress-summary-head"><div><span className="cv-eyebrow">YOUR PERSONAL PROGRESS</span>
          <h2>{map?.title || pathways.find((p) => p.slug === slug)?.title || 'Your pathway progress'}</h2>
          {pathways.filter((p) => p.slug).length > 1 && <select className="cv-pathway-select" value={slug} onChange={(event) => setSlug(event.target.value)} aria-label="Choose which pathway to track">{pathways.filter((p) => p.slug).map((p) => <option key={p.slug} value={p.slug}>{p.title || p.slug}</option>)}</select>}
        </div><strong>{progressPercent}%</strong></div>
        <div className="cv-progress-track"><span style={{ width: `${progressPercent}%` }}/></div>
        <div className="cv-progress-summary-foot"><span>{completed.length} of {totalSteps || '—'} steps completed</span><span>{inProgress.length ? `${inProgress.length} active path${inProgress.length === 1 ? '' : 's'}` : 'Start a verified path to track progress'}</span></div>
        {mapErr && <p className="cv-inline-error" role="alert">{mapErr}</p>}
        <button className="cv-report-button" type="button" onClick={() => void downloadReport()} disabled={exporting}>{exporting ? 'Preparing PDF…' : 'Download progress report'}</button>
      </section>
    )}

    {milestones.length > 0 && <section className="cv-milestone-section" aria-label="Active roadmap milestones"><div className="cv-section-heading"><div><span className="cv-eyebrow">ACTIVE MILESTONES</span><h2>Deadline tracker</h2></div><span className="cv-milestone-count">{milestones.filter((item) => item.status !== 'completed').length} open</span></div><div className="cv-milestone-grid">{milestones.map((item) => <article className={`cv-milestone-card ${item.status === 'completed' ? 'complete' : item.days_left < 0 ? 'overdue' : ''}`} key={item.step_id}><span className="cv-milestone-icon" aria-hidden="true">{item.status === 'completed' ? '✓' : item.days_left < 0 ? '!' : '◷'}</span><div><strong>{item.title}</strong><p>{item.status === 'completed' ? 'Completed and synced' : item.days_left < 0 ? `${Math.abs(item.days_left)} days overdue` : `Due in ${item.days_left} days`}</p></div><time>{item.due_at ? item.due_at.slice(0, 10) : '—'}</time></article>)}</div></section>}

    {notifications.length > 0 && <section className="cv-alert-section" aria-label="Notifications"><div className="cv-section-heading"><div><span className="cv-eyebrow">NOTIFICATIONS</span><h2>Deadline alerts {unread > 0 && <span className="cv-unread-count">{unread}</span>}</h2></div></div><div className="cv-alert-list">{notifications.slice(0, 4).map((item) => <button className={`cv-alert-item ${item.read ? 'read' : ''}`} key={item.id} type="button" onClick={() => !item.read && void markRead(item.id)}><span className="cv-alert-dot" aria-hidden="true">{item.read ? '✓' : '!'}</span><span><strong>{item.title}</strong><small>{item.body}</small></span><b aria-hidden="true">›</b></button>)}</div></section>}

    {inProgress.length > 0 && <section className="cv-active-paths" aria-label="Active paths"><div className="cv-section-heading"><div><span className="cv-eyebrow">SAVED WORK</span><h2>Active verified paths</h2></div></div><div className="cv-active-path-grid">{inProgress.map(([slug, count]) => <article className="cv-active-path" key={slug}><span className="cv-active-path-icon" aria-hidden="true">⌂</span><div><strong>{slug.replace(/-/g, ' ')}</strong><p>{count} completed step{count === 1 ? '' : 's'} synced to your account</p></div><span className="cv-active-path-arrow" aria-hidden="true">›</span></article>)}</div></section>}

    <div className="cv-dashboard-grid">
      <section className="cv-section-card"><h2>{t.have || 'What you have'}</h2><div className="cv-doc-grid">{documents.length === 0 && <p className="cv-empty">{t.noDocs || 'No verified documents yet.'}</p>}{documents.map((doc: string, index: number) => <div key={`${doc}-${index}`} className="cv-doc-card cv-doc-verified"><span className="cv-doc-status" aria-hidden="true">✓</span><span className="cv-doc-title">{doc}</span><span className="cv-badge cv-badge-success">Verified</span></div>)}</div></section>
      <section className="cv-section-card"><h2>{t.next || 'Easiest next steps'}</h2>{nextActions.length === 0 && <p className="cv-empty">{t.none || 'Nothing pending.'}</p>}<div className="cv-next-list">{nextActions.map((next: any, index: number) => <article key={`${next.get}-${index}`} className="cv-next-item"><div className="cv-next-header"><strong className="cv-next-title">{next.get}</strong>{next.effort && <span className="cv-next-effort">{next.effort}</span>}</div><p className="cv-next-why">{next.why || ''}</p></article>)}</div></section>
      <section className="cv-section-card"><h2>Quick actions</h2><div className="cv-action-buttons"><ConnectDigiLocker/><ConnectTelegram/></div></section>
    </div>

    {brief?.brief && <section className="cv-brief-card"><h2>{t.brief || 'Your plain-language brief'} <small>({brief?.via || ''})</small></h2><p>{brief.brief}</p></section>}
  </div>;
}

function ConnectTelegram() {
  const t = STR[lang()];
  const [code, setCode] = useState('');
  return <div className="cv-action-card"><h3>{t.tgTitle || 'Telegram alerts'}</h3><p>{t.tgBody || ''}</p><button type="button" onClick={async () => { try { const response = await api.telegramLinkCode(); setCode(response.code || ''); } catch (error: any) { setCode(String(error.message || error)); } }} className="cv-btn cv-btn-ghost">{t.tgBtn || 'Get code'}</button>{code && <p className="cv-code-display">Send <b>/start {code}</b> {t.tgSend || ''}</p>}</div>;
}

function ConnectDigiLocker() {
  const t = STR[lang()];
  const [url, setUrl] = useState('');
  return <div className="cv-action-card"><h3>{t.dlTitle || 'Connect DigiLocker'}</h3><p>{t.dlBody || ''}</p><button type="button" onClick={async () => { const response = await api.dlConnect(); sessionStorage.setItem('oauth_state', response.state); setUrl(response.authorize_url); }} className="cv-btn cv-btn-ghost">{t.dlBtn || 'Get consent link'}</button>{url && <a href={url} target="_blank" rel="noreferrer" className="cv-dl-link">{t.dlOpen || 'Open'} ↗</a>}</div>;
}
