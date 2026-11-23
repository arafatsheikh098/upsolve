// Typed client for the Upsolve API. Types mirror backend/app/schemas.py.

export interface ProblemRef {
  id: string;
  name: string;
  rating: number | null;
  tags: string[];
  url: string | null;
}

export interface HandleOut {
  handle: string;
  rating: number | null;
  max_rating: number | null;
  rank: string | null;
  max_rank: string | null;
  avatar: string | null;
  sync_state: "idle" | "queued" | "syncing" | "ready" | "error";
  sync_error: string | null;
  last_synced_at: string | null;
}

export interface SyncStatus extends HandleOut {
  submissions: number;
}

export type SkillLabel = "weak" | "average" | "strong" | "insufficient";

export interface TagSkill {
  tag: string;
  delta: number;
  sd: number;
  ci_low: number;
  ci_high: number;
  level: number;
  exposure: number;
  attempts: number;
  solved: number;
  label: SkillLabel;
}

export interface Weakness {
  tag: string;
  score: number;
  kinds: ("skill" | "coverage")[];
  summary: string;
  delta: number;
  ci_low: number;
  ci_high: number;
  label: SkillLabel;
  importance: number;
  pool_share: number;
  user_share: number;
  evidence: {
    attempts: number;
    solved: number;
    solve_rate: number | null;
    avg_wrong_before_ac: number | null;
    hardest_solved: ProblemRef | null;
    recent_failures: ProblemRef[];
  };
}

export interface History {
  dates: string[];
  level: number[];
  tags: Record<string, (number | null)[]>;
}

export interface WeekStat {
  week_start: string;
  solved: number;
}

export interface Analysis {
  handle: HandleOut;
  overview: {
    attempts: number;
    solved: number;
    submissions: number;
    level: number;
    level_sd: number;
    comfort_median: number | null;
    comfort_p80: number | null;
    upsolve: { failed_in_contest: number; upsolved: number; rate: number | null };
    verdicts: Record<string, number>;
    languages: Record<string, number>;
  };
  skills: TagSkill[];
  weaknesses: Weakness[];
  rating_history: { at: string; rating: number; contest_id: number; contest_name: string }[];
  by_rating: { rating: number; attempted: number; solved: number }[];
  weekly: WeekStat[];
  history: History;
  model: {
    anchor: number;
    iterations: number;
    converged: boolean;
    half_life_attempts: number;
    prior_sd: number;
  };
}

export type RecKind = "weak" | "stretch" | "upsolve";

export interface Recommendation {
  problem: ProblemRef;
  kind: RecKind;
  focus_tag: string | null;
  reason: string;
  predicted: number;
}

export interface PlanItem extends Recommendation {
  id: number;
  status: "todo" | "solved" | "skipped";
  solved_at: string | null;
}

export interface Plan {
  day: string;
  items: PlanItem[];
  streak: number;
  solved_today: number;
}

export interface Goals {
  target_rating: number | null;
  daily_count: number;
  focus_tags: string[];
}

export interface Progress {
  history: History;
  weekly: WeekStat[];
  streak: number;
  plan_days: number;
  plan_solved: number;
}

export interface CompareSide {
  handle: HandleOut;
  level: number;
  skills: TagSkill[];
}

export interface VerifyStart {
  verification_id: string;
  handle: string;
  problem: ProblemRef;
  submit_url: string | null;
  expires_at: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      credentials: "same-origin",
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
      ...init,
    });
  } catch {
    throw new ApiError(0, "Can't reach the Upsolve server. Is it running?");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? (detail[0]?.msg ?? "Invalid request.")
          : `Request failed (${res.status}).`;
    throw new ApiError(res.status, message);
  }
  return body as T;
}

const enc = encodeURIComponent;

export const api = {
  sync: (h: string, force = false) =>
    request<SyncStatus>(`/handles/${enc(h)}/sync${force ? "?force=true" : ""}`, { method: "POST" }),
  status: (h: string) => request<SyncStatus>(`/handles/${enc(h)}/status`),
  analysis: (h: string) => request<Analysis>(`/handles/${enc(h)}/analysis`),
  recommendations: (h: string, n = 4) =>
    request<{ day: string; items: Recommendation[] }>(`/handles/${enc(h)}/recommendations?n=${n}`),
  compare: (a: string, b: string) =>
    request<{ a: CompareSide; b: CompareSide }>(`/compare?a=${enc(a)}&b=${enc(b)}`),

  me: () => request<{ handle: string; verified_at: string }>("/auth/me"),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  verifyStart: (handle: string) =>
    request<VerifyStart>("/auth/verify/start", { method: "POST", body: JSON.stringify({ handle }) }),
  verifyCheck: (verification_id: string) =>
    request<{ verified: boolean; message: string; handle: string | null }>("/auth/verify/check", {
      method: "POST",
      body: JSON.stringify({ verification_id }),
    }),

  plan: () => request<Plan>("/me/plan/today"),
  setItemStatus: (id: number, status: "todo" | "skipped") =>
    request<PlanItem>(`/me/plan/items/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  goals: () => request<Goals>("/me/goals"),
  saveGoals: (g: Goals) => request<Goals>("/me/goals", { method: "PUT", body: JSON.stringify(g) }),
  progress: () => request<Progress>("/me/progress"),
};
