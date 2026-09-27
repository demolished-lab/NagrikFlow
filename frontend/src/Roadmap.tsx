import React, { useCallback, useEffect, useMemo, useState } from 'react';
import ReactFlow, { Background, Controls, Handle, MarkerType, MiniMap, Position, type Edge, type Node } from 'reactflow';
import 'reactflow/dist/style.css';
import * as dagre from 'dagre';
import { api } from './api';
import type { CivicSource } from './types';

type GNode = { id: string; type: string; title: string; detail?: string; url?: string; link?: string; fee?: string };
type Status = 'ready' | 'action' | 'unlocked' | 'verified';
type Filters = { node_type: string; status: string; q: string };
type MapPayload = {
  slug: string;
  graph: { nodes: GNode[]; edges: string[][] };
  filters?: { types?: string[]; statuses?: string[]; total?: number };
  sources?: CivicSource[];
  title?: string;
  city?: string;
  state?: string;
  service_type?: string;
  verified?: boolean;
  edge_sources?: Record<string, string>;
};

type Props = { slug: string; onBack: () => void };

const STATUS_CONFIG: Record<Status, { color: string; bg: string; badge: string; icon: string }> = {
  ready: { color: '#254f74', bg: '#eef4f8', badge: 'Up next', icon: '○' },
  action: { color: '#936300', bg: '#fff6d7', badge: 'Action needed', icon: '!' },
  unlocked: { color: '#087b5b', bg: '#e7f7ef', badge: 'Unlocked', icon: '↗' },
  verified: { color: '#087b5b', bg: '#dff5e9', badge: 'Complete', icon: '✓' },
};

function sourceUrl(source: CivicSource): string {
  return typeof source === 'string' ? source : source?.url || '';
}

function sourceOk(source: CivicSource): boolean {
  return typeof source === 'string' || source.ok !== false;
}

function sourceName(source: CivicSource): string {
  const url = sourceUrl(source);
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return url || 'Government source'; }
}

function CivicNode({ data }: { data: { title: string; status: Status; index: number; onSelect: () => void } }) {
  const cfg = STATUS_CONFIG[data.status];
  return <div className={`cv-flow-node cv-flow-node-${data.status}`} onClick={data.onSelect} role="button" tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); data.onSelect(); } }}>
    <Handle type="target" position={Position.Left} />
    <div className="cv-flow-node-top"><span className="cv-step-number">{data.index + 1}</span><span className="cv-flow-type">{cfg.badge}</span><span className="cv-flow-icon">{cfg.icon}</span></div>
    <strong>{data.title}</strong>
    <span className="cv-flow-status" style={{ color: cfg.color, background: cfg.bg }}>{cfg.badge}</span>
    <Handle type="source" position={Position.Right} />
  </div>;
}

const nodeTypes = { civic: CivicNode };

