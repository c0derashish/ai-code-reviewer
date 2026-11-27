import { createContext, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";
import { readSetting, saveSetting } from "../utils/storage";
import { makeSampleIssues } from "../utils/sampleIssues";
import { API_CONFIGURED, ApiError } from "../services/api";
import { startAnalysis, toIssues, waitForAnalysis } from "../services/analysisService";
import type {
  AnalysisScope,
  AnalysisStatus,
  Issue,
  JumpTarget,
  Project,
  ProjectFile,
} from "../types";

export type WorkspaceLayout = "single" | "tabs";

const LAYOUTS = ["single", "tabs"] as const;
const STORAGE_KEY = "vedix-layout";
const SAVE_KEY = "vedix-save";
const SAVE_VALUES = ["on", "off"] as const;

// repoId: the fetched GitHub repository this project came from (the server needs it for the licence rule)
// issues: issues of a saved analysis, shown right away
export type OpenOptions = { repoId?: string | null; issues?: Issue[] };

type WorkspaceContextValue = {
  // layout (saved in browser)
  layout: WorkspaceLayout;
  setLayout: (layout: WorkspaceLayout) => void;

  // save analyses to the history of a signed-in user (saved in browser)
  saveToHistory: boolean;
  setSaveToHistory: (value: boolean) => void;

  // open project (kept in memory only, lost on refresh)
  project: Project | null;
  repoId: string | null;
  activeFile: ProjectFile | null;
  openProject: (project: Project, options?: OpenOptions) => void;
  selectFile: (path: string) => void;
  updateFile: (path: string, content: string) => void;

  // analysis
  analysisStatus: AnalysisStatus;
  logs: string[];
  requestAnalysis: (scope: AnalysisScope) => void;

  // review issues
  issues: Issue[];
  issuesAreSample: boolean; // true = test data, not a real analysis
  issuesStale: boolean; // true = code was edited after the issues were made
  selectedIssueId: string | null;
  jumpTarget: JumpTarget | null;
  openIssue: (issue: Issue) => void;
  clearJump: () => void;
  loadSampleIssues: () => void;
  clearIssues: () => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [layout, setLayoutState] = useState<WorkspaceLayout>(() =>
    readSetting(STORAGE_KEY, LAYOUTS, "single")
  );
  const [saveToHistory, setSaveState] = useState<boolean>(
    () => readSetting(SAVE_KEY, SAVE_VALUES, "on") === "on"
  );
  const [project, setProject] = useState<Project | null>(null);
  const [repoId, setRepoId] = useState<string | null>(null);
  const [activePath, setActivePath] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus>("not_started");

  const [issues, setIssues] = useState<Issue[]>([]);
  const [issuesAreSample, setIssuesAreSample] = useState(false);
  const [issuesStale, setIssuesStale] = useState(false);
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);
  const [jumpTarget, setJumpTarget] = useState<JumpTarget | null>(null);
  const jumpCount = useRef(0);

  // runId: a new run or a new project makes the old run stop quietly
  const runId = useRef(0);
  // editCount: used to tell if the code changed while analysis was running
  const editCount = useRef(0);

  function addLog(line: string) {
    setLogs((current) => [...current, line].slice(-200));
  }

  function setLayout(next: WorkspaceLayout) {
    setLayoutState(next);
    saveSetting(STORAGE_KEY, next);
  }

  function setSaveToHistory(value: boolean) {
    setSaveState(value);
    saveSetting(SAVE_KEY, value ? "on" : "off");
  }

  function clearIssues() {
    setIssues([]);
    setIssuesAreSample(false);
    setIssuesStale(false);
    setSelectedIssueId(null);
    setJumpTarget(null);
  }

  function openProject(next: Project, options: OpenOptions = {}) {
    runId.current += 1; // stop any run for the old project
    setProject(next);
    setRepoId(options.repoId ?? null);
    setActivePath(next.files[0]?.path ?? null);
    clearIssues();

    const loaded = options.issues ?? [];
    const count = next.files.length;
    const lines = [`Loaded "${next.name}": ${count} file${count === 1 ? "" : "s"}.`];

    if (loaded.length > 0) {
      setIssues(loaded);
      setAnalysisStatus("done");
      lines.push(`Opened a saved analysis with ${loaded.length} issue${loaded.length === 1 ? "" : "s"}.`);
    } else {
      setAnalysisStatus("not_started");
    }
    setLogs(lines);
  }

  function selectFile(path: string) {
    setActivePath(path);
  }

  function updateFile(path: string, content: string) {
    editCount.current += 1;
    setProject((current) => {
      if (!current) return current;
      return {
        ...current,
        files: current.files.map((f) => (f.path === path ? { ...f, content } : f)),
      };
    });
    setIssuesStale(true);
  }

  const activeFile =
    project?.files.find((f) => f.path === activePath) ?? project?.files[0] ?? null;

  async function requestAnalysis(scope: AnalysisScope) {
    if (!project || !activeFile) return;
    if (analysisStatus === "running") return;

    const target =
      scope === "file"
        ? activeFile.path
        : `${project.name} (${project.files.length} files)`;

    if (!API_CONFIGURED) {
      addLog(
        `Analysis requested: ${target}. Backend is not connected, so nothing was sent. Set VITE_API_BASE_URL to connect it.`
      );
      return;
    }

    runId.current += 1;
    const myRun = runId.current;
    const isCurrent = () => runId.current === myRun;
    const editsAtStart = editCount.current;

    setAnalysisStatus("running");
    addLog(`Sending ${target} for analysis.`);

    try {
      const started = await startAnalysis(project, scope, activeFile.path, {
        save: saveToHistory,
        repoId,
      });
      if (!isCurrent()) return;
      addLog(`Analysis queued (id ${started.id}).`);

      const result = await waitForAnalysis(started.id, () => !isCurrent());
      if (!result || !isCurrent()) return;

      if (result.status === "failed") {
        setAnalysisStatus("failed");
        addLog(`Analysis failed: ${(result.error ?? "no reason given").slice(0, 300)}`);
        return;
      }

      const validPaths = new Set(project.files.map((f) => f.path));
      const { issues: found, dropped } = toIssues(result.issues, validPaths);

      setIssues(found);
      setIssuesAreSample(false);
      setIssuesStale(editCount.current !== editsAtStart);
      setSelectedIssueId(null);
      setJumpTarget(null);
      setAnalysisStatus("done");

      addLog(`Analysis finished: ${found.length} issue${found.length === 1 ? "" : "s"}.`);
      if (dropped > 0) addLog(`${dropped} issue(s) ignored: unknown file or invalid line.`);

      // the server tells us if it saved the analysis to the history
      const summary = result.summary;
      if (summary?.saved === true) {
        addLog("Saved to your history.");
      } else if (summary?.saved === false) {
        addLog(`Not saved: ${String(summary.save_error ?? "unknown reason").slice(0, 200)}`);
      }
    } catch (err) {
      if (!isCurrent()) return;
      setAnalysisStatus("failed");
      addLog(`Analysis failed: ${err instanceof ApiError ? err.message : "unexpected error."}`);
    }
  }

  // open the issue's file and ask the editor to scroll to its line
  function openIssue(issue: Issue) {
    setSelectedIssueId(issue.id);
    setActivePath(issue.filePath);
    jumpCount.current += 1;
    setJumpTarget({ path: issue.filePath, line: issue.line, nonce: jumpCount.current });
  }

  function clearJump() {
    setJumpTarget(null);
  }

  // UI test only. The button for this shows in dev mode.
  function loadSampleIssues() {
    if (!project) return;
    setIssues(makeSampleIssues(project.files));
    setIssuesAreSample(true);
    setIssuesStale(false);
    setSelectedIssueId(null);
    setJumpTarget(null);
  }

  return (
    <WorkspaceContext.Provider
      value={{
        layout,
        setLayout,
        saveToHistory,
        setSaveToHistory,
        project,
        repoId,
        activeFile,
        openProject,
        selectFile,
        updateFile,
        analysisStatus,
        logs,
        requestAnalysis,
        issues,
        issuesAreSample,
        issuesStale,
        selectedIssueId,
        jumpTarget,
        openIssue,
        clearJump,
        loadSampleIssues,
        clearIssues,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return value;
}