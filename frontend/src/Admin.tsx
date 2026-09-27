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

  return <div className="cv-admin-view cv-anim-up">
    <header className="cv-admin-header">
      <div><span className="cv-eyebrow">ADMIN WORKSPACE</span><h1>Pathway verification desk</h1><p>Review source-backed civic maps, approve verified workflows, and recheck changes from official websites.</p></div>
      <span className="cv-admin-role">ADMIN ONLY</span>
    </header>

    {err && <div className="cv-admin-notice is-error" role="alert">{err}<button type="button" onClick={() => setErr('')} aria-label="Dismiss error">×</button></div>}
    {notice && <div className="cv-admin-notice" role="status">{notice}<button type="button" onClick={() => setNotice('')} aria-label="Dismiss message">×</button></div>}

    <section className="cv-admin-panel" aria-labelledby="admin-review-heading">
      <div className="cv-admin-section-head">
        <div><h2 id="admin-review-heading">Pathway review</h2><p>Review source freshness before marking a map ready for citizen progress tracking.</p></div>
        <button className="cv-admin-recheck" type="button" onClick={() => void recheck('')} disabled={Boolean(checking)}>{checking === 'all' ? 'Checking all sources…' : t.admRecheckAll}</button>
      </div>
      {loading ? <p className="cv-muted" role="status">Loading pathways…</p> : maps.length === 0 ? <div className="cv-admin-empty">No pathway maps are available for review yet.</div> : <div className="cv-admin-list">{maps.map((map) => {
        const sources = (map.sources || []).map((source) => typeof source === 'string' ? source : source?.url || '').filter(Boolean);
        return <article className="cv-admin-map" key={map.slug}>
          <div className="cv-admin-map-main">
            <h3 className="cv-admin-map-title">{map.title}</h3>
            <p className="cv-admin-map-meta"><strong>{map.verified ? 'Reviewed and verified' : 'Awaiting review'}</strong> · {map.slug} · {map.steps || 0} steps</p>
            <p className="cv-admin-map-meta">Content hash: {map.hash || '—'} · Last checked: {map.checked || 'Never'}</p>
            <p className="cv-admin-map-sources"><strong>Official sources:</strong> {sources.length ? sources.join(' · ') : 'No source URLs recorded'}</p>
          </div>
          <div className="cv-admin-map-actions">
            <button type="button" onClick={() => void verify(map.slug, !map.verified)}>{map.verified ? t.admUnverify : t.admVerify}</button>
            <button type="button" onClick={() => void recheck(map.slug)} disabled={Boolean(checking)}>{checking === map.slug ? 'Checking…' : t.admRecheck}</button>
            <button type="button" onClick={() => void toggleSteps(map.slug)}>{editingSlug === map.slug ? 'Close editor' : 'Edit steps'}</button>
          </div>
          {editingSlug === map.slug && <div className="cv-admin-step-editor" style={{ width: '100%' }}>
            <h4>Step editor — {map.title}</h4>
            <p className="cv-muted" style={{ margin: '0 0 8px' }}>Update titles, details, fees and official links. Edits persist until the map is rebuilt from sources.</p>
            {steps.length === 0 ? <p className="cv-muted">This map has no steps yet — add the first one below.</p> : steps.map((step) => draft?.id === step.id
              ? <div className="cv-admin-form" key={step.id} style={{ border: '1px dashed #c9d4d0', borderRadius: 8, padding: 10, marginBottom: 8 }}>
                  <label className="cv-admin-field">Title<input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
                  <div className="cv-admin-form-grid">
                    <label className="cv-admin-field">Type<select value={draft.type} onChange={(event) => setDraft({ ...draft, type: event.target.value })}>{STEP_TYPES.map((kind) => <option key={kind} value={kind}>{kind}</option>)}</select></label>
                    <label className="cv-admin-field">Fee<input value={draft.fee || ''} onChange={(event) => setDraft({ ...draft, fee: event.target.value })} placeholder="e.g. ₹500" /></label>
                  </div>
                  <label className="cv-admin-field">Official source URL<input value={draft.url || ''} onChange={(event) => setDraft({ ...draft, url: event.target.value })} placeholder="https://...gov.in/..." /></label>
                  <label className="cv-admin-field">Application / form link<input value={draft.link || ''} onChange={(event) => setDraft({ ...draft, link: event.target.value })} placeholder="https://...gov.in/form (deep link, optional)" /></label>
                  <label className="cv-admin-field">Detail<textarea value={draft.detail || ''} rows={2} onChange={(event) => setDraft({ ...draft, detail: event.target.value })} /></label>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button type="button" onClick={() => void saveStep(map.slug)} disabled={stepBusy || !draft.title.trim()}>{stepBusy ? 'Saving…' : 'Save step'}</button>
                    <button type="button" onClick={() => setDraft(null)} disabled={stepBusy}>Cancel</button>
                  </div>
                </div>
              : <div className="cv-admin-step-row" key={step.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid #eef2f0' }}>
                  <strong style={{ flex: 1 }}>{step.title}</strong>
                  <small className="cv-muted">{step.type}{step.fee ? ` · ${step.fee}` : ''}</small>
                  <button type="button" onClick={() => setDraft({ ...step })} disabled={stepBusy}>Edit</button>
                  <button type="button" onClick={() => void deleteStep(map.slug, step.id)} disabled={stepBusy}>Delete</button>
                </div>)}
            <div className="cv-admin-form" style={{ marginTop: 10 }}>
              <div className="cv-admin-form-grid">
                <label className="cv-admin-field">New step title<input value={newStep.title} onChange={(event) => setNewStep({ ...newStep, title: event.target.value })} placeholder="e.g. Collect signed declaration" /></label>
                <label className="cv-admin-field">Type<select value={newStep.type} onChange={(event) => setNewStep({ ...newStep, type: event.target.value })}>{STEP_TYPES.map((kind) => <option key={kind} value={kind}>{kind}</option>)}</select></label>
              </div>
              <label className="cv-admin-field">Official source URL<input value={newStep.url} onChange={(event) => setNewStep({ ...newStep, url: event.target.value })} placeholder="https://...gov.in/... (optional)" /></label>
              <label className="cv-admin-field">Application / form link<input value={newStep.link} onChange={(event) => setNewStep({ ...newStep, link: event.target.value })} placeholder="https://...gov.in/form (deep link, optional)" /></label>
              <div><button type="button" onClick={() => void addStep(map.slug)} disabled={stepBusy || !newStep.title.trim()}>{stepBusy ? 'Saving…' : 'Add step'}</button></div>
            </div>
          </div>}
        </article>;
      })}</div>}
    </section>

    <section className="cv-admin-panel" aria-labelledby="admin-build-heading">
      <div className="cv-admin-section-head"><div><h2 id="admin-build-heading">Build a pathway map</h2><p>Start a source-backed map from known official URLs. New maps remain unverified until reviewed.</p></div></div>
      <div className="cv-admin-form">
        <label className="cv-admin-field" htmlFor="admin-task">Civic task<input id="admin-task" value={form.task} placeholder="e.g. Apply for a birth certificate" onChange={(event) => setForm({ ...form, task: event.target.value })}/></label>
        <div className="cv-admin-form-grid">
          <label className="cv-admin-field" htmlFor="admin-slug">Pathway slug<input id="admin-slug" value={form.slug} placeholder="e.g. birth-cert" onChange={(event) => setForm({ ...form, slug: event.target.value })}/></label>
          <label className="cv-admin-field" htmlFor="admin-urls">Official source URLs<textarea id="admin-urls" value={form.urls} rows={3} placeholder="One government URL per line" onChange={(event) => setForm({ ...form, urls: event.target.value })}/></label>
        </div>
        <div><button className="cv-btn cv-btn-indigo" type="button" onClick={() => void build()} disabled={building || !form.task.trim() || !form.slug.trim()}>{building ? 'Building map…' : 'Build map'}</button></div>
      </div>
    </section>
  </div>;
}
