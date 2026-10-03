import React, { useMemo, useState } from 'react';
import { SERVICE_CATALOG, type CatalogService } from './nf-kit';

type Props = {
  authed: boolean;
  onRequireAuth: (task: string) => void;
  onBuildService: (service: CatalogService) => void;
};

const TABS = ['All', 'Business', 'Licences', 'Certificates', 'Other'] as const;

function queryFromHash(): string {
  const hash = window.location.hash;
  const q = hash.indexOf('?');
  if (q < 0) return '';
  return new URLSearchParams(hash.slice(q + 1)).get('q') || '';
}

export default function SearchView({ authed, onRequireAuth, onBuildService }: Props) {
  const [tab, setTab] = useState<(typeof TABS)[number]>('All');
  const [location, setLocation] = useState('Mumbai, Maharashtra');
  const [serviceType, setServiceType] = useState('Small Business');
  const [department, setDepartment] = useState('All departments');
  const [sort, setSort] = useState('Relevance');
  const initialQuery = useMemo(queryFromHash, []);
  const [query, setQuery] = useState(initialQuery);

  const departments = useMemo(() => ['All departments', ...Array.from(new Set(SERVICE_CATALOG.map((s) => s.department)))], []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = SERVICE_CATALOG.filter((s) => {
      if (tab !== 'All') {
        if (tab === 'Business') return s.category === 'Business' || s.tags.includes('Business');
        return s.category === tab;
      }
      return true;
    });
    if (q) list = list.filter((s) => `${s.title} ${s.description} ${s.department} ${s.tags.join(' ')}`.toLowerCase().includes(q));
    if (department !== 'All departments') list = list.filter((s) => s.department === department);
    if (sort === 'Name A–Z') list = [...list].sort((a, b) => a.title.localeCompare(b.title));
    return list;
  }, [tab, query, department, sort]);

  const counts = useMemo(() => ({
    All: SERVICE_CATALOG.length,
    Business: SERVICE_CATALOG.filter((s) => s.category === 'Business' || s.tags.includes('Business')).length,
    Licences: SERVICE_CATALOG.filter((s) => s.category === 'Licences').length,
    Certificates: SERVICE_CATALOG.filter((s) => s.category === 'Certificates').length,
    Other: SERVICE_CATALOG.filter((s) => s.category === 'Other').length,
  }), []);

  const viewPath = (service: CatalogService) => {
    if (!authed) onRequireAuth(service.task);
    else onBuildService(service);
  };

  return <div>
    <div className="nf-crumb"><button onClick={() => { window.location.hash = ''; }}>Home</button> · <b>Search Results</b></div>
    <div className="nf-page-head">
      <span className="nf-eyebrow">Service discovery</span>
      <h1>We found {results.length} result{results.length === 1 ? '' : 's'}{query.trim() ? <> for &ldquo;{query.trim()}&rdquo;</> : null} in {location}</h1>
    </div>
    <div className="nf-task-main" style={{ marginBottom: 6 }}>
      <span className="nf-q" aria-hidden="true">⌕</span>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search services, departments, licences…" aria-label="Search services" />
    </div>
    <div className="nf-tabs" role="tablist" aria-label="Service categories">
      {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'is-active' : ''} onClick={() => setTab(t)}>{t} ({counts[t]})</button>)}
    </div>
    <div className="nf-search-layout">
      <aside className="nf-card nf-filters" aria-label="Search filters">
        <h3>Refine results</h3>
        <div className="nf-field"><label htmlFor="sv-loc">Location</label><input id="sv-loc" value={location} onChange={(e) => setLocation(e.target.value)} /></div>
        <div className="nf-field"><label htmlFor="sv-type">Service Type</label><input id="sv-type" value={serviceType} onChange={(e) => setServiceType(e.target.value)} /></div>
        <div className="nf-field"><label htmlFor="sv-dept">Department</label><select id="sv-dept" value={department} onChange={(e) => setDepartment(e.target.value)}>{departments.map((d) => <option key={d} value={d}>{d}</option>)}</select></div>
        <div className="nf-field"><label htmlFor="sv-sort">Sort By</label><select id="sv-sort" value={sort} onChange={(e) => setSort(e.target.value)}><option>Relevance</option><option>Name A–Z</option></select></div>
      </aside>
      <div>
        {results.length === 0 && <div className="nf-card" style={{ padding: 24 }}><strong>No services match.</strong><p className="nf-muted" style={{ fontSize: 13 }}>Try a different keyword or clear the department filter.</p></div>}
        {results.map((s) => <article className="nf-card nf-result-card" key={s.id}>
          <span className="nf-result-icon" style={{ background: s.color }} aria-hidden="true">{s.icon}</span>
          <div className="nf-result-body">
            <h3>{s.title}</h3>
            <p className="nf-dept">{s.department}</p>
            <p>{s.description}</p>
            <div className="nf-tag-row">{s.tags.map((t) => <span className="nf-tag" key={t}>{t}</span>)}</div>
          </div>
          <div className="nf-result-side">
            <button className="nf-btn nf-btn-outline nf-btn-sm" onClick={() => viewPath(s)} aria-label={`View path for ${s.title}`}>View Path →</button>
          </div>
        </article>)}
      </div>
    </div>
  </div>;
}
