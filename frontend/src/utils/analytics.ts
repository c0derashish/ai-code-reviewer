import type { AnalysisRecord, Severity } from "../types";
import { formatMonth } from "./format";
import { getLanguageLabel } from "./language";
import { SEVERITIES, SEVERITY_META } from "./severity";

export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "var(--danger)",
  high: "var(--chart-high)",
  medium: "var(--warn)",
  low: "var(--info)",
  info: "var(--text-muted)",
};

export function countIssues(record: AnalysisRecord): number {
  return SEVERITIES.reduce((sum, severity) => sum + record.issues[severity], 0);
}

type ScoredRecord = AnalysisRecord & { score: number };

// finished analyses that have a score
function scored(records: AnalysisRecord[]): ScoredRecord[] {
  return records.filter((r): r is ScoredRecord => r.status === "done" && r.score !== null);
}

export function getSummary(records: AnalysisRecord[]) {
  const done = scored(records);
  const projects = new Set(done.map((r) => r.projectName));
  const scoreTotal = done.reduce((sum, r) => sum + r.score, 0);

  return {
    analyses: done.length,
    projects: projects.size,
    files: done.reduce((sum, r) => sum + r.files, 0),
    issues: done.reduce((sum, r) => sum + countIssues(r), 0),
    avgScore: done.length > 0 ? Math.round(scoreTotal / done.length) : null,
  };
}

// average score per month, oldest first
export function getScoreTrend(records: AnalysisRecord[]) {
  const months = new Map<string, { total: number; count: number }>();

  for (const record of scored(records)) {
    const key = record.date.slice(0, 7); // "2026-10"
    const bucket = months.get(key) ?? { total: 0, count: 0 };
    bucket.total += record.score;
    bucket.count += 1;
    months.set(key, bucket);
  }

  return [...months.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, bucket]) => ({
      month: formatMonth(key),
      score: Math.round(bucket.total / bucket.count),
    }));
}

// issue totals per severity. "fill" is read by the donut chart
export function getSeverityTotals(records: AnalysisRecord[]) {
  const done = scored(records);

  return SEVERITIES.map((severity) => ({
    name: SEVERITY_META[severity].label,
    value: done.reduce((sum, r) => sum + r.issues[severity], 0),
    fill: SEVERITY_COLOR[severity],
  })).filter((item) => item.value > 0);
}

// how many analyses per language
export function getLanguageTotals(records: AnalysisRecord[]) {
  const counts = new Map<string, number>();
  for (const record of scored(records)) {
    counts.set(record.language, (counts.get(record.language) ?? 0) + 1);
  }

  return [...counts.entries()]
    .map(([id, analyses]) => ({ name: getLanguageLabel(id), analyses }))
    .sort((a, b) => b.analyses - a.analyses);
}

// average score per project, best first
export function getProjectScores(records: AnalysisRecord[]) {
  const projects = new Map<string, { total: number; count: number }>();

  for (const record of scored(records)) {
    const bucket = projects.get(record.projectName) ?? { total: 0, count: 0 };
    bucket.total += record.score;
    bucket.count += 1;
    projects.set(record.projectName, bucket);
  }

  return [...projects.entries()]
    .map(([name, bucket]) => ({ name, score: Math.round(bucket.total / bucket.count) }))
    .sort((a, b) => b.score - a.score);
}