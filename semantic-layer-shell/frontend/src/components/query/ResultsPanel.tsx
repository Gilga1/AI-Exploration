import { StreamEvent } from "../../services/api";

const MAX_DISPLAY_ROWS = 1000;

export function ResultsPanel({ events }: { events: StreamEvent[] }) {
  const dataEvent = [...events].reverse().find((e) => e.event === "data_rows");
  const answer = events.filter((e) => e.event === "token").map((e) => String(e.delta)).join("");

  const rows = (dataEvent?.rows as Record<string, unknown>[]) || [];
  const columns = (dataEvent?.columns as string[]) || [];
  const truncated = Boolean(dataEvent?.truncated);
  const rowCount = Number(dataEvent?.row_count ?? rows.length);

  return (
    <div style={{ marginTop: "1rem" }}>
      <h3>Results</h3>
      {answer && <p>{answer}</p>}
      {dataEvent && (
        <p style={{ color: "#475569", fontSize: "0.9rem" }}>
          Showing {Math.min(rows.length, MAX_DISPLAY_ROWS)} of {rowCount} row(s)
          {truncated ? " (truncated at server limit)" : ""}
        </p>
      )}
      {rows.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, MAX_DISPLAY_ROWS).map((row, i) => (
                <tr key={i}>
                  {columns.map((c) => (
                    <td key={c}>{String(row[c] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!dataEvent && !answer && <p>No results yet.</p>}
    </div>
  );
}
