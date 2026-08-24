export interface ScoreMetric {
  name: string;
  status: "passed" | "partial" | "failed" | "skipped";
  score: number | null;
  reason?: string;
  cases_scored?: number;
}

export interface EvaluationScorecard {
  status: "completed" | "partial" | "skipped";
  dataset: string;
  total_cases: number;
  llm_provider: string;
  metrics: ScoreMetric[];
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function runEvaluation(): Promise<EvaluationScorecard> {
  return apiRequest<EvaluationScorecard>("/api/v1/eval/run", { method: "POST" });
}

export interface TraceSummary {
  id: string;
  name: string;
  start_time: string | null;
  end_time: string | null;
  duration_ms: number | null;
  status: string;
  attributes: Record<string, unknown>;
}

export interface TraceSpan {
  id: string;
  trace_id: string;
  parent_span_id: string | null;
  name: string;
  kind: string;
  start_time: string;
  end_time: string;
  duration_ms: number | null;
  status: string;
  attributes: Record<string, unknown>;
}

export interface TraceDetail extends TraceSummary {
  spans: TraceSpan[];
}

export function listTraces(): Promise<TraceSummary[]> {
  return apiRequest<TraceSummary[]>("/api/v1/traces");
}

export function getTrace(traceId: string): Promise<TraceDetail> {
  return apiRequest<TraceDetail>(`/api/v1/traces/${traceId}`);
}
