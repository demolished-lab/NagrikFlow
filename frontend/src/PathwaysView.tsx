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

  return <div>
    <div className="nf-crumb"><button onClick={() => { window.location.hash = ''; }}>Home</button> · <b>My pathways</b></div>
    <div className="nf-page-head">
      <span className="nf-eyebrow">Your civic tasks</span>
      <h1>My pathways</h1>
      <p>Continue a saved procedure or check its review status.</p>
    </div>
    {error && <div className="nf-error-box" role="alert">{error} <button className="nf-link-btn" onClick={() => void load()}>Try again</button></div>}
    {loading ? <div className="nf-card" style={{ padding: 20 }} role="status"><p className="nf-muted">Loading your saved pathways…</p></div>
      : pathways.length === 0 ? <div className="nf-card" style={{ padding: 28, textAlign: 'center' }}>
        <h2>No pathways yet</h2><p className="nf-muted">Describe a civic task and we&rsquo;ll save its steps and source links here.</p>
        <button className="nf-btn nf-btn-primary" onClick={() => { window.location.hash = ''; }}>Describe your first task</button>
      </div>
      : <div>{pathways.map((path) => <article className="nf-card nf-result-card" key={`${path.job_id}-${path.slug}`}>
        <span className="nf-result-icon" style={{ background: 'var(--nf-primary-soft)' }} aria-hidden="true">🏛</span>
        <div className="nf-result-body">
          <h2 style={{ fontSize: 16, margin: '0 0 2px' }}>{path.title}</h2>
          <p className="nf-dept">{locationOf(path)} · Started {path.created_at ? new Date(path.created_at).toLocaleDateString() : 'recently'}</p>
          {path.error && <p className="nf-error-box">{path.error}</p>}
          <div className="nf-progress-copy"><span>{path.completed || 0} of {path.steps || 0} steps complete</span><span>{path.steps ? Math.round(((path.completed || 0) / path.steps) * 100) : 0}%</span></div>
          <div className="nf-progress-track"><span style={{ width: `${path.steps ? Math.min(100, ((path.completed || 0) / path.steps) * 100) : 0}%` }} /></div>
          {!!path.steps_preview?.length && <ol className="nf-step-rows">{path.steps_preview.slice(0, 3).map((step, i) => <li key={step.id || i}><span className="nf-tl-marker">{i + 1}</span><div><strong style={{ fontSize: 13.5 }}>{step.title}</strong><br />{step.detail && <small className="nf-muted">{step.detail}</small>}</div></li>)}</ol>}
          {!!path.sources?.length && <p className="nf-muted" style={{ fontSize: 12.5 }}>{path.sources.length} source{path.sources.length === 1 ? '' : 's'} attached</p>}
        </div>
        <div className="nf-result-side">
          <span className={`nf-badge ${path.verified ? 'is-done' : path.status === 'failed' ? 'is-error' : 'is-pending'}`}>{statusLabel(path)}</span>
          {path.status !== 'failed'
            ? <button className="nf-btn nf-btn-outline nf-btn-sm" onClick={() => onOpenPath(path.slug)} disabled={!path.slug} aria-label="Open pathway">View Path →</button>
            : <span className="nf-muted" style={{ fontSize: 12.5 }}>Build failed — try again from Home.</span>}
          {(path.status === 'queued' || path.status === 'running') && <span className="nf-muted" style={{ fontSize: 12.5 }}>Still building — refresh to update.</span>}
        </div>
      </article>)}</div>}
  </div>;
}
