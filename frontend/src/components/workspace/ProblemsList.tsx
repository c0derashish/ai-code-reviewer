import { useMemo } from "react";
import { useWorkspace } from "../../context/WorkspaceContext";
import { SEVERITY_META, compareIssues } from "../../utils/severity";

export default function ProblemsList() {
  const { issues, selectedIssueId, openIssue } = useWorkspace();

  const sorted = useMemo(() => [...issues].sort(compareIssues), [issues]);

  if (sorted.length === 0) {
    return (
      <p className="text-muted">
        No analysis has run, so there are no problems to show. Issues will be listed here
        with file and line.
      </p>
    );
  }

  return (
    <ul className="space-y-0.5">
      {sorted.map((issue) => (
        <li key={issue.id}>
          <button
            type="button"
            onClick={() => openIssue(issue)}
            className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left text-xs transition hover:bg-raised ${
              issue.id === selectedIssueId ? "bg-saffron/10" : ""
            }`}
          >
            <span className={`h-2 w-2 shrink-0 rounded-full ${SEVERITY_META[issue.severity].dot}`} />
            <span className="truncate">{issue.title}</span>
            <span className="ml-auto shrink-0 font-mono text-muted">
              {issue.filePath}:{issue.line}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}