// One source file the user picked.
// path = where it sits inside the project, e.g. "src/app.py"
export type PickedFile = {
  file: File;
  path: string;
};

// What the user wants analysed.
export type Submission =
  | { kind: "files"; files: PickedFile[] } // 1 file = single-file mode, more = project
  | { kind: "zip"; file: File }
  | { kind: "paste"; code: string; language: string };

// A file opened in the workspace. content is editable.
export type ProjectFile = {
  path: string;
  name: string;
  language: string; // Monaco language id, e.g. "python"
  content: string;
};

// What the workspace shows.
export type Project = {
  name: string;
  files: ProjectFile[];
};

export type AnalysisStatus = "not_started" | "running" | "done" | "failed";

export type AnalysisScope = "file" | "project";


export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type IssueCategory =
  | "security"
  | "bug"
  | "complexity"
  | "maintainability"
  | "code_smell"
  | "performance"
  | "style";

// One finding. Phase 10 will fill these from the backend.
export type Issue = {
  id: string;
  filePath: string; // must match a ProjectFile path
  line: number; // 1-based
  severity: Severity;
  category: IssueCategory;
  title: string;
  explanation: string;
  suggestion?: string;
  before?: string; // code now
  after?: string; // code suggested
};

// "scroll the editor to this line". nonce makes repeated clicks count.
export type JumpTarget = { path: string; line: number; nonce: number };

export type User = {
  id: string;
  name: string;
  email: string;
  demo: boolean; // true = local demo session, not a real account
};


// One past analysis, as shown in History and Analytics.
export type AnalysisRecord = {
  id: string;
  projectName: string;
  date: string; // ISO date, e.g. "2026-10-30T09:15:00Z"
  language: string; // Monaco language id
  files: number;
  score: number | null; // null when the analysis failed
  issues: Record<Severity, number>;
  status: AnalysisStatus;
};