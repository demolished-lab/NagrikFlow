import React from 'react';
import { TopNav, Footer, StatusBadge, ProgressBar, type NavTab } from './nf-kit';

type Props = {
  guest: boolean;
  userName: string;
  isAdmin: boolean;
  lang: string;
  onLang: () => void;
  onLogin: () => void;
  onRegister: () => void;
  onLogout: () => void;
  onNavigate: (tab: NavTab) => void;
};

function Phone({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="nf-phone">
    <div className="nf-phone-bezel"><div className="nf-phone-screen">
      <div className="nf-phone-notch"><i /></div>
      <div className="nf-phone-body">{children}</div>
    </div></div>
    <div className="nf-phone-label">{label}</div>
  </div>;
}

export default function ShowcaseView(props: Props) {
  const { guest, onNavigate } = props;
  return <div className="nf-shell">
    <TopNav
      active="showcase" onNavigate={onNavigate}
      userName={guest ? '' : props.userName} isAdmin={props.isAdmin} unread={0}
      lang={props.lang} onLang={props.onLang}
      onLogin={props.onLogin} onRegister={props.onRegister} onLogout={props.onLogout}
    />
    <main className="nf-main nf-main-wide" id="main-content">
      <div className="nf-crumb"><button onClick={() => onNavigate('home')}>Home</button> · <b>Brand showcase</b></div>

      {/* Panel 9 — mobile responsive views */}
      <section aria-labelledby="show-mobile">
        <div className="nf-show-head">
          <span className="nf-eyebrow">NagrikFlow on every screen</span>
          <h1 id="show-mobile">Mobile Responsive Views</h1>
          <p>The full civic journey — home, task input, roadmap, progress and profile — in your pocket.</p>
        </div>
        <div className="nf-phones">
          <Phone label="1. Home (Mobile)">
            <h5>Your Guide to Government Services</h5><p>From complex procedures to clear next steps.</p>
            <div className="nf-mbtn">Find My Path →</div>
            <div className="nf-mcard"><b>Popular Services</b><p>🏪 Register a Small Business</p><p>🚗 Driving Licence</p></div>
            <div className="nf-mcard"><b>Verified Sources</b><p>Every detail linked to .gov portals</p></div>
          </Phone>
          <Phone label="2. Task Input (Mobile)">
            <h5>Describe Your Civic Task</h5>
            <div className="nf-mcard"><p>⌕ I want to register…</p></div>
            <div className="nf-mcard"><p>📍 Mumbai, Maharashtra</p></div>
            <div className="nf-mbtn">Find My Path →</div>
            <div className="nf-mcard"><b>Popular Examples</b><p>Birth certificate · Property tax</p></div>
          </Phone>
          <Phone label="3. Roadmap (Mobile)">
            <h5>Small Business Registration</h5>
            <div className="nf-mbar"><i style={{ width: '40%' }} /></div>
            {[['✓', '#2f9e6e', 'Eligibility Check'], ['2', '#2f7fe0', 'Documents Required'], ['3', '#7a5af8', 'Fill Application Form'], ['4', '#8a93a8', 'Pay Fees'], ['5', '#8a93a8', 'Verification']].map(([n, c, t]) => (
              <div className="nf-mcard" key={t} style={{ display: 'flex', gap: 6, alignItems: 'center' }}><span className="nf-mdot" style={{ background: c }}>{n}</span><b>{t}</b></div>
            ))}
          </Phone>
          <Phone label="4. Progress (Mobile)">
            <h5>My Progress</h5>
            <div className="nf-mbar"><i style={{ width: '40%' }} /></div>
            <div className="nf-mcard"><b>✓ Eligibility Check</b><p>Completed Apr 10, 2025</p></div>
            <div className="nf-mcard"><b>✓ Documents Required</b><p>Completed Apr 12, 2025</p></div>
            <div className="nf-mcard"><b>◌ Fill Application Form</b><p>In Progress — you are here</p></div>
          </Phone>
          <Phone label="5. Profile (Mobile)">
            <h5>Welcome back, Priya!</h5>
            <div className="nf-mcard"><b>3 Active · 5 Completed</b><div className="nf-mbar"><i style={{ width: '62%' }} /></div></div>
            <div className="nf-mcard"><b>⚙ Settings</b><p>Language · Notifications · Help</p></div>
            <div className="nf-mbtn">Contact Support</div>
          </Phone>
        </div>
      </section>

      {/* Panel 10 — key UI components */}
      <section aria-labelledby="show-components" style={{ marginTop: 34 }}>
        <div className="nf-show-head">
          <span className="nf-eyebrow">One kit, every screen</span>
          <h1 id="show-components">Key UI Components</h1>
          <p>The building blocks of every NagrikFlow page — live, not screenshots.</p>
        </div>
        <div className="nf-comp-grid">
          <div className="nf-card nf-comp-demo"><h3>Service Card <span>· discovery</span></h3>
            <div className="nf-service-card" style={{ boxShadow: 'none' }}><span className="nf-svc-icon" style={{ background: '#e5f5ec' }}>🏪</span><h3>Shop &amp; Establishments Registration</h3><p>MCGM · Mumbai · Licence</p><button onClick={() => onNavigate('search')}>View Path →</button></div>
          </div>
          <div className="nf-card nf-comp-demo"><h3>Status Badge <span>· progress states</span></h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}><StatusBadge status="Completed" /><StatusBadge status="In Progress" /><StatusBadge status="Pending" /><StatusBadge status="Conflict" /></div>
          </div>
          <div className="nf-card nf-comp-demo"><h3>Progress Bar <span>· 40% complete</span></h3><ProgressBar percent={40} /></div>
          <div className="nf-card nf-comp-demo"><h3>Step Indicator <span>· 1–6</span></h3>
            <div style={{ display: 'flex', gap: 8 }}>{[1, 2, 3, 4, 5, 6].map((n) => <span key={n} className="nf-tl-marker" style={n <= 2 ? { background: 'var(--nf-green-soft)', color: 'var(--nf-green)' } : n === 3 ? { background: 'var(--nf-primary)', color: '#fff' } : undefined}>{n <= 2 ? '✓' : n}</span>)}</div>
            <p className="nf-muted" style={{ fontSize: 12.5, margin: '8px 0 0' }}>Completed · Current · Pending</p>
          </div>
          <div className="nf-card nf-comp-demo"><h3>Error / Conflict Box <span>· attention</span></h3>
            <div className="nf-banner is-warn" style={{ margin: 0 }}><span aria-hidden="true">!</span><p><strong>Information conflict detected.</strong> Two sources disagree on fees. Please review.</p></div>
          </div>
          <div className="nf-card nf-comp-demo"><h3>Source Link <span>· trust</span></h3>
            <div className="nf-source-row" style={{ border: 0, padding: 0 }}><span aria-hidden="true">✓</span><div><strong>udyamregistration.gov.in</strong><small>Fetched for this pathway</small></div><a href="https://udyamregistration.gov.in/" target="_blank" rel="noreferrer">↗</a></div>
          </div>
          <div className="nf-card nf-comp-demo"><h3>Document Item <span>· checklist</span></h3>
            <div className="nf-req-row" style={{ margin: 0 }}><span className="nf-doc-ic">📄</span><span><strong>Identity proof (Aadhaar / PAN)</strong><small>Mandatory</small></span></div>
          </div>
          <div className="nf-card nf-comp-demo"><h3>Activity Timeline <span>· live builds</span></h3>
            <ol className="nf-timeline" style={{ margin: 0 }}>
              <li className="is-done"><span className="nf-tl-marker">✓</span><span><strong>Task received</strong></span><span className="nf-tl-state">Complete</span></li>
              <li className="is-active"><span className="nf-tl-marker">◌</span><span><strong>Finding official sources</strong></span><span className="nf-tl-state">In progress</span></li>
              <li><span className="nf-tl-marker">3</span><span><strong>Building your roadmap</strong></span></li>
            </ol>
          </div>
          <div className="nf-card nf-comp-demo"><h3>Stat Card <span>· dashboards</span></h3>
            <div className="nf-stat" style={{ padding: 0 }}><span className="nf-stat-ic" style={{ background: 'var(--nf-green-soft)' }}>📄</span><div><b>3</b><small>Active Applications</small></div></div>
          </div>
        </div>
      </section>
    </main>
    <Footer onNavigate={onNavigate} />
  </div>;
}
