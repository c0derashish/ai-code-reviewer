import { useMemo, useState } from "react";
import { FlaskConical, Sparkles, Trash2 } from "lucide-react";
import Button from "../common/Button";
import EmptyState from "../common/EmptyState";
import Notice from "../common/Notice";
import IssueCard from "./IssueCard";
import { useWorkspace } from "../../context/WorkspaceContext";
import type { Issue, Severity } from "../../types";
import { SEVERITIES, SEVERITY_META, compareIssues } from "../../utils/severity";
import { API_CONFIGURED } from "../../services/api";

type ReviewPanelProps = {
  onOpenIssue: (issue: Issue) => void;
};

export default function ReviewPanel({ onOpenIssue }: ReviewPanelProps) {
  const {
    project,
    activeFile,
    issues,
    issuesAreSample,
    issuesStale,
    selectedIssueId,
    loadSampleIssues,
    clearIssues,
  } = useWorkspace();

  const [scope, setScope] = useState<"file" | "all">("all");
  const [hidden, setHidden] = useState<Set<Severity>>(new Set());

  const multiFile = (project?.files.length ?? 0) > 1;

  // 1. scope: this file or all files
  const inScope = useMemo(() => {
    if (scope === "file" && activeFile) {
      return issues.filter((issue) => issue.filePath === activeFile.path);
    }
    return issues;
  }, [issues, scope, activeFile]);

  // 2. severity chips, then sort
  const visible = useMemo(
    () => inScope.filter((issue) => !hidden.has(issue.severity)).sort(compareIssues),
    [inScope, hidden]
  );

  const counts = SEVERITIES.map((severity) => ({
    severity,
    count: inScope.filter((issue) => issue.severity === severity).length,
  })).filter((item) => item.count > 0);

  function toggleSeverity(severity: Severity) {
    setHidden((current) => {
      const next = new Set(current);
      if (next.has(severity)) next.delete(severity);
      else next.add(severity);
      return next;
    });
  }

  function scopeClass(active: boolean) {
    return `rounded px-2.5 py-1 text-xs transition ${
      active ? "bg-saffron/15 text-saffron" : "text-muted hover:text-main"
    }`;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <span className="text-sm font-medium">AI Review</span>
        {issues.length > 0 && (
          <span className="flex items-center gap-1">
            <span className="text-xs text-muted">
              {issues.length} issue{issues.length === 1 ? "" : "s"}
            </span>
            {issuesAreSample && (
              <Button variant="ghost" size="icon" aria-label="Clear sample issues" onClick={clearIssues}>
                <Trash2 size={14} />
              </Button>
            )}
          </span>
        )}
      </div>

      {issues.length === 0 ? (
        <div className="min-h-0 flex-1 overflow-auto">
          <EmptyState icon={<Sparkles size={28} />} title="No analysis yet">
            <p>
              {API_CONFIGURED
                ? "Click Analyse file or Analyse project in the toolbar. Issues will appear here."
                : "Analysis needs the backend, which is not connected yet. Issues, severity, and suggested fixes will appear here."}
            </p>
            {import.meta.env.DEV && (
              <Button
                variant="outline"
                className="mt-4"
                icon={<FlaskConical size={16} />}
                onClick={loadSampleIssues}
              >
                Load sample issues (UI test)
              </Button>
            )}
          </EmptyState>
        </div>
      ) : (
        <div className="min-h-0 flex-1 space-y-3 overflow-auto p-3">
          {issuesAreSample && (
            <Notice kind="info">Sample data for UI testing. This is not a real analysis.</Notice>
          )}
          {issuesStale && (
            <Notice kind="info">
              Code changed after these issues were made. Line numbers may be off.
            </Notice>
          )}

          {multiFile && (
            <div
              role="group"
              aria-label="Issue scope"
              className="inline-flex rounded-md border border-line p-0.5"
            >
              <button
                type="button"
                aria-pressed={scope === "file"}
                className={scopeClass(scope === "file")}
                onClick={() => setScope("file")}
              >
                This file
              </button>
              <button
                type="button"
                aria-pressed={scope === "all"}
                className={scopeClass(scope === "all")}
                onClick={() => setScope("all")}
              >
                All files
              </button>
            </div>
          )}

          <div className="flex flex-wrap gap-1.5">
            {counts.map(({ severity, count }) => {
              const off = hidden.has(severity);
              return (
                <button
                  key={severity}
                  type="button"
                  aria-pressed={!off}
                  onClick={() => toggleSeverity(severity)}
                  className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition ${
                    off ? "border-line text-muted opacity-60" : "border-saffron/40 text-main"
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full ${SEVERITY_META[severity].dot}`} />
                  {SEVERITY_META[severity].label} {count}
                </button>
              );
            })}
          </div>

          {visible.length === 0 ? (
            <p className="text-sm text-muted">No issues match the current filters.</p>
          ) : (
            <ul className="space-y-2">
              {visible.map((issue) => (
                <IssueCard
                  key={issue.id}
                  issue={issue}
                  selected={issue.id === selectedIssueId}
                  onOpen={onOpenIssue}
                />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}