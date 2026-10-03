import React, { useCallback, useEffect, useState } from 'react';
import { STR, lang } from './i18n';
import { api, req } from './api';

type AdminMap = {
  slug: string;
  title: string;
  steps?: number;
  verified?: boolean | string;
  hash?: string;
  checked?: string;
  sources?: (string | { url?: string })[];
};

type AdminStep = {
  id: string;
  type: string;
  title: string;
  detail?: string;
  url?: string;
  link?: string;
  fee?: string;
};

const STEP_TYPES = ['prereq', 'action', 'payment', 'visit', 'unlocked', 'document'];
const EMPTY_STEP = { title: '', detail: '', fee: '', url: '', link: '', type: 'action' };

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export default function Admin() {
  const t = STR[lang()];
  const [maps, setMaps] = useState<AdminMap[]>([]);
  const [err, setErr] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ task: '', slug: '', urls: '' });
  const [building, setBuilding] = useState(false);
  const [checking, setChecking] = useState('');
  const [editingSlug, setEditingSlug] = useState('');
  const [steps, setSteps] = useState<AdminStep[]>([]);
  const [draft, setDraft] = useState<AdminStep | null>(null);
  const [newStep, setNewStep] = useState({ ...EMPTY_STEP });
  const [stepBusy, setStepBusy] = useState(false);
  const [side, setSide] = useState('overview');

  const load = useCallback(async () => {
    try {
      const rows = await req('/admin/maps');
      setMaps(Array.isArray(rows) ? rows : []);
      setErr('');
    } catch (error: any) {
      setErr(String(error.message || error));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const verify = async (slug: string, verified: boolean) => {
    setErr('');
    setNotice('');
    try {
      await req(`/admin/maps/${encodeURIComponent(slug)}/verify`, {
        method: 'POST', body: JSON.stringify({ verified }),
      });
      await load();
      setNotice(verified ? `${slug} is marked as reviewed and verified.` : `${slug} is no longer marked as verified.`);
    } catch (error: any) {
      setErr(String(error.message || error));
    }
  };

  const pollJob = async (id: number) => {
    for (let index = 0; index < 100; index++) {
      await new Promise((resolve) => setTimeout(resolve, 3000));
      const job = await req(`/admin/jobs/${id}`);
      if (job.status === 'done' || job.status === 'failed') return job;
    }
    return { status: 'timeout' };
  };

  const recheck = async (slug: string) => {
    setChecking(slug || 'all');
    setErr('');
    setNotice('');
    try {
      const { job_id } = await req('/admin/jobs/recheck', {
        method: 'POST', body: JSON.stringify({ slug }),
      });
      const job = await pollJob(job_id);
      if (job.status === 'failed') {
        setErr(`The source check failed: ${JSON.stringify(job.result || {})}`);
      } else if (job.status === 'timeout') {
        setNotice('The source check is taking longer than expected. It may still finish in the background.');
      } else {
        const changed = ((job.result || {}).maps || []).filter((map: any) => map.changed);
        setNotice(changed.length
          ? `Changed source content found for ${changed.map((map: any) => map.slug).join(', ')}. Verification was revoked.`
          : 'No changes found. The checked maps remain verified.');
      }
      await load();
    } catch (error: any) {
      setErr(String(error.message || error));
    } finally {
      setChecking('');
    }
  };

  const build = async () => {
    setBuilding(true);
    setErr('');
    setNotice('');
    try {
      const { job_id } = await req('/admin/jobs/build', {
        method: 'POST',
        body: JSON.stringify({ ...form, urls: form.urls.split('\n').map((url) => url.trim()).filter(Boolean) }),
      });
      const job = await pollJob(job_id);
      if (job.status === 'failed') throw new Error(JSON.stringify(job.result || {}));
      if (job.status === 'timeout') {
        setNotice('The map build is taking longer than expected and may still finish. Refresh the review desk shortly.');
      } else {
        setNotice(`Built ${job.result.slug}: ${job.result.steps} steps. This map is unverified until it has been reviewed.`);
      }
      await load();
    } catch (error: any) {
      setErr(String(error.message || error));
    } finally {
      setBuilding(false);
    }
  };

  const loadSteps = async (slug: string) => {
    const data = await api.adminSteps(slug);
    setSteps(Array.isArray(data.nodes) ? data.nodes : []);
  };

  const toggleSteps = async (slug: string) => {
    if (editingSlug === slug) {
      setEditingSlug('');
      setDraft(null);
      return;
    }
    setErr('');
    setNotice('');
    try {
      await loadSteps(slug);
      setEditingSlug(slug);
      setDraft(null);
      setNewStep({ ...EMPTY_STEP });
    } catch (error: any) {
      setErr(String(error.message || error));
    }
  };

  const saveStep = async (slug: string) => {
    if (!draft || !draft.title.trim()) return;
    setStepBusy(true);
    setErr('');
    setNotice('');
    try {
      await api.adminUpdateStep(slug, draft.id, draft);
      await loadSteps(slug);
      setDraft(null);
      setNotice(`Step "${draft.title}" updated on ${slug}. Re-verify the map if it was already approved.`);
    } catch (error: any) {
      setErr(String(error.message || error));
    } finally {
      setStepBusy(false);
    }
  };

  const deleteStep = async (slug: string, stepId: string) => {
    setStepBusy(true);
    setErr('');
    setNotice('');
    try {
      await api.adminDeleteStep(slug, stepId);
      await loadSteps(slug);
      if (draft?.id === stepId) setDraft(null);
      await load();
      setNotice(`Step "${stepId}" removed from ${slug}.`);
    } catch (error: any) {
      setErr(String(error.message || error));
    } finally {
      setStepBusy(false);
    }
  };

  const addStep = async (slug: string) => {
    if (!newStep.title.trim()) return;
    setStepBusy(true);
    setErr('');
    setNotice('');
    try {
      await api.adminAddStep(slug, newStep);
      await loadSteps(slug);
      setNewStep({ ...EMPTY_STEP });
      await load();
      setNotice(`Step "${newStep.title}" added to ${slug}.`);
    } catch (error: any) {
      setErr(String(error.message || error));
    } finally {
      setStepBusy(false);
    }
  };

  const go = (id: string) => { setSide(id); scrollTo(`admin-${id}`); };
  const pending = maps.filter((m) => !m.verified).length;
  const validated = maps.filter((m) => m.verified).length;

  return <div>
    <div className="nf-crumb"><button onClick={() => { window.location.hash = ''; }}>Home</button> · <b>Admin Dashboard</b></div>
    <div className="nf-page-head">
      <span className="nf-eyebrow">Admin workspace</span>
      <h1>Pathway verification desk</h1>
      <p>Review source-backed civic maps, approve verified workflows, and recheck changes from official websites.</p>
    </div>

    {err && <div className="nf-error-box" role="alert" style={{ marginBottom: 12 }}>{err}<button type="button" className="nf-link-btn" onClick={() => setErr('')} aria-label="Dismiss error"> ×</button></div>}
    {notice && <div className="nf-ok-box" role="status" style={{ marginBottom: 12 }}>{notice}<button type="button" className="nf-link-btn" onClick={() => setNotice('')} aria-label="Dismiss message"> ×</button></div>}

    <div className="nf-admin-layout">
      <aside className="nf-card nf-admin-side" aria-label="Admin sections">
        {[['overview', '◉', 'Overview'], ['queue', '☰', 'Extraction Queue'], ['review', '✓', 'Validation'], ['build', '＋', 'Build map'], ['users', '👥', 'Users'], ['reports', '📊', 'Reports'], ['settings', '⚙', 'Settings']].map(([id, icon, label]) => (
          <button key={id} className={side === id ? 'is-active' : ''} onClick={() => go(id)}><span aria-hidden="true">{icon}</span>{label}</button>
        ))}
      </aside>

      <div>
        <section id="admin-overview" aria-label="Overview">
          <div className="nf-admin-stats">
            <div className="nf-card nf-stat"><span className="nf-stat-ic" style={{ background: 'var(--nf-blue-soft)' }} aria-hidden="true">📚</span><div><b>{loading ? '…' : maps.length}</b><small>Total Services</small></div></div>
            <div className="nf-card nf-stat"><span className="nf-stat-ic" style={{ background: 'var(--nf-amber-soft)' }} aria-hidden="true">⏳</span><div><b>{loading ? '…' : pending}</b><small>Pending Review</small></div></div>
            <div className="nf-card nf-stat"><span className="nf-stat-ic" style={{ background: 'var(--nf-green-soft)' }} aria-hidden="true">✅</span><div><b>{loading ? '…' : validated}</b><small>Validated</small></div></div>
            <div className="nf-card nf-stat"><span className="nf-stat-ic" style={{ background: 'var(--nf-red-soft)' }} aria-hidden="true">⚠</span><div><b>0</b><small>Conflicts</small></div></div>
          </div>
        </section>

        <section id="admin-queue" aria-label="Extraction queue" style={{ marginBottom: 18 }}>
          <div className="nf-section-head"><h2>Extraction Queue</h2><button className="nf-text-link" onClick={() => { setSide('review'); scrollTo('admin-review'); }}>View All →</button></div>
          <div className="nf-table-wrap"><table className="nf-table">
            <thead><tr><th>Service</th><th>Source</th><th>Status</th><th>Updated At</th><th>Action</th></tr></thead>
            <tbody>
              {loading && <tr><td colSpan={5} role="status">Loading pathways…</td></tr>}
              {!loading && maps.length === 0 && <tr><td colSpan={5}>No pathway maps are available for review yet.</td></tr>}
              {maps.map((map) => {
                const sources = (map.sources || []).map((s) => typeof s === 'string' ? s : s?.url || '').filter(Boolean);
                return <tr key={map.slug}>
                  <td><strong>{map.title}</strong></td>
                  <td className="nf-muted">{sources[0] || '—'}</td>
                  <td><span className={`nf-badge ${map.verified ? 'is-done' : 'is-pending'}`}>{map.verified ? 'Validated' : 'In Progress'}</span></td>
                  <td className="nf-muted">{map.checked ? new Date(map.checked).toLocaleString() : 'Never'}</td>
                  <td><button className="nf-tbtn" onClick={() => { setSide('review'); scrollTo('admin-review'); }}>Review</button></td>
                </tr>;
              })}
            </tbody>
          </table></div>
        </section>

        <section id="admin-review" className="nf-card nf-admin-panel" aria-labelledby="admin-review-heading">
          <h2 id="admin-review-heading">Pathway review</h2>
          <p className="nf-sub">Review source freshness before marking a map ready for citizen progress tracking.</p>
          <div style={{ marginBottom: 12 }}><button className="nf-btn nf-btn-ghost nf-btn-sm" type="button" onClick={() => void recheck('')} disabled={Boolean(checking)}>{checking === 'all' ? 'Checking all sources…' : t.admRecheckAll}</button></div>
          {loading ? <p className="nf-muted" role="status">Loading pathways…</p> : maps.length === 0 ? <div className="nf-muted">No pathway maps are available for review yet.</div> : maps.map((map) => {
            const sources = (map.sources || []).map((s) => typeof s === 'string' ? s : s?.url || '').filter(Boolean);
            return <article className="nf-admin-map" key={map.slug}>
              <h3>{map.title}</h3>
              <p><strong>{map.verified ? 'Reviewed and verified' : 'Awaiting review'}</strong> · {map.slug} · {map.steps || 0} steps</p>
              <p>Content hash: {map.hash || '—'} · Last checked: {map.checked || 'Never'}</p>
              <p><strong>Official sources:</strong> {sources.length ? sources.join(' · ') : 'No source URLs recorded'}</p>
              <div className="nf-admin-actions">
                <button type="button" className="nf-btn nf-btn-ghost nf-btn-sm" onClick={() => void verify(map.slug, !map.verified)}>{map.verified ? t.admUnverify : t.admVerify}</button>
                <button type="button" className="nf-btn nf-btn-outline nf-btn-sm" onClick={() => void recheck(map.slug)} disabled={Boolean(checking)}>{checking === map.slug ? 'Checking…' : t.admRecheck}</button>
                <button type="button" className="nf-btn nf-btn-ghost nf-btn-sm" onClick={() => void toggleSteps(map.slug)}>{editingSlug === map.slug ? 'Close editor' : 'Edit steps'}</button>
              </div>
              {editingSlug === map.slug && <div className="nf-admin-form" style={{ marginTop: 12, borderTop: '1px dashed var(--nf-line)', paddingTop: 12 }}>
                <h4 style={{ margin: '0 0 4px' }}>Step editor — {map.title}</h4>
                <p className="nf-muted" style={{ fontSize: 12.5 }}>Update titles, details, fees and official links. Edits persist until the map is rebuilt from sources.</p>
                {steps.length === 0 ? <p className="nf-muted" style={{ fontSize: 13 }}>This map has no steps yet — add the first one below.</p> : steps.map((step) => draft?.id === step.id
                  ? <div key={step.id} style={{ border: '1px dashed var(--nf-primary)', borderRadius: 10, padding: 12, marginBottom: 8 }}>
                      <label>Title<input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></label>
                      <div className="nf-admin-grid2">
                        <label>Type<select value={draft.type} onChange={(e) => setDraft({ ...draft, type: e.target.value })}>{STEP_TYPES.map((k) => <option key={k} value={k}>{k}</option>)}</select></label>
                        <label>Fee<input value={draft.fee || ''} onChange={(e) => setDraft({ ...draft, fee: e.target.value })} placeholder="e.g. ₹500" /></label>
                      </div>
                      <label>Official source URL<input value={draft.url || ''} onChange={(e) => setDraft({ ...draft, url: e.target.value })} placeholder="https://...gov.in/..." /></label>
                      <label>Application / form link<input value={draft.link || ''} onChange={(e) => setDraft({ ...draft, link: e.target.value })} placeholder="https://...gov.in/form (deep link, optional)" /></label>
                      <label>Detail<textarea value={draft.detail || ''} rows={2} onChange={(e) => setDraft({ ...draft, detail: e.target.value })} /></label>
                      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                        <button type="button" className="nf-btn nf-btn-primary nf-btn-sm" onClick={() => void saveStep(map.slug)} disabled={stepBusy || !draft.title.trim()}>{stepBusy ? 'Saving…' : 'Save step'}</button>
                        <button type="button" className="nf-btn nf-btn-ghost nf-btn-sm" onClick={() => setDraft(null)} disabled={stepBusy}>Cancel</button>
                      </div>
                    </div>
                  : <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--nf-line)' }}>
                      <strong style={{ flex: 1, fontSize: 13.5 }}>{step.title}</strong>
                      <small className="nf-muted">{step.type}{step.fee ? ` · ${step.fee}` : ''}</small>
                      <button type="button" className="nf-link-btn" onClick={() => setDraft({ ...step })} disabled={stepBusy}>Edit</button>
                      <button type="button" className="nf-link-btn" onClick={() => void deleteStep(map.slug, step.id)} disabled={stepBusy}>Delete</button>
                    </div>)}
                <div style={{ marginTop: 10 }}>
                  <div className="nf-admin-grid2">
                    <label>New step title<input value={newStep.title} onChange={(e) => setNewStep({ ...newStep, title: e.target.value })} placeholder="e.g. Collect signed declaration" /></label>
                    <label>Type<select value={newStep.type} onChange={(e) => setNewStep({ ...newStep, type: e.target.value })}>{STEP_TYPES.map((k) => <option key={k} value={k}>{k}</option>)}</select></label>
                  </div>
                  <label>Official source URL<input value={newStep.url} onChange={(e) => setNewStep({ ...newStep, url: e.target.value })} placeholder="https://...gov.in/... (optional)" /></label>
                  <label>Application / form link<input value={newStep.link} onChange={(e) => setNewStep({ ...newStep, link: e.target.value })} placeholder="https://...gov.in/form (deep link, optional)" /></label>
                  <div style={{ marginTop: 8 }}><button type="button" className="nf-btn nf-btn-primary nf-btn-sm" onClick={() => void addStep(map.slug)} disabled={stepBusy || !newStep.title.trim()}>{stepBusy ? 'Saving…' : 'Add step'}</button></div>
                </div>
              </div>}
            </article>;
          })}
        </section>

        <section id="admin-build" className="nf-card nf-admin-panel" aria-labelledby="admin-build-heading">
          <h2 id="admin-build-heading">Build a pathway map</h2>
          <p className="nf-sub">Start a source-backed map from known official URLs. New maps remain unverified until reviewed.</p>
          <div className="nf-admin-form">
            <label htmlFor="admin-task">Civic task<input id="admin-task" value={form.task} placeholder="e.g. Apply for a birth certificate" onChange={(e) => setForm({ ...form, task: e.target.value })} /></label>
            <div className="nf-admin-grid2">
              <label htmlFor="admin-slug">Pathway slug<input id="admin-slug" value={form.slug} placeholder="e.g. birth-cert" onChange={(e) => setForm({ ...form, slug: e.target.value })} /></label>
              <label htmlFor="admin-urls">Official source URLs<textarea id="admin-urls" value={form.urls} rows={3} placeholder="One government URL per line" onChange={(e) => setForm({ ...form, urls: e.target.value })} /></label>
            </div>
            <div style={{ marginTop: 10 }}><button className="nf-btn nf-btn-primary nf-btn-sm" type="button" onClick={() => void build()} disabled={building || !form.task.trim() || !form.slug.trim()}>{building ? 'Building map…' : 'Build map'}</button></div>
          </div>
        </section>

        <section id="admin-users" className="nf-card nf-admin-panel" aria-label="Users">
          <h2>Users</h2><p className="nf-sub">Administrators with review-desk access.</p>
          <p style={{ fontSize: 13.5 }}>Signed in as an administrator. Role changes are managed through the backend user store.</p>
        </section>

        <section id="admin-reports" className="nf-card nf-admin-panel" aria-label="Reports">
          <h2>Reports</h2><p className="nf-sub">Citizen progress exports run from the documents view; source rechecks run from validation above.</p>
        </section>

        <section id="admin-settings" className="nf-card nf-admin-panel" aria-label="Settings">
          <h2>Settings</h2><p className="nf-sub">Server configuration lives in backend environment (DATABASE_URL, REDIS_URL, FRONTEND_ORIGINS). Changes require a backend restart.</p>
        </section>
      </div>
    </div>
  </div>;
}
