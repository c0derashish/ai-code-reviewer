import type { Issue, Severity } from "./index";

export type Storage = "full" | "link_only";

export type LicenceInfo = {
  status: string;
  spdxId: string | null;
  name: string | null;
};

export type HistoryItem = {
  id: string;
  projectId: string;
  projectName: string;
  source: "upload" | "github";
  repoUrl: string | null;
  createdAt: string; // UTC, like 2026-11-20T10:00:00Z
  scope: string;
  primaryLanguage: string | null;
  files: number;
  filesAnalyzed: number;
  loc: number; // code lines of the analysed files
  issueCount: number;
  ruleIssueCount: number; // without the AI findings
  severityCounts: Record<Severity, number>;
  storage: Storage;
  storageReason: string | null;
  licence: LicenceInfo | null;
};

export type HistoryDetail = HistoryItem & {
  issues: Issue[];
  issuesStored: boolean; // false when only the link was stored
};

export type AnalyticsData = {
  totals: {
    projects: number;
    analyses: number;
    filesAnalyzed: number;
    loc: number;
    issueCount: number;
    ruleIssueCount: number;
    issuesPer100Loc: number | null;
  };
  severity: Record<Severity, number>;
  languages: { language: string; lines: number }[];
  trend: { month: string; analyses: number; issuesPer100Loc: number | null }[];
  projects: {
    projectId: string;
    projectName: string;
    analyses: number;
    latestAt: string;
    loc: number;
    latestIssueCount: number;
    latestIssuesPer100Loc: number | null;
  }[];
  truncated: boolean;
};