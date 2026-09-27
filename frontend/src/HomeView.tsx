import React, { useState, useCallback } from 'react';
import { api } from './api';
import { STR, lang } from './i18n';

interface BuildState {
  status: 'idle' | 'discovering' | 'building' | 'done' | 'failed';
  slug: string | null;
  jobId: number | null;
  task: string;
  steps: any[];
  sources: any[];
  error: string;
}

export default function HomeView() {
  const t = STR[lang()];
  const [task, setTask] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [build, setBuild] = useState<BuildState>({
    status: 'idle',
    slug: null,
    jobId: null,
    task: '',
    steps: [],
    sources: [],
    error: '',
  });

  const pollJob = useCallback(async (jobId: number, initialSlug: string) => {
    const poll = setInterval(async () => {
      try {
        const status = await api.jobStatus(jobId);
        if (status.status === 'done') {
          clearInterval(poll);
          const slug = status.result?.slug || initialSlug;
          setBuild(prev => ({ ...prev, status: 'done', slug }));
        } else if (status.status === 'failed') {
          clearInterval(poll);
          setBuild(prev => ({ 
            ...prev, 
            status: 'failed', 
            error: status.result?.error || 'Build failed' 
          }));
        }
      } catch {
        clearInterval(poll);
        setBuild(prev => ({ ...prev, status: 'failed', error: 'Polling error' }));
      }
    }, 2000);
    
    // Timeout after 3 minutes
    setTimeout(() => clearInterval(poll), 180000);
  }, []);

  const handleBuild = async () => {
    if (!task.trim()) return;
    
    setBuild({ status: 'discovering', slug: null, jobId: null, task, steps: [], sources: [], error: '' });
    
    try {
      // Step 1: Submit build task to backend
      const result = await api.buildTask(task, city, state);
      
      setBuild(prev => ({ 
        ...prev, 
        status: 'building', 
        jobId: result.job_id,
        slug: result.slug 
      }));
      
      // Step 2: Start polling
      pollJob(result.job_id, result.slug);
      
    } catch (e: any) {
      setBuild({ status: 'failed', slug: null, jobId: null, task, steps: [], sources: [], error: String(e.message || e) });
    }
  };

  const navigateToRoadmap = () => {
    if (build.slug) {
      window.location.hash = `/roadmap/${build.slug}`;
    }
  };

  const getStatusMessage = () => {
    switch (build.status) {
      case 'discovering': return 'Discovering government sources...';
      case 'building': return 'Building your verified path...';
      case 'done': return 'Path ready!';
      case 'failed': return build.error;
      default: return '';
    }
  };

  return (
    <div className="cv-home-view cv-anim-up">
      {/* Task Input Section */}
      <section className="cv-task-composer">
        <div className="cv-eyebrow">{t.buildPath || 'DESCRIBE YOUR CIVIC TASK'}</div>
        <div className="cv-task-row">
          <div className="cv-task-input-wrap">
            <span className="cv-inline-icon">⌕</span>
            <input
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder={t.pathInputPlaceholder || "e.g., I want to get a new water connection..."}
              aria-label="Civic task"
              className="cv-task-input"
              disabled={build.status === 'discovering' || build.status === 'building'}
            />
          </div>
          <button 
            className="cv-build-btn" 
            onClick={handleBuild}
            disabled={build.status === 'discovering' || build.status === 'building' || !task.trim()}
          >
            {build.status === 'building' || build.status === 'discovering' ? 'Processing...' : `${t.buildPath || 'Build verified path'} →`}
          </button>
        </div>
        <div className="cv-city-row">
          <input
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="City (optional)"
            className="cv-city-input"
            disabled={build.status === 'discovering' || build.status === 'building'}
          />
          <input
            value={state}
            onChange={(e) => setState(e.target.value)}
            placeholder="State (optional)"
            className="cv-state-input"
            disabled={build.status === 'discovering' || build.status === 'building'}
          />
        </div>
        <p className="cv-helper">{t.rmDesc || 'Plain-language task → verified government workflow'}</p>
        
        {(build.status === 'discovering' || build.status === 'building') && (
          <div className="cv-building-status">
            <span className="cv-spinner"></span>
            <span>{getStatusMessage()}</span>
          </div>
        )}
        
        {build.status === 'failed' && (
          <div className="cv-error-msg">{build.error}</div>
        )}
      </section>

      {/* Success State - Navigate to Roadmap */}
      {build.status === 'done' && build.slug && (
        <section className="cv-path-card cv-animated-in">
          <div className="cv-path-heading">
            <div>
              <div className="cv-path-title">
                <span className="cv-check-circle">✓</span> Your Path is Ready
              </div>
              <div className="cv-path-meta">
                {build.task} • Generated at {new Date().toLocaleString()}
              </div>
            </div>
            <span className="cv-verified-pill">✓ BUILT</span>
          </div>
          
          <div className="cv-action-row">
            <button className="cv-btn cv-btn-primary cv-btn-lg" onClick={navigateToRoadmap}>
              View Full Roadmap →
            </button>
          </div>
          
          <p className="cv-note">This will take you to the interactive roadmap where you can track progress.</p>
        </section>
      )}
    </div>
  );
}
