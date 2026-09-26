import React, { useCallback, useEffect, useMemo, useState } from 'react';
import ReactFlow, { Background, Controls, Handle, MiniMap, Position, type Edge, type Node } from 'reactflow';
import 'reactflow/dist/style.css';
import { api } from './api';
import { STR, lang } from './i18n';

type GNode = { id: string; type: string; title: string; detail?: string; url?: string; fee?: string };
type Status = 'ready' | 'action' | 'unlocked' | 'verified';
type Filters = { node_type: string; status: string; q: string };
type MapPayload = { graph: { nodes: GNode[]; edges: string[][] }; filters?: { types?: string[]; statuses?: string[]; total?: number }; sources?: string[]; title?: string; city?: string };

const STATUS_CONFIG: Record<Status, { color: string; bg: string; badge: string; icon: string }> = {
  ready: { color: '#1e3a8a', bg: '#eff6ff', badge: 'Ready', icon: '◌' },
  action: { color: '#936300', bg: '#fff7d6', badge: 'Needs Action', icon: '!' },
  unlocked: { color: '#087b5b', bg: '#e0f8ed', badge: 'Unlocked', icon: '↗' },
  verified: { color: '#087b5b', bg: '#d9f7e9', badge: 'Verified', icon: '✓' },
};

function CivicNode({ data }: { data: { title: string; status: Status; index: number; onSelect: () => void } }) {
  const cfg = STATUS_CONFIG[data.status];
  return <div className={`cv-flow-node cv-flow-node-${data.status}`} onClick={data.onSelect} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && data.onSelect()}>
    <Handle type="target" position={Position.Left} />
    <div className="cv-flow-node-top"><span className="cv-step-number">{data.index + 1}</span><span className="cv-flow-type">{cfg.badge}</span><span className="cv-flow-icon">{cfg.icon}</span></div>
    <strong>{data.title}</strong>
    <span className="cv-flow-status" style={{ color: cfg.color, background: cfg.bg }}>{cfg.badge}</span>
    <Handle type="source" position={Position.Right} />
  </div>;
}

const nodeTypes = { civic: CivicNode };

