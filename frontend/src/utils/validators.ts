export type RepoCheck =
  | { ok: true; owner: string; repo: string }
  | { ok: false; message: string };

export function checkGithubUrl(input: string): RepoCheck {
  const text = input.trim();
  if (text === "") {
    return { ok: false, message: "Enter a repository URL." };
  }

  let url: URL;
  try {
    url = new URL(text);
  } catch {
    return {
      ok: false,
      message: "That is not a valid URL. Example: https://github.com/username/repository",
    };
  }

  // never accept tokens or passwords in the URL
  if (url.username || url.password || url.search) {
    return {
      ok: false,
      message:
        "Remove credentials, tokens, and ?query parts from the URL. Private repositories will use GitHub sign-in.",
    };
  }

  if (url.protocol !== "https:" || url.hostname !== "github.com") {
    return { ok: false, message: "Only https://github.com repositories are supported." };
  }

  const parts = url.pathname.split("/").filter(Boolean);
  if (parts.length !== 2) {
    return {
      ok: false,
      message: "URL must look like https://github.com/username/repository",
    };
  }

  const owner = parts[0];
  const repo = parts[1].replace(/\.git$/, "");

  const ownerOk = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/.test(owner);
  const repoOk = /^[A-Za-z0-9._-]{1,100}$/.test(repo);
  if (!ownerOk || !repoOk) {
    return { ok: false, message: "Username or repository name has invalid characters." };
  }

  return { ok: true, owner, repo };
}

// ---------- account form checks. Each returns an error message, or null if fine ----------

export function checkEmail(input: string): string | null {
  const text = input.trim();
  if (text === "") return "Enter your email.";
  if (text.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text)) {
    return "Enter a valid email, like name@example.com.";
  }
  return null;
}

export function checkPassword(input: string): string | null {
  if (input === "") return "Enter a password.";
  if (input.length < 8) return "Use at least 8 characters.";
  if (input.length > 128) return "Use 128 characters or fewer.";
  return null;
}

export function checkName(input: string): string | null {
  const text = input.trim();
  if (text === "") return "Enter your name.";
  if (text.length > 60) return "Use 60 characters or fewer.";
  return null;
}