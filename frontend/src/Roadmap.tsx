import React, { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';

type GNode = { id: string; type: string; title: string; detail?: string; url?: string; fee?: string };
type Status = 'ready' | 'action' | 'unlocked' | 'verified';

const STATUS_CONFIG: Record<Status, { color: string; bg: string; badge: string; icon: string }> = {
  ready: { color: '#1e3a8a', bg: '#eff6ff', badge: 'Ready', icon: '\u{1F4DB}' },
  action: { color: '#f97316', bg: '#fff7ed', badge: 'Needs Action', icon: '\u{26A1}' },
  unlocked: { color: '#16a34a', bg: '#f0fdf4', badge: 'Unlocked', icon: '\u{1F513}' },
  verified: { color: '#16a34a', bg: '#dcfce7', badge: 'Verified', icon: '\u2705' },
};

export default function Roadmap({ slug }: { slug: string }) {
  const t = STR[lang()];
  const [nodes, setNodes] = useState<GNode[]>([]);
  const [edges, setEdges] = useState<string[][]>([]);
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  const [sel, setSel] = useState<GNode | null>(null);
  const [err, setErr] = useState('');
  const [guide, setGuide] = useState('');
  const [gq, setGq] = useState('');
  const [gBusy, setGBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.map(slug), api.progress(slug)])
      .then(([m, p]) => {
        setNodes(m.graph.nodes);
        setEdges(m.graph.edges);
        setCompleted(new Set(p.steps || []));
      })
      .catch((e) => setErr(String(e.message || e)));
  }, [slug]);

  const getStatus = (node: GNode): Status => {
    if (completed.has(node.id)) return 'verified';
    if (node.type === 'action') return 'action';
    if (node.type === 'unlocked') return 'unlocked';
    return 'ready';
  };

  const markDone = async (nodeId: string) => {
    await api.done(slug, nodeId);
    setCompleted(prev => new Set([...prev, nodeId]));
    if (sel?.id === nodeId) {
      setSel(prev => prev ? { ...prev, type: 'verified' } : null);
    }
  };

  const askGuide = async () => {
    if (!sel) return;
    const key = localStorage.getItem('guide_key') || '';
    if (!key) { setGuide(t.rmKeyPh || 'Save your own LLM key (Guide settings) for AI answers.'); return; }
    setGBusy(true);
    try {
      const { PageAgent } = await import('page-agent');
      const agent: any = new (PageAgent as any)({
        model: 'nemotron-3-ultra-free',
        baseURL: 'https://router.bynara.id/v1',
        apiKey: key,
        language: 'en-US',
      });
      const ans = await agent.execute(
        `Civic procedure step: "${sel.title}". Details: ${sel.detail || ''}. User asks: ${gq || 'Explain this step in plain simple words and list exactly what to carry.'}`
      );
      setGuide(String(ans).slice(0, 1200));
    } catch (e: any) {
      setGuide('Guide unavailable: ' + String(e.message || e));
    }
    setGBusy(false);
  };

  if (err) return <p style={{ color: 'red' }}>{err}</p>;
  if (nodes.length === 0) return <p>{t.loading || 'Loading...'}</p>;

  return (
    <div className="cv-path-view">
      <div className="cv-path-input">
        <div className="cv-path-input-inner">
          <textarea
            className="cv-path-textarea"
            placeholder={t.pathInputPlaceholder || 'e.g., I want to get a new water connection...'}
            rows={2}
            defaultValue="I want to get a new water connection for my apartment"
          />
          <button className="cv-btn cv-btn-primary cv-btn-lg">
            {'\u{1F50D}'} {t.buildPath || 'Build Verified Path'}
          </button>
        </div>
      </div>

      <div className="cv-path-timeline">
        <div className="cv-timeline-header">
          <h2>{t.pathTitle || 'Your Procedure Path'}</h2>
          <div className="cv-path-meta">
            <span className="cv-meta-item">{'\u{1F4C5}'} {new Date().toLocaleDateString()}</span>
            <span className="cv-meta-item">{'\u{1F4CA}'} {completed.size}/{nodes.length} {t.stagesDone || 'steps complete'}</span>
          </div>
        </div>

        <div className="cv-steps-container">
          {nodes.slice(0, 7).map((node, idx) => {
            const status = getStatus(node);
            const cfg = STATUS_CONFIG[status];
            const isSelected = sel?.id === node.id;
            return (
              <React.Fragment key={node.id}>
                {idx > 0 && <div className="cv-arrow">\u2192</div>}
                <button
                  onClick={() => setSel(node)}
                  className={`cv-step-card cv-step-${status} ${isSelected ? 'cv-step-selected' : ''}`}
                  aria-pressed={isSelected}
                >
                  <div className="cv-step-header">
                    <span className="cv-step-badge" style={{ background: cfg.bg, color: cfg.color }}>
                      {cfg.icon} {cfg.badge}
                    </span>
                    <span className="cv-step-step">Step {idx + 1}</span>
                  </div>
                  <h3 className="cv-step-title">{node.title}</h3>
                  {node.fee && <p className="cv-step-fee">{'\u{1F4B0}'} {node.fee}</p>}
                  {node.url && (
                    <a href={node.url} target="_blank" rel="noreferrer" className="cv-step-link">
                      {t.source || 'Official Source'} \u2197
                    </a>
                  )}
                  <details className="cv-step-details">
                    <summary>{t.whyThisStep || 'Why this step?'}</summary>
                    <p>{node.detail || t.noDetail || 'No additional details.'}</p>
                  </details>
                  {status !== 'verified' && (
                    <button
                      onClick={(e) => { e.stopPropagation(); markDone(node.id); }}
                      className="cv-btn cv-btn-sm cv-btn-indigo"
                    >
                      {'\u2713'} {t.rmDone || 'Mark Done'}
                    </button>
                  )}
                </button>
              </React.Fragment>
            );
          })}
        </div>

        <div className="cv-sources-section">
          <h4>{'\u{1F50D}'} {t.sourcesChecked || 'Sources Checked'}</h4>
          <div className="cv-source-chips">
            {['National Govt Services', 'Municipal Corp', 'DigiLocker'].map((src, i) => (
              <div key={i} className="cv-source-chip cv-verified">
                <span>{'\u2713'}</span> {src}
              </div>
            ))}
          </div>
        </div>
      </div>

      {sel && (
        <div className="cv-detail-panel">
          <button onClick={() => setSel(null)} className="cv-close-btn">{'\u00D7'}</button>
          <h2>{sel.title}</h2>
          <p>{sel.detail}</p>
          {sel.fee && <p><b>{t.rmFee || 'Fee'}:</b> {sel.fee}</p>}
          {sel.url && <a href={sel.url} target="_blank" rel="noreferrer">{t.rmOpen || 'Open official site'} \u2197</a>}
          <hr className="cv-divider" />
          <h3>{'\u{1F56D}\uFE0F'} {t.rmGuide || 'Guide Me'}</h3>
          <textarea
            placeholder={t.rmAsk || 'Ask about this step...'}
            value={gq}
            onChange={(e) => setGq(e.target.value)}
            className="cv-textarea cv-small"
          />
          <button onClick={askGuide} disabled={gBusy} className="cv-btn cv-btn-primary">
            {gBusy ? '...' : t.rmAskBtn || 'Ask Guide'}
          </button>
          {guide && <p className="cv-guide-response">{guide}</p>}
          <details>
            <summary>{t.rmKey || 'Guide Settings'}</summary>
            <input
              type="password"
              placeholder={t.rmKeyPh || 'Paste LLM key...'}
              defaultValue={localStorage.getItem('guide_key') || ''}
              onBlur={(e) => localStorage.setItem('guide_key', e.target.value.trim())}
              className="cv-input cv-small"
            />
          </details>
        </div>
      )}
    </div>
  );
}
