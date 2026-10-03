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
  warnings?: string[];
};

type Props = { slug: string; onBack: () => void };

type PacketGuide = { url: string; title?: string };
type Packet = {
  slug: string;
  title: string;
  generated_at: string;
  steps: { order: number; id: string; title: string; detail?: string; fee?: string; link?: string; prereqs: string[] }[];
  checklist: string[];
  fees: string[];
  guides: PacketGuide[];
  sources: { url: string; ok?: boolean; final_url?: string; tier?: string; guides?: PacketGuide[] }[];
  counts: { steps: number; documents: number; sources: number; guides: number };
  warnings?: string[];
};

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

function nodeColor(status: Status): string {
  if (status === 'verified') return '#2f9e6e';
  if (status === 'action') return '#dd8a0b';
  if (status === 'unlocked') return '#7a5af8';
  return '#2f7fe0';
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
  const [detailId, setDetailId] = useState<string | null>(null);
  const [filters, setFilters] = useState<Filters>({ node_type: '', status: '', q: '' });
  const [view, setView] = useState<'map' | 'list'>('list');
  const [zoom, setZoom] = useState(1);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(true);
  const [packet, setPacket] = useState<Packet | null>(null);
  const [packetErr, setPacketErr] = useState('');
  const [packetBusy, setPacketBusy] = useState(false);
  const [packetNote, setPacketNote] = useState('');

  useEffect(() => {
    setFilters({ node_type: '', status: '', q: '' });
    setSelected(null);
    setDetailId(null);
    setPayload(null);
    setPacket(null);
    setPacketErr('');
    setPacketNote('');
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

  const loadPacket = async () => {
    setPacketBusy(true);
    setPacketErr('');
    setPacketNote('');
    try {
      setPacket(await api.taskPacket(slug));
    } catch (e: any) {
      setPacketErr(String(e.message || e));
    } finally {
      setPacketBusy(false);
    }
  };

  const downloadPacket = async () => {
    setPacketErr('');
    try {
      await api.downloadPacketMd(slug);
    } catch (e: any) {
      setPacketErr(String(e.message || e));
    }
  };

  const sendPacket = async () => {
    setPacketErr('');
    setPacketNote('');
    try {
      const res = await api.deliverPacket(slug);
      setPacketNote(`Sent to Telegram chat ${res.chat_id} (via ${res.via}).`);
    } catch (e: any) {
      setPacketErr(String(e.message || e));
    }
  };

  const flowNodes = useMemo<Node[]>(() => {
    if (!payload) return [];
    const graph = payload.graph;
    const base: Node[] = graph.nodes.map((node, index) => ({
      id: node.id,
      type: 'civic',
      position: { x: 0, y: 0 },
      data: { title: node.title, status: getStatus(node), index, onSelect: () => { setSelected(node); setDetailId(node.id); } },
    }));
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

  if (loading && !payload) return <div className="nf-card" style={{ padding: 24 }} role="status"><p className="nf-muted">Loading your pathway…</p></div>;
  if (!payload) return <div className="nf-card" style={{ padding: 24 }}><div className="nf-error-box" role="alert">{err || 'This pathway could not be loaded.'}</div><div style={{ display: 'flex', gap: 8, marginTop: 12 }}><button className="nf-btn nf-btn-ghost nf-btn-sm" onClick={onBack}>← Back to My pathways</button><button className="nf-btn nf-btn-primary nf-btn-sm" onClick={() => void loadMap()}>Try again</button></div></div>;

  const location = [payload.city, payload.state].filter(Boolean).join(', ');
  const total = payload.filters?.total ?? payload.graph.nodes.length;
  const doneCount = payload.graph.nodes.filter((n) => completed.has(n.id)).length;
  const percent = total ? Math.round((doneCount / total) * 100) : 0;
  const firstSource = (payload.sources || []).map(sourceUrl).find(Boolean) || '';
  const fees = Array.from(new Set(payload.graph.nodes.map((n) => n.fee).filter(Boolean)));
  const nodes = payload.graph.nodes;
  const detailIndex = detailId ? nodes.findIndex((n) => n.id === detailId) : -1;
  const detailNode = detailIndex >= 0 ? nodes[detailIndex] : null;
  const nextNode = detailNode ? nodes[detailIndex + 1] || null : null;
  const docNodes = nodes.filter((n) => ['prereq', 'document'].includes((n.type || '').toLowerCase()));

  return <div>
    <div className="nf-crumb"><button onClick={() => { window.location.hash = ''; }}>Home</button> · <b>{payload.title || 'Roadmap'}</b></div>
    <div className="nf-road-head">
      <div>
        <span className="nf-eyebrow">{payload.verified ? 'REVIEWED CIVIC PATHWAY' : 'DRAFT PATHWAY'}</span>
        <h1>{payload.title || 'Your procedure path'}</h1>
        <p className="nf-loc">{location || 'Location not specified'}{payload.service_type ? ` · ${payload.service_type}` : ''} · MCGM</p>
      </div>
      <div className="nf-road-progress"><small>{percent}% Completed</small><div className="nf-progress-track" style={{ marginTop: 6 }}><span style={{ width: `${percent}%` }} /></div></div>
    </div>

    {!payload.verified && <div className="nf-banner is-review" role="note"><span aria-hidden="true">ⓘ</span><p><strong>This pathway is awaiting source review.</strong> You can inspect its steps and official links; progress tracking will be available after an administrator approves it.</p></div>}
    {!!payload.warnings?.length && <div className="nf-banner is-warn" role="note"><span aria-hidden="true">!</span><p><strong>Some sources for this pathway need your attention.</strong> {payload.warnings.join(' ')}</p></div>}
    {payload.verified && <p className="nf-muted" style={{ fontSize: 13 }}>Your progress is saved to your account when you mark a step complete.</p>}
    {err && <div className="nf-error-box" role="alert">{err}</div>}

    {detailNode ? (
      /* ---- Step detail (panel 5) ---- */
      <aside className="nf-step-layout" aria-label="Step details" style={{ marginTop: 12 }}>
        <div className="nf-card nf-rail" aria-label="All pathway steps">
          {nodes.map((n, i) => {
            const st = getStatus(n);
            const done = st === 'verified';
            return <button key={n.id} className={`${n.id === detailId ? 'is-active' : ''} ${done ? 'is-done' : ''}`} onClick={() => { setDetailId(n.id); setSelected(n); }} aria-current={n.id === detailId ? 'step' : undefined}>
              <span className="nf-rail-num">{done ? '✓' : i + 1}</span>
              <span><small>{n.title}</small><br /><span className="nf-rail-st">{done ? 'Done' : n.id === detailId ? 'Current' : 'Pending'}</span></span>
            </button>;
          })}
        </div>
        <div className="nf-card nf-step-main">
          <button className="nf-text-link" onClick={() => setDetailId(null)}>← Back to roadmap</button>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
            <span className="nf-badge is-progress">Step {detailIndex + 1}</span>
            {getStatus(detailNode) === 'verified' ? <span className="nf-badge is-done">Done</span> : <span className="nf-badge is-progress">Current Step</span>}
          </div>
          <h1>{detailNode.title}</h1>
          <p>{detailNode.detail || 'Step in this civic procedure.'}</p>
          {detailNode.fee && <p style={{ fontSize: 13 }}><b>Fee:</b> {detailNode.fee}</p>}
          <div className="nf-req-docs">
            <h3>Required Documents</h3>
            {packet && packet.checklist.length > 0 ? packet.checklist.map((doc) => <div className="nf-req-row" key={doc}><span className="nf-doc-ic" aria-hidden="true">📄</span><span><strong>{doc}</strong></span><span className="nf-spacer" />{detailNode.url && <a className="nf-link-btn" href={detailNode.url} target="_blank" rel="noreferrer">View Example</a>}</div>)
              : <p className="nf-muted" style={{ fontSize: 13 }}>Load the path workflow packet below to see the exact document checklist extracted from official sources.</p>}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            {detailNode.link && detailNode.link !== detailNode.url && <a className="nf-btn nf-btn-outline nf-btn-sm" href={detailNode.link} target="_blank" rel="noreferrer">Open application / form ↗</a>}
            {detailNode.url && <a className="nf-btn nf-btn-outline nf-btn-sm" href={detailNode.url} target="_blank" rel="noreferrer">Open official site ↗</a>}
            {payload.verified && getStatus(detailNode) !== 'verified' && <button className="nf-btn nf-btn-primary nf-btn-sm" onClick={() => void markDone(detailNode)}>✓ Mark complete</button>}
            {getStatus(detailNode) === 'verified' && <span className="nf-badge is-done">Complete</span>}
          </div>
        </div>
        <div className="nf-side-stack">
          <div className="nf-card nf-side-card">
            <h3>Official Source</h3>
            <p className="nf-sub">{detailNode.url ? sourceName(detailNode.url) : 'No direct source link for this step.'}</p>
            {detailNode.url && <a className="nf-btn nf-btn-outline nf-btn-sm nf-btn-block" href={detailNode.url} target="_blank" rel="noreferrer">View Source ↗</a>}
            <div className="nf-kv" style={{ marginTop: 8 }}><span className="nf-k">Estimated Time</span><span className="nf-v">Confirm on official site</span></div>
          </div>
          <div className="nf-card nf-side-card">
            <h3>Next Step</h3>
            <p className="nf-sub">{nextNode ? nextNode.title : 'This is the final step.'}</p>
            {nextNode && <button className="nf-btn nf-btn-ghost nf-btn-sm nf-btn-block" onClick={() => { setDetailId(nextNode.id); setSelected(nextNode); }}>{nextNode.title} →</button>}
          </div>
        </div>
      </aside>
    ) : (
      /* ---- Visual roadmap (panel 4) ---- */
      <div className="nf-road-layout" style={{ marginTop: 4 }}>
        <div className="nf-card nf-flow-card" aria-label="Visual pathway flow">
          <div className="nf-flow-list" style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}>
            {nodes.length === 0 && <p className="nf-muted">No steps match these filters.</p>}
            {nodes.map((node) => {
              const st = getStatus(node);
              const isDone = st === 'verified';
              const cls = isDone ? 'is-done' : node.id === nodes[Math.min(doneCount, nodes.length - 1)]?.id ? 'is-current' : st === 'action' ? 'is-action' : '';
              return <div className="nf-flow-node-wrap" key={node.id}>
                <button className={`nf-flow-pill ${cls}`} onClick={() => { setDetailId(node.id); setSelected(node); }} aria-label={`Open step details: ${node.title}`}>
                  <span className="nf-ndot" style={{ background: nodeColor(st) }} aria-hidden="true">{isDone ? '✓' : '•'}</span><span className="nf-pill-txt" data-title={node.title} aria-hidden="true" />
                </button>
              </div>;
            })}
          </div>
          <div className="nf-flow-legend" aria-hidden="true">
            <span><i style={{ background: '#2f7fe0' }} />Step Order</span>
            <span><i style={{ background: '#7a5af8' }} />Dependency</span>
            <span><i style={{ background: '#2f9e6e' }} />Completed</span>
            <span><i style={{ background: '#dd8a0b' }} />Pending</span>
            <span><i style={{ background: '#2f7fe0' }} />Current</span>
          </div>
          <div className="nf-zoom" aria-label="Flow zoom">
            <button onClick={() => setZoom((z) => Math.min(1.4, +(z + 0.1).toFixed(2)))} aria-label="Zoom in">+</button>
            <button onClick={() => setZoom((z) => Math.max(0.7, +(z - 0.1).toFixed(2)))} aria-label="Zoom out">−</button>
          </div>
        </div>
        <div className="nf-side-stack">
          <div className="nf-card nf-keyinfo" aria-label="Key information">
            <h3>🛈 Key Information</h3>
            <div className="nf-kv"><span className="nf-k">Department</span><span className="nf-v">{payload.service_type || 'Municipal body'}</span></div>
            <div className="nf-kv"><span className="nf-k">Processing Time</span><span className="nf-v">Confirm on official site</span></div>
            <div className="nf-kv"><span className="nf-k">Fees</span><span className="nf-v">{fees.length ? fees.join(' · ') : 'As per official notice'}</span></div>
            <div className="nf-kv"><span className="nf-k">Office</span><span className="nf-v">{location ? `${location}` : 'See official portal'}</span></div>
            {firstSource && <a className="nf-btn nf-btn-primary nf-btn-sm nf-btn-block" style={{ marginTop: 10 }} href={firstSource} target="_blank" rel="noreferrer">View Official Website ↗</a>}
          </div>
          <div className="nf-card nf-docs-card" aria-label="Documents required">
            <h3>Documents Required</h3>
            {packet && packet.checklist.length > 0 ? packet.checklist.slice(0, 6).map((doc) => <div className="nf-doc-item" key={doc}><span className="nf-doc-ic" aria-hidden="true">📄</span><div><strong>{doc}</strong><small>See packet checklist</small></div></div>)
              : <p className="nf-muted" style={{ fontSize: 13 }}>{docNodes.length > 0 ? `${docNodes.length} document step${docNodes.length === 1 ? '' : 's'} identified — load the packet below for the exact checklist.` : 'Load the packet below for the exact document checklist.'}</p>}
          </div>
        </div>
      </div>
    )}

    {/* ---- filters + list/map ---- */}
    <div className="nf-filter-bar" style={{ marginTop: 18 }}>
      <input value={filters.q} onChange={(e) => updateFilter('q', e.target.value)} placeholder="⌕ Search steps, documents or fees" aria-label="Search pathway steps" />
      <select value={filters.node_type} onChange={(e) => updateFilter('node_type', e.target.value)} aria-label="Filter by step type"><option value="">All step types</option>{(payload.filters?.types || []).map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}</select>
      <select value={filters.status} onChange={(e) => updateFilter('status', e.target.value)} aria-label="Filter by status"><option value="">All statuses</option>{(payload.filters?.statuses || []).map((s) => <option key={s} value={s}>{STATUS_CONFIG[s as Status]?.badge || s}</option>)}</select>
      <button className="nf-btn nf-btn-ghost nf-btn-sm" onClick={resetFilters}>Reset</button>
      <div className="cv-view-toggle" role="group" aria-label="Pathway display mode"><button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')}>☷ List</button><button className={view === 'map' ? 'active' : ''} onClick={() => setView('map')}>⌘ Map</button></div>
    </div>
    <p className="nf-filter-note" aria-live="polite">{loading ? 'Refreshing steps…' : `${nodes.length} visible steps`}{(filters.q || filters.node_type || filters.status) && <span> · Filters are synced with the API</span>}</p>

    {view === 'map' ? <section className="nf-card" style={{ height: 480, overflow: 'hidden' }} aria-label="Interactive civic procedure map"><ReactFlow nodes={flowNodes} edges={flowEdges} nodeTypes={nodeTypes} fitView minZoom={0.35} maxZoom={1.4}><MiniMap nodeColor={(node) => STATUS_CONFIG[(node.data?.status || 'ready') as Status]?.color || '#187b69'} /><Controls /><Background color="#dce8e3" gap={22} /></ReactFlow>{flowNodes.length === 0 && <div style={{ padding: 16 }}>No steps match these filters. <button className="nf-link-btn" onClick={resetFilters}>Clear filters</button></div>}</section>
      : <section aria-label="Pathway steps">{nodes.map((node, index) => {
        const status = getStatus(node);
        const cfg = STATUS_CONFIG[status];
        return <article className="cv-filtered-step" key={node.id}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>{status !== 'verified' && <span className="nf-badge" style={{ background: cfg.bg, color: cfg.color }}>{cfg.icon} {cfg.badge}</span>}<span className="nf-muted" style={{ fontSize: 12.5 }}>Step {index + 1}</span></div>
          <h2 style={{ fontSize: 16, margin: '0 0 4px' }}>{node.title}</h2>
          <p className="nf-muted" style={{ fontSize: 13.5, margin: '0 0 6px' }}>{node.detail || 'Step in this civic procedure.'}</p>
          {node.fee && <p style={{ fontSize: 13 }}><b>Fee:</b> {node.fee}</p>}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
            {node.link && node.link !== node.url && <a className="nf-link-btn" href={node.link} target="_blank" rel="noreferrer">Apply / open form ↗</a>}
            {node.url && <a className="nf-link-btn" href={node.url} target="_blank" rel="noreferrer">Official source ↗</a>}
            <button className="nf-link-btn" onClick={() => { setDetailId(node.id); setSelected(node); }} aria-label={`Open step details: ${node.title}`}>Details →</button>
            {payload.verified && status !== 'verified' && <button className="nf-btn nf-btn-ghost nf-btn-sm" onClick={() => void markDone(node)}>Mark complete</button>}
            {status === 'verified' && <span className="nf-badge is-done">Complete</span>}
          </div>
        </article>;
      })}{nodes.length === 0 && <div className="nf-card" style={{ padding: 16 }}>No steps match these filters. <button className="nf-link-btn" onClick={resetFilters}>Clear filters</button></div>}</section>}

    {/* ---- packet ---- */}
    <section className="nf-card" style={{ padding: 20, marginTop: 18 }} aria-label="Path workflow packet">
      <span className="nf-eyebrow">PATH WORKFLOW PACKET</span>
      <h2 style={{ fontSize: 17, margin: '4px 0 6px' }}>Your packet: steps, checklist, guides</h2>
      {!packet && !packetBusy && <p className="nf-muted" style={{ fontSize: 13.5 }}>One bundle with the ordered steps, your document checklist, official guide links, and every source (with the real redirect target we verified) — downloadable as Markdown or sent to your Telegram.</p>}
      {!packet && !packetBusy && <button className="nf-btn nf-btn-primary nf-btn-sm" style={{ marginTop: 8 }} onClick={() => void loadPacket()}>Load packet</button>}
      {packetBusy && <p role="status">Building your packet from the fetched sources…</p>}
      {packetErr && <div className="nf-error-box" role="alert">{packetErr}</div>}
      {packet && <div className="cv-packet-body">
        {!!packet.warnings?.length && <div className="nf-banner is-warn" role="note"><span aria-hidden="true">!</span><p><strong>Source warnings for this packet.</strong> {packet.warnings.join(' ')}</p></div>}
        <p className="nf-muted" style={{ fontSize: 13 }}>{packet.counts.steps} steps · {packet.counts.documents} documents · {packet.counts.sources} sources · {packet.counts.guides} guides · generated {new Date(packet.generated_at).toLocaleString()}</p>
        {packet.checklist.length > 0 && <div><h3 style={{ fontSize: 14 }}>Document checklist</h3><ul style={{ fontSize: 13.5 }}>{packet.checklist.map((doc) => <li key={doc}>{doc}</li>)}</ul></div>}
        {packet.guides.length > 0 && <div><h3 style={{ fontSize: 14 }}>Official guides</h3><ul style={{ fontSize: 13.5 }}>{packet.guides.map((guide) => <li key={guide.url}><a href={guide.url} target="_blank" rel="noreferrer">{guide.title || guide.url} ↗</a></li>)}</ul></div>}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
          <button className="nf-btn nf-btn-ghost nf-btn-sm" onClick={() => void downloadPacket()}>Download .md</button>
          <button className="nf-btn nf-btn-primary nf-btn-sm" onClick={() => void sendPacket()}>Send to Telegram</button>
          <button className="nf-btn nf-btn-ghost nf-btn-sm" onClick={() => { setPacket(null); setPacketNote(''); }}>Hide packet</button>
        </div>
        {packetNote && <p role="status" style={{ fontSize: 13.5 }}>{packetNote}</p>}
      </div>}
    </section>

    {/* ---- sources ---- */}
    <section className="nf-card" style={{ padding: 20, marginTop: 18 }} aria-label="Official sources">
      <span className="nf-eyebrow">SOURCE LINKS</span>
      <h2 style={{ fontSize: 17, margin: '4px 0 6px' }}>Official sources for this pathway <span className="nf-muted" style={{ fontSize: 13 }}>({payload.sources?.length || 0})</span></h2>
      {!!payload.sources?.length ? payload.sources.map((source, index) => {
        const url = sourceUrl(source);
        const okay = sourceOk(source);
        return <div className="nf-source-row" key={`${url}-${index}`}><span aria-hidden="true">{okay ? '✓' : '!'}</span><div><strong>{sourceName(source)}</strong><small>{okay ? 'Fetched for this pathway' : 'Source could not be fetched'}</small></div>{url && <a href={url} target="_blank" rel="noreferrer" aria-label={`Open source ${sourceName(source)}`}>↗</a>}</div>;
      }) : <p className="nf-muted" style={{ fontSize: 13.5 }}>No source links were saved with this pathway.</p>}
      <p className="nf-muted" style={{ fontSize: 12.5, marginTop: 8 }}>Always confirm current eligibility, fees, documents and deadlines on the official site before applying.</p>
    </section>

    {selected && !detailNode && <aside className="nf-card" style={{ padding: 20, marginTop: 18 }} aria-label="Step details">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><span className="nf-badge is-info">{STATUS_CONFIG[getStatus(selected)].badge}</span><button className="nf-link-btn" onClick={() => setSelected(null)} aria-label="Close step details">× Close</button></div>
      <h2 style={{ fontSize: 17, margin: '8px 0 4px' }}>{selected.title}</h2>
      <p className="nf-muted" style={{ fontSize: 13.5 }}>{selected.detail || 'No additional details are available for this step.'}</p>
      {selected.fee && <p style={{ fontSize: 13 }}><b>Fee:</b> {selected.fee}</p>}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
        {selected.link && selected.link !== selected.url && <a className="nf-link-btn" href={selected.link} target="_blank" rel="noreferrer">Open application / form ↗</a>}
        {selected.url && <a className="nf-link-btn" href={selected.url} target="_blank" rel="noreferrer">Open official site ↗</a>}
        {payload.verified && getStatus(selected) !== 'verified' && <button className="nf-btn nf-btn-primary nf-btn-sm" onClick={() => void markDone(selected)}>✓ Mark complete</button>}
      </div>
    </aside>}
  </div>;
}
