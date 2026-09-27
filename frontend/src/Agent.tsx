import React, { useEffect, useRef, useState } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';

type AgentTab = 'chat' | 'tools' | 'audit';

export default function AgentPanel() {
  const t = STR[lang()];
  const [task, setTask] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState('');
  const [audit, setAudit] = useState<any[]>([]);
  const [tools, setTools] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<AgentTab>('chat');
  const pollRef = useRef<number | null>(null);

  const runAgent = async () => {
    if (!task.trim() || running) return;
    setRunning(true);
    setResult(null);
    setErr('');
    try {
      const { job_id } = await api.hermesRun(task, 'auto', 30);
      const poll = async () => {
        try {
          const job = await api.hermesResult(job_id);
          if (job.status === 'done' || job.status === 'failed' || job.status === 'timeout') {
            setResult(job);
            setRunning(false);
            if (pollRef.current !== null) window.clearInterval(pollRef.current);
          }
        } catch { /* Ignore transient poll errors and retry on the next interval. */ }
      };
      void poll();
      pollRef.current = window.setInterval(() => { void poll(); }, 3000);
      window.setTimeout(() => { if (pollRef.current !== null) window.clearInterval(pollRef.current); }, 600_000);
    } catch (error: any) {
      setErr(String(error.message || error));
      setRunning(false);
    }
  };

  useEffect(() => {
    void Promise.all([
      api.hermesAudit(30).then(setAudit).catch(() => {}),
      api.hermesTools().then((response) => setTools(response.tools || [])).catch(() => {}),
    ]);
    return () => { if (pollRef.current !== null) window.clearInterval(pollRef.current); };
  }, []);

  const tabs: { id: AgentTab; label: string }[] = [
    { id: 'chat', label: 'Research agent' },
    { id: 'tools', label: 'Available tools' },
    { id: 'audit', label: 'Activity log' },
  ];
  const resultTitle = result?.status === 'done' ? t.agentStatusDone : result?.status === 'failed' ? t.agentStatusFailed : t.agentStatusTimeout;

  return <div className="cv-agent-view cv-anim-up">
    <header className="cv-page-heading cv-agent-heading"><div><span className="cv-eyebrow">ADMIN TOOLS</span><h1>Research workspace</h1><p>Run an assisted research task and review its tool activity.</p></div></header>

    <div className="cv-agent-tabs" role="tablist" aria-label="Research workspace sections">
      {tabs.map((tab) => <button key={tab.id} type="button" role="tab" id={`agent-tab-${tab.id}`} aria-selected={activeTab === tab.id} aria-controls={`agent-panel-${tab.id}`} className={`cv-agent-tab ${activeTab === tab.id ? 'is-active' : ''}`} onClick={() => setActiveTab(tab.id)}>{tab.label}</button>)}
    </div>

    {activeTab === 'chat' && <section className="cv-agent-card" role="tabpanel" id="agent-panel-chat" aria-labelledby="agent-tab-chat">
      <h2>{t.agentTitle}</h2><p>{t.agentDesc}</p>
      <label className="sr-only" htmlFor="agent-task">Research task</label>
      <textarea id="agent-task" placeholder={t.agentInput} value={task} onChange={(event) => setTask(event.target.value)} rows={4}/>
      {err && <div className="cv-admin-notice is-error" role="alert">{err}</div>}
      <button className="cv-agent-run" type="button" onClick={() => void runAgent()} disabled={running || !task.trim()}>{running ? t.agentRunning : t.agentRun}</button>
      {running && <p className="cv-muted" role="status">Research is running. This page will update when the result is ready.</p>}
    </section>}

    {activeTab === 'tools' && <section className="cv-agent-card" role="tabpanel" id="agent-panel-tools" aria-labelledby="agent-tab-tools">
      <h2>{t.agentTools} <span className="cv-muted">({tools.length})</span></h2>
      {tools.length ? <div className="cv-agent-tools">{tools.map((tool: any, index) => <article className="cv-agent-tool" key={`${tool.name}-${index}`}><strong>{tool.name}</strong><p>{tool.description}</p></article>)}</div> : <p>No research tools are available right now.</p>}
    </section>}

    {activeTab === 'audit' && <section className="cv-agent-card" role="tabpanel" id="agent-panel-audit" aria-labelledby="agent-tab-audit">
      <h2>{t.agentAudit}</h2>
      {audit.length === 0 ? <p>No audit entries yet.</p> : <div className="cv-agent-audit">{audit.map((entry: any, index) => <div className="cv-agent-audit-row" key={`${entry.ts}-${index}`}><time>{new Date(entry.ts).toLocaleString()}</time>{' '}<strong>{entry.action}</strong> → {entry.target}{' '}<span aria-label={entry.success === false ? 'Failed' : 'Succeeded'}>{entry.success === false ? '×' : '✓'}</span>{entry.summary ? `: ${entry.summary.slice(0, 120)}` : ''}</div>)}</div>}
    </section>}

    {result && <section className={`cv-agent-result ${result.status === 'done' ? '' : 'is-error'}`} aria-live="polite">
      <h3>{resultTitle} <span className="cv-muted">— {result.turns} {t.agentTurns}, {result.elapsed_secs}s {t.agentTime} ({result.via})</span></h3>
      {result.final && <div className="cv-agent-result-copy">{result.final.slice(0, 3000)}{result.final.length > 3000 ? '…' : ''}</div>}
      {result.errors?.length > 0 && <div className="cv-agent-result-errors"><strong>Errors</strong><ul>{result.errors.map((message: string, index: number) => <li key={`${index}-${message}`}>{message}</li>)}</ul></div>}
    </section>}
  </div>;
}
