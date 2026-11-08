import type { PickedFile, Submission } from "../types";
import { formatFileSize } from "../utils/format";
import {
  SUPPORTED_EXTENSIONS,
  getExtension,
  getLanguageFromFileName,
  getLanguageLabel,
} from "../utils/language";

// ---------- limits ----------
export const MAX_FILE_SIZE = 2 * 1024 * 1024; // per source file
export const MAX_ZIP_SIZE = 25 * 1024 * 1024; // per ZIP
export const MAX_FILES = 500;

// folders we never read
const IGNORED_FOLDERS = [
  "node_modules",
  ".git",
  "dist",
  "build",
  "__pycache__",
  "venv",
  ".venv",
  ".idea",
  ".vscode",
];

// ---------- reading what the user picked ----------

// From a Choose file / Choose folder / ZIP input
export function filesFromInput(list: FileList): PickedFile[] {
  return Array.from(list).map((file) => ({
    file,
    // webkitRelativePath is filled when a folder is chosen
    path: file.webkitRelativePath || file.name,
  }));
}

function readFileEntry(entry: FileSystemFileEntry): Promise<File> {
  return new Promise((resolve, reject) => entry.file(resolve, reject));
}

// folders return their children in batches, so keep reading until empty
function readAllEntries(dir: FileSystemDirectoryEntry): Promise<FileSystemEntry[]> {
  const reader = dir.createReader();
  return new Promise((resolve, reject) => {
    const all: FileSystemEntry[] = [];
    function readBatch() {
      reader.readEntries((batch) => {
        if (batch.length === 0) {
          resolve(all);
        } else {
          all.push(...batch);
          readBatch();
        }
      }, reject);
    }
    readBatch();
  });
}

// walk one dropped file or folder, collect every file inside
async function walk(entry: FileSystemEntry, parentPath: string, out: PickedFile[]) {
  const path = parentPath + entry.name;

  if (entry.isFile) {
    const file = await readFileEntry(entry as FileSystemFileEntry);
    out.push({ file, path });
  } else if (entry.isDirectory) {
    // do not even enter node_modules, .git, etc.
    if (IGNORED_FOLDERS.includes(entry.name)) return;
    const children = await readAllEntries(entry as FileSystemDirectoryEntry);
    for (const child of children) {
      await walk(child, path + "/", out);
    }
  }
}

// From drag and drop (files and folders)
export async function filesFromDrop(items: DataTransferItemList): Promise<PickedFile[]> {
  // must grab entries right away, before any await
  const entries: FileSystemEntry[] = [];
  for (const item of Array.from(items)) {
    const entry = item.webkitGetAsEntry();
    if (entry) entries.push(entry);
  }

  const out: PickedFile[] = [];
  for (const entry of entries) {
    await walk(entry, "", out);
  }
  return out;
}

// ---------- checking ----------

type PrepareResult = {
  files: PickedFile[];
  skipped: number;
  error: string | null;
};

function prepareFiles(picked: PickedFile[]): PrepareResult {
  const files: PickedFile[] = [];
  let skipped = 0;

  for (const item of picked) {
    const folders = item.path.split("/").slice(0, -1);
    const inIgnoredFolder = folders.some((name) => IGNORED_FOLDERS.includes(name));
    const supported = SUPPORTED_EXTENSIONS.includes(getExtension(item.file.name));
    const empty = item.file.size === 0;

    if (inIgnoredFolder || !supported || empty) {
      skipped += 1;
    } else {
      files.push(item);
    }
  }

  if (files.length === 0) {
    const list = SUPPORTED_EXTENSIONS.map((ext) => "." + ext).join(" ");
    return { files, skipped, error: `No supported source files found. Supported types: ${list}` };
  }

  const tooBig = files.find((f) => f.file.size > MAX_FILE_SIZE);
  if (tooBig) {
    return {
      files,
      skipped,
      error: `${tooBig.path} is ${formatFileSize(tooBig.file.size)}. Limit is ${formatFileSize(MAX_FILE_SIZE)} per file.`,
    };
  }

  if (files.length > MAX_FILES) {
    return { files, skipped, error: `Too many files (${files.length}). Limit is ${MAX_FILES}.` };
  }

  return { files, skipped, error: null };
}

function checkZip(file: File): string | null {
  if (file.size === 0) return `${file.name} is empty.`;
  if (file.size > MAX_ZIP_SIZE) {
    return `${file.name} is ${formatFileSize(file.size)}. ZIP limit is ${formatFileSize(MAX_ZIP_SIZE)}.`;
  }
  return null;
}

export type PickResult = {
  selection: Submission | null;
  skipped: number;
  error: string | null;
};

// Takes whatever the user picked or dropped, returns a clean selection or an error
export function processPicked(picked: PickedFile[]): PickResult {
  if (picked.length === 0) {
    return { selection: null, skipped: 0, error: "No files found." };
  }

  // exactly one ZIP
  if (picked.length === 1 && getExtension(picked[0].file.name) === "zip") {
    const error = checkZip(picked[0].file);
    if (error) return { selection: null, skipped: 0, error };
    return { selection: { kind: "zip", file: picked[0].file }, skipped: 0, error: null };
  }

  const result = prepareFiles(picked);
  if (result.error) {
    return { selection: null, skipped: result.skipped, error: result.error };
  }
  return {
    selection: { kind: "files", files: result.files },
    skipped: result.skipped,
    error: null,
  };
}

// Pasted code check. Returns an error message or null.
export function checkPastedCode(code: string): string | null {
  if (code.trim() === "") return "Paste or write some code first.";
  if (new Blob([code]).size > MAX_FILE_SIZE) {
    return `Code is larger than ${formatFileSize(MAX_FILE_SIZE)}. Upload it as a file instead.`;
  }
  return null;
}

// ---------- text for the UI ----------

export function describeSubmission(s: Submission): { title: string; lines: string[] } {
  if (s.kind === "zip") {
    return {
      title: s.file.name,
      lines: [`Size: ${formatFileSize(s.file.size)}`, "Type: project (ZIP)"],
    };
  }

  if (s.kind === "paste") {
    return {
      title: "Pasted code",
      lines: [
        `Language: ${getLanguageLabel(s.language)}`,
        `Lines: ${s.code.split("\n").length}`,
        "Type: single file",
      ],
    };
  }

  if (s.files.length === 1) {
    const only = s.files[0];
    const language = getLanguageFromFileName(only.file.name) ?? "plaintext";
    return {
      title: only.path,
      lines: [
        `Size: ${formatFileSize(only.file.size)}`,
        `Language: ${getLanguageLabel(language)}`,
        "Type: single file",
      ],
    };
  }

  const total = s.files.reduce((sum, f) => sum + f.file.size, 0);
  return {
    title: `${s.files.length} files`,
    lines: [`Total size: ${formatFileSize(total)}`, "Type: project"],
  };
}