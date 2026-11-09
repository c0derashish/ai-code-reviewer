// Every request to the backend goes through here.
// Pages and components never call fetch() directly.
// Contract: docs/API_CONTRACT.md (proposed, backend not built yet).

const RAW_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export const API_BASE_URL = RAW_BASE.trim().replace(/\/+$/, "");
export const API_CONFIGURED = API_BASE_URL !== "";

export type ApiErrorCode =
  | "not_configured"
  | "network"
  | "timeout"
  | "unauthorized"
  | "http"
  | "bad_response";

export class ApiError extends Error {
  code: ApiErrorCode;
  status: number; // HTTP status, or 0 when no answer came back

  constructor(code: ApiErrorCode, message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

type RequestOptions = {
  method?: "GET" | "POST";
  json?: unknown; // JSON body
  form?: FormData; // file upload. Browser sets the multipart header itself
  timeoutMs?: number;
};

function messageForStatus(status: number): string {
  if (status === 401) return "Please sign in again.";
  if (status === 403) return "You do not have access to this.";
  if (status === 404) return "Not found on the server.";
  if (status === 413) return "That is too large for the server.";
  if (status === 422) return "The server rejected this request.";
  if (status === 429) return "Too many requests. Wait a moment and try again.";
  if (status >= 500) return "The server had a problem. Try again later.";
  return `Request failed (${status}).`;
}

// FastAPI errors look like {"detail": "message"}
async function readDetail(response: Response): Promise<string | null> {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail.slice(0, 200);
  } catch {
    // not JSON
  }
  return null;
}

// Callers must still check the fields they use. "as T" is only a type hint.
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!API_CONFIGURED) {
    throw new ApiError("not_configured", "Backend is not connected. Set VITE_API_BASE_URL.");
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;

  if (options.form) {
    body = options.form;
  } else if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? 30_000);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
      credentials: "include", // needed later for cookie sessions
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("timeout", "The server took too long to answer.");
    }
    throw new ApiError("network", "Cannot reach the server. Check that the backend is running.");
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    if (response.status === 401) {
      throw new ApiError("unauthorized", messageForStatus(401), 401);
    }
    // show the server's own message for 4xx only. Never for 5xx
    const detail = response.status < 500 ? await readDetail(response) : null;
    throw new ApiError("http", detail ?? messageForStatus(response.status), response.status);
  }

  if (response.status === 204) return undefined as T;

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("bad_response", "The server sent an unreadable answer.", response.status);
  }
}