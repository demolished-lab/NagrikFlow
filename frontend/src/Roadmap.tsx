import React, { useCallback, useEffect, useState } from 'react';
import ReactFlow, { Background, Controls, MiniMap, Node, Edge } from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';
import { api } from './api';
import { STR, lang } from './i18n';

type GNode = { id: string; type: string; title: string; detail?: string; url?: string; fee?: string };

const DEPTH_COLORS = ['#888', '#36c', '#7a3cc0', '#c07418', '#c02c4d', '#0d7377'];

function depths(nodes: GNode[], edges: string[][]): Record<string, number> {
  // Longest-path depths via relaxation: parallel branches share color bands.
  const ids = new Set(nodes.map((n) => n.id));
  const d: Record<string, number> = {};
  nodes.forEach((n) => { d[n.id] = 0; });
  for (let i = 0; i < nodes.length; i++) {
    edges.forEach(([a, b]) => {
      if (ids.has(a) && ids.has(b)) d[b] = Math.max(d[b], d[a] + 1);
    });
  }
  return d;
}

function layout(nodes: GNode[], edges: string[][], completed: Set<string>): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'TB', nodesep: 40, ranksep: 70 });
  g.setDefaultEdgeLabel(() => ({}));
  nodes.forEach((n) => g.setNode(n.id, { width: 220, height: 90 }));
  edges.forEach(([a, b]) => g.setEdge(a, b));
  dagre.layout(g);
  const dep = depths(nodes, edges);
  return {
    nodes: nodes.map((n) => {
      const p = g.node(n.id);
      const done = completed.has(n.id);
      const band = DEPTH_COLORS[dep[n.id] % DEPTH_COLORS.length];
      return {
        id: n.id,
        position: { x: p.x - 110, y: p.y - 45 },
        data: { label: `${done ? '✅ ' : ''}${n.title}${n.fee ? ` (${n.fee})` : ''}` },
        style: {
          border: '2px solid ' + (done ? '#2a2' : band),
          borderRadius: 10, padding: 8, width: 220, background: done ? '#eaffea' : '#fff',
        },
      };
    }),
    edges: edges.map(([a, b], i) => ({ id: `e${i}`, source: a, target: b, animated: true })),
  };
}

export default function Roadmap({ slug }: { slug: string }) {
  const t = STR[lang()];
  const [flow, setFlow] = useState<{ nodes: Node[]; edges: Edge[] }>({ nodes: [], edges: [] });
  const [sel, setSel] = useState<GNode | null>(null);
  const [all, setAll] = useState<GNode[]>([]);
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [err, setErr] = useState('');

  useEffect(() => {
    Promise.all([api.map(slug), api.progress(slug)]).then(([m, p]) => {
      const done = new Set<string>(p.steps || []);
      setCompleted(done);
      setAll(m.graph.nodes);
      setFlow(layout(m.graph.nodes, m.graph.edges, done));
    }).catch((e) => setErr(String(e.message || e)));
  }, [slug]);

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => setSel(all.find((n) => n.id === node.id) || null), [all]);

  const [guide, setGuide] = useState('');
  const [gq, setGq] = useState('');
  const [gBusy, setGBusy] = useState(false);

  const askGuide = async () => {
    // In-page copilot (page-agent lib) answers about THIS step.
    // Uses the visitor's own key if saved, else falls back to checklist text.
    const key = localStorage.getItem('guide_key') || '';
    if (!key || !sel) { setGuide('Save your own LLM key (Guide settings) for AI answers, or follow the checklist below.'); return; }
    setGBusy(true);
    try {
      const { PageAgent } = await import('page-agent');
      const agent: any = new (PageAgent as any)({
        model: 'nemotron-3-ultra-free',
        baseURL: 'https://router.bynara.id/v1',
        apiKey: key, language: 'en-US',
      });
      const ans = await agent.execute(
        `Civic procedure step: "${sel.title}". Details: ${sel.detail || ''}. ` +
        `User asks: ${gq || 'Explain this step in plain simple words and list exactly what to carry.'}`);
      setGuide(String(ans).slice(0, 1200));
    } catch (e: any) { setGuide('Guide unavailable: ' + String(e.message || e)); }
    setGBusy(false);
  };

  const markDone = async () => {
    if (!sel) return;
    await api.done(slug, sel.id);
    const done = new Set(completed);
    done.add(sel.id);
    setCompleted(done);
    setFlow((f) => ({
      ...f,
      nodes: f.nodes.map((n) =>
        n.id === sel.id
          ? { ...n, data: { label: '✅ ' + String(n.data.label).replace(/^✅ /, '') },
              style: { ...n.style, background: '#eaffea', border: '2px solid #2a2' } }
          : n),
    }));
    setSel({ ...sel });
  };

  if (err) return <p style={{ color: 'red' }}>{err}</p>;
  return (
    <div style={{ display: 'flex', height: 520, gap: 12 }}>
      <div style={{ flex: 3, border: '1px solid #ddd', borderRadius: 8 }}>
        <ReactFlow nodes={flow.nodes} edges={flow.edges} onNodeClick={onNodeClick} fitView>
          <Background /><Controls /><MiniMap />
        </ReactFlow>
      </div>
      <div style={{ flex: 1, border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        {!sel && <p>{t.rmClick}</p>}
        {sel && (
          <>
            <h3>{sel.title}</h3>
            <p>{sel.detail}</p>
            {sel.fee && <p><b>{t.rmFee}:</b> {sel.fee}</p>}
            {sel.url && <p><a href={sel.url} target="_blank" rel="noreferrer">{t.rmOpen} ↗</a></p>}
            <button onClick={markDone}>✓ {t.rmDone}</button>
            <hr />
            <h4>🧭 {t.rmGuide}</h4>
            <input placeholder={t.rmAsk} aria-label={t.rmAsk} value={gq}
              onChange={(e) => setGq(e.target.value)}
              style={{ width: '100%', padding: 6, marginBottom: 6 }} />
            <button onClick={askGuide} disabled={gBusy}>{gBusy ? '…' : t.rmAskBtn}</button>
            {guide && <p aria-live="polite"><small>{guide}</small></p>}
            <details>
              <summary><small>{t.rmKey}</small></summary>
              <input type="password" placeholder={t.rmKeyPh}
                aria-label={t.rmKey}
                defaultValue={localStorage.getItem('guide_key') || ''}
                onBlur={(e) => localStorage.setItem('guide_key', e.target.value.trim())}
                style={{ width: '100%', padding: 6 }} />
            </details>
          </>
        )}
      </div>
    </div>
  );
}
