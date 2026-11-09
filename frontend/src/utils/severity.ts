import type { Issue, IssueCategory, Severity } from "../types";

// most serious first
export const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEVERITY_META: Record<Severity, { label: string; badge: string; dot: string }> = {
  critical: { label: "Critical", badge: "border-danger bg-danger text-white", dot: "bg-danger" },
  high: { label: "High", badge: "border-danger/40 bg-danger/15 text-danger", dot: "bg-danger" },
  medium: { label: "Medium", badge: "border-warn/40 bg-warn/15 text-warn", dot: "bg-warn" },
  low: { label: "Low", badge: "border-info/40 bg-info/15 text-info", dot: "bg-info" },
  info: { label: "Info", badge: "border-line bg-main/10 text-muted", dot: "bg-muted" },
};

export const CATEGORY_LABEL: Record<IssueCategory, string> = {
  security: "Security",
  bug: "Bug",
  complexity: "Complexity",
  maintainability: "Maintainability",
  code_smell: "Code smell",
  performance: "Performance",
  style: "Style",
};

// sort: severity, then file, then line
export function compareIssues(a: Issue, b: Issue) {
  const rank = SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity);
  if (rank !== 0) return rank;
  if (a.filePath !== b.filePath) return a.filePath.localeCompare(b.filePath);
  return a.line - b.line;
}