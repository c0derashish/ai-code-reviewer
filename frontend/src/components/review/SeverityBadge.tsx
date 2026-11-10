import type { Severity } from "../../types";
import { SEVERITY_META } from "../../utils/severity";

export default function SeverityBadge({ severity }: { severity: Severity }) {
  const meta = SEVERITY_META[severity];

  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium ${meta.badge}`}
    >
      {meta.label}
    </span>
  );
}