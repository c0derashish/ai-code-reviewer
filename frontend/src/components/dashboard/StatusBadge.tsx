import type { AnalysisStatus } from "../../types";

const STATUS: Record<AnalysisStatus, { label: string; tone: string }> = {
  not_started: { label: "Not started", tone: "border-line text-muted" },
  running: { label: "Running", tone: "border-info/40 bg-info/15 text-info" },
  done: { label: "Completed", tone: "border-ok/40 bg-ok/15 text-ok" },
  failed: { label: "Failed", tone: "border-danger/40 bg-danger/15 text-danger" },
};

export default function StatusBadge({ status }: { status: AnalysisStatus }) {
  const { label, tone } = STATUS[status];

  return (
    <span className={`inline-flex rounded border px-2 py-0.5 text-xs font-medium ${tone}`}>
      {label}
    </span>
  );
}