export default function Roadmap({ slug, onBack }: Props) {
  const [payload, setPayload] = useState<MapPayload | null>(null);
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<GNode | null>(null);
  const [filters, setFilters] = useState<Filters>({ node_type: '', status: '', q: '' });
  const [view, setView] = useState<'map' | 'list'>('list');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setFilters({ node_type: '', status: '', q: '' });
    setSelected(null);
    setPayload(null);
  }, [slug]);

  const loadMap = useCallback(async () => {
    if (!slug) {
      setErr('No pathway was selected. Return to My pathways and choose one.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr('');
    try {
      const [map, progress] = await Promise.all([api.map(slug, filters), api.progress(slug)]);
      setPayload(map);
      setCompleted(new Set<string>(progress.steps || []));
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [slug, filters]);

  useEffect(() => { void loadMap(); }, [loadMap]);

  const getStatus = useCallback((node: GNode): Status => {
    if (completed.has(node.id)) return 'verified';
    if (node.type === 'action') return 'action';
    if (node.type === 'unlocked') return 'unlocked';
    return 'ready';
  }, [completed]);

  const markDone = async (node: GNode) => {
    if (!payload?.verified) return;
    try {
      await api.done(slug, node.id);
      setCompleted((previous) => new Set([...previous, node.id]));
      setSelected((previous) => previous?.id === node.id ? node : previous);
    } catch (e: any) {
      setErr(String(e.message || e));
    }
  };

  const flowNodes = useMemo<Node[]>(() => {
    if (!payload) return [];
    const graph = payload.graph;
    const base: Node[] = graph.nodes.map((node, index) => ({
      id: node.id,
      type: 'civic',
      position: { x: 0, y: 0 },
      data: { title: node.title, status: getStatus(node), index, onSelect: () => setSelected(node) },
    }));
    // dagre layered layout (left→right follows step order); grid fallback
    try {
      const flow = new dagre.graphlib.Graph();
      flow.setDefaultEdgeLabel(() => ({}));
      flow.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 90, marginx: 20, marginy: 20 });
      const ids = new Set(graph.nodes.map((node) => node.id));
      base.forEach((node) => flow.setNode(node.id, { width: 250, height: 120 }));
      (graph.edges || []).forEach(([source, target]) => {
        if (source !== target && ids.has(source) && ids.has(target)) flow.setEdge(source, target);
      });
      dagre.layout(flow);
      return base.map((node) => {
        const pos = flow.node(node.id);
        return pos ? { ...node, position: { x: pos.x - 125, y: pos.y - 60 } } : node;
      });
    } catch {
      return base.map((node, index) => ({
        ...node,
        position: { x: (index % 3) * 270, y: Math.floor(index / 3) * 170 },
      }));
    }
  }, [payload, getStatus]);

  const flowEdges = useMemo<Edge[]>(() => (payload?.graph.edges || []).map(([source, target]) => ({
    id: `${source}-${target}`, source, target,
    style: { stroke: '#187b69', strokeWidth: 2 },
    markerEnd: { type: MarkerType.ArrowClosed, color: '#187b69' },
  })), [payload]);
  const updateFilter = (key: keyof Filters, value: string) => setFilters((previous) => ({ ...previous, [key]: value }));
  const resetFilters = () => setFilters({ node_type: '', status: '', q: '' });

  if (loading && !payload) return <div className="cv-page-state" role="status">Loading your pathway…</div>;
  if (!payload) return <div className="cv-page-state"><div className="cv-api-error" role="alert">{err || 'This pathway could not be loaded.'}</div><button className="cv-btn cv-btn-ghost" onClick={onBack}>← Back to My pathways</button><button className="cv-btn cv-btn-indigo" onClick={() => void loadMap()}>Try again</button></div>;

  const location = [payload.city, payload.state].filter(Boolean).join(', ');
  const context = [payload.service_type, location].filter(Boolean).join(' · ');

  return <div className="cv-path-view cv-roadmap-view cv-anim-up">
    <section className="cv-roadmap-toolbar cv-roadmap-panel">
      <button className="cv-back-link" onClick={onBack}>← My pathways</button>
      <div className="cv-roadmap-toolbar-head">
        <div><span className="cv-eyebrow">{payload.verified ? 'REVIEWED CIVIC PATHWAY' : 'DRAFT PATHWAY'}</span><h1>{payload.title || 'Your procedure path'}</h1><p>{context ? `${context} · ` : ''}{payload.filters?.total ?? payload.graph.nodes.length} steps</p></div>
        <div className="cv-view-toggle" role="group" aria-label="Pathway display mode"><button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>☷ List</button><button className={view === 'map' ? 'active' : ''} onClick={() => setView('map')}>⌘ Map</button></div>
      </div>
      {!payload.verified && <div className="cv-review-banner" role="note"><span aria-hidden="true">i</span><p><strong>This pathway is awaiting source review.</strong> You can inspect its steps and official links; progress tracking will be available after an administrator approves it.</p></div>}
      {payload.verified && <p className="cv-roadmap-progress-note">Your progress is saved to your account when you mark a step complete.</p>}
      <div className="cv-filter-row"><label className="cv-filter-search"><span aria-hidden="true">⌕</span><input value={filters.q} onChange={(event) => updateFilter('q', event.target.value)} placeholder="Search steps, documents or fees" aria-label="Search pathway steps" /></label><select value={filters.node_type} onChange={(event) => updateFilter('node_type', event.target.value)} aria-label="Filter by step type"><option value="">All step types</option>{(payload.filters?.types || []).map((type) => <option key={type} value={type}>{type.replace(/_/g, ' ')}</option>)}</select><select value={filters.status} onChange={(event) => updateFilter('status', event.target.value)} aria-label="Filter by status"><option value="">All statuses</option>{(payload.filters?.statuses || []).map((status) => <option key={status} value={status}>{STATUS_CONFIG[status as Status]?.badge || status}</option>)}</select><button className="cv-filter-reset" onClick={resetFilters}>Reset</button></div>
      <div className="cv-filter-summary" aria-live="polite">{loading ? 'Refreshing steps…' : `${payload.graph.nodes.length} visible steps`}{(filters.q || filters.node_type || filters.status) && <span> · Filters are synced with the API</span>}</div>
    </section>

    {err && <div className="cv-api-error" role="alert">{err}</div>}

    {view === 'map' ? <section className="cv-interactive-map" aria-label="Interactive civic procedure map"><ReactFlow nodes={flowNodes} edges={flowEdges} nodeTypes={nodeTypes} fitView minZoom={0.35} maxZoom={1.4}><MiniMap nodeColor={(node) => STATUS_CONFIG[(node.data?.status || 'ready') as Status]?.color || '#187b69'} /><Controls /><Background color="#dce8e3" gap={22} /></ReactFlow>{flowNodes.length === 0 && <div className="cv-map-empty">No steps match these filters. <button onClick={resetFilters}>Clear filters</button></div>}</section> : <section className="cv-path-timeline cv-filtered-list" aria-label="Pathway steps">{payload.graph.nodes.map((node, index) => { const status = getStatus(node); const cfg = STATUS_CONFIG[status]; return <article className="cv-filtered-step" key={node.id}><div className="cv-step-header"><span className="cv-step-badge" style={{ background: cfg.bg, color: cfg.color }}>{cfg.icon} {cfg.badge}</span><span className="cv-step-step">Step {index + 1}</span></div><h2 className="cv-step-title">{node.title}</h2><p>{node.detail || 'Step in this civic procedure.'}</p>{node.fee && <small>Fee: {node.fee}</small>}<div className="cv-filtered-step-actions">{node.link && node.link !== node.url && <a href={node.link} target="_blank" rel="noreferrer">Apply / open form ↗</a>}{node.url && <a href={node.url} target="_blank" rel="noreferrer">Official source ↗</a>}{payload.verified && status !== 'verified' && <button className="cv-btn cv-btn-sm cv-btn-ghost" onClick={() => void markDone(node)}>Mark complete</button>}</div></article>; })}{payload.graph.nodes.length === 0 && <div className="cv-map-empty">No steps match these filters. <button onClick={resetFilters}>Clear filters</button></div>}</section>}

    <section className="cv-sources-section cv-map-sources cv-roadmap-panel"><div className="cv-sources-title-row"><div><span className="cv-eyebrow">SOURCE LINKS</span><h2>Official sources for this pathway</h2></div><span className="cv-source-count">{payload.sources?.length || 0} source{payload.sources?.length === 1 ? '' : 's'}</span></div>
      {!!payload.sources?.length ? <div className="cv-roadmap-source-list">{payload.sources.map((source, index) => { const url = sourceUrl(source); const okay = sourceOk(source); return <a className="cv-roadmap-source" key={`${url}-${index}`} href={url || undefined} target="_blank" rel="noreferrer"><span className={`cv-source-status-dot ${okay ? 'is-ok' : 'is-error'}`}>{okay ? '✓' : '!'}</span><span><strong>{sourceName(source)}</strong><small>{okay ? 'Fetched for this pathway' : 'Source could not be fetched'}</small></span><span aria-hidden="true">↗</span></a>; })}</div> : <p className="cv-muted">No source links were saved with this pathway.</p>}
      <p className="cv-source-disclaimer">Always confirm current eligibility, fees, documents and deadlines on the official site before applying.</p>
    </section>

    {selected && <aside className="cv-detail-panel cv-map-detail" aria-label="Step details"><button onClick={() => setSelected(null)} className="cv-close-btn" aria-label="Close step details">×</button><span className={`cv-status cv-status-${getStatus(selected)}`}>{STATUS_CONFIG[getStatus(selected)].badge}</span><h2>{selected.title}</h2><p>{selected.detail || 'No additional details are available for this step.'}</p>{selected.fee && <p><b>Fee:</b> {selected.fee}</p>}{selected.link && selected.link !== selected.url && <a href={selected.link} target="_blank" rel="noreferrer">Open application / form ↗</a>}{selected.url && <a href={selected.url} target="_blank" rel="noreferrer">Open official site ↗</a>}{payload.edge_sources && (() => { const key = Object.keys(payload.edge_sources).find((candidate) => candidate.includes(selected.id)); return key ? <p><small>Source: {payload.edge_sources[key]}</small></p> : null; })()}{payload.verified && getStatus(selected) !== 'verified' && <button className="cv-btn cv-btn-indigo" onClick={() => void markDone(selected)}>✓ Mark complete</button>}</aside>}
  </div>;
}
