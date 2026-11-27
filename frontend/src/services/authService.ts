import type { User } from "../types";
import { API_CONFIGURED, ApiError, apiRequest } from "./api";

// Accounts live on the server. The browser holds only an HttpOnly cookie that scripts cannot read.

export type AuthResult = { ok: true; user: User } | { ok: false; message: string };
export type SimpleResult = { ok: true } | { ok: false; message: string };

const NOT_CONNECTED = "Accounts need the backend, which is not connected yet.";
const UNEXPECTED = "The server sent an unexpected answer.";

// Server answers are not trusted: fields are checked and cut to size.
function toUser(data: unknown): User | null {
  const item = data as Partial<User> | null;
  if (
    item &&
    typeof item.id === "string" &&
    typeof item.name === "string" &&
    typeof item.email === "string"
  ) {
    return { id: item.id.slice(0, 40), name: item.name.slice(0, 60), email: item.email.slice(0, 254) };
  }
  return null;
}

function messageOf(err: unknown): string {
  return err instanceof ApiError ? err.message : "Something went wrong. Try again.";
}

async function sendCredentials(path: string, body: unknown): Promise<AuthResult> {
  if (!API_CONFIGURED) return { ok: false, message: NOT_CONNECTED };

  try {
    const user = toUser(await apiRequest<unknown>(path, { method: "POST", json: body }));
    return user ? { ok: true, user } : { ok: false, message: UNEXPECTED };
  } catch (err) {
    return { ok: false, message: messageOf(err) };
  }
}

export function login(email: string, password: string): Promise<AuthResult> {
  return sendCredentials("/auth/login", { email, password });
}

export function register(name: string, email: string, password: string): Promise<AuthResult> {
  return sendCredentials("/auth/register", { name, email, password });
}

// Who is signed in? The server knows from the cookie. null = nobody (or the server is not reachable).
export async function getCurrentUser(): Promise<User | null> {
  if (!API_CONFIGURED) return null;
  try {
    return toUser(await apiRequest<unknown>("/auth/me"));
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  if (!API_CONFIGURED) return;
  try {
    await apiRequest<void>("/auth/logout", { method: "POST" });
  } catch {
    // the cookie may already be gone. Nothing to do
  }
}

export async function deleteAccount(password: string): Promise<SimpleResult> {
  if (!API_CONFIGURED) return { ok: false, message: NOT_CONNECTED };

  try {
    await apiRequest<void>("/auth/account", { method: "DELETE", json: { password } });
    return { ok: true };
  } catch (err) {
    return { ok: false, message: messageOf(err) };
  }
}