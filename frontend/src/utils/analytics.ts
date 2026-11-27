import type { Severity } from "../types";

export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "var(--danger)",
  high: "var(--chart-high)",
  medium: "var(--warn)",
  low: "var(--info)",
  info: "var(--text-muted)",
};