import { Link } from "react-router-dom";
import { History, LoaderCircle } from "lucide-react";
import EmptyState from "../components/common/EmptyState";
import Notice from "../components/common/Notice";
import PageShell from "../components/common/PageShell";
import StorageBadge from "../components/dashboard/StorageBadge";
import { useHistory } from "../hooks/useHistory";
import { formatDate } from "../utils/format";
import { getLanguageLabel } from "../utils/language";

// column sizes on wide screens. Small screens use 2 columns
const COLUMNS =
  "md:grid-cols-[minmax(0,2fr)_minmax(0,1.1fr)_minmax(0,1fr)_80px_80px_100px]";

export default function HistoryPage() {
  const { items, loading, error } = useHistory();

  return (
    <PageShell title="Analysis History">
      <div className="space-y-4">
        {loading && (
          <p className="flex items-center gap-2 text-sm text-muted">
            <LoaderCircle size={16} className="animate-spin" />
            Loading
          </p>
        )}

        {error && <Notice kind="error">{error}</Notice>}

        {items && items.length === 0 && (
          <div className="glass-panel rounded-xl border py-12">
            <EmptyState icon={<History size={32} />} title="No saved analyses yet">
              Analyse a project in the workspace while you are signed in and "Saving" is on.
              It will be listed here.
            </EmptyState>
          </div>
        )}

        {items && items.length > 0 && (
          <div className="glass-panel overflow-hidden rounded-xl border">
            <div
              className={`hidden gap-x-4 border-b border-line px-4 py-2.5 text-xs uppercase tracking-wide text-muted md:grid ${COLUMNS}`}
            >
              <span>Project</span>
              <span>Date</span>
              <span>Language</span>
              <span>Code lines</span>
              <span>Issues</span>
              <span>Stored</span>
            </div>

            <ul className="divide-y divide-line">
              {items.map((item) => (
                <li key={item.id}>
                  <Link
                    to={`/history/${encodeURIComponent(item.id)}`}
                    className={`grid grid-cols-2 items-center gap-x-4 gap-y-2 px-4 py-3 transition hover:bg-saffron/5 ${COLUMNS}`}
                  >
                    <span className="col-span-2 truncate font-medium md:col-span-1">
                      {item.projectName}
                    </span>
                    <span className="text-sm text-muted">{formatDate(item.createdAt)}</span>
                    <span className="text-sm">
                      {item.primaryLanguage ? getLanguageLabel(item.primaryLanguage) : "—"}
                    </span>
                    <span className="font-mono text-sm">{item.loc}</span>
                    <span className="font-mono text-sm">{item.issueCount}</span>
                    <span>
                      <StorageBadge storage={item.storage} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}

        {items && items.length >= 100 && (
          <p className="text-xs text-muted">Only the 100 newest analyses are shown.</p>
        )}
      </div>
    </PageShell>
  );
}