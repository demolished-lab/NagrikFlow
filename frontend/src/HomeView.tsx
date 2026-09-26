import React from 'react';

export default function HomeView() {
  return (
    <div className="cv-home-view">
      <h2 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 24px 0' }}>🏠 Home Overview</h2>
      <div className="cv-feature-grid">
        {[
          { icon: '🗺️', title: 'Build Path', desc: 'Describe any civic task in plain words and get a verified step-by-step roadmap.' },
          { icon: '🔐', title: 'Connect DigiLocker', desc: 'Consent-based import of your verified documents. You approve on the official site.' },
          { icon: '🤖', title: 'Hermes Agent', desc: 'Ask the built-in AI agent to fix bugs, add features, or explore the codebase.' },
          { icon: '📱', title: 'Telegram Alerts', desc: 'One bot for everyone; your chat links only to your account via a one-time code.' },
        ].map((f, i) => (
          <div key={i} className="cv-feature-card">
            <div className="cv-feature-icon">{f.icon}</div>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