export default function Roadmap({ slug }: { slug: string }) {
  const t = STR[lang()];
  const [payload, setPayload] = useState<MapPayload | null>(null);
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<GNode | null>(null);
  const [filters, setFilters] = useState<Filters>({ node_type: '', status: '', q: '' });
  const [view, setView] = useState<'map' | 'list'>('map');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(true);

  const loadMap = useCallback(async () => {
    setLoading(true);
    setErr('');
    try {
      const [map, progress] = await Promise.all([api.map(slug, filters), api.progress(slug)]);
      setPayload(map);
      setCompleted(new Set(progress.steps || []));
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [slug, filters]);

  useEffect(() => { loadMap(); }, [loadMap]);

  const getStatus = useCallback((node: GNode): Status => {
    if (completed.has(node.id)) return 'verified';
    if (node.type === 'action') return 'action';
    if (node.type === 'unlocked') return 'unlocked';
    return 'ready';
  }, [completed]);

  const markDone = async (node: GNode) => {
    try {
      await api.done(slug, node.id);
      setCompleted((prev) => new Set([...prev, node.id]));
      setSelected((prev) => prev?.id === node.id ? node : prev);
    } catch (e: any) {
      setErr(String(e.message || e));
    }
  };

  const flowNodes = useMemo<Node[]>(() => {
    if (!payload) return [];
    return payload.graph.nodes.map((node, index) => ({
      id: node.id,
      type: 'civic',
      position: { x: (index % 3) * 270, y: Math.floor(index / 3) * 170 },
      data: { title: node.title, status: getStatus(node), index, onSelect: () => setSelected(node) },
    }));
  }, [payload, getStatus]);

  const flowEdges = useMemo<Edge[]>(() => (payload?.graph.edges || []).map(([source, target]) => ({ id: `${source}-${target}`, source, target, animated: false, style: { stroke: '#0871cf', strokeWidth: 2 } })), [payload]);
  const updateFilter = (key: keyof Filters, value: string) => setFilters((prev) => ({ ...prev, [key]: value }));
  const resetFilters = () => setFilters({ node_type: '', status: '', q: '' });

  if (loading && !payload) return <p aria-live="polite">{t.loading || 'Loading your verified path…'}</p>;
  if (err && !payload) return <p role="alert" className="cv-api-error">{err}</p>;
  if (!payload) return null;

  return <div className="cv-path-view cv-roadmap-view">
    <section className="cv-path-input cv-roadmap-toolbar">
      <div className="cv-roadmap-toolbar-head"><div><span className="cv-eyebrow">VERIFIED CIVIC MAP</span><h1>{payload.title || t.pathTitle || 'Your Procedure Path'}</h1><p>{payload.city ? `${payload.city} · ` : ''}{payload.filters?.total || payload.graph.nodes.length} steps from verified sources</p></div><div className="cv-view-toggle"><button className={view === 'map' ? 'active' : ''} onClick={() => setView('map')}>⌘ Map</button><button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>☷ List</button></div></div>
      <div className="cv-filter-row"><label className="cv-filter-search">⌕<input value={filters.q} onChange={(e) => updateFilter('q', e.target.value)} placeholder="Search steps, documents or fees" /></label><select value={filters.node_type} onChange={(e) => updateFilter('node_type', e.target.value)} aria-label="Filter by step type"><option value="">All step types</option>{(payload.filters?.types || []).map((type) => <option key={type} value={type}>{type.replace(/_/g, ' ')}</option>)}</select><select value={filters.status} onChange={(e) => updateFilter('status', e.target.value)} aria-label="Filter by status"><option value="">All statuses</option>{(payload.filters?.statuses || []).map((status) => <option key={status} value={status}>{STATUS_CONFIG[status as Status]?.badge || status}</option>)}</select><button className="cv-filter-reset" onClick={resetFilters}>Reset</button></div>
      <div className="cv-filter-summary">{loading ? 'Refreshing map…' : `${payload.graph.nodes.length} visible steps`} {filters.q || filters.node_type || filters.status ? <span> · Filters are synced with the API</span> : null}</div>
    </section>

    {view === 'map' ? <section className="cv-interactive-map" aria-label="Interactive civic procedure map"><ReactFlow nodes={flowNodes} edges={flowEdges} nodeTypes={nodeTypes} fitView minZoom={0.4} maxZoom={1.4}><MiniMap nodeColor={(node) => STATUS_CONFIG[(node.data?.status || 'ready') as Status]?.color || '#0871cf'} /><Controls /><Background color="#d9e6f2" gap={20} /></ReactFlow>{flowNodes.length === 0 && <div className="cv-map-empty">No steps match these filters. <button onClick={resetFilters}>Clear filters</button></div>}</section> : <section className="cv-path-timeline cv-filtered-list">{payload.graph.nodes.map((node, index) => { const status = getStatus(node); const cfg = STATUS_CONFIG[status]; return <article className="cv-step-card cv-filtered-step" key={node.id} onClick={() => setSelected(node)}><div className="cv-step-header"><span className="cv-step-badge" style={{ background: cfg.bg, color: cfg.color }}>{cfg.icon} {cfg.badge}</span><span className="cv-step-step">Step {index + 1}</span></div><h3 className="cv-step-title">{node.title}</h3><p>{node.detail || 'Verified dependency in your civic workflow.'}</p>{node.fee && <small>Fee: {node.fee}</small>}<div className="cv-filtered-step-actions">{node.url && <a href={node.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>Official source ↗</a>}{status !== 'verified' && <button className="cv-btn cv-btn-sm cv-btn-indigo" onClick={(e) => { e.stopPropagation(); markDone(node); }}>✓ Mark Done</button>}</div></article>; })}</section>}

    <section className="cv-sources-section cv-map-sources"><h4>⌕ {t.sourcesChecked || 'Sources Checked'}</h4><div className="cv-source-chips">{(payload.sources || []).map((source) => <div key={source} className="cv-source-chip cv-verified"><span>✓</span> {new URL(source).hostname.replace(/^www\./, '')}</div>)}</div></section>
    {selected && <aside className="cv-detail-panel cv-map-detail"><button onClick={() => setSelected(null)} className="cv-close-btn">×</button><span className={`cv-status cv-status-${getStatus(selected)}`}>{STATUS_CONFIG[getStatus(selected)].badge}</span><h2>{selected.title}</h2><p>{selected.detail || t.noDetail || 'No additional details available for this step.'}</p>{selected.fee && <p><b>{t.rmFee || 'Fee'}:</b> {selected.fee}</p>}{selected.url && <a href={selected.url} target="_blank" rel="noreferrer">{t.rmOpen || 'Open official site'} ↗</a>}{getStatus(selected) !== 'verified' && <button className="cv-btn cv-btn-indigo" onClick={() => markDone(selected)}>✓ {t.rmDone || 'Mark done'}</button>}</aside>}
  </div>;
}
