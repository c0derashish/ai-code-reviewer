import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut, Trash2 } from "lucide-react";
import AuthField from "../components/auth/AuthField";
import Button from "../components/common/Button";
import Notice from "../components/common/Notice";
import PageShell from "../components/common/PageShell";
import { useAuth } from "../context/AuthContext";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 border-b border-line py-3 last:border-b-0 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm text-muted">{label}</span>
      <span className="break-all text-sm font-medium">{value}</span>
    </div>
  );
}

export default function AccountPage() {
  const { user, logout, removeAccount } = useAuth();
  const navigate = useNavigate();
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // RequireAuth already blocks guests. This only keeps TypeScript happy.
  if (!user) return null;

  async function handleDelete(e: FormEvent) {
    e.preventDefault();
    if (password === "") {
      setError("Enter your password to confirm.");
      return;
    }

    setError(null);
    setBusy(true);
    const result = await removeAccount(password);
    if (!result.ok) {
      setError(result.message);
      setBusy(false);
      return;
    }
    navigate("/", { replace: true });
  }

  return (
    <PageShell title="Account information">
      <div className="glass-panel max-w-xl space-y-5 rounded-xl border p-6">
        <div>
          <Row label="Name" value={user.name} />
          <Row label="Email" value={user.email} />
        </div>

        <Notice kind="info">
          The server stores your name, your email and a hash of your password (never the password
          itself), and the analyses you save to your history: results, and the code of your own
          uploads and of repositories with an open licence. For other GitHub repositories only the
          link and counts are kept. Deleting the account deletes everything stored for it.
        </Notice>

        <Button variant="outline" icon={<LogOut size={16} />} onClick={() => void logout()}>
          Logout
        </Button>

        <div className="border-t border-line pt-5">
          {!deleting ? (
            <Button variant="ghost" icon={<Trash2 size={16} />} onClick={() => setDeleting(true)}>
              Delete my account
            </Button>
          ) : (
            <form onSubmit={handleDelete} noValidate className="space-y-4">
              <p className="text-sm">
                This deletes your account and all data stored for it. It cannot be undone.
              </p>
              <AuthField
                id="delete-password"
                label="Your password"
                type="password"
                value={password}
                onChange={setPassword}
                autoComplete="current-password"
              />
              {error && <Notice kind="error">{error}</Notice>}
              <div className="flex gap-2">
                <Button type="submit" disabled={busy} icon={<Trash2 size={16} />}>
                  {busy ? "Deleting" : "Delete forever"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setDeleting(false);
                    setPassword("");
                    setError(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </PageShell>
  );
}