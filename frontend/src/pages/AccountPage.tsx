import { LogOut } from "lucide-react";
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
  const { user, logout } = useAuth();

  // RequireAuth already blocks guests. This only keeps TypeScript happy.
  if (!user) return null;

  return (
    <PageShell title="Account information">
      <div className="glass-panel max-w-xl space-y-5 rounded-xl border p-6">
        <div>
          <Row label="Name" value={user.name} />
          <Row label="Email" value={user.email} />
          <Row
            label="Session"
            value={user.demo ? "Demo, stored in this browser only" : "Signed in"}
          />
        </div>

        {user.demo && (
          <Notice kind="info">
            This is a demo session. No real account exists until the backend is connected.
          </Notice>
        )}

        <Button variant="outline" icon={<LogOut size={16} />} onClick={logout}>
          Logout
        </Button>
      </div>
    </PageShell>
  );
}