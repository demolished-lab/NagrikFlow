export type CivicSource = string | {
  url: string;
  ok?: boolean;
  tier?: string;
  fetched_at?: string;
  error?: string;
};

// Explicit "type of service" categories (PSWB 02: task + location + service type)
export const SERVICE_TYPES = [
  'Business & Trade',
  'Certificates & Records',
  'Transport & Licences',
  'Property & Tax',
  'Welfare & Schemes',
  'Education & Skills',
  'Health & Family',
  'Other',
] as const;

export type PathwayStepPreview = {
  id: string;
  title: string;
  detail?: string;
  url?: string;
  type?: string;
};

export type PathwaySummary = {
  job_id: number;
  slug: string;
  title: string;
  city?: string;
  state?: string;
  status: 'queued' | 'running' | 'done' | 'verified' | 'review_required' | 'failed' | string;
  verified: boolean;
  verified_at?: string | null;
  steps: number;
  completed: number;
  completed_steps: string[];
  steps_preview: PathwayStepPreview[];
  sources: CivicSource[];
  created_at: string;
  error?: string;
};

export type UserProfile = {
  id?: number;
  email?: string;
  name?: string;
  city?: string;
  state?: string;
  role?: 'citizen' | 'admin' | string;
};
