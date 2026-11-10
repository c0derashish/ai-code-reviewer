import type { User } from "../types";

// MOCK AUTH. There is no backend yet.
// - Dev mode (npm run dev): demo sign-in, local only. No password is stored or sent.
// - Production build: sign-in is refused, so no fake login ships.
// Phase 10: replace login() and register() with real FastAPI calls.
// A real backend should keep the session in an httpOnly cookie, not in localStorage.

export const AUTH_IS_DEMO = import.meta.env.DEV;

const SESSION_KEY = "vedix-session";

export type AuthResult = { ok: true; user: User } | { ok: false; message: string };

const NO_BACKEND = "Sign-in needs the backend, which is not connected yet.";

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function saveSession(user: User) {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(user));
  } catch {
    // storage blocked: session lasts until refresh
  }
}

// read the saved session, and check its shape before trusting it
export function getStoredSession(): User | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (
      typeof data?.id === "string" &&
      typeof data?.name === "string" &&
      typeof data?.email === "string"
    ) {
      return { id: data.id, name: data.name, email: data.email, demo: true };
    }
  } catch {
    // bad data: ignore it
  }
  return null;
}

// "ashish.chandra@x.com" -> "Ashish.chandra"
function nameFromEmail(email: string) {
  const local = email.split("@")[0];
  return local.charAt(0).toUpperCase() + local.slice(1);
}

export async function login(email: string, _password: string): Promise<AuthResult> {
  if (!AUTH_IS_DEMO) return { ok: false, message: NO_BACKEND };

  await wait(600); // MOCK delay so the loading state is visible
  const clean = email.trim().toLowerCase();
  const user: User = { id: `demo-${clean}`, name: nameFromEmail(clean), email: clean, demo: true };
  saveSession(user);
  return { ok: true, user };
}

export async function register(
  name: string,
  email: string,
  _password: string
): Promise<AuthResult> {
  if (!AUTH_IS_DEMO) return { ok: false, message: NO_BACKEND };

  await wait(600); // MOCK delay
  const clean = email.trim().toLowerCase();
  const user: User = { id: `demo-${clean}`, name: name.trim(), email: clean, demo: true };
  saveSession(user);
  return { ok: true, user };
}

export function logout() {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    // ignore
  }
}