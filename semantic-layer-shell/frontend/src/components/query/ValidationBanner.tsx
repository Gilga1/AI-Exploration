import { StreamEvent } from "../../services/api";

const CONFIDENCE_STYLES: Record<string, { bg: string; color: string }> = {
  high: { bg: "#dcfce7", color: "#166534" },
  medium: { bg: "#fef3c7", color: "#92400e" },
  low: { bg: "#fee2e2", color: "#991b1b" },
};

export function ValidationBanner({ events }: { events: StreamEvent[] }) {
  const validationEvent = events.find((e) => e.event === "validation");
  const responseEvent = events.find((e) => e.event === "response");
  const validation =
    (validationEvent?.validation as Record<string, unknown>) ||
    ((responseEvent?.payload as Record<string, unknown>)?.validation as Record<string, unknown>);

  if (!validation) return null;

  const overall = String(validation.overall_confidence || "medium");
  const style = CONFIDENCE_STYLES[overall] || CONFIDENCE_STYLES.medium;
  const findings = (validation.findings as Array<Record<string, unknown>>) || [];
  const failed = findings.filter((f) => !f.passed);

  return (
    <div
      style={{
        marginTop: "1rem",
        padding: "0.75rem",
        borderRadius: "0.5rem",
        border: `1px solid ${style.color}`,
        background: style.bg,
      }}
    >
      <strong>
        Overall confidence: {overall.toUpperCase()}
      </strong>
      <p style={{ margin: "0.35rem 0" }}>
        {Number(validation.rules_passed)} / {Number(validation.rules_evaluated)} validation rules passed
      </p>
      {failed.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
          {failed.map((finding) => (
            <li key={String(finding.rule_id)}>
              {String(finding.rule_id)}: {String(finding.message)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
