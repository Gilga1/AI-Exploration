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

export interface RagMetricSummary {
  name: string;
  avg_score: number | null;
  cases_scored: number;
  status: "passed" | "failed" | "no-data";
}

export interface RagMetricTraceRow {
  trace_id: string;
  metric: string;
  score: number | null;
  status: string;
  reasoning?: string | null;
  scored_at?: string | null;
}

export interface RagMetrics {
  summary: RagMetricSummary[];
  total_traces_scored: number;
  per_trace?: RagMetricTraceRow[];
}

export function getRagMetrics(perTrace = false): Promise<RagMetrics> {
  return apiRequest<RagMetrics>(`/api/v1/metrics/rag${perTrace ? "?per_trace=true" : ""}`);
}

export interface AgentMetricSummary {
  name: string;
  avg_score: number | null;
  cases_scored: number;
  status: "passed" | "failed" | "no-data";
}

export interface AgentRunRow {
  trace_id: string;
  tool_correctness: number | null;
  task_success: boolean;
  loop_efficiency: number | null;
  classification: "efficient" | "thrashing";
}

export interface AgentMetrics {
  summary: AgentMetricSummary[];
  total_agent_traces_scored: number;
  runs: AgentRunRow[];
}

export function getAgentMetrics(): Promise<AgentMetrics> {
  return apiRequest<AgentMetrics>("/api/v1/metrics/agent");
}
