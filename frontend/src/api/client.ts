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
