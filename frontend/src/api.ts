import { recordApi } from './performance';

// Prod: set VITE_API_URL to the backend URL. Dev: Vite proxies /api to localhost:8000.
const API = (import.meta as any).env?.VITE_API_URL || '/api';

function headers(): Record<string, string> {
  const t = localStorage.getItem('civic_token');
  return { 'Content-Type': 'application/json', ...(t ? { Authorization: `Bearer ${t}` } : {}) };
}

export async function req(path: string, opts: RequestInit = {}): Promise<any> {
  const started = performance.now();
  try {
    const r = await fetch(API + path, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } });
    recordApi({ path, durationMs: Math.round(performance.now() - started), ok: r.ok, status: r.status, at: Date.now() });
    if (!r.ok) {
      const body = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(body.detail || r.statusText);
    }
    return r.json();
  } catch (error) {
    if (error instanceof TypeError) recordApi({ path, durationMs: Math.round(performance.now() - started), ok: false, status: 0, at: Date.now() });
    throw error;
  }
}

export const api = {
  register: (b: object) => req('/auth/register', { method: 'POST', body: JSON.stringify(b) }),
  login: (b: object) => req('/auth/login', { method: 'POST', body: JSON.stringify(b) }),
  dashboard: () => req('/me/dashboard'),
  profile: () => req('/me/profile'),
  brief: () => req('/me/brief'),
  myPathways: () => req('/me/pathways'),
  map: (slug: string, filters: Record<string, string> = {}) => {
    const query = new URLSearchParams(
      Object.entries(filters).filter(([, value]) => Boolean(value)),
    ).toString();
    return req(`/maps/${encodeURIComponent(slug)}${query ? `?${query}` : ''}`);
  },
  done: (map_slug: string, step_id: string) =>
    req('/me/progress', { method: 'POST', body: JSON.stringify({ map_slug, step_id }) }),
  progress: (map_slug: string) => req(`/me/progress/${encodeURIComponent(map_slug)}`),
  milestones: (map_slug: string) => req(`/me/milestones/${encodeURIComponent(map_slug)}`),
  notifications: () => req('/me/notifications'),
  readNotification: (id: number) => req(`/me/notifications/${id}/read`, { method: 'POST' }),
  progressReport: () => fetch(`${API}/me/progress-report.pdf`, { headers: headers() }),
  telegramLinkCode: () => req('/me/telegram/link-code', { method: 'POST' }),
  dlConnect: () => req('/auth/digilocker/connect'),
  // Build task (dynamic civic path generation)
  buildTask: (task: string, city?: string, state?: string, serviceType?: string) =>
    req('/build-task', {
      method: 'POST',
      body: JSON.stringify({ task, city, state, service_type: serviceType || '' }),
    }),
  jobStatus: (jobId: number) => req(`/jobs/${jobId}`),
  taskMap: (slug: string) => req(`/task/${encodeURIComponent(slug)}`),
  adminMetrics: () => req('/admin/metrics'),
  // Path-workflow packet (steps + checklist + sources/guides)
  taskPacket: (slug: string) => req(`/task/${encodeURIComponent(slug)}/packet`),
  deliverPacket: (slug: string) =>
    req(`/task/${encodeURIComponent(slug)}/deliver`, { method: 'POST' }),
  downloadPacketMd: async (slug: string) => {
    const r = await fetch(`${API}/task/${encodeURIComponent(slug)}/packet.md`, { headers: headers() });
    if (!r.ok) {
      const body = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(body.detail || r.statusText);
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${slug}-packet.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
  // Admin per-step editing (review, validate, update extracted info)
  adminSteps: (slug: string) => req(`/admin/maps/${encodeURIComponent(slug)}/steps`),
  adminUpdateStep: (slug: string, stepId: string, body: object) =>
    req(`/admin/maps/${encodeURIComponent(slug)}/steps/${encodeURIComponent(stepId)}`,
      { method: 'PUT', body: JSON.stringify(body) }),
  adminAddStep: (slug: string, body: object) =>
    req(`/admin/maps/${encodeURIComponent(slug)}/steps`, { method: 'POST', body: JSON.stringify(body) }),
  adminDeleteStep: (slug: string, stepId: string) =>
    req(`/admin/maps/${encodeURIComponent(slug)}/steps/${encodeURIComponent(stepId)}`, { method: 'DELETE' }),
  // Agent API
  agentRun: (task: string, mode: string, budget: number) =>
    req('/agent/run', { method: 'POST', body: JSON.stringify({ task, mode, budget }) }),  agentResult: (jobId: number) => req(`/agent/result/${jobId}`),
  agentTools: () => req('/agent/tools'),
  agentAudit: (n: number) => req(`/agent/audit?n=${n}`),
  // Hermes API
  hermesRun: (task: string, mode: string, budget: number) =>
    req('/hermes/run', { method: 'POST', body: JSON.stringify({ task, mode, budget }) }),
  hermesResult: (jobId: number) => req(`/hermes/result/${jobId}`),
  hermesTools: () => req('/hermes/tools'),
  hermesAudit: (n: number) => req(`/hermes/audit?n=${n}`),
  hermesSpawn: (parentJobId: number, tasks: any[]) =>
    req('/hermes/spawn', { method: 'POST', body: JSON.stringify({ parent_job_id: parentJobId, tasks }) }),
  hermesSubResult: (subId: number) => req(`/hermes/sub/${subId}`),
};
