import type { Project, ProjectFile } from "../types";
import type {
  JobStatus,
  RepositoryFileDto,
  RepositoryFilesResponse,
  RepositoryStatusResponse,
  SubmitRepositoryRequest,
  SubmitRepositoryResponse,
} from "../types/api";
import { LANGUAGES, getLanguageFromFileName } from "../utils/language";
import { API_CONFIGURED, ApiError, apiRequest } from "./api";

// Written against docs/API_CONTRACT.md. Server answers are not trusted: every field is checked.

const POLL_EVERY_MS = 1500;
const GIVE_UP_AFTER_MS = 90_000;
const MAX_POLL_FAILURES = 3;
const MAX_FILES = 500;
const MAX_FILE_CHARS = 2 * 1024 * 1024;
const MAX_PATH_LENGTH = 300;

export type RepositoryResult =
  | { state: "not_connected"; message: string }
  | { state: "stopped" }
  | { state: "ready"; project: Project; repoId: string };

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isJobStatus(value: unknown): value is JobStatus {
  return value === "queued" || value === "running" || value === "done" || value === "failed";
}

// Polls until the fetch is done. true = done, false = the caller stopped waiting.
// Throws an ApiError when the fetch failed or took too long.
async function waitUntilFetched(
  id: string,
  shouldStop: () => boolean,
  onStatus: (text: string) => void
): Promise<boolean> {
  const startedAt = Date.now();
  let failures = 0;

  while (!shouldStop()) {
    if (Date.now() - startedAt > GIVE_UP_AFTER_MS) {
      throw new ApiError("timeout", "Fetching is taking too long. Try again later.");
    }

    await wait(POLL_EVERY_MS);
    if (shouldStop()) break;

    try {
      const status = await apiRequest<RepositoryStatusResponse>(
        `/repositories/${encodeURIComponent(id)}`
      );
      failures = 0;

      if (!isJobStatus(status?.status)) {
        throw new ApiError("bad_response", "The server sent an unexpected answer.");
      }
      if (status.status === "failed") {
        const reason = typeof status.error === "string" && status.error ? status.error : "";
        throw new ApiError("http", reason.slice(0, 300) || "The repository could not be fetched.");
      }
      if (status.status === "done") return true;

      onStatus(status.status === "running" ? "Downloading from GitHub" : "Waiting in the queue");
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

  return false;
}

export function toProjectFiles(list: unknown): ProjectFile[] {
  if (!Array.isArray(list)) {
    throw new ApiError("bad_response", "The server sent an unexpected answer.");
  }

  const files: ProjectFile[] = [];
  const seen = new Set<string>();

  for (const item of list.slice(0, MAX_FILES)) {
    const dto = item as Partial<RepositoryFileDto> | null;
    if (!dto || typeof dto.path !== "string" || typeof dto.content !== "string") continue;

    const path = dto.path;
    if (path === "" || path.length > MAX_PATH_LENGTH) continue;
    if (dto.content.length > MAX_FILE_CHARS || seen.has(path)) continue;
    seen.add(path);

    const name = path.split("/").pop() ?? path;
    const serverLanguage = typeof dto.language === "string" ? dto.language : "";
    const known = LANGUAGES.some((language) => language.id === serverLanguage);

    files.push({
      path,
      name,
      language: known ? serverLanguage : getLanguageFromFileName(name) ?? "plaintext",
      content: dto.content,
    });
  }
  return files;
}

// owner and repo already passed checkGithubUrl(). The URL is rebuilt, not copied.
export async function fetchRepository(
  owner: string,
  repo: string,
  shouldStop: () => boolean,
  onStatus: (text: string) => void
): Promise<RepositoryResult> {
  if (!API_CONFIGURED) {
    return {
      state: "not_connected",
      message: `${owner}/${repo} looks valid, but the backend is not connected yet. Nothing was fetched or sent anywhere.`,
    };
  }

  const body: SubmitRepositoryRequest = { url: `https://github.com/${owner}/${repo}` };
  const started = await apiRequest<SubmitRepositoryResponse>("/repositories", {
    method: "POST",
    json: body,
  });
  if (typeof started?.id !== "string") {
    throw new ApiError("bad_response", "The server sent an unexpected answer.");
  }

  onStatus("Waiting for GitHub");
  const finished = await waitUntilFetched(started.id, shouldStop, onStatus);
  if (!finished) return { state: "stopped" };

  const data = await apiRequest<RepositoryFilesResponse>(
    `/repositories/${encodeURIComponent(started.id)}/files`,
    { timeoutMs: 60_000 }
  );

  const files = toProjectFiles(data?.files);
  if (files.length === 0) {
    throw new ApiError("bad_response", "The repository has no files we can show.");
  }

  const name =
    typeof data.project_name === "string" && data.project_name ? data.project_name.slice(0, 100) : repo;
  return { state: "ready", project: { name, files }, repoId: started.id };
}