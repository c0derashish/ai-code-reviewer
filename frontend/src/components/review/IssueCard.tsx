import type { Issue } from "../../types";
import { CATEGORY_LABEL } from "../../utils/severity";
import SeverityBadge from "./SeverityBadge";

type CodeBlockProps = {
  label: string;
  code: string;
  tone: string;
};

function CodeBlock({ label, code, tone }: CodeBlockProps) {
  return (
    <div>
      <p className="mb-1 text-xs text-muted">{label}</p>
      <pre className={`overflow-x-auto rounded-md border p-2 font-mono text-xs ${tone}`}>
        {code}
      </pre>
    </div>
  );
}

type IssueCardProps = {
  issue: Issue;
  selected: boolean;
  onOpen: (issue: Issue) => void;
};

export default function IssueCard({ issue, selected, onOpen }: IssueCardProps) {
  return (
    <li
      className={`glass-panel rounded-lg border transition ${
        selected ? "border-saffron/60 bg-saffron/5" : "border-line hover:border-saffron/30"
      }`}
    >
      <button
        type="button"
        aria-expanded={selected}
        onClick={() => onOpen(issue)}
        className="w-full p-3 text-left"
      >
        <div className="flex items-center gap-2">
          <SeverityBadge severity={issue.severity} />
          <span className="text-xs text-muted">{CATEGORY_LABEL[issue.category]}</span>
        </div>
        <p className="mt-1.5 text-sm font-medium">{issue.title}</p>
        <p className="mt-0.5 truncate font-mono text-xs text-muted">
          {issue.filePath}:{issue.line}
        </p>
      </button>

      {selected && (
        <div className="space-y-3 border-t border-line px-3 pb-3 pt-3 text-sm">
          <p>{issue.explanation}</p>

          {issue.suggestion && (
            <div>
              <p className="mb-1 text-xs text-muted">Suggested improvement</p>
              <p>{issue.suggestion}</p>
            </div>
          )}

          {issue.before && (
            <CodeBlock label="Before" code={issue.before} tone="border-danger/30 bg-danger/10" />
          )}
          {issue.after && (
            <CodeBlock label="After" code={issue.after} tone="border-ok/30 bg-ok/10" />
          )}
        </div>
      )}
    </li>
  );
}