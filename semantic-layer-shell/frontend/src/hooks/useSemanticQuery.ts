import { useCallback, useState } from "react";
import { StreamEvent, streamNdjson } from "../services/api";

export type DisambiguationSelection = {
  entity_type: string;
  selected_key: string;
  selected_label?: string;
};

export function useSemanticQuery() {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<string>("");
  const [pendingMetricId, setPendingMetricId] = useState<string | undefined>();
  const [pendingRevisionHint, setPendingRevisionHint] = useState<string | undefined>();

  const runQuery = useCallback(
    async (
      question: string,
      metricId?: string,
      revisionHint?: string,
      disambiguation?: DisambiguationSelection,
    ) => {
      setLoading(true);
      setError(null);
      if (!disambiguation) {
        setEvents([]);
      }
      setPendingQuestion(question);
      setPendingMetricId(metricId);
      setPendingRevisionHint(revisionHint);
      try {
        for await (const event of streamNdjson("/api/v1/query/stream", {
          question,
          metric_id: metricId,
          revision_hint: revisionHint,
          disambiguation,
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

  const resumeWithDisambiguation = useCallback(
    (selection: DisambiguationSelection) => {
      if (!pendingQuestion) return;
      return runQuery(pendingQuestion, pendingMetricId, pendingRevisionHint, selection);
    },
    [pendingQuestion, pendingMetricId, pendingRevisionHint, runQuery],
  );

  return { events, loading, error, runQuery, resumeWithDisambiguation };
}
