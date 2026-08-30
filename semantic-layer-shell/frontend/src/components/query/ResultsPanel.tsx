import { StreamEvent } from "../../services/api";

export function ResultsPanel({ events }: { events: StreamEvent[] }) {
  const dataEvent = [...events].reverse().find((e) => e.event === "data_rows");
  const answer = events.filter((e) => e.event === "token").map((e) => String(e.delta)).join("");

  return (
    <div style={{ marginTop: "1rem" }}>
      <h3>Results</h3>
      {answer && <p>{answer}</p>}
      {dataEvent && Array.isArray(dataEvent.rows) && (
        <table>
          <thead>
            <tr>
              {Array.isArray(dataEvent.columns) &&
                dataEvent.columns.map((c) => <th key={String(c)}>{String(c)}</th>)}
            </tr>
          </thead>
          <tbody>
            {(dataEvent.rows as Record<string, unknown>[]).slice(0, 20).map((row, i) => (
              <tr key={i}>
                {Array.isArray(dataEvent.columns) &&
                  dataEvent.columns.map((c) => <td key={String(c)}>{String(row[String(c)] ?? "")}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!dataEvent && !answer && <p>No results yet.</p>}
    </div>
  );
}
