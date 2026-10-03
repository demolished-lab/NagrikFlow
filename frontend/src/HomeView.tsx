import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import { SERVICE_TYPES } from './types';
import type { CivicSource, PathwaySummary, UserProfile } from './types';
import { Skyline } from './nf-kit';

type Props = {
  profile: UserProfile | null;
  onNavigate: (tab: 'home' | 'search' | 'pathways' | 'documents' | 'help' | 'agent' | 'admin' | 'roadmap', slug?: string) => void;
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
  if (path.verified) return { label: 'Reviewed and ready', className: 'is-done' };
  if (path.status === 'review_required') return { label: 'Awaiting source review', className: 'is-pending' };
  if (path.status === 'failed') return { label: 'Build failed', className: 'is-error' };
  if (path.status === 'queued' || path.status === 'running') return { label: 'Building pathway', className: 'is-progress' };
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

  const beginBuildWith = useCallback(async (taskValue: string, cityValue: string, stateValue: string, serviceValue: string) => {
    const cleanTask = taskValue.trim();
    if (!cleanTask || pollRef.current !== null) return;
    setBuildStartedAt(Date.now());
    setBuildTick(0);
    setBuild({ status: 'discovering', slug: '', task: cleanTask });
    try {
      const response = await api.buildTask(cleanTask, cityValue.trim(), stateValue.trim(), serviceValue);
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
            pollRef.current = null;
            setBuildStartedAt(null);
            setBuild({ status: 'failed', slug, task: cleanTask, jobId, error: job.result?.error || 'The pathway could not be built. Please try again.' });
            void loadPathways();
          } else if (job.status === 'done') {
            if (pollRef.current !== null) window.clearInterval(pollRef.current);
            pollRef.current = null;
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
            pollRef.current = null;
            setBuild({ status: 'timeout', slug, task: cleanTask, jobId, error: 'This is taking longer than expected. The job may still finish; check My pathways in a moment.' });
            void loadPathways();
          } else if (attempts >= 90 && !softTimedOut) {
            softTimedOut = true;
            setBuild({ status: 'timeout', slug, task: cleanTask, jobId, error: 'This is taking longer than expected. The job may still finish; check My pathways in a moment.' });
            void loadPathways();
          }
        } catch (e: any) {
          if (attempts >= 3) {
            if (pollRef.current !== null) window.clearInterval(pollRef.current);
            pollRef.current = null;
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
  }, [loadPathways]);

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
    // prefill from guest flow / service search, with optional auto-build
    const pending = sessionStorage.getItem('civic_task_prefill');
    const locationPrefill = sessionStorage.getItem('civic_location_prefill');
    let preCity = '', preState = '', preService = '';
    if (locationPrefill) {
      try {
        const location = JSON.parse(locationPrefill) as { city?: string; state?: string; serviceType?: string };
        if (location.city) { setCity(location.city); preCity = location.city; }
        if (location.state) { setState(location.state); preState = location.state; }
        if (location.serviceType) { setServiceType(location.serviceType); preService = location.serviceType; }
      } catch { /* Ignore invalid transient guest-form data. */ }
      sessionStorage.removeItem('civic_location_prefill');
    }
    const autoBuild = sessionStorage.getItem('civic_autobuild');
    if (pending) {
      sessionStorage.removeItem('civic_task_prefill');
      if (autoBuild) {
        sessionStorage.removeItem('civic_autobuild');
        setTask(pending);
        window.setTimeout(() => { void beginBuildWith(pending, preCity, preState, preService); }, 50);
      } else {
        setTask(pending);
        window.setTimeout(() => taskInputRef.current?.focus(), 0);
      }
    }
    window.addEventListener('civic:pathways-updated', refresh);
    window.addEventListener('civic:search-task', applySearch);
    return () => {
      window.removeEventListener('civic:pathways-updated', refresh);
      window.removeEventListener('civic:search-task', applySearch);
      if (pollRef.current !== null) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [loadPathways, beginBuildWith]);

  useEffect(() => {
    const busy = build.status === 'discovering' || build.status === 'building' || build.status === 'timeout';
    if (!busy) return;
    const timer = window.setInterval(() => setBuildTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [build.status]);

  const beginBuild = (event: React.FormEvent) => {
    event.preventDefault();
    if (build.status === 'discovering' || build.status === 'building') return;
    void beginBuildWith(task, city, state, serviceType);
  };

  const focusedPathway = build.pathway || (build.slug ? pathways.find((path) => path.slug === build.slug) : null) || pathways[0] || null;
  const focusedSources = focusedPathway?.sources || [];
  const isBusy = build.status === 'discovering' || build.status === 'building';
  const elapsedSeconds = buildStartedAt ? Math.max(0, Math.floor((Date.now() - buildStartedAt) / 1000)) : 0;
  const activityStage = build.status === 'discovering' ? 1 : build.status === 'building' ? (elapsedSeconds > 24 ? 3 : 2) : build.status === 'timeout' ? 4 : 0;
  const activityStages = [
    { label: 'Task received', detail: 'Reading your request and location' },
    { label: 'Finding official sources', detail: 'Checking government websites and service portals' },
    { label: 'Cross-checking requirements', detail: 'Comparing documents, fees and eligibility' },
    { label: 'Building your roadmap', detail: 'Ordering steps and connecting dependencies' },
    { label: 'Saving your pathway', detail: 'Preparing a clear view with source links' },
  ];
  void buildTick;

  return <div>
    <div className="nf-crumb"><span>Home</span> · <b>New pathway</b></div>
    <div className="nf-two-col">
      <div>
        <div className="nf-card nf-task-card" style={{ margin: 0 }}>
          <span className="nf-eyebrow">Public services for a brighter tomorrow</span>
          <h1>What do you need to get done?</h1>
          <p>Tell us what you want to do and we&rsquo;ll create a personalised pathway with the right steps, documents and official sources.</p>
          <form onSubmit={beginBuild}>
            <div className="nf-task-main">
              <span className="nf-q" aria-hidden="true">⌕</span>
              <input ref={taskInputRef} value={task} onChange={(e) => setTask(e.target.value)} placeholder="I want to register a small business" aria-label="Describe your civic task" disabled={isBusy} required />
            </div>
            <div className="nf-task-row nf-task-row-3">
              <div className="nf-field"><label htmlFor="hv-city">Location</label><input id="hv-city" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Hyderabad" aria-label="City" disabled={isBusy} /></div>
              <div className="nf-field"><label htmlFor="hv-state">State</label><input id="hv-state" value={state} onChange={(e) => setState(e.target.value)} placeholder="Telangana" aria-label="State" disabled={isBusy} /></div>
              <div className="nf-field"><label htmlFor="hv-svc">Service Type</label><select id="hv-svc" value={serviceType} onChange={(e) => setServiceType(e.target.value)} aria-label="Type of service" disabled={isBusy}><option value="">Select a service type</option>{SERVICE_TYPES.map((k) => <option key={k} value={k}>{k}</option>)}</select></div>
            </div>
            <button className="nf-btn nf-btn-primary nf-find-btn" type="submit" disabled={isBusy || !task.trim()}>{isBusy ? <><span className="nf-spin" aria-hidden="true">◌</span> Building…</> : 'Build my pathway ›'}</button>
          </form>
          <div className="nf-examples"><span>Try these examples</span>{EXAMPLES.map((ex) => <button key={ex} type="button" onClick={() => { setTask(ex); taskInputRef.current?.focus(); }}>{ex}</button>)}</div>
          <Skyline />
        </div>

        {isBusy && <div className="cv-build-status" role="status" aria-live="polite"><span className="nf-spin" aria-hidden="true">◌</span><span><strong>{build.status === 'discovering' ? 'Finding official sources…' : 'Putting your pathway together…'}</strong><br /><small>This may take a little while. Watch every stage below — nothing runs hidden.</small></span><span className="nf-live-dot" aria-label="Live" style={{ marginLeft: 'auto', alignSelf: 'center' }} /></div>}
        {(isBusy || build.status === 'timeout') && <section className="nf-card nf-activity" aria-label="Live pathway activity" aria-live="polite">
          <div className="nf-activity-head"><div><span className="nf-eyebrow">Live pathway activity</span><h2>Here&rsquo;s what&rsquo;s happening in the background</h2><p>We poll the build job every 2 seconds until your source-backed pathway is ready.</p></div><span className="nf-activity-timer">{elapsedSeconds}s</span></div>
          <ol className="nf-timeline">{activityStages.map((stage, index) => {
            const done = index < activityStage;
            const active = index === activityStage;
            return <li key={stage.label} className={`${done ? 'is-done' : ''} ${active ? 'is-active' : ''}`}><span className="nf-tl-marker">{done ? '✓' : active ? '◌' : index + 1}</span><span><strong>{stage.label}</strong><br /><small>{stage.detail}</small></span>{active && <span className="nf-tl-state">In progress</span>}{done && <span className="nf-tl-state">Complete</span>}</li>;
          })}</ol>
          {build.status === 'timeout' && <p className="nf-muted" style={{ fontSize: 13 }}>This is taking longer than usual, but the job is still being checked. You can open My pathways without losing this work.</p>}
        </section>}
        {build.status === 'failed' && <div className="nf-error-box" role="alert" style={{ marginTop: 16 }}><strong>We couldn&rsquo;t build that pathway.</strong><br />{build.error} <button type="button" className="nf-link-btn" onClick={() => setBuild({ status: 'idle', slug: '', task: '' })}>Try again</button></div>}
        {build.status === 'timeout' && <div className="nf-note-box" role="status" style={{ marginTop: 16 }}><strong>Still working.</strong> {build.error} <button type="button" className="nf-link-btn" onClick={() => onNavigate('pathways')}>Open My pathways</button></div>}
        {(build.status === 'verified' || build.status === 'review_required') && <div className={build.status === 'verified' ? 'nf-ok-box' : 'nf-note-box'} role="status" style={{ marginTop: 16 }}>
          <strong>{build.status === 'verified' ? 'Your reviewed pathway is ready.' : 'Your pathway was built and is awaiting source review.'}</strong><br />
          <span style={{ fontSize: 13 }}>{build.status === 'verified' ? 'Its steps and progress are available below.' : 'You can preview the draft now. Step tracking becomes available after review.'}</span><br />
          <button type="button" className="nf-btn nf-btn-primary nf-btn-sm" style={{ marginTop: 8 }} onClick={() => onNavigate('roadmap', build.slug)}>Preview pathway →</button>
        </div>}

        <section className="nf-section" aria-labelledby="recent-title">
          <div className="nf-section-head"><h2 id="recent-title">Recently created pathway</h2><button className="nf-text-link" onClick={() => onNavigate('pathways')}>View all my pathways →</button></div>
          {pathwaysError && <div className="nf-error-box" role="alert">Couldn&rsquo;t load saved pathways: {pathwaysError} <button className="nf-link-btn" onClick={() => void loadPathways()}>Retry</button></div>}
          {pathwaysLoading ? <div className="nf-card" style={{ padding: 20 }} role="status"><p className="nf-muted">Loading your saved pathways…</p></div> : pathways.length > 0 ? <article className="nf-card" style={{ padding: 20 }}>
            {(() => {
              const path = pathways[0];
              const status = pathStatus(path);
              const percent = path.steps ? Math.round(((path.completed || 0) / path.steps) * 100) : 0;
              return <>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 10 }}>
                  <span style={{ fontSize: 26 }} aria-hidden="true">⌂</span>
                  <div style={{ flex: 1 }}><h3 style={{ margin: 0, fontSize: 16 }}>{path.title}</h3><p className="nf-muted" style={{ margin: 0, fontSize: 13 }}>{[path.city, path.state].filter(Boolean).join(', ') || 'Location not specified'} · Created {formatDate(path.created_at) || 'recently'}</p></div>
                  <span className={`nf-badge ${status.className === 'is-done' ? 'is-done' : status.className === 'is-error' ? 'is-error' : status.className === 'is-progress' ? 'is-progress' : 'is-pending'}`}>{status.label}</span>
                </div>
                {path.error && <p className="nf-error-box">{path.error}</p>}
                <div className="nf-progress-copy"><span>{path.completed || 0} of {path.steps || 0} steps complete</span><span>{percent}%</span></div>
                <div className="nf-progress-track"><span style={{ width: `${percent}%` }} /></div>
                {!!path.steps_preview?.length && <ol className="nf-step-rows">{path.steps_preview.slice(0, 4).map((step, i) => <li key={step.id || i}><span className="nf-tl-marker">{i + 1}</span><div style={{ flex: 1 }}><strong style={{ fontSize: 14 }}>{step.title}</strong><br />{step.detail && <small className="nf-muted">{step.detail}</small>}</div>{step.url && <a href={step.url} target="_blank" rel="noreferrer" aria-label={`Open official source for ${step.title}`}>↗</a>}</li>)}</ol>}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}><span className="nf-muted" style={{ fontSize: 13 }}>{path.steps} steps · {path.sources?.length || 0} sources</span><button className="nf-btn nf-btn-ghost nf-btn-sm" onClick={() => onNavigate('roadmap', path.slug)}>Open pathway</button></div>
              </>;
            })()}
          </article> : <div className="nf-card" style={{ padding: 20 }}><strong>No pathway created yet</strong><p className="nf-muted" style={{ fontSize: 13 }}>Start with a task above. Your saved steps and source links will appear here.</p></div>}
        </section>
      </div>

      <div className="nf-side-stack">
        <div className="nf-card nf-side-card">
          <h2>Source confidence</h2><p className="nf-sub">Check the official pages behind your pathway.</p>
          {focusedSources.length ? focusedSources.slice(0, 4).map((source, i) => {
            const url = sourceUrl(source);
            const okay = sourceSucceeded(source);
            return <div className="nf-source-row" key={`${url}-${i}`}><span aria-hidden="true">{okay ? '✓' : '!'}</span><div><strong>{sourceHost(source)}</strong><small>{okay ? 'Page fetched for this pathway' : 'Could not fetch this source'}</small></div>{url && <a href={url} target="_blank" rel="noreferrer" aria-label={`Open ${sourceHost(source)} official source`}>↗</a>}</div>;
          }) : <p className="nf-muted" style={{ fontSize: 13 }}>{focusedPathway ? 'No source links were saved for this pathway.' : 'Build a pathway to see its official source links here.'}</p>}
          <div className="nf-caution"><span aria-hidden="true">ⓘ</span><p><strong>Confirm details with the official source before applying.</strong> Rules, fees and procedures can change.</p></div>
        </div>
        <div className="nf-card nf-side-card nf-help-card">
          <h2>Need help?</h2><p className="nf-sub">Get clear answers and step-by-step guidance.</p>
          <button className="nf-btn nf-btn-primary nf-btn-sm" onClick={() => onNavigate('help')}>Visit Help Centre ›</button>
        </div>
      </div>
    </div>
  </div>;
}
