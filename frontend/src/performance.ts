export type ApiMetric = {
  path: string;
  durationMs: number;
  ok: boolean;
  status: number;
  at: number;
};

export type ActivityMetric = {
  name: string;
  durationMs: number;
  status: 'completed' | 'failed' | 'timeout';
  at: number;
};

const apiMetrics: ApiMetric[] = [];
const activityMetrics: ActivityMetric[] = [];
const activityStarts = new Map<string, number>();

function notify() {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event('civic:performance-updated'));
}

export function recordApi(metric: ApiMetric) {
  apiMetrics.push(metric);
  if (apiMetrics.length > 100) apiMetrics.shift();
  notify();
}

export function beginActivity(name: string) {
  activityStarts.set(name, performance.now());
}

export function finishActivity(name: string, status: ActivityMetric['status']) {
  const started = activityStarts.get(name);
  if (started === undefined) return;
  activityStarts.delete(name);
  activityMetrics.push({ name, durationMs: Math.round(performance.now() - started), status, at: Date.now() });
  if (activityMetrics.length > 30) activityMetrics.shift();
  notify();
}

function percentile(values: number[], percentileValue: number) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.ceil(sorted.length * percentileValue) - 1)];
}

export function snapshot() {
  const navigation = typeof performance !== 'undefined'
    ? performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined
    : undefined;
  const apiDurations = apiMetrics.map((metric) => metric.durationMs);
  const activityDurations = activityMetrics.map((metric) => metric.durationMs);
  return {
    capturedAt: Date.now(),
    navigation: {
      domContentLoadedMs: Math.round(navigation?.domContentLoadedEventEnd || 0),
      loadMs: Math.round(navigation?.loadEventEnd || 0),
      responseMs: Math.round(navigation?.responseEnd || 0),
      transferSize: navigation?.transferSize || 0,
    },
    api: {
      count: apiMetrics.length,
      errors: apiMetrics.filter((metric) => !metric.ok).length,
      avgMs: apiDurations.length ? Math.round(apiDurations.reduce((sum, value) => sum + value, 0) / apiDurations.length) : 0,
      p95Ms: Math.round(percentile(apiDurations, .95)),
      recent: [...apiMetrics].slice(-8).reverse(),
    },
    activity: {
      count: activityMetrics.length,
      avgMs: activityDurations.length ? Math.round(activityDurations.reduce((sum, value) => sum + value, 0) / activityDurations.length) : 0,
      p95Ms: Math.round(percentile(activityDurations, .95)),
      recent: [...activityMetrics].slice(-8).reverse(),
    },
  };
}

export type PerformanceSnapshot = ReturnType<typeof snapshot>;
