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