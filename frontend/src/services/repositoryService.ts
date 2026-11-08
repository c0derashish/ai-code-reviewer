export type RepositoryResult = {
  connected: false;
  message: string;
};

export async function submitRepository(owner: string, repo: string): Promise<RepositoryResult> {
  // MOCK: short wait so the loading state can be seen. No request is made.
  await new Promise((resolve) => setTimeout(resolve, 700));

  return {
    connected: false,
    message: `${owner}/${repo} looks valid, but the backend is not connected yet. Nothing was cloned or sent anywhere.`,
  };
}