import React, { useEffect, useState } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';
import type { PathwaySummary } from './types';

type MapSummary = { title?: string; graph?: { nodes?: { id: string; title?: string; detail?: string }[] }; city?: string; state?: string; verified?: boolean };

export default function Dashboard({ onNavigate }: { onNavigate?: (tab: 'home' | 'roadmap', slug?: string) => void } = {}) {
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
    api.myPathways()
      .then((pathwayData: PathwaySummary[]) => {
        const list = pathwayData || [];
        setPathways(list);
        const usable = list.filter((p) => p.slug && p.status !== 'failed');
        const first = usable.find((p) => p.verified) || usable[0];
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
    Promise.all([api.map(slug), api.progress(slug)])
      .then(async ([mapData, progressData]) => {
        const milestoneData = mapData.verified
          ? await api.milestones(slug)
          : { milestones: [] as any[] };
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

  if (err) return <div className="nf-error-box" role="alert">{err}</div>;
  if (!d || !slugChosen) return <div className="nf-card" style={{ padding: 24 }} aria-live="polite"><p className="nf-muted">{t.loading}</p></div>;

  const totalSteps = map?.graph?.nodes?.length || 0;
  const progressPercent = totalSteps ? Math.round((completed.length / totalSteps) * 100) : 0;
  const inProgress = Object.entries(d.in_progress_maps || {}) as [string, number][];
  const documents = d.have || [];
  const nextActions = d.next_easiest || [];
  const completedPaths = pathways.filter((p) => p.verified).length;
  const activePaths = pathways.filter((p) => !p.verified && p.status !== 'failed').length;
  const completedSet = new Set(completed);
  const nodeList = map?.graph?.nodes || [];
  const nextIndex = nodeList.findIndex((n) => !completedSet.has(n.id));
  const milestoneByStep = new Map((milestones || []).map((m: any) => [m.step_id, m]));

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

  const goRoadmap = () => { if (slug && onNavigate) onNavigate('roadmap', slug); else window.location.hash = `#/roadmap/${slug}`; };

  return <div>
    <div className="nf-dash-head">
      <span className="nf-eyebrow">Your civic account</span>
      <h1>{d.user?.name ? `Welcome back, ${d.user.name}!` : (t.welcomeBack || 'Welcome back')}</h1>
      <p>{brief?.brief || t.briefDesc || 'Here is your civic journey at a glance.'}</p>
    </div>

    <div className="nf-stat-grid">
      <div className="nf-card nf-stat"><span className="nf-stat-ic" style={{ background: 'var(--nf-green-soft)' }} aria-hidden="true">📄</span><div><b>{inProgress.length}</b><small>Active Applications</small></div></div>
      <div className="nf-card nf-stat"><span className="nf-stat-ic" style={{ background: 'var(--nf-blue-soft)' }} aria-hidden="true">✅</span><div><b>{completedPaths}</b><small>Completed</small></div></div>
      <div className="nf-card nf-stat"><span className="nf-stat-ic" style={{ background: 'var(--nf-amber-soft)' }} aria-hidden="true">⏳</span><div><b>{activePaths}</b><small>In Progress</small></div></div>
      <div className="nf-card nf-stat"><span className="nf-stat-ic" style={{ background: 'var(--nf-purple-soft)' }} aria-hidden="true">📊</span><div><b>{pathways.length}</b><small>Total Tasks</small></div></div>
    </div>

    <div className="nf-dash-grid">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        <section className="nf-card" style={{ padding: 20 }}>
          <div className="nf-section-head"><h2>Your Recent Paths</h2>{pathways.length > 3 && <button className="nf-text-link" onClick={() => { window.location.hash = '#/pathways'; }}>View All →</button>}</div>
          {pathways.length === 0 && <p className="nf-muted" style={{ fontSize: 13.5 }}>No pathways yet — describe a civic task on Home to create your first path.</p>}
          {pathways.slice(0, 3).map((p) => {
            const pct = p.steps ? Math.round(((p.completed || 0) / p.steps) * 100) : 0;
            return <div className="nf-path-row" key={`${p.job_id}-${p.slug}`}>
              <span className="nf-result-icon" style={{ background: 'var(--nf-primary-soft)', width: 40, height: 40, fontSize: 18 }} aria-hidden="true">🏛</span>
              <div style={{ flex: 1 }}><strong>{p.title}</strong><br /><small>{[p.city, p.state].filter(Boolean).join(', ') || 'Location not specified'} · {pct}% complete</small></div>
              <span className={`nf-badge ${p.verified ? 'is-done' : 'is-progress'}`}>{p.verified ? 'Completed' : 'In Progress'}</span>
            </div>;
          })}
        </section>

        {slugChosen && !slug ? (
          <section className="nf-card" style={{ padding: 20 }} aria-label="Personalized roadmap progress">
            <span className="nf-eyebrow">PERSONAL PROGRESS</span>
            <h2 style={{ fontSize: 17, margin: '4px 0 6px' }}>No pathway yet</h2>
            <p className="nf-muted" style={{ fontSize: 13.5 }}>Describe a civic task and we will build your pathway — its steps, sources and progress will appear here.</p>
            <button className="nf-btn nf-btn-primary nf-btn-sm" type="button" onClick={() => { window.location.hash = ''; }}>Build your first pathway</button>
          </section>
        ) : (
          <section className="nf-card nf-tracker" aria-label="Personalized roadmap progress">
            <span className="nf-eyebrow">PERSONAL PROGRESS</span>
            <div className="nf-tracker-head">
              <span className="nf-result-icon" style={{ background: 'var(--nf-blue-soft)' }} aria-hidden="true">🗺</span>
              <div style={{ flex: 1 }}><h2>{map?.title || pathways.find((p) => p.slug === slug)?.title || 'My Progress'}</h2><p>Track your completed tasks and see what&rsquo;s next. {[map?.city, map?.state].filter(Boolean).join(', ')}</p></div>
              {pathways.filter((p) => p.slug).length > 1 && <select value={slug} onChange={(e) => setSlug(e.target.value)} aria-label="Choose which pathway to track">{pathways.filter((p) => p.slug).map((p) => <option key={p.slug} value={p.slug}>{p.title || p.slug}</option>)}</select>}
            </div>
            <div className="nf-progress-copy"><span>Progress</span><span>{progressPercent}%</span></div>
            <div className="nf-progress-track"><span style={{ width: `${progressPercent}%` }} /></div>
            <p className="nf-muted" style={{ fontSize: 13, margin: '8px 0 0' }}>{completed.length} of {totalSteps || '—'} steps completed{inProgress.length ? ` · ${inProgress.length} active path${inProgress.length === 1 ? '' : 's'}` : ''}</p>
            {mapErr && <p className="nf-error-box" role="alert">{mapErr}</p>}
            {!!nodeList.length && <ol className="nf-track-steps">{nodeList.map((n, i) => {
              const done = completedSet.has(n.id);
              const isNext = i === nextIndex;
              const ms = milestoneByStep.get(n.id);
              return <li key={n.id}><span className="nf-tl-marker" style={done ? { background: 'var(--nf-green-soft)', color: 'var(--nf-green)' } : isNext ? { background: 'var(--nf-primary)', color: '#fff' } : undefined}>{done ? '✓' : i + 1}</span><div style={{ flex: 1 }}><strong>{n.title || n.id}</strong><br /><small>{n.detail || ''}</small></div><span className="nf-right"><span className={`nf-badge ${done ? 'is-done' : isNext ? 'is-progress' : 'is-pending'}`}>{done ? 'Completed' : isNext ? 'In Progress' : 'Pending'}</span><br /><small className="nf-muted">{done ? 'Done' : ms?.due_at ? `Due ${String(ms.due_at).slice(0, 10)}` : isNext ? 'You are here' : 'Locked'}</small></span></li>;
            })}</ol>}
            <button className="nf-btn nf-btn-ghost nf-btn-sm" type="button" onClick={() => void downloadReport()} disabled={exporting} style={{ marginTop: 12 }}>{exporting ? 'Preparing PDF…' : 'Download progress report'}</button>
          </section>
        )}

        <div className="nf-dash-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
          <section className="nf-card" style={{ padding: 20 }}><h2 style={{ fontSize: 16, margin: '0 0 10px' }}>{t.have || 'What you hold'}</h2><div className="nf-doc-grid">{documents.length === 0 && <p className="nf-muted" style={{ fontSize: 13 }}>{t.noDocs || 'No verified documents yet.'}</p>}{documents.map((doc: string, i: number) => <div key={`${doc}-${i}`} className="nf-doc-card"><span aria-hidden="true">✓</span>{doc}</div>)}</div></section>
          <section className="nf-card" style={{ padding: 20 }}><h2 style={{ fontSize: 16, margin: '0 0 10px' }}>{t.next || 'Easiest next steps'}</h2>{nextActions.length === 0 && <p className="nf-muted" style={{ fontSize: 13 }}>{t.none || 'Nothing pending.'}</p>}{nextActions.map((next: any, i: number) => <div className="nf-next-item" key={`${next.get}-${i}`}><strong>{next.get}</strong>{next.effort && <span className="nf-badge is-progress" style={{ marginLeft: 6 }}>{next.effort}</span>}<p>{next.why || ''}</p></div>)}</section>
        </div>

        {milestones.length > 0 && <section className="nf-card" style={{ padding: 20 }} aria-label="Active roadmap milestones"><div className="nf-section-head"><h2>Deadline tracker</h2><span className="nf-badge is-warn">{milestones.filter((m) => m.status !== 'completed').length} open</span></div>{milestones.map((m) => <div className="nf-act-row" key={m.step_id}><span aria-hidden="true">{m.status === 'completed' ? '✓' : '◷'}</span><div><strong>{m.title}</strong><small>{m.status === 'completed' ? 'Completed and synced' : m.days_left < 0 ? `${Math.abs(m.days_left)} days overdue` : `Due in ${m.days_left} days`}</small></div></div>)}</section>}

        {brief?.brief && <section className="nf-card" style={{ padding: 20 }}><h2 style={{ fontSize: 16, margin: '0 0 6px' }}>{t.brief || 'Your plain-language brief'} <small className="nf-muted">({brief?.via || ''})</small></h2><p style={{ fontSize: 13.5 }}>{brief.brief}</p></section>}
      </div>

      <div className="nf-side-stack">
        <section className="nf-card nf-quick-actions" aria-label="Quick actions">
          <h3>Quick Actions</h3>
          <button className="nf-qa-btn" onClick={goRoadmap} disabled={!slug}>🗺 View Roadmap</button>
          <button className="nf-qa-btn" onClick={() => void downloadReport()} disabled={exporting}>⬇ Download Checklist</button>
          <button className="nf-qa-btn" onClick={() => { window.location.hash = '#/help'; }}>💬 Contact Support</button>
          <div style={{ marginTop: 6 }}><ConnectDigiLocker /><ConnectTelegram /></div>
        </section>
        <section className="nf-card nf-activity-card" aria-label="Recent activity">
          <h3>Recent Activity</h3>
          {notifications.length === 0 && <p className="nf-muted" style={{ fontSize: 13 }}>No recent activity yet.</p>}
          {notifications.slice(0, 4).map((item) => <button key={item.id} className="nf-act-row" style={{ width: '100%', background: 'none', border: 0, borderBottom: '1px dashed var(--nf-line)', textAlign: 'left', cursor: 'pointer', padding: '8px 0' }} onClick={() => !item.read && void markRead(item.id)}><span aria-hidden="true">{item.read ? '✓' : '!'}</span><div><strong>{item.title}</strong><small>{item.body}</small></div></button>)}
        </section>
        <section className="nf-card nf-side-card nf-help-card">
          <h3>Need Help?</h3><p className="nf-sub">Our support team is here to assist you with any queries.</p>
          <button className="nf-btn nf-btn-primary nf-btn-sm nf-btn-block" onClick={() => { window.location.hash = '#/help'; }}>Contact Us</button>
        </section>
      </div>
    </div>
  </div>;
}

function ConnectTelegram() {
  const t = STR[lang()];
  const [code, setCode] = useState('');
  return <div className="nf-next-item"><strong style={{ fontSize: 13.5 }}>{t.tgTitle || 'Telegram alerts'}</strong><p>{t.tgBody || ''}</p><button type="button" onClick={async () => { try { const response = await api.telegramLinkCode(); setCode(response.code || ''); } catch (error: any) { setCode(String(error.message || error)); } }} className="nf-btn nf-btn-ghost nf-btn-sm">{t.tgBtn || 'Get code'}</button>{code && <p style={{ fontSize: 13 }}>Send <b>/start {code}</b> {t.tgSend || ''}</p>}</div>;
}

function ConnectDigiLocker() {
  const t = STR[lang()];
  const [url, setUrl] = useState('');
  return <div className="nf-next-item"><strong style={{ fontSize: 13.5 }}>{t.dlTitle || 'Connect DigiLocker'}</strong><p>{t.dlBody || ''}</p><button type="button" onClick={async () => { const response = await api.dlConnect(); sessionStorage.setItem('oauth_state', response.state); setUrl(response.authorize_url); }} className="nf-btn nf-btn-ghost nf-btn-sm">{t.dlBtn || 'Get consent link'}</button>{url && <div><a href={url} target="_blank" rel="noreferrer" className="nf-link-btn">{t.dlOpen || 'Open'} ↗</a></div>}</div>;
}
