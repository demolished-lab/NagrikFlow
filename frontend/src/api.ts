// Prod: set VITE_API_URL to the backend tunnel URL (e.g. https://api-xxx.trycloudflare.com).
// Dev: falls back to vite proxy (/api -> localhost:8000).
const API = (import.meta as any).env?.VITE_API_URL || '/api';

function headers(): Record<string, string> {
  const t = localStorage.getItem('civic_token');
  return { 'Content-Type': 'application/json', ...(t ? { Authorization: `Bearer ${t}` } : {}) };
}

export async function req(path: string, opts: RequestInit = {}) {
  const r = await fetch(API + path, { ...opts, headers: { ...headers(), ...(opts.headers || {}) } });
  if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: r.statusText }))).detail || r.statusText);
  return r.json();
}

export const api = {
  register: (b: object) => req('/auth/register', { method: 'POST', body: JSON.stringify(b) }),
  login: (b: object) => req('/auth/login', { method: 'POST', body: JSON.stringify(b) }),
  dashboard: () => req('/me/dashboard'),
  brief: () => req('/me/brief'),
  map: (slug: string) => req(`/maps/${slug}`),
  done: (map_slug: string, step_id: string) =>
    req('/me/progress', { method: 'POST', body: JSON.stringify({ map_slug, step_id }) }),
  progress: (map_slug: string) => req(`/me/progress/${encodeURIComponent(map_slug)}`),
  telegramLinkCode: () => req('/me/telegram/link-code', { method: 'POST' }),
  dlConnect: () => req('/auth/digilocker/connect'),
};
