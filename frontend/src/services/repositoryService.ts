import type { SubmitRepositoryRequest, SubmitRepositoryResponse } from "../types/api";
import { API_CONFIGURED, ApiError, apiRequest } from "./api";

// Written against docs/API_CONTRACT.md. UNTESTED until a backend exists.

export type RepositoryResult =
  | { state: "not_connected"; message: string }
  | { state: "submitted"; id: string; message: string };

// owner and repo already passed checkGithubUrl(). The URL is rebuilt, not copied
export async function submitRepository(owner: string, repo: string): Promise<RepositoryResult> {
  if (!API_CONFIGURED) {
    return {
      state: "not_connected",
      message: `${owner}/${repo} looks valid, but the backend is not connected yet. Nothing was cloned or sent anywhere.`,
    };
  }

  const body: SubmitRepositoryRequest = { url: `https://github.com/${owner}/${repo}` };
  const response = await apiRequest<SubmitRepositoryResponse>("/repositories", {
    method: "POST",
    json: body,
  });

  if (typeof response?.id !== "string") {
    throw new ApiError("bad_response", "The server sent an unexpected answer.");
  }

  return {
    state: "submitted",
    id: response.id,
    message: `${owner}/${repo} was submitted. Opening it in the workspace is not wired yet.`,
  };
}