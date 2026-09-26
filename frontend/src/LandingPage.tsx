import React, { useEffect, useState } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';

interface LandingProps {
  onLogin: () => void;
}

export default function LandingPage({ onLogin }: LandingProps) {
  const t = STR[lang()];
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    // Check if user is already logged in
    const token = localStorage.getItem('civic_token');
    if (token) {
      onLogin();
    } else {
      setLoading(false);
    }
  }, [onLogin]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div className="skeleton" style={{ width: 200, height: 200, borderRadius: '50%' }} />
      </div>
    );
  }

  return (
    <div className="cv-anim-up">
      {/* Tricolor top bar */}
      <div className="tricolor-bar" style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100 }} />
      
      {/* Navigation */}
      <nav style={{ 
        background: 'rgba(255,255,255,0.95)', 
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--color-border)',
        padding: 'var(--space-4) var(--space-6)',
        position: 'sticky',
        top: 4,
        zIndex: 99,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <div className="tricolor-bar-thin" style={{ width: 40, height: 3 }} />
          <span style={{ fontWeight: 700, fontSize: 18, color: 'var(--color-indigo)' }}>
            {t.appTitle}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button className="btn btn-ghost" onClick={onLogin}>
            {t.login}
          </button>
          <button className="btn btn-primary" onClick={onLogin}>
            {t.register}
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <section style={{
        padding: 'var(--space-20) var(--space-6)',
        textAlign: 'center',
        background: 'linear-gradient(180deg, var(--color-bg-secondary) 0%, var(--color-bg) 100%)',
      }}>
        <h1 style={{
          fontSize: 'clamp(32px, 5vw, 56px)',
          fontWeight: 700,
          color: 'var(--color-indigo)',
          marginBottom: 'var(--space-4)',
          lineHeight: 1.2,
        }}>
          {t.appSubtitle}
        </h1>
        <p style={{
          fontSize: 'clamp(18px, 2vw, 24px)',
          color: 'var(--color-text-secondary)',
          maxWidth: 600,
          margin: '0 auto var(--space-8)',
          lineHeight: 1.6,
        }}>
          {t.tagline}
        </p>
        <div style={{ display: 'flex', gap: 'var(--space-4)', justifyContent: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" style={{ padding: 'var(--space-4) var(--space-8)', fontSize: 16 }} onClick={onLogin}>
            {t.register} →
          </button>
          <button className="btn btn-ghost" style={{ padding: 'var(--space-4) var(--space-8)', fontSize: 16 }} onClick={onLogin}>
            Learn More
          </button>
        </div>
        
        {/* Trust badges */}
        <div style={{ 
          marginTop: 'var(--space-12)',
          display: 'flex',
          justifyContent: 'center',
          gap: 'var(--space-8)',
          flexWrap: 'wrap',
          opacity: 0.7,
        }}>
          <TrustBadge icon="🔒" text="DPDP Compliant" />
          <TrustBadge icon="🇮🇳" text="Digital India" />
          <TrustBadge icon="✓" text="Consent-Based" />
        </div>
      </section>

      {/* Features Grid */}
      <section style={{ padding: 'var(--space-16) var(--space-6)', maxWidth: 1200, margin: '0 auto' }}>
        <h2 style={{ textAlign: 'center', fontSize: 32, fontWeight: 700, marginBottom: 'var(--space-12)', color: 'var(--color-indigo)' }}>
          What You Get
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-6)' }}>
          <FeatureCard 
            icon="🗺️"
            title="Smart Roadmaps"
            desc="Visual, step-by-step guidance for any government service"
          />
          <FeatureCard 
            icon="🔐"
            title="Consent-First Privacy"
            desc="Your data, your control. Export or delete anytime under DPDP Act"
          />
          <FeatureCard 
            icon="🤖"
            title="AI Assistant"
            desc="Built-in mini-Hermes agent to help with any question or task"
          />
          <FeatureCard 
            icon="📱"
            title="Telegram Alerts"
            desc="Get step reminders and updates via Telegram bot"
          />
          <FeatureCard 
            icon="🏛️"
            title="Verified Sources"
            desc="All information comes directly from official .gov websites"
          />
          <FeatureCard 
            icon="🌐"
            title="Bilingual Support"
            desc="Full Hindi and English interface with proper Devanagari rendering"
          />
        </div>
      </section>

      {/* Stats Section */}
      <section style={{ 
        background: 'var(--color-indigo)',
        color: 'white',
        padding: 'var(--space-12) var(--space-6)',
      }}>
        <div style={{ 
          maxWidth: 1000, 
          margin: '0 auto',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--space-8)',
          textAlign: 'center',
        }}>
          <Stat number="29+" label="Tests Passing" />
          <Stat number="100%" label="Consent-Based" />
          <Stat number="2" label="Languages" />
          <Stat number="24/7" label="Availability" />
        </div>
      </section>

      {/* CTA Section */}
      <section style={{ padding: 'var(--space-16) var(--space-6)', textAlign: 'center' }}>
        <h2 style={{ fontSize: 28, fontWeight: 700, marginBottom: 'var(--space-4)' }}>
          Ready to Navigate?
        </h2>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-6)' }}>
          Join thousands of citizens using civic-pathfinder to access government services
        </p>
        <button className="btn btn-primary" style={{ padding: 'var(--space-4) var(--space-10)', fontSize: 18 }} onClick={onLogin}>
          Get Started →
        </button>
      </section>

      {/* Footer */}
      <footer style={{ 
        background: 'var(--color-bg-tertiary)',
        padding: 'var(--space-8) var(--space-6)',
        borderTop: '1px solid var(--color-border)',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', textAlign: 'center' }}>
          <div className="tricolor-bar-thin" style={{ width: 60, margin: '0 auto var(--space-4)' }} />
          <p style={{ color: 'var(--color-text-muted)', fontSize: 14 }}>
            {t.footer || 'An initiative supporting Digital India. DPDP Act compliant.'}
          </p>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 12, marginTop: 'var(--space-2)' }}>
            {t.disclaimer || 'Informational purposes only. Verify with official government sources.'}
          </p>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <div className="cv-card" style={{ padding: 'var(--space-6)' }}>
      <div style={{ fontSize: 32, marginBottom: 'var(--space-3)' }}>{icon}</div>
      <h3 style={{ fontWeight: 600, marginBottom: 'var(--space-2)', color: 'var(--color-indigo)' }}>
        {title}
      </h3>
      <p style={{ color: 'var(--color-text-secondary)', fontSize: 14, lineHeight: 1.6 }}>
        {desc}
      </p>
    </div>
  );
}

function Stat({ number, label }: { number: string; label: string }) {
  return (
    <div>
      <div style={{ fontSize: 40, fontWeight: 700, marginBottom: 'var(--space-2)' }}>{number}</div>
      <div style={{ opacity: 0.8, fontSize: 14 }}>{label}</div>
    </div>
  );
}

function TrustBadge({ icon, text }: { icon: string; text: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 14, color: 'var(--color-text-muted)' }}>
      <span style={{ fontSize: 20 }}>{icon}</span>
      <span>{text}</span>
    </div>
  );
}
