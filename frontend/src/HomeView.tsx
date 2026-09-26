import React, { useState } from 'react';

const steps = [
  { title: 'New water\nconnection', label: 'Task', status: 'READY', tone: 'ready', icon: '◯', source: 'Municipal portal' },
  { title: 'Property / occupancy\nproof', label: 'Proof', status: 'NEEDS ACTION', tone: 'action', icon: '⌂', source: 'Municipal portal' },
  { title: 'Identity verification', label: 'Verification', status: 'UNLOCKED', tone: 'unlocked', icon: '▣', source: 'DigiLocker / API Setu' },
  { title: 'No-dues / tax status', label: 'Clearance', status: 'READY', tone: 'ready', icon: '▤', source: 'Municipal portal' },
  { title: 'Application', label: 'Form', status: 'NEEDS ACTION', tone: 'action', icon: '☷', source: 'Municipal portal' },
  { title: 'Inspection', label: 'Review', status: 'UNLOCKED', tone: 'unlocked', icon: '⌕', source: 'Municipal portal' },
  { title: 'Connection approval', label: 'Outcome', status: 'VERIFIED', tone: 'verified', icon: '♧', source: 'Municipal portal' },
];

export default function HomeView() {
  const [task, setTask] = useState('I want to get a new water connection for my apartment');
  const [built, setBuilt] = useState(false);

  return (
    <div className="cv-home-view cv-anim-up">
      <section className="cv-task-composer">
        <div className="cv-eyebrow">DESCRIBE YOUR CIVIC TASK</div>
        <div className="cv-task-row">
          <div className="cv-task-input-wrap">
            <span className="cv-inline-icon">⌕</span>
            <input value={task} onChange={(e) => setTask(e.target.value)} aria-label="Civic task" />
          </div>
          <button className="cv-build-btn" onClick={() => setBuilt(true)}>
            {built ? 'Path verified' : 'Build verified path'} <span>→</span>
          </button>
        </div>
        <p className="cv-helper">Plain-language task <span>→</span> verified government workflow</p>
      </section>

      <section className="cv-path-card">
        <div className="cv-path-heading">
          <div>
            <div className="cv-path-title"><span className="cv-check-circle">✓</span> Your Verified Path</div>
            <div className="cv-path-meta">7 steps <span>•</span> 6 dependencies <span>•</span> 100% from verified sources</div>
          </div>
          <span className="cv-verified-pill">✓ VERIFIED PATH</span>
        </div>
        <div className="cv-step-grid">
          {steps.map((step, index) => (
            <React.Fragment key={step.title}>
              {index === 4 && <div className="cv-step-break" aria-hidden="true" />}
              {index > 0 && index !== 4 && <div className="cv-step-arrow" aria-hidden="true">→</div>}
              <article className={`cv-verified-step cv-step-${step.tone}`}>
                <div className="cv-step-topline"><span className="cv-step-number">{index + 1}</span><span className="cv-step-label">{step.label}</span><span className="cv-step-icon">{step.icon}</span></div>
                <h3>{step.title.split('\n').map((line) => <React.Fragment key={line}>{line}<br /></React.Fragment>)}</h3>
                <span className={`cv-status cv-status-${step.tone}`}>{step.status}</span>
                <p>{step.source} <span>•</span> verified</p>
                <small>27 Sep 2026</small>
                <details><summary>Why this step?</summary><div>Verified dependency in your civic workflow.</div></details>
              </article>
            </React.Fragment>
          ))}
        </div>
      </section>

      <section className="cv-sources-card">
        <div className="cv-sources-heading"><div><div className="cv-sources-title"><span className="cv-check-circle small">✓</span> Sources checked</div><p>We’ve verified this path with trusted government sources.</p></div><span className="cv-last-checked">Last checked 27 Sep 2026&nbsp; ↻</span></div>
        <div className="cv-source-grid">
          {['National Government Services Portal', 'Municipal corporation portal', 'DigiLocker / API Setu'].map((source, index) => <div className="cv-source-card" key={source}><span className="cv-source-icon">{['◎', '⌂', '⌁'][index]}</span><div><strong>{source}</strong><p>{['Service information & eligibility', 'Local rules, fees & application process', 'Document verification & sharing'][index]}</p><small>Checked 27 Sep 2026</small><span className="cv-mini-verified">✓ VERIFIED</span></div><span className="cv-card-chevron">›</span></div>)}
          <div className="cv-legend"><strong>Path legend</strong><span><i className="legend-solid" /> Verified dependency</span><span><i className="legend-dotted" /> Dependency inferred</span><span><i className="legend-person" /> User-provided document</span><span><i className="legend-dot" /> Needs confirmation</span></div>
        </div>
      </section>
    </div>
  );
}
