import React, { useEffect, useState } from 'react';
import { STR, lang } from './i18n';

const H = (t: string | null): Record<string, string> => ({
  'Content-Type': 'application/json',
  ...(t ? { Authorization: `Bearer ${t}` } : {}),
});

export default function Admin() {
  const t = STR[lang()];
  const tok = localStorage.getItem('civic_token');
  const [maps, setMaps] = useState<any[]>([]);
  const [err, setErr] = useState('');
  const [form, setForm] = useState({ task: '', slug: '', urls: '' });
  const [building, setBuilding] = useState(false);

  const load = () =>
    fetch('/api/admin/maps', { headers: H(tok) })
      .then(async (r) => (r.ok ? setMaps(await r.json()) : setErr('Admin only (403). Is your account admin?')))
      .catch((e) => setErr(String(e)));
  useEffect(() => { load(); }, []);

  const verify = async (slug: string, v: boolean) => {
    await fetch(`/api/admin/maps/${slug}/verify`, {
      method: 'POST', headers: H(tok), body: JSON.stringify({ verified: v }),
    });
    load();
  };

  const [checking, setChecking] = useState('');

  const pollJob = async (id: number) => {
    for (let i = 0; i < 100; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      const j = await fetch(`/api/admin/jobs/${id}`, { headers: H(tok) }).then((x) => x.json());
      if (j.status === 'done' || j.status === 'failed') return j;
    }
    return { status: 'timeout' };
  };

  const recheck = async (slug: string) => {
    setChecking(slug || 'all');
    setErr('');
    try {
      const { job_id } = await fetch('/api/admin/jobs/recheck', {
        method: 'POST', headers: H(tok), body: JSON.stringify({ slug }),
      }).then((x) => x.json());
      const j = await pollJob(job_id);
      const changed = ((j.result || {}).maps || []).filter((m: any) => m.changed);
      alert(j.status === 'failed' ? `Job failed: ${JSON.stringify(j.result)}`
        : changed.length ? `CHANGED: ${changed.map((m: any) => m.slug).join(', ')} — verification revoked.`
        : 'No changes. All maps still verified.');
      load();
    } catch (e: any) { setErr(String(e.message || e)); }
    setChecking('');
  };

  const build = async () => {
    setBuilding(true);
    setErr('');
    try {
      const { job_id } = await fetch('/api/admin/jobs/build', {
        method: 'POST', headers: H(tok),
        body: JSON.stringify({ ...form, urls: form.urls.split('\n').map((s) => s.trim()).filter(Boolean) }),
      }).then(async (r) => {
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail || 'build failed');
        return j;
      });
      const j = await pollJob(job_id);
      if (j.status === 'failed') throw new Error(JSON.stringify(j.result));
      alert(`Built ${j.result.slug}: ${j.result.steps} steps (UNVERIFIED — review then stamp).`);
      load();
    } catch (e: any) { setErr(String(e.message || e)); }
    setBuilding(false);
  };

  return (
    <div style={{ display: 'grid', gap: 12, maxWidth: 760 }}>
      {err && <p style={{ color: 'red' }}>{err}</p>}
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        <h3>🗂️ {t.admTitle}</h3>
        <button onClick={() => recheck('')} disabled={!!checking}>
          {checking === 'all' ? 'Checking all…' : `🌙 ${t.admRecheckAll}`}
        </button>
        {maps.map((m) => (
          <div key={m.slug} style={{ borderBottom: '1px solid #eee', padding: '6px 0' }}>
            <b>{m.title}</b> <small>({m.slug}, {m.steps} steps)</small><br />
            <small>Status: {m.verified ? `✅ verified ${m.verified}` : '⚠️ UNVERIFIED'}</small><br />
            <small>hash: {m.hash || '—'} · checked: {m.checked || 'never'}</small><br />
            <small>sources: {(m.sources || []).map((s: any) => typeof s === 'string' ? s : s.url).join(', ')}</small><br />
            <button onClick={() => verify(m.slug, !m.verified)}>
              {m.verified ? t.admUnverify : t.admVerify}
            </button>{' '}
            <button onClick={() => recheck(m.slug)} disabled={!!checking}>
              {checking === m.slug ? 'Checking…' : t.admRecheck}
            </button>
          </div>
        ))}
      </div>
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        <h3>🏗️ {t.admBuild}</h3>
        <input placeholder="task, e.g. Apply for birth certificate" value={form.task}
          onChange={(e) => setForm({ ...form, task: e.target.value })}
          style={{ display: 'block', width: '100%', margin: '6px 0', padding: 8 }} />
        <input placeholder="slug, e.g. birth-cert" value={form.slug}
          onChange={(e) => setForm({ ...form, slug: e.target.value })}
          style={{ display: 'block', width: '100%', margin: '6px 0', padding: 8 }} />
        <textarea placeholder="official .gov URLs, one per line" value={form.urls} rows={3}
          onChange={(e) => setForm({ ...form, urls: e.target.value })}
          style={{ display: 'block', width: '100%', margin: '6px 0', padding: 8 }} />
        <button onClick={build} disabled={building}>{building ? 'Building (minutes)…' : 'Build map'}</button>
      </div>
    </div>
  );
}
