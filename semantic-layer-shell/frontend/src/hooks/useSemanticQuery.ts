import { useCallback, useState } from "react";
import { StreamEvent, streamNdjson } from "../services/api";

export function useSemanticQuery() {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runQuery = useCallback(
    async (question: string, metricId?: string, revisionHint?: string) => {
      setLoading(true);
      setError(null);
      setEvents([]);
      try {
        for await (const event of streamNdjson("/api/v1/query/stream", {
          question,
          metric_id: metricId,
          revision_hint: revisionHint,
        })) {
          setEvents((prev) => [...prev, event]);
          if (event.event === "error") {
            setError(String(event.error));
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Query failed");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return { events, loading, error, runQuery };
}
