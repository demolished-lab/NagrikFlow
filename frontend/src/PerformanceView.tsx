import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from './api';
import { snapshot, type PerformanceSnapshot } from './performance';

type ServerMetric = { hits: number; errors: number; avg_ms: number };

function ms(value: number) {
  return value ? `${value} ms` : '—';
}

function time(value: number) {
  return value ? new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
}

export default function PerformanceView() {
  const [client, setClient] = useState<PerformanceSnapshot>(() => snapshot());
  const [server, setServer] = useState<Record<string, ServerMetric>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshedAt, setRefreshedAt] = useState(0);

  const load = useCallback(async () => {
    setClient(snapshot());
    try {
      const data = await api.adminMetrics();
      setServer(data && typeof data === 'object' ? data : {});
      setError('');
    } catch (reason: any) {
      setError(String(reason?.message || reason));
    } finally {
      setLoading(false);
      setRefreshedAt(Date.now());
    }
  }, []);

  useEffect(() => {
    const update = () => setClient(snapshot());
    window.addEventListener('civic:performance-updated', update);
    void load();
    const timer = window.setInterval(() => void load(), 10000);
    return () => { window.removeEventListener('civic:performance-updated', update); window.clearInterval(timer); };
  }, [load]);

  const routeRows = useMemo(() => Object.entries(server).sort(([, a], [, b]) => b.hits - a.hits).slice(0, 10), [server]);
  const latestActivity = client.activity.recent[0];

  return <div className="cv-performance-view cv-anim-up">
    <header className="cv-admin-header cv-performance-header">
      <div><span className="cv-eyebrow">ADMIN TOOLS</span><h1>Performance monitoring</h1><p>Track real page speed, API responsiveness, and the latency of source-backed pathway generation.</p></div>
      <div className="cv-performance-actions"><span className="cv-admin-role">LIVE SNAPSHOT</span><button className="cv-admin-recheck" type="button" onClick={() => void load()} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh metrics'}</button></div>
    </header>
    {error && <div className="cv-admin-notice is-error" role="alert">Server metrics unavailable: {error}</div>}
    <div className="cv-performance-grid" aria-label="Performance summary">
      <MetricCard label="Page load" value={ms(client.navigation.loadMs)} detail={`DOM ready ${ms(client.navigation.domContentLoadedMs)}`} tone="blue" />
      <MetricCard label="API average" value={ms(client.api.avgMs)} detail={`${client.api.count} calls · p95 ${ms(client.api.p95Ms)}`} tone="green" />
      <MetricCard label="Pathway activity" value={ms(latestActivity?.durationMs || client.activity.avgMs)} detail={latestActivity ? `${latestActivity.status} · ${time(latestActivity.at)}` : 'No pathway build recorded yet'} tone="amber" />
      <MetricCard label="Client errors" value={String(client.api.errors)} detail="Network or non-2xx responses" tone={client.api.errors ? 'red' : 'green'} />
    </div>
    <div className="cv-performance-columns">
      <section className="cv-performance-panel" aria-labelledby="client-performance-heading">
        <div className="cv-admin-section-head"><div><h2 id="client-performance-heading">Frontend timings</h2><p>Measured in this browser session. Values update after every API call.</p></div><span className="cv-performance-updated">Updated {time(refreshedAt)}</span></div>
        <div className="cv-performance-detail-grid">
          <Detail label="Response start" value={ms(client.navigation.responseMs)} />
          <Detail label="Transfer size" value={client.navigation.transferSize ? `${Math.round(client.navigation.transferSize / 1024)} KB` : '—'} />
          <Detail label="API p95" value={ms(client.api.p95Ms)} />
          <Detail label="Activity p95" value={ms(client.activity.p95Ms)} />
        </div>
        <h3 className="cv-performance-subheading">Recent API calls</h3>
        {client.api.recent.length === 0 ? <p className="cv-muted">No API calls recorded yet.</p> : <div className="cv-performance-table-wrap"><table className="cv-performance-table"><thead><tr><th>Endpoint</th><th>Time</th><th>Status</th><th>When</th></tr></thead><tbody>{client.api.recent.map((item, index) => <tr key={`${item.at}-${index}`}><td>{item.path}</td><td>{ms(item.durationMs)}</td><td><span className={`cv-perf-status ${item.ok ? 'is-ok' : 'is-error'}`}>{item.status || 'network error'}</span></td><td>{time(item.at)}</td></tr>)}</tbody></table></div>}
      </section>
      <section className="cv-performance-panel" aria-labelledby="server-performance-heading">
        <div className="cv-admin-section-head"><div><h2 id="server-performance-heading">Backend route health</h2><p>In-memory request metrics from the live FastAPI process.</p></div><span className="cv-performance-live-dot">● Live</span></div>
        {routeRows.length === 0 ? <p className="cv-muted">No server requests recorded yet.</p> : <div className="cv-performance-table-wrap"><table className="cv-performance-table"><thead><tr><th>Route</th><th>Hits</th><th>Errors</th><th>Avg</th></tr></thead><tbody>{routeRows.map(([route, metric]) => <tr key={route}><td>{route}</td><td>{metric.hits}</td><td className={metric.errors ? 'cv-perf-number-error' : ''}>{metric.errors}</td><td>{ms(metric.avg_ms)}</td></tr>)}</tbody></table></div>}
      </section>
    </div>
  </div>;
}

function MetricCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: string }) {
  return <article className={`cv-performance-card is-${tone}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div className="cv-performance-detail"><span>{label}</span><strong>{value}</strong></div>;
}
