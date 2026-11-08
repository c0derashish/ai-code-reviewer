// One source file the user picked.
// path = where it sits inside the project, e.g. "src/app.py"
export type PickedFile = {
  file: File;
  path: string;
};

// What the user wants analysed. The workspace (Phase 5) will read this.
export type Submission =
  | { kind: "files"; files: PickedFile[] } // 1 file = single-file mode, more = project
  | { kind: "zip"; file: File }
  | { kind: "paste"; code: string; language: string };