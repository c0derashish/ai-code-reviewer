import type { Issue, IssueCategory, ProjectFile, Severity } from "../types";

// SAMPLE DATA for testing the review panel. Not a real analysis.
// Delete this file (and the sample button) when the backend is connected.

const TEMPLATES: { severity: Severity; category: IssueCategory; title: string }[] = [
  { severity: "high", category: "security", title: "Sample: possible security issue" },
  { severity: "medium", category: "complexity", title: "Sample: high complexity" },
  { severity: "low", category: "code_smell", title: "Sample: code smell" },
  { severity: "info", category: "style", title: "Sample: style note" },
  { severity: "critical", category: "bug", title: "Sample: possible bug" },
];

// find a non-empty line at or near this index. Returns a 1-based line number.
function pickLine(lines: string[], target: number): number | null {
  for (let i = target; i < lines.length; i++) {
    if (lines[i].trim() !== "") return i + 1;
  }
  for (let i = target; i >= 0; i--) {
    if (lines[i].trim() !== "") return i + 1;
  }
  return null;
}

export function makeSampleIssues(files: ProjectFile[]): Issue[] {
  const issues: Issue[] = [];
  let count = 0;

  for (const file of files.slice(0, 3)) {
    const lines = file.content.split("\n");
    const used = new Set<number>();

    for (const position of [0.1, 0.5, 0.9]) {
      const line = pickLine(lines, Math.floor(lines.length * position));
      if (line === null || used.has(line)) continue;
      used.add(line);

      const template = TEMPLATES[count % TEMPLATES.length];
      count += 1;

      issues.push({
        id: `sample-${count}`,
        filePath: file.path,
        line,
        severity: template.severity,
        category: template.category,
        title: template.title,
        explanation: "Sample data to test the review panel. This is not a real finding.",
        suggestion: "Real suggestions will come from the analysis backend.",
        before: lines[line - 1],
        after: "(sample: no real suggestion)",
      });
    }
  }

  return issues;
}