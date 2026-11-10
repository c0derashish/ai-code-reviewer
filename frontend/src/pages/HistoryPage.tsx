import { Link } from "react-router-dom";
import { History, LoaderCircle } from "lucide-react";
import EmptyState from "../components/common/EmptyState";
import Notice from "../components/common/Notice";
import PageShell from "../components/common/PageShell";
import SampleDataNote from "../components/dashboard/SampleDataNote";
import ScoreBadge from "../components/dashboard/ScoreBadge";
import StatusBadge from "../components/dashboard/StatusBadge";
import { useHistory } from "../hooks/useHistory";
import { countIssues } from "../utils/analytics";
import { formatDate } from "../utils/format";
import { getLanguageLabel } from "../utils/language";

// column sizes on wide screens. Small screens use 2 columns
const COLUMNS =
  "md:grid-cols-[minmax(0,2fr)_minmax(0,1.2fr)_minmax(0,1fr)_72px_72px_110px]";

export default function HistoryPage() {
  const { records, loading, error } = useHistory();

  return (
    <PageShell title="Analysis History">
      <div className="space-y-4">
        <SampleDataNote />

        {loading && (
          <p className="flex items-center gap-2 text-sm text-muted">
            <LoaderCircle size={16} className="animate-spin" />
            Loading
          </p>
        )}

        {error && <Notice kind="error">{error}</Notice>}

        {records && records.length === 0 && (
          <div className="glass-panel rounded-xl border py-12">
            <EmptyState icon={<History size={32} />} title="No analyses yet">
              Upload code or connect a repository. Finished analyses will be listed here.
            </EmptyState>
          </div>
        )}

        {records && records.length > 0 && (
          <div className="glass-panel overflow-hidden rounded-xl border">
            <div
              className={`hidden gap-x-4 border-b border-line px-4 py-2.5 text-xs uppercase tracking-wide text-muted md:grid ${COLUMNS}`}
            >
              <span>Project</span>
              <span>Date</span>
              <span>Language</span>
              <span>Score</span>
              <span>Issues</span>
              <span>Status</span>
            </div>

            <ul className="divide-y divide-line">
              {records.map((record) => (
                <li key={record.id}>
                  <Link
                    to={`/history/${record.id}`}
                    className={`grid grid-cols-2 items-center gap-x-4 gap-y-2 px-4 py-3 transition hover:bg-saffron/5 ${COLUMNS}`}
                  >
                    <span className="col-span-2 truncate font-medium md:col-span-1">
                      {record.projectName}
                    </span>
                    <span className="text-sm text-muted">{formatDate(record.date)}</span>
                    <span className="text-sm">{getLanguageLabel(record.language)}</span>
                    <span>
                      <ScoreBadge score={record.score} />
                    </span>
                    <span className="font-mono text-sm">
                      {record.status === "done" ? countIssues(record) : "—"}
                      <span className="font-sans text-xs text-muted md:hidden"> issues</span>
                    </span>
                    <span>
                      <StatusBadge status={record.status} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </PageShell>
  );
}