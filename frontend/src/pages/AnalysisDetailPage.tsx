import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ExternalLink, FolderOpen, LoaderCircle, Trash2 } from "lucide-react";
import Button from "../components/common/Button";
import EmptyState from "../components/common/EmptyState";
import Notice from "../components/common/Notice";
import PageShell from "../components/common/PageShell";
import StatCard from "../components/dashboard/StatCard";
import StorageBadge from "../components/dashboard/StorageBadge";
import SeverityBadge from "../components/review/SeverityBadge";
import { useWorkspace } from "../context/WorkspaceContext";
import { ApiError } from "../services/api";
import { deleteAnalysis, getHistoryDetail, getSavedFiles } from "../services/historyService";
import type { HistoryDetail } from "../types/history";
import { formatDate } from "../utils/format";
import { getLanguageLabel } from "../utils/language";
import { SEVERITIES, SEVERITY_META } from "../utils/severity";

const MAX_ISSUES_SHOWN = 50;

function messageOf(err: unknown) {
  return err instanceof ApiError ? err.message : "Something went wrong. Try again.";
}

export default function AnalysisDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { openProject } = useWorkspace();

  // undefined = loading, null = not found
  const [detail, setDetail] = useState<HistoryDetail | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    getHistoryDetail(id)
      .then((found) => {
        if (!cancelled) setDetail(found);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setDetail(null);
        else setError(messageOf(err));
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  async function handleOpen() {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      const files = await getSavedFiles(detail.id);
      const paths = new Set(files.map((file) => file.path));
      const issues = detail.issues.filter((issue) => paths.has(issue.filePath));
      openProject({ name: detail.projectName, files }, { issues });
      navigate("/workspace");
    } catch (err) {
      setError(messageOf(err));
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!detail) return;
    setBusy(true);
    setError(null);
    try {
      await deleteAnalysis(detail.id);
      navigate("/history", { replace: true });
    } catch (err) {
      setError(messageOf(err));
      setBusy(false);
    }
  }

  const notFound = !id || detail === null;
  const maxCount = detail ? Math.max(1, ...SEVERITIES.map((s) => detail.severityCounts[s])) : 1;

  return (
    <PageShell title={detail?.projectName ?? "Analysis"}>
      <Link
        to="/history"
        className="mb-5 inline-flex items-center gap-2 text-sm text-muted transition hover:text-saffron"
      >
        <ArrowLeft size={16} />
        Back to history
      </Link>

      <div className="space-y-5">
        {error && <Notice kind="error">{error}</Notice>}

        {notFound ? (
          <div className="glass-panel rounded-xl border py-12">
            <EmptyState icon={<ArrowLeft size={32} />} title="Analysis not found">
              It may have been deleted, or the link is wrong.
            </EmptyState>
          </div>
        ) : detail === undefined ? (
          !error && (
            <p className="flex items-center gap-2 text-sm text-muted">
              <LoaderCircle size={16} className="animate-spin" />
              Loading
            </p>
          )
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
              <StorageBadge storage={detail.storage} />
              <span>{formatDate(detail.createdAt)}</span>
              <span>{detail.source === "github" ? "GitHub repository" : "Upload"}</span>
              {detail.licence?.status === "found" && detail.licence.spdxId && (
                <span>Licence: {detail.licence.spdxId}</span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatCard label="Files" value={`${detail.filesAnalyzed} of ${detail.files}`} hint="analysed of found" />
              <StatCard label="Code lines" value={detail.loc} />
              <StatCard label="Issues" value={detail.issueCount} />
              <StatCard
                label="Language"
                value={detail.primaryLanguage ? getLanguageLabel(detail.primaryLanguage) : "—"}
              />
            </div>

            <section className="glass-panel rounded-xl border p-5">
              <h2 className="mb-4 font-medium">Issues by severity</h2>
              <ul className="space-y-3">
                {SEVERITIES.map((severity) => {
                  const count = detail.severityCounts[severity];
                  return (
                    <li key={severity} className="flex items-center gap-3 text-sm">
                      <span className="w-16 shrink-0 text-muted">{SEVERITY_META[severity].label}</span>
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

            {detail.storage === "link_only" && (
              <Notice kind="info">
                Only the link and the counts are stored. {detail.storageReason} The issue list and the
                code are not kept. Fetch the repository again from the start page to see them.
              </Notice>
            )}

            <div className="flex flex-wrap gap-2">
              {detail.storage === "full" && (
                <Button icon={<FolderOpen size={16} />} onClick={handleOpen} disabled={busy}>
                  Open in workspace
                </Button>
              )}
              {detail.repoUrl && (
                <a
                  href={detail.repoUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-md border border-line px-5 py-2.5 text-sm text-main transition hover:border-saffron/50 hover:text-saffron"
                >
                  <ExternalLink size={16} />
                  Open on GitHub
                </a>
              )}
              {!confirmDelete ? (
                <Button variant="ghost" icon={<Trash2 size={16} />} onClick={() => setConfirmDelete(true)}>
                  Delete
                </Button>
              ) : (
                <>
                  <Button icon={<Trash2 size={16} />} onClick={handleDelete} disabled={busy}>
                    Delete forever
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
                    Cancel
                  </Button>
                </>
              )}
            </div>

            {detail.issuesStored && detail.issues.length > 0 && (
              <section className="glass-panel rounded-xl border p-5">
                <h2 className="mb-3 font-medium">Issues</h2>
                <ul className="divide-y divide-line">
                  {detail.issues.slice(0, MAX_ISSUES_SHOWN).map((issue) => (
                    <li key={issue.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
                      <SeverityBadge severity={issue.severity} />
                      <span className="min-w-0 flex-1 truncate">{issue.title}</span>
                      <span className="shrink-0 font-mono text-xs text-muted">
                        {issue.filePath}:{issue.line}
                      </span>
                    </li>
                  ))}
                </ul>
                {detail.issues.length > MAX_ISSUES_SHOWN && (
                  <p className="mt-3 text-xs text-muted">
                    The first {MAX_ISSUES_SHOWN} of {detail.issues.length} issues. Open the workspace for all of them.
                  </p>
                )}
              </section>
            )}
          </>
        )}
      </div>
    </PageShell>
  );
}