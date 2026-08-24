import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { apiRequest, TraceDetail as TraceDetailData } from "../api/client";

const kindColors: Record<string, string> = {
  chain: "bg-cyan-400",
  retriever: "bg-violet-400",
  llm: "bg-amber-400",
  tool: "bg-emerald-400",
};

function SpanRow({
  span,
  traceStart,
  traceDuration,
}: {
  span: TraceDetailData["spans"][number];
  traceStart: number;
  traceDuration: number;
}) {
  const startOffset = new Date(span.start_time).getTime() - traceStart;
  const offsetPct = Math.min(100, Math.max(0, (startOffset / (traceDuration || 1)) * 100));
  const widthPct = Math.max(
    1.5,
    ((span.duration_ms || 0) / (traceDuration || 1)) * 100,
  );

  return (
    <div className="space-y-1 px-5 py-3">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium text-slate-200">{span.name}</span>
        <span className="shrink-0 tabular-nums text-xs text-slate-400">
          {span.duration_ms?.toFixed(2)} ms
        </span>
      </div>
      <div className="relative h-2.5 w-full rounded bg-slate-950/70">
        <div
          className={`absolute h-2.5 rounded ${kindColors[span.kind] ?? "bg-slate-500"}`}
          style={{ left: `${offsetPct}%`, width: `${widthPct}%` }}
          title={`${span.name} · ${span.kind} · ${span.duration_ms?.toFixed(2)} ms`}
        />
      </div>
      {Object.keys(span.attributes ?? {}).length > 0 && (
        <details className="text-xs text-slate-500">
          <summary className="cursor-pointer select-none hover:text-slate-300">
            attributes
          </summary>
          <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all text-[11px] leading-relaxed text-slate-400">
            {JSON.stringify(span.attributes, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

export default function TraceDetail() {
  const { traceId } = useParams<{ traceId: string }>();
  const [trace, setTrace] = useState<TraceDetailData>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!traceId) return;
    apiRequest<TraceDetailData>(`/api/v1/traces/${traceId}`)
      .then(setTrace)
      .catch((requestError) =>
        setError(requestError instanceof Error ? requestError.message : "Failed to load trace"),
      );
  }, [traceId]);

  const timeline = useMemo(() => {
    if (!trace?.spans?.length) return null;
    const start = new Date(trace.spans[0].start_time).getTime();
    let end = start;
    for (const span of trace.spans) end = Math.max(end, new Date(span.end_time).getTime());
    return { start, duration: end - start };
  }, [trace]);

  if (error)
    return <p className="rounded-md bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>;
  if (!trace) return <p className="text-sm text-slate-500">Loading trace…</p>;

  return (
    <section className="w-full max-w-4xl space-y-6">
      <Link
        to="/traces"
        className="inline-flex items-center gap-1.5 text-sm text-cyan-300 hover:text-cyan-200"
      >
        <ArrowLeft className="h-4 w-4" /> All traces
      </Link>

      <div className="rounded-lg border border-slate-800 bg-slate-900/70">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-5 py-4">
          <h1 className="font-semibold text-white">{trace.name}</h1>
          <div className="text-xs tabular-nums text-slate-400">
            {trace.duration_ms?.toFixed(1)} ms · {trace.status}
          </div>
        </div>
        <div className="divide-y divide-slate-800/70">
          {timeline &&
            trace.spans.map((span) => (
              <SpanRow
                key={span.id}
                span={span}
                traceStart={timeline.start}
                traceDuration={timeline.duration}
              />
            ))}
        </div>
      </div>

      {Object.keys(trace.attributes ?? {}).length > 0 && (
        <details className="rounded-lg border border-slate-800 bg-slate-900/70 p-4 text-sm">
          <summary className="cursor-pointer select-none font-medium text-slate-300">
            Trace attributes
          </summary>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all text-xs text-slate-400">
            {JSON.stringify(trace.attributes, null, 2)}
          </pre>
        </details>
      )}
    </section>
  );
}
