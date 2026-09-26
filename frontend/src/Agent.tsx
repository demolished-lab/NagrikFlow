import React, { useEffect, useState, useRef } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';

export default function AgentPanel() {
  const t = STR[lang()];
  const [task, setTask] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState('');
  const [audit, setAudit] = useState<any[]>([]);
  const [tools, setTools] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'chat' | 'tools' | 'audit'>('chat');
  const pollRef = useRef<number | null>(null);

  const runAgent = async () => {
    if (!task.trim()) return;
    setRunning(true);
    setResult(null);
    setErr('');
    try {
      const { job_id } = await api.hermesRun(task, 'auto', 30);
      // Poll for result
      const poll = async () => {
        try {
          const j = await api.hermesResult(job_id);
          if (j.status === 'done' || j.status === 'failed' || j.status === 'timeout') {
            setResult(j);
            setRunning(false);
            if (pollRef.current) clearInterval(pollRef.current);
          }
        } catch { /* ignore transient errors */ }
      };
      poll(); // check immediately
      pollRef.current = window.setInterval(poll, 3000);
      // Cleanup on unmount
      setTimeout(() => { if (pollRef.current) clearInterval(pollRef.current); }, 600_000);
    } catch (e: any) {
      setErr(String(e.message || e));
      setRunning(false);
    }
  };

  useEffect(() => {
    Promise.all([
      api.hermesAudit(30).then(setAudit).catch(() => {}),
      api.hermesTools().then(r => setTools(r.tools || [])).catch(() => {})
    ]);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  return (
    <div style={{ display: 'grid', gap: 16, maxWidth: 900 }}>
      {/* Tab Navigation */}
      <div style={{ display: 'flex', gap: 8, borderBottom: '2px solid var(--line)', marginBottom: 8 }}>
        {(['chat', 'tools', 'audit'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 16px',
              borderRadius: '8px 8px 0 0',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid var(--saffron)' : '2px solid transparent',
              background: activeTab === tab ? 'rgba(249,115,22,0.1)' : 'transparent',
              color: activeTab === tab ? 'var(--saffron)' : 'var(--ink-2)',
              fontWeight: activeTab === tab ? 600 : 500,
              cursor: 'pointer',
              fontSize: 14,
            }}
          >
            {tab === 'chat' && '💬 '}
            {tab === 'tools' && '🔧 '}
            {tab === 'audit' && '📋 '}
            {tab.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Chat Tab */}
      {activeTab === 'chat' && (
        <div style={{ border: '1px solid #ddd', borderRadius: 10, padding: 16, background: '#fafafa' }}>
          <h3 style={{ margin: '0 0 8px' }}>🤖 {t.agentTitle}</h3>
          <p style={{ fontSize: 13, color: '#666', margin: '0 0 12px' }}>{t.agentDesc}</p>
          <textarea
            placeholder={t.agentInput}
            value={task}
            onChange={(e) => setTask(e.target.value)}
            rows={4}
            style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #ccc', fontSize: 14, resize: 'vertical', boxSizing: 'border-box' }}
          />
          <button
            onClick={runAgent}
            disabled={running || !task.trim()}
            style={{
              marginTop: 10, padding: '10px 24px', borderRadius: 8, border: 'none',
              background: running ? '#ccc' : '#2563eb', color: '#fff', cursor: running ? 'not-allowed' : 'pointer',
              fontWeight: 600, fontSize: 14,
            }}
          >
            {running ? `⏳ ${t.agentRunning}` : `▶ ${t.agentRun}`}
          </button>
          {err && <p role="alert" style={{ color: 'red', marginTop: 8 }}>{err}</p>}
        </div>
      )}

      {/* Tools Tab */}
      {activeTab === 'tools' && (
        <div style={{ border: '1px solid #ddd', borderRadius: 10, padding: 16 }}>
          <h4 style={{ margin: '0 0 12px' }}>🔧 {t.agentTools} ({tools.length})</h4>
          <div style={{ display: 'grid', gap: 8 }}>
            {tools.map((tool: any, i: number) => (
              <div key={i} style={{ padding: 12, background: '#f8fafc', borderRadius: 8, border: '1px solid var(--line)' }}>
                <div style={{ fontWeight: 600, color: 'var(--indigo)' }}>{tool.name}</div>
                <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>{tool.description}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Audit Tab */}
      {activeTab === 'audit' && (
        <div style={{ border: '1px solid #ddd', borderRadius: 10, padding: 16 }}>
          <h4 style={{ margin: '0 0 12px' }}>📋 {t.agentAudit}</h4>
          {audit.length === 0 ? (
            <p style={{ color: '#888' }}>No audit entries yet.</p>
          ) : (
            <div style={{ maxHeight: 400, overflowY: 'auto', fontSize: 12, fontFamily: 'monospace' }}>
              {audit.map((e: any, i: number) => (
                <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid #eee' }}>
                  <span style={{ color: '#888' }}>{new Date(e.ts).toLocaleString()}</span>
                  {' '}<b>{e.action}</b> → {e.target}
                  {' '}<span style={{ color: e.success === false ? 'red' : 'green' }}>{e.success === false ? '✗' : '✓'}</span>
                  {': '}{e.summary?.slice(0, 80)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Result Display */}
      {result && (
        <div style={{ border: '1px solid #ddd', borderRadius: 10, padding: 16, background: result.status === 'done' ? '#f0fdf4' : '#fef2f2' }}>
          <h4 style={{ margin: '0 0 8px' }}>
            {result.status === 'done' ? t.agentStatusDone : result.status === 'failed' ? t.agentStatusFailed : t.agentStatusTimeout}
            <span style={{ fontSize: 12, color: '#666', fontWeight: 400 }}>
              {' '}— {result.turns} {t.agentTurns}, {result.elapsed_secs}s {t.agentTime} ({result.via})
            </span>
          </h4>
          {result.final && (
            <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.6, color: '#333' }}>
              {result.final.slice(0, 3000)}
              {result.final.length > 3000 && '...'}
            </div>
          )}
          {result.errors && result.errors.length > 0 && (
            <div style={{ marginTop: 12, padding: 12, background: '#fee2e2', borderRadius: 8, fontSize: 13 }}>
              <b>Errors:</b>
              <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
                {result.errors.map((e: string, i: number) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
