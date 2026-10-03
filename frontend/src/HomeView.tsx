import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import { SERVICE_TYPES } from './types';
import type { CivicSource, PathwaySummary, UserProfile } from './types';

type Props = {
  profile: UserProfile | null;
  onNavigate: (tab: 'home' | 'pathways' | 'documents' | 'help' | 'agent' | 'admin' | 'roadmap', slug?: string) => void;
};

type BuildState = {
  status: 'idle' | 'discovering' | 'building' | 'review_required' | 'verified' | 'failed' | 'timeout';
  slug: string;
  task: string;
  jobId?: number;
  error?: string;
  pathway?: PathwaySummary;
};

const EXAMPLES = ['Apply for a birth certificate', 'Renew a driving licence', 'Register a small business'];

function sourceUrl(source: CivicSource): string {
  return typeof source === 'string' ? source : source?.url || '';
}

function sourceSucceeded(source: CivicSource): boolean {
  return typeof source === 'string' || source.ok !== false;
}

function sourceHost(source: CivicSource): string {
  const url = sourceUrl(source);
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return url || 'Government source'; }
}

function formatDate(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function pathStatus(path: PathwaySummary) {
  if (path.verified) return { label: 'Reviewed and ready', className: 'is-verified' };
  if (path.status === 'review_required') return { label: 'Awaiting source review', className: 'is-pending' };
  if (path.status === 'failed') return { label: 'Build failed', className: 'is-failed' };
  if (path.status === 'queued' || path.status === 'running') return { label: 'Building pathway', className: 'is-building' };
  return { label: 'Saved pathway', className: 'is-pending' };
}

export default function HomeView({ profile, onNavigate }: Props) {
  const [task, setTask] = useState('');
  const [city, setCity] = useState(profile?.city || '');
  const [state, setState] = useState(profile?.state || '');
  const [serviceType, setServiceType] = useState('');
  const [pathways, setPathways] = useState<PathwaySummary[]>([]);
  const [pathwaysLoading, setPathwaysLoading] = useState(true);
  const [pathwaysError, setPathwaysError] = useState('');
  const [build, setBuild] = useState<BuildState>({ status: 'idle', slug: '', task: '' });
  const [buildStartedAt, setBuildStartedAt] = useState<number | null>(null);
  const [buildTick, setBuildTick] = useState(0);
  const pollRef = useRef<number | null>(null);
  const checkingRef = useRef(false);
  const taskInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!city && profile?.city) setCity(profile.city);
    if (!state && profile?.state) setState(profile.state);
  }, [profile?.city, profile?.state]);

  const loadPathways = useCallback(async () => {
    setPathwaysLoading(true);
    setPathwaysError('');
    try {
      const saved = await api.myPathways();
      setPathways(Array.isArray(saved) ? saved : []);
      return Array.isArray(saved) ? saved as PathwaySummary[] : [];
    } catch (e: any) {
      setPathwaysError(String(e.message || e));
      return [];
    } finally {
      setPathwaysLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPathways();
    const refresh = () => { void loadPathways(); };
    const applySearch = (event: Event) => {
      const value = (event as CustomEvent<string>).detail || '';
      if (value) {
        sessionStorage.removeItem('civic_task_prefill');
        setTask(value);
        window.setTimeout(() => taskInputRef.current?.focus(), 0);
      }
    };
    const pending = sessionStorage.getItem('civic_task_prefill');
    if (pending) {
      setTask(pending);
      sessionStorage.removeItem('civic_task_prefill');
      window.setTimeout(() => taskInputRef.current?.focus(), 0);
    }
    const locationPrefill = sessionStorage.getItem('civic_location_prefill');
    if (locationPrefill) {
      try {
        const location = JSON.parse(locationPrefill) as { city?: string; state?: string; serviceType?: string };
        if (location.city) setCity(location.city);
        if (location.state) setState(location.state);
        if (location.serviceType) setServiceType(location.serviceType);
      } catch { /* Ignore invalid transient guest-form data. */ }
      sessionStorage.removeItem('civic_location_prefill');
    }
    window.addEventListener('civic:pathways-updated', refresh);
    window.addEventListener('civic:search-task', applySearch);
    return () => {
      window.removeEventListener('civic:pathways-updated', refresh);
      window.removeEventListener('civic:search-task', applySearch);
      if (pollRef.current !== null) window.clearInterval(pollRef.current);
    };
  }, [loadPathways]);

  useEffect(() => {
    const busy = build.status === 'discovering' || build.status === 'building' || build.status === 'timeout';
    if (!busy) return;
    const timer = window.setInterval(() => setBuildTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [build.status]);

  const beginBuild = async (event: React.FormEvent) => {
    event.preventDefault();
    const cleanTask = task.trim();
    if (!cleanTask || build.status === 'discovering' || build.status === 'building') return;
    if (pollRef.current !== null) window.clearInterval(pollRef.current);
    setBuildStartedAt(Date.now());
    setBuildTick(0);
    setBuild({ status: 'discovering', slug: '', task: cleanTask });
    try {
      const response = await api.buildTask(cleanTask, city.trim(), state.trim(), serviceType);
      const jobId = Number(response.job_id);
      const slug = String(response.slug || '');
      setBuild({ status: 'building', slug, task: cleanTask, jobId });
      let attempts = 0;
      let softTimedOut = false;
      const check = async () => {
        if (checkingRef.current) return;
        checkingRef.current = true;
        attempts += 1;
        try {
          const job = await api.jobStatus(jobId);
          if (job.status === 'failed') {
            if (pollRef.current !== null) window.clearInterval(pollRef.current);
            setBuildStartedAt(null);
            setBuild({ status: 'failed', slug, task: cleanTask, jobId, error: job.result?.error || 'The pathway could not be built. Please try again.' });
            void loadPathways();
          } else if (job.status === 'done') {
            if (pollRef.current !== null) window.clearInterval(pollRef.current);
            setBuildStartedAt(null);
            const resultSlug = String(job.result?.slug || slug);
            let map: any = null;
            try { map = await api.taskMap(resultSlug); } catch { /* the job row still records the completed build */ }
            const saved = await loadPathways();
            const pathway = saved.find((item) => item.slug === resultSlug);
            const verified = Boolean(map?.verified || pathway?.verified);
            setBuild({ status: verified ? 'verified' : 'review_required', slug: resultSlug, task: cleanTask, jobId, pathway });
            window.dispatchEvent(new Event('civic:pathways-updated'));
          } else if (attempts >= 300) {
            if (pollRef.current !== null) window.clearInterval(pollRef.current);
            setBuild({ status: 'timeout', slug, task: cleanTask, jobId, error: 'This is taking longer than expected. The job may still finish; check My pathways in a moment.' });
            void loadPathways();
          } else if (attempts >= 90 && !softTimedOut) {
            // soft timeout: warn the citizen but KEEP polling — builds
            // routinely take 4-5 min and must auto-flip to the ready banner
            softTimedOut = true;
            setBuild({ status: 'timeout', slug, task: cleanTask, jobId, error: 'This is taking longer than expected. The job may still finish; check My pathways in a moment.' });
            void loadPathways();
          }
        } catch (e: any) {
          if (attempts >= 3) {
            if (pollRef.current !== null) window.clearInterval(pollRef.current);
            setBuild({ status: 'failed', slug, task: cleanTask, jobId, error: String(e.message || 'Could not check pathway status.') });
          }
        } finally {
          checkingRef.current = false;
        }
      };
      void check();
      pollRef.current = window.setInterval(() => { void check(); }, 2000);
    } catch (e: any) {
      setBuild({ status: 'failed', slug: '', task: cleanTask, error: String(e.message || e) });
    }
  };

  const focusedPathway = build.pathway || (build.slug ? pathways.find((path) => path.slug === build.slug) : null) || pathways[0] || null;
  const focusedSources = focusedPathway?.sources || [];
  const isBusy = build.status === 'discovering' || build.status === 'building';
  const location = [city.trim(), state.trim()].filter(Boolean).join(', ');
  const elapsedSeconds = buildStartedAt ? Math.max(0, Math.floor((Date.now() - buildStartedAt) / 1000)) : 0;
  const activityStage = build.status === 'discovering' ? 1 : build.status === 'building' ? (elapsedSeconds > 24 ? 3 : 2) : build.status === 'timeout' ? 4 : 0;
  const activityStages = [
    { label: 'Task received', detail: 'Reading your request and location', icon: '✓' },
    { label: 'Finding official sources', detail: 'Checking government websites and service portals', icon: '⌕' },
    { label: 'Cross-checking requirements', detail: 'Comparing documents, fees and eligibility', icon: '↗' },
    { label: 'Building your roadmap', detail: 'Ordering steps and connecting dependencies', icon: '◌' },
    { label: 'Saving your pathway', detail: 'Preparing a clear view with source links', icon: '□' },
  ];
  void buildTick;

  return <div className="cv-home-view cv-anim-up">
    <div className="cv-concierge-grid">
      <main className="cv-concierge-main">
        <section className="cv-concierge-intro">
          <span className="cv-eyebrow">PUBLIC SERVICES FOR A BRIGHTER TOMORROW</span>
          <h1>What do you need to get done?</h1>
          <p>Tell us what you want to do and we’ll create a personalised pathway with the right steps, documents and official sources.</p>
        </section>

        <form className="cv-concierge-form" onSubmit={beginBuild}>
          <div className="cv-concierge-fields">
            <label className="cv-task-field"><span>I want to</span><input ref={taskInputRef} value={task} onChange={(event) => setTask(event.target.value)} placeholder="e.g. Register a small business" aria-label="Describe your civic task" disabled={isBusy} required /></label>
            <div className="cv-location-fields">
              <label><span>City</span><input value={city} onChange={(event) => setCity(event.target.value)} placeholder="Hyderabad" aria-label="City" disabled={isBusy} /></label>
              <label><span>State</span><input value={state} onChange={(event) => setState(event.target.value)} placeholder="Telangana" aria-label="State" disabled={isBusy} /></label>
              <label><span>Type of service</span><select value={serviceType} onChange={(event) => setServiceType(event.target.value)} aria-label="Type of service" disabled={isBusy}><option value="">Select a service type</option>{SERVICE_TYPES.map((kind) => <option key={kind} value={kind}>{kind}</option>)}</select></label>
            </div>
            <button className="cv-build-btn" type="submit" disabled={isBusy || !task.trim()}>{isBusy ? <><span className="cv-button-spinner" /> Building…</> : <>Build my pathway <span aria-hidden="true">›</span></>}</button>
          </div>
          <div className="cv-example-row"><span>Examples:</span>{EXAMPLES.map((example) => <React.Fragment key={example}><button type="button" onClick={() => { setTask(example); taskInputRef.current?.focus(); }}>{example}</button>{example !== EXAMPLES[EXAMPLES.length - 1] && <span className="cv-example-separator">|</span>}</React.Fragment>)}</div>
        </form>

        {isBusy && <div className="cv-build-status" role="status" aria-live="polite"><span className="cv-status-spinner" /><span><strong>{build.status === 'discovering' ? 'Finding official sources…' : 'Putting your pathway together…'}</strong><small>This may take a little while. You can keep this page open.</small></span></div>}
        {(isBusy || build.status === 'timeout') && <section className="cv-activity-card" aria-label="Live pathway activity" aria-live="polite">
          <div className="cv-activity-heading"><div><span className="cv-eyebrow">LIVE PATHWAY ACTIVITY</span><h2>Here’s what’s happening in the background</h2><p>We’ll keep checking until your source-backed pathway is ready.</p></div><span className="cv-activity-timer">{elapsedSeconds}s</span></div>
          <ol className="cv-activity-timeline">{activityStages.map((stage, index) => {
            const done = index < activityStage;
            const active = index === activityStage;
            return <li key={stage.label} className={`${done ? 'is-done' : ''} ${active ? 'is-active' : ''}`}><span className="cv-activity-marker">{done ? '✓' : active ? <span className="cv-activity-pulse">{stage.icon}</span> : index + 1}</span><span className="cv-activity-copy"><strong>{stage.label}</strong><small>{stage.detail}</small></span>{active && <span className="cv-activity-state">In progress</span>}{done && <span className="cv-activity-state is-complete">Complete</span>}</li>;
          })}</ol>
          {build.status === 'timeout' && <p className="cv-activity-note">This is taking longer than usual, but the job is still being checked. You can open My pathways without losing this work.</p>}
        </section>}
        {build.status === 'failed' && <div className="cv-build-alert is-error" role="alert"><strong>We couldn’t build that pathway.</strong><span>{build.error}</span><button type="button" onClick={() => setBuild({ status: 'idle', slug: '', task: '' })}>Try again</button></div>}
        {build.status === 'timeout' && <div className="cv-build-alert is-info" role="status"><strong>Still working</strong><span>{build.error}</span><button type="button" onClick={() => onNavigate('pathways')}>Open My pathways</button></div>}
        {(build.status === 'verified' || build.status === 'review_required') && <div className={`cv-build-alert ${build.status === 'verified' ? 'is-success' : 'is-info'}`} role="status">
          <strong>{build.status === 'verified' ? 'Your reviewed pathway is ready.' : 'Your pathway was built and is awaiting source review.'}</strong>
          <span>{build.status === 'verified' ? 'Its steps and progress are available below.' : 'You can preview the draft now. Step tracking becomes available after review.'}</span>
          <button type="button" onClick={() => onNavigate('roadmap', build.slug)}>Preview pathway <span aria-hidden="true">→</span></button>
        </div>}

        <section className="cv-recent-section" aria-labelledby="recent-pathways-title">
          <div className="cv-section-heading"><h2 id="recent-pathways-title">Recently created pathway</h2><button className="cv-text-link" onClick={() => onNavigate('pathways')}>View all my pathways <span aria-hidden="true">→</span></button></div>
          {pathwaysError && <div className="cv-inline-error" role="alert">Couldn’t load saved pathways: {pathwaysError} <button onClick={() => void loadPathways()}>Retry</button></div>}
          {pathwaysLoading ? <div className="cv-recent-skeleton" role="status">Loading your saved pathways…</div> : pathways.length > 0 ? <article className="cv-recent-pathway-card">
            {(() => {
              const path = pathways[0];
              const status = pathStatus(path);
              const percent = path.steps ? Math.round(((path.completed || 0) / path.steps) * 100) : 0;
              const completedSteps = new Set(path.completed_steps || []);
              const nextStepIndex = (path.steps_preview || []).findIndex((step) => !completedSteps.has(step.id));
              return <>
                <div className="cv-recent-pathway-head"><span className="cv-pathway-emblem" aria-hidden="true">⌂</span><div className="cv-recent-pathway-title"><h3>{path.title}</h3><p>{[path.city, path.state].filter(Boolean).join(', ') || 'Location not specified'} <span aria-hidden="true">·</span> Created {formatDate(path.created_at) || 'recently'}</p><small>Follow these steps and check each official source before applying.</small></div><span className={`cv-status-pill ${status.className}`}>{status.label}</span></div>
                {path.error && <p className="cv-inline-error">{path.error}</p>}
                <div className="cv-recent-progress"><div className="cv-progress-copy"><span>{path.completed || 0} of {path.steps || 0} steps complete</span><span>{percent}%</span></div><div className="cv-progress-track"><span style={{ width: `${percent}%` }} /></div></div>
                <ol className="cv-recent-step-list">{(path.steps_preview || []).slice(0, 4).map((step, index) => { const isComplete = completedSteps.has(step.id); const isNext = index === nextStepIndex; return <li key={step.id || index} className={isComplete ? 'is-complete' : ''}><span className="cv-recent-step-number">{isComplete ? '✓' : index + 1}</span><div className="cv-recent-step-copy"><strong>{step.title}</strong>{step.detail && <small>{step.detail}</small>}</div><span className={`cv-step-state ${isComplete ? 'is-complete' : isNext ? 'is-ready' : ''}`}>{isComplete ? 'Complete' : isNext ? 'Ready' : 'Up next'}</span><button className="cv-step-open" type="button" aria-label={`Open ${step.title}`} onClick={() => onNavigate('roadmap', path.slug)}>›</button></li>; })}</ol>
                <div className="cv-recent-pathway-footer"><span>{path.steps} steps <span aria-hidden="true">·</span> {path.sources?.length || 0} sources</span><button className="cv-btn cv-btn-ghost" type="button" onClick={() => onNavigate('roadmap', path.slug)}>Open pathway</button></div>
              </>;
            })()}
          </article> : <div className="cv-empty-recent"><span className="cv-empty-path-icon" aria-hidden="true">⌁</span><div><strong>No pathway created yet</strong><p>Start with a task above. Your saved steps and source links will appear here.</p></div><button className="cv-btn cv-btn-ghost" type="button" onClick={() => setTask('Register a small business')}>Try an example</button></div>}
        </section>
      </main>

      <aside className="cv-concierge-aside" aria-label="Source information and support">
        <section className="cv-aside-card cv-source-confidence">
          <div className="cv-aside-card-heading"><div><h2>Source confidence</h2><p>Check the official pages behind your pathway.</p></div><span className="cv-aside-info" aria-hidden="true">i</span></div>
          {focusedSources.length ? <div className="cv-official-source-list">{focusedSources.slice(0, 4).map((source, index) => {
            const url = sourceUrl(source);
            const okay = sourceSucceeded(source);
            const fetched = typeof source === 'string' ? '' : source.fetched_at;
            return <div className="cv-official-source" key={`${url}-${index}`}><span className={`cv-source-status-dot ${okay ? 'is-ok' : 'is-error'}`} aria-hidden="true">{okay ? '✓' : '!'}</span><div><strong>{sourceHost(source)}</strong><small>{okay ? 'Page fetched for this pathway' : 'Could not fetch this source'}</small>{fetched && <small>Checked {formatDate(fetched)}</small>}</div>{url && <a href={url} target="_blank" rel="noreferrer" aria-label={`Open ${sourceHost(source)} official source`}>↗</a>}</div>;
          })}</div> : <div className="cv-source-empty"><span aria-hidden="true">⌕</span><p>{focusedPathway ? 'No source links were saved for this pathway.' : 'Build a pathway to see its official source links here.'}</p></div>}
          <div className="cv-source-caution"><span aria-hidden="true">i</span><p><strong>Confirm details with the official source before applying.</strong><br />Rules, fees and procedures can change. Always check the latest instructions on the linked website.</p></div>
        </section>

        <section className="cv-aside-card cv-help-card"><div className="cv-aside-card-heading"><div><h2>Need help?</h2><p>Get clear answers and step-by-step guidance.</p></div></div><button className="cv-help-center-button" onClick={() => onNavigate('help')}><span className="cv-help-round"><span aria-hidden="true">?</span></span>Visit Help Centre<span className="cv-button-chevron" aria-hidden="true">›</span></button></section>
        <section className="cv-aside-promise"><span className="cv-promise-leaf" aria-hidden="true">✦</span><div><strong>Civic services, made simpler</strong><p>Clear steps. Source links. Real progress.</p></div></section>
      </aside>
    </div>
  </div>;
}
