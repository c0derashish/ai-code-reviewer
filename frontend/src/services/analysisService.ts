import type { AnalysisScope, Issue, IssueCategory, Project, Severity } from "../types";
import type { AnalysisResultResponse, IssueDto, JobStatus, StartAnalysisResponse } from "../types/api";
import { CATEGORY_LABEL, SEVERITIES } from "../utils/severity";
import { ApiError, apiRequest } from "./api";

// Written against docs/API_CONTRACT.md. UNTESTED until a backend exists.
// With no backend set, apiRequest throws "not_configured". Nothing is faked.

const POLL_EVERY_MS = 1500;
const GIVE_UP_AFTER_MS = 3 * 60 * 1000;
const MAX_POLL_FAILURES = 3;

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isJobStatus(value: unknown): value is JobStatus {
  return value === "queued" || value === "running" || value === "done" || value === "failed";
}

// send the code for analysis. Edited text is sent, not the original upload
export async function startAnalysis(
  project: Project,
  scope: AnalysisScope,
  activePath: string
): Promise<StartAnalysisResponse> {
  const files =
    scope === "file" ? project.files.filter((f) => f.path === activePath) : project.files;

  const form = new FormData();
  form.append("project_name", project.name);
  form.append("scope", scope);
  for (const file of files) {
    // "paths" and "files" are in the same order. The server pairs them by index
    form.append("paths", file.path);
    form.append("files", new Blob([file.content], { type: "text/plain" }), file.name);
  }

  const response = await apiRequest<StartAnalysisResponse>("/analyses", {
    method: "POST",
    form,
    timeoutMs: 120_000,
  });

  if (typeof response?.id !== "string" || !isJobStatus(response.status)) {
    throw new ApiError("bad_response", "The server sent an unexpected answer.");
  }
  return response;
}

// ask for the result every 1.5 seconds. Returns null if shouldStop() turned true
export async function waitForAnalysis(
  id: string,
  shouldStop: () => boolean
): Promise<AnalysisResultResponse | null> {
  const startedAt = Date.now();
  let failures = 0;

  while (!shouldStop()) {
    if (Date.now() - startedAt > GIVE_UP_AFTER_MS) {
      throw new ApiError("timeout", "Analysis is taking too long. Try again later.");
    }

    await wait(POLL_EVERY_MS);
    if (shouldStop()) break;

    try {
      const result = await apiRequest<AnalysisResultResponse>(
        `/analyses/${encodeURIComponent(id)}`
      );
      failures = 0;
      if (!isJobStatus(result?.status)) {
        throw new ApiError("bad_response", "The server sent an unexpected answer.");
      }
      if (result.status === "done" || result.status === "failed") return result;
    } catch (err) {
      // allow short network blips, give up on anything else
      const blip = err instanceof ApiError && (err.code === "network" || err.code === "timeout");
      if (blip && failures < MAX_POLL_FAILURES) {
        failures += 1;
        continue;
      }
      throw err;
    }
  }

  return null;
}

function cap(text: unknown, max: number): string {
  return typeof text === "string" ? text.slice(0, max) : "";
}

// Server data is not trusted. Bad rows are dropped, odd values get safe defaults
export function toIssues(dtos: IssueDto[] | undefined, validPaths: Set<string>) {
  const issues: Issue[] = [];
  let dropped = 0;

  (dtos ?? []).forEach((dto, index) => {
    const line = Number(dto?.line);
    if (!dto || !validPaths.has(dto.file_path) || !Number.isInteger(line) || line < 1) {
      dropped += 1;
      return;
    }

    const severity = SEVERITIES.includes(dto.severity as Severity)
      ? (dto.severity as Severity)
      : "info";
    const category = Object.prototype.hasOwnProperty.call(CATEGORY_LABEL, dto.category)
      ? (dto.category as IssueCategory)
      : "code_smell";

    issues.push({
      id: `${cap(dto.id, 60) || "issue"}-${index}`,
      filePath: dto.file_path,
      line,
      severity,
      category,
      title: cap(dto.title, 200) || "Untitled issue",
      explanation: cap(dto.explanation, 2000),
      suggestion: cap(dto.suggestion, 2000) || undefined,
      before: cap(dto.before, 4000) || undefined,
      after: cap(dto.after, 4000) || undefined,
    });
  });

  return { issues, dropped };
}