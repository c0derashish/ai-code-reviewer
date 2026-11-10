import { useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import type { BeforeMount, Monaco, OnMount } from "@monaco-editor/react";
import { useTheme } from "../../context/ThemeContext";
import { useWorkspace } from "../../context/WorkspaceContext";
import { getLanguageLabel } from "../../utils/language";
import type { ProjectFile, Severity } from "../../types";
import { defineVedixThemes } from "./monacoThemes";

type EditorInstance = Parameters<OnMount>[0];
type Decorations = ReturnType<EditorInstance["createDecorationsCollection"]>;

type CodeEditorProps = {
  file: ProjectFile;
  onChange: (content: string) => void;
};

function markerSeverity(monaco: Monaco, severity: Severity) {
  if (severity === "critical" || severity === "high") return monaco.MarkerSeverity.Error;
  if (severity === "medium") return monaco.MarkerSeverity.Warning;
  return monaco.MarkerSeverity.Info;
}

export default function CodeEditor({ file, onChange }: CodeEditorProps) {
  const { theme } = useTheme();
  const { issues, selectedIssueId, jumpTarget, clearJump } = useWorkspace();
  const [cursor, setCursor] = useState({ line: 1, column: 1 });
  const [ready, setReady] = useState<{ editor: EditorInstance; monaco: Monaco } | null>(null);
  const decorations = useRef<Decorations | null>(null);

  // issues that belong to the open file
  const fileIssues = useMemo(
    () => issues.filter((issue) => issue.filePath === file.path),
    [issues, file.path]
  );

  const handleBeforeMount: BeforeMount = (monaco) => {
    defineVedixThemes(monaco);
  };

  const handleMount: OnMount = (editor, monaco) => {
    editor.onDidChangeCursorPosition((e) => {
      setCursor({ line: e.position.lineNumber, column: e.position.column });
    });
    setReady({ editor, monaco });
  };

  // squiggles + gutter dots + tinted lines
  useEffect(() => {
    if (!ready) return;
    const { editor, monaco } = ready;

    // wipe old markers on every file, then set the ones for the open file
    for (const model of monaco.editor.getModels()) {
      monaco.editor.setModelMarkers(model, "vedix", []);
    }
    decorations.current?.clear();

    const model = editor.getModel();
    if (!model) return;

    const lineCount = model.getLineCount();
    const valid = fileIssues.filter((i) => i.line >= 1 && i.line <= lineCount);

    monaco.editor.setModelMarkers(
      model,
      "vedix",
      valid.map((issue) => ({
        severity: markerSeverity(monaco, issue.severity),
        message: `${issue.title}\n${issue.explanation}`,
        startLineNumber: issue.line,
        startColumn: 1,
        endLineNumber: issue.line,
        endColumn: model.getLineMaxColumn(issue.line),
        source: "VEDIX",
      }))
    );

    decorations.current = editor.createDecorationsCollection(
      valid.map((issue) => ({
        range: new monaco.Range(issue.line, 1, issue.line, 1),
        options: {
          isWholeLine: true,
          className: `vedix-line vedix-sev-${issue.severity}${
            issue.id === selectedIssueId ? " vedix-line-selected" : ""
          }`,
          glyphMarginClassName: `vedix-glyph vedix-sev-${issue.severity}`,
        },
      }))
    );
  }, [ready, file.path, fileIssues, selectedIssueId]);

  // scroll to the line when an issue was clicked
  useEffect(() => {
    if (!ready || !jumpTarget) return;
    if (jumpTarget.path !== file.path) return; // wait until that file is open

    const { editor } = ready;
    const lineCount = editor.getModel()?.getLineCount() ?? jumpTarget.line;
    const line = Math.min(Math.max(jumpTarget.line, 1), lineCount);

    editor.revealLineInCenter(line);
    editor.setPosition({ lineNumber: line, column: 1 });
    editor.focus();
    clearJump(); // done, so coming back to this tab later does not jump again
  }, [ready, jumpTarget, file.path, clearJump]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* file strip */}
      <div className="glass-panel flex items-center justify-between gap-4 border-b px-3 py-1.5 text-xs">
        <span className="truncate font-mono text-main">{file.path}</span>
        <span className="flex shrink-0 gap-3 text-muted">
          <span>
            Ln {cursor.line}, Col {cursor.column}
          </span>
          <span>{getLanguageLabel(file.language)}</span>
        </span>
      </div>

      <div className="glass-panel min-h-0 flex-1">
        <Editor
          height="100%"
          path={file.path}
          language={file.language}
          value={file.content}
          theme={theme === "dark" ? "vedix-dark" : "vedix-light"}
          beforeMount={handleBeforeMount}
          onMount={handleMount}
          onChange={(value) => onChange(value ?? "")}
          loading={<p className="text-sm text-muted">Loading editor</p>}
          options={{
            fontSize: 14,
            fontFamily: "'JetBrains Mono Variable', ui-monospace, monospace",
            minimap: { enabled: true },
            lineNumbers: "on",
            glyphMargin: true, // room for the issue dots
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 4,
            padding: { top: 8 },
            smoothScrolling: true,
            renderWhitespace: "selection",
          }}
        />
      </div>
    </div>
  );
}