import React, { useCallback, useEffect, useState } from 'react';
import ReactFlow, { Background, Controls, MiniMap, Node, Edge } from 'reactflow';
import dagre from 'dagre';
import 'reactflow/dist/style.css';
import { api } from './api';

type GNode = { id: string; type: string; title: string; detail?: string; url?: string; fee?: string };

function layout(nodes: GNode[], edges: string[][]): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'TB', nodesep: 40, ranksep: 70 });
  g.setDefaultEdgeLabel(() => ({}));
  nodes.forEach((n) => g.setNode(n.id, { width: 220, height: 90 }));
  edges.forEach(([a, b]) => g.setEdge(a, b));
  dagre.layout(g);
  return {
    nodes: nodes.map((n) => {
      const p = g.node(n.id);
      const done = localStorage.getItem(`done-${n.id}`) === '1';
      return {
        id: n.id,
        position: { x: p.x - 110, y: p.y - 45 },
        data: { label: `${done ? '✅ ' : ''}${n.title}${n.fee ? ` (${n.fee})` : ''}` },
        style: {
          border: '2px solid ' + (n.type === 'prereq' ? '#888' : done ? '#2a2' : '#36c'),
          borderRadius: 10, padding: 8, width: 220, background: done ? '#eaffea' : '#fff',
        },
      };
    }),
    edges: edges.map(([a, b], i) => ({ id: `e${i}`, source: a, target: b, animated: true })),
  };
}

export default function Roadmap({ slug }: { slug: string }) {
  const [flow, setFlow] = useState<{ nodes: Node[]; edges: Edge[] }>({ nodes: [], edges: [] });
  const [sel, setSel] = useState<GNode | null>(null);
  const [all, setAll] = useState<GNode[]>([]);
  const [err, setErr] = useState('');

  useEffect(() => {
    api.map(slug).then((m) => {
      setAll(m.graph.nodes);
      setFlow(layout(m.graph.nodes, m.graph.edges));
    }).catch((e) => setErr(String(e.message || e)));
  }, [slug]);

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => setSel(all.find((n) => n.id === node.id) || null), [all]);

  const markDone = async () => {
    if (!sel) return;
    await api.done(slug, sel.id);
    localStorage.setItem(`done-${sel.id}`, '1');
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
        {!sel && <p>Click a step on the map.</p>}
        {sel && (
          <>
            <h3>{sel.title}</h3>
            <p>{sel.detail}</p>
            {sel.fee && <p><b>Fee:</b> {sel.fee}</p>}
            {sel.url && <p><a href={sel.url} target="_blank" rel="noreferrer">Open official site ↗</a></p>}
            <button onClick={markDone}>✓ Mark done</button>
          </>
        )}
      </div>
    </div>
  );
}
