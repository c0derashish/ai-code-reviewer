import type { ProjectFile, Severity } from "../types";
import type { AnalyticsData, HistoryDetail, HistoryItem, LicenceInfo } from "../types/history";
import type { IssueDto } from "../types/api";
import { SEVERITIES } from "../utils/severity";
import { ApiError, apiRequest } from "./api";
import { toIssues } from "./analysisService";
import { toProjectFiles } from "./repositoryService";

const UNEXPECTED = "The server sent an unexpected answer.";
const GITHUB_URL = /^https:\/\/github\.com\/[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/;

type Raw = Record<string, unknown>;

function isObject(value: unknown): value is Raw {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, max: number): string | null {
  return typeof value === "string" ? value.slice(0, max) : null;
}

function whole(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0;
}

function decimal(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function severityCounts(value: unknown): Record<Severity, number> {
  const source = isObject(value) ? value : {};
  const counts = {} as Record<Severity, number>;
  for (const severity of SEVERITIES) counts[severity] = whole(source[severity]);
  return counts;
}

function toLicence(value: unknown): LicenceInfo | null {
  if (!isObject(value)) return null;
  return {
    status: text(value.status, 20) ?? "error",
    spdxId: text(value.spdx_id, 50),
    name: text(value.name, 100),
  };
}

function toHistoryItem(value: unknown): HistoryItem | null {
  if (!isObject(value)) return null;

  const id = text(value.id, 40);
  const projectName = text(value.project_name, 200);
  const createdAt = text(value.created_at, 40);
  if (!id || !projectName || !createdAt) return null;

  // the link is shown as a real link, so only a plain github.com address is accepted
  const repoUrl =
    typeof value.repo_url === "string" && GITHUB_URL.test(value.repo_url) ? value.repo_url : null;

  return {
    id,
    projectId: text(value.project_id, 40) ?? "",
    projectName,
    source: value.source === "github" ? "github" : "upload",
    repoUrl,
    createdAt,
    scope: text(value.scope, 20) ?? "project",
    primaryLanguage: text(value.primary_language, 30),
    files: whole(value.files),
    filesAnalyzed: whole(value.files_analyzed),
    loc: whole(value.loc),
    issueCount: whole(value.issue_count),
    ruleIssueCount: whole(value.rule_issue_count),
    severityCounts: severityCounts(value.severity_counts),
    storage: value.storage === "link_only" ? "link_only" : "full",
    storageReason: text(value.storage_reason, 300),
    licence: toLicence(value.licence),
  };
}

export async function getHistory(): Promise<HistoryItem[]> {
  const data = await apiRequest<unknown>("/history?limit=100");
  if (!Array.isArray(data)) throw new ApiError("bad_response", UNEXPECTED);

  const items: HistoryItem[] = [];
  for (const raw of data) {
    const item = toHistoryItem(raw);
    if (item) items.push(item);
  }
  return items;
}

export async function getHistoryDetail(id: string): Promise<HistoryDetail> {
  const data = await apiRequest<unknown>(`/history/${encodeURIComponent(id)}`);
  const item = toHistoryItem(data);
  if (!item || !isObject(data)) throw new ApiError("bad_response", UNEXPECTED);

  const dtos = Array.isArray(data.issues) ? (data.issues as IssueDto[]) : [];
  const paths = new Set(dtos.map((dto) => String(dto?.file_path)));
  return {
    ...item,
    issues: toIssues(dtos, paths).issues,
    issuesStored: data.issues_stored !== false,
  };
}

// The saved files of an analysis, to open them in the workspace.
export async function getSavedFiles(id: string): Promise<ProjectFile[]> {
  const data = await apiRequest<unknown>(`/history/${encodeURIComponent(id)}/files`, {
    timeoutMs: 60_000,
  });
  const files = isObject(data) ? toProjectFiles(data.files) : [];
  if (files.length === 0) throw new ApiError("bad_response", "No files were saved for this analysis.");
  return files;
}

export async function deleteAnalysis(id: string): Promise<void> {
  await apiRequest<void>(`/history/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function getAnalytics(): Promise<AnalyticsData> {
  const data = await apiRequest<unknown>("/analytics");
  if (!isObject(data) || !isObject(data.totals)) throw new ApiError("bad_response", UNEXPECTED);

  const totals = data.totals;
  const list = (value: unknown): Raw[] => (Array.isArray(value) ? value.filter(isObject) : []);

  return {
    totals: {
      projects: whole(totals.projects),
      analyses: whole(totals.analyses),
      filesAnalyzed: whole(totals.files_analyzed),
      loc: whole(totals.loc),
      issueCount: whole(totals.issue_count),
      ruleIssueCount: whole(totals.rule_issue_count),
      issuesPer100Loc: decimal(totals.issues_per_100_loc),
    },
    severity: severityCounts(data.severity),
    languages: list(data.languages).map((item) => ({
      language: text(item.language, 30) ?? "plaintext",
      lines: whole(item.lines),
    })),
    trend: list(data.trend).map((item) => ({
      month: text(item.month, 7) ?? "",
      analyses: whole(item.analyses),
      issuesPer100Loc: decimal(item.issues_per_100_loc),
    })),
    projects: list(data.projects).map((item) => ({
      projectId: text(item.project_id, 40) ?? "",
      projectName: text(item.project_name, 200) ?? "",
      analyses: whole(item.analyses),
      latestAt: text(item.latest_at, 40) ?? "",
      loc: whole(item.loc),
      latestIssueCount: whole(item.latest_issue_count),
      latestIssuesPer100Loc: decimal(item.latest_issues_per_100_loc),
    })),
    truncated: data.truncated === true,
  };
}