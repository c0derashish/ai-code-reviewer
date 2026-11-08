import { useState } from "react";
import type { FormEvent } from "react";
import { LoaderCircle, Lock } from "lucide-react";
import Modal from "./Modal";
import Button from "../common/Button";
import Notice from "../common/Notice";
import GitHubIcon from "../common/GitHubIcon";
import { submitRepository } from "../../services/repositoryService";
import { checkGithubUrl } from "../../utils/validators";

type RepositoryModalProps = {
  onClose: () => void;
};

export default function RepositoryModal({ onClose }: RepositoryModalProps) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setNotice(null);

    const check = checkGithubUrl(url);
    if (!check.ok) {
      setError(check.message);
      return;
    }

    setError(null);
    setLoading(true);
    try {
      const result = await submitRepository(check.owner, check.repo);
      if (!result.connected) setNotice(result.message);
    } catch {
      setError("Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal title="Connect to repository" onClose={onClose} narrow>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-line bg-base text-main">
            <GitHubIcon size={24} />
          </span>
          <p className="text-sm text-muted">Paste the link to a public GitHub repository.</p>
        </div>

        <div>
          <label htmlFor="repo-url" className="mb-1.5 block text-sm font-medium">
            Repository URL
          </label>
          <input
            id="repo-url"
            type="text"
            inputMode="url"
            autoFocus
            autoComplete="off"
            spellCheck={false}
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setError(null);
            }}
            placeholder="https://github.com/username/repository"
            aria-invalid={error !== null}
            className="w-full rounded-md border border-line bg-base px-4 py-3 font-mono text-sm text-main placeholder:text-muted focus:border-saffron focus:outline-none"
          />
        </div>

        {error && <Notice kind="error">{error}</Notice>}
        {notice && <Notice kind="info">{notice}</Notice>}

        {/* private repos: future GitHub sign-in, never a pasted token */}
        <div className="rounded-lg border border-dashed border-line p-4">
          <div className="flex items-start gap-3">
            <Lock size={18} className="mt-0.5 shrink-0 text-gold" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">Private repository?</p>
              <p className="mt-1 text-sm text-muted">
                Private repositories will use GitHub sign-in. Never paste an access token here.
              </p>
              <Button
                type="button"
                variant="outline"
                disabled
                icon={<GitHubIcon size={16} />}
                className="mt-3"
              >
                Sign in with GitHub (coming soon)
              </Button>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={loading}
            icon={loading ? <LoaderCircle size={16} className="animate-spin" /> : undefined}
          >
            {loading ? "Connecting" : "Connect repository"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}