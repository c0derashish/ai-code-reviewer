import type { AnalysisRecord, Severity } from "../types";

// MOCK DATA for the History and Analytics pages. Not real analyses.
// Phase 10: replace getHistory() and getAnalysis() with real backend calls.

const NONE: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };

const MOCK_RECORDS: AnalysisRecord[] = [
  { id: "a-101", projectName: "inventory-api", date: "2026-06-14T10:20:00Z", language: "python", files: 24, score: 58, status: "done", issues: { critical: 1, high: 4, medium: 9, low: 7, info: 3 } },
  { id: "a-102", projectName: "weather-cli", date: "2026-07-02T15:05:00Z", language: "go", files: 9, score: 81, status: "done", issues: { critical: 0, high: 1, medium: 3, low: 4, info: 2 } },
  { id: "a-103", projectName: "inventory-api", date: "2026-07-21T09:40:00Z", language: "python", files: 27, score: 64, status: "done", issues: { critical: 0, high: 3, medium: 8, low: 6, info: 3 } },
  { id: "a-104", projectName: "shop-frontend", date: "2026-08-05T18:12:00Z", language: "typescript", files: 56, score: 71, status: "done", issues: { critical: 0, high: 2, medium: 12, low: 15, info: 6 } },
  { id: "a-105", projectName: "chat-server", date: "2026-08-19T11:30:00Z", language: "java", files: 38, score: null, status: "failed", issues: NONE },
  { id: "a-106", projectName: "chat-server", date: "2026-08-19T12:02:00Z", language: "java", files: 38, score: 62, status: "done", issues: { critical: 1, high: 5, medium: 14, low: 11, info: 4 } },
  { id: "a-107", projectName: "shop-frontend", date: "2026-09-09T14:25:00Z", language: "typescript", files: 58, score: 76, status: "done", issues: { critical: 0, high: 1, medium: 9, low: 12, info: 5 } },
  { id: "a-108", projectName: "inventory-api", date: "2026-09-23T08:50:00Z", language: "python", files: 29, score: 72, status: "done", issues: { critical: 0, high: 2, medium: 6, low: 5, info: 2 } },
  { id: "a-109", projectName: "weather-cli", date: "2026-10-04T16:10:00Z", language: "go", files: 10, score: 86, status: "done", issues: { critical: 0, high: 0, medium: 2, low: 3, info: 1 } },
  { id: "a-110", projectName: "notes-app", date: "2026-10-17T13:35:00Z", language: "javascript", files: 15, score: 55, status: "done", issues: { critical: 2, high: 4, medium: 7, low: 6, info: 2 } },
  { id: "a-111", projectName: "shop-frontend", date: "2026-10-30T09:15:00Z", language: "typescript", files: 61, score: 83, status: "done", issues: { critical: 0, high: 0, medium: 7, low: 9, info: 4 } },
  { id: "a-112", projectName: "inventory-api", date: "2026-11-05T17:45:00Z", language: "python", files: 31, score: 79, status: "done", issues: { critical: 0, high: 1, medium: 5, low: 4, info: 2 } },
];

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// newest first
export async function getHistory(): Promise<AnalysisRecord[]> {
  await wait(400); // MOCK delay so the loading state is visible
  return [...MOCK_RECORDS].sort((a, b) => b.date.localeCompare(a.date));
}

export async function getAnalysis(id: string): Promise<AnalysisRecord | null> {
  await wait(300); // MOCK delay
  return MOCK_RECORDS.find((record) => record.id === id) ?? null;
}