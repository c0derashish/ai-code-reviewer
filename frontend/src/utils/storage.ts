// Read a saved setting. Only accepts values from the allowed list.
export function readSetting<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T
): T {
  try {
    const value = localStorage.getItem(key);
    if (value !== null && (allowed as readonly string[]).includes(value)) {
      return value as T;
    }
  } catch {
    // storage blocked: use fallback
  }
  return fallback;
}

export function saveSetting(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // storage blocked: ignore
  }
}