import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, LoaderCircle } from "lucide-react";
import EmptyState from "../components/common/EmptyState";
import Notice from "../components/common/Notice";
import PageShell from "../components/common/PageShell";
import SampleDataNote from "../components/dashboard/SampleDataNote";
import StatCard from "../components/dashboard/StatCard";
import StatusBadge from "../components/dashboard/StatusBadge";
import { getAnalysis } from "../services/historyService";
import type { AnalysisRecord } from "../types";
import { countIssues } from "../utils/analytics";
import { formatDate } from "../utils/format";
import { getLanguageLabel } from "../utils/language";
import { SEVERITIES, SEVERITY_META } from "../utils/severity";

export default function AnalysisDetailPage() {
  const { id } = useParams();
  // undefined = loading, null = not found
  const [record, setRecord] = useState<AnalysisRecord | null | undefined>(undefined);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    getAnalysis(id)
      .then((found) => {
        if (!cancelled) setRecord(found);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  const notFound = !id || record === null;
  const maxCount = record ? Math.max(1, ...SEVERITIES.map((s) => record.issues[s])) : 1;

  return (
    <PageShell title={record?.projectName ?? "Analysis"}>
      <Link
        to="/history"
        className="mb-5 inline-flex items-center gap-2 text-sm text-muted transition hover:text-saffron"
      >
        <ArrowLeft size={16} />
        Back to history
      </Link>

      <div className="space-y-5">
        <SampleDataNote />

        {error ? (
          <Notice kind="error">Could not load this analysis. Try again.</Notice>
        ) : notFound ? (
          <div className="glass-panel rounded-xl border py-12">
            <EmptyState icon={<ArrowLeft size={32} />} title="Analysis not found">
              It may have been removed, or the link is wrong.
            </EmptyState>
          </div>
        ) : record === undefined ? (
          <p className="flex items-center gap-2 text-sm text-muted">
            <LoaderCircle size={16} className="animate-spin" />
            Loading
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
              <StatusBadge status={record.status} />
              <span>{formatDate(record.date)}</span>
            </div>

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatCard
                label="Quality score"
                value={record.score === null ? "—" : `${record.score}/100`}
              />
              <StatCard
                label="Issues"
                value={record.status === "done" ? countIssues(record) : "—"}
              />
              <StatCard label="Files" value={record.files} />
              <StatCard label="Language" value={getLanguageLabel(record.language)} />
            </div>

            {record.status === "done" ? (
              <section className="glass-panel rounded-xl border p-5">
                <h2 className="mb-4 font-medium">Issues by severity</h2>
                <ul className="space-y-3">
                  {SEVERITIES.map((severity) => {
                    const count = record.issues[severity];
                    return (
                      <li key={severity} className="flex items-center gap-3 text-sm">
                        <span className="w-16 shrink-0 text-muted">
                          {SEVERITY_META[severity].label}
                        </span>
                        <div className="h-2 flex-1 overflow-hidden rounded bg-main/10">
                          <div
                            className={`h-full rounded ${SEVERITY_META[severity].dot}`}
                            style={{ width: `${(count / maxCount) * 100}%` }}
                          />
                        </div>
                        <span className="w-8 shrink-0 text-right font-mono">{count}</span>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ) : (
              <Notice kind="error">This analysis failed. No results were stored.</Notice>
            )}

            <Notice kind="info">
              Saved code and issue details are not stored yet. Reopening a past analysis in
              the workspace needs the backend.
            </Notice>
          </>
        )}
      </div>
    </PageShell>
  );
}