import React, { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import type { PathwaySummary } from './types';

type Props = { onOpenPath: (slug: string) => void };

function locationOf(path: PathwaySummary) {
  return [path.city, path.state].filter(Boolean).join(', ') || 'Location not specified';
}

function statusLabel(path: PathwaySummary) {
  if (path.status === 'verified' || path.verified) return 'Reviewed and ready';
  if (path.status === 'review_required') return 'Awaiting source review';
  if (path.status === 'failed') return 'Build failed';
  if (path.status === 'queued' || path.status === 'running') return 'Building pathway';
  return 'In progress';
}

export default function PathwaysView({ onOpenPath }: Props) {
  const [pathways, setPathways] = useState<PathwaySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setPathways(await api.myPathways());
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const refresh = () => { void load(); };
    window.addEventListener('civic:pathways-updated', refresh);
    return () => window.removeEventListener('civic:pathways-updated', refresh);
  }, [load]);

  return <section className="cv-pathways-page cv-anim-up">
    <div className="cv-page-heading">
      <div><span className="cv-eyebrow">YOUR CIVIC TASKS</span><h1>My pathways</h1><p>Continue a saved procedure or check its review status.</p></div>
      <button className="cv-btn cv-btn-indigo" onClick={() => { window.location.hash = ''; }}>＋ Build a pathway</button>
    </div>
    {error && <div className="cv-api-error" role="alert">{error} <button onClick={() => void load()}>Try again</button></div>}
    {loading ? <p className="cv-muted" role="status">Loading your saved pathways…</p> : pathways.length === 0 ? <div className="cv-empty-card">
      <span className="cv-empty-icon" aria-hidden="true">⌁</span><h2>No pathways yet</h2><p>Describe a civic task and we’ll save its steps and source links here.</p><button className="cv-btn cv-btn-indigo" onClick={() => { window.location.hash = ''; }}>Describe your first task</button>
    </div> : <div className="cv-pathway-list">{pathways.map((path) => <article className="cv-pathway-record" key={`${path.job_id}-${path.slug}`}>
      <div className="cv-pathway-record-top"><span className="cv-path-icon" aria-hidden="true">⌂</span><div className="cv-pathway-record-title"><h2>{path.title}</h2><p>{locationOf(path)} <span aria-hidden="true">·</span> Started {path.created_at ? new Date(path.created_at).toLocaleDateString() : 'recently'}</p></div><span className={`cv-status-pill ${path.verified ? 'is-verified' : path.status === 'failed' ? 'is-failed' : 'is-pending'}`}>{path.verified ? '✓ ' : '• '}{statusLabel(path)}</span></div>
      {path.error && <p className="cv-inline-error">{path.error}</p>}
      <div className="cv-pathway-progress"><div className="cv-progress-copy"><span>{path.completed || 0} of {path.steps || 0} steps complete</span><span>{path.steps ? Math.round(((path.completed || 0) / path.steps) * 100) : 0}%</span></div><div className="cv-progress-track"><span style={{ width: `${path.steps ? Math.min(100, ((path.completed || 0) / path.steps) * 100) : 0}%` }} /></div></div>
      {!!path.steps_preview?.length && <ol className="cv-pathway-preview">{path.steps_preview.slice(0, 4).map((step, index) => <li key={step.id || index}><span className="cv-preview-index">{index + 1}</span><span><strong>{step.title}</strong>{step.detail && <small>{step.detail}</small>}</span>{step.url && <a href={step.url} target="_blank" rel="noreferrer" aria-label={`Open official source for ${step.title}`}>↗</a>}</li>)}</ol>}
      {!!path.sources?.length && <p className="cv-pathway-source-count">{path.sources.length} source{path.sources.length === 1 ? '' : 's'} attached</p>}
      <div className="cv-pathway-record-actions">{path.status !== 'failed' && <button className="cv-btn cv-btn-ghost" onClick={() => onOpenPath(path.slug)} disabled={!path.slug}>Open pathway</button>}{(path.status === 'queued' || path.status === 'running') && <span className="cv-muted">This pathway is still building. Refresh this page to update its status.</span>}</div>
    </article>)}</div>}
  </section>;
}
