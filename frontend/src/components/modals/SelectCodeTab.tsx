import { useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { Archive, FileCode, FolderOpen, Trash2, Upload } from "lucide-react";
import Button from "../common/Button";
import type { PickedFile, Submission } from "../../types";
import { describeSubmission, filesFromDrop, filesFromInput } from "../../services/uploadService";
import { formatFileSize } from "../../utils/format";
import { SUPPORTED_EXTENSIONS } from "../../utils/language";

const FILE_ACCEPT = SUPPORTED_EXTENSIONS.map((ext) => "." + ext).join(",");

type SelectCodeTabProps = {
  selection: Submission | null;
  skipped: number;
  onPicked: (picked: PickedFile[]) => void;
  onError: (message: string) => void;
  onClear: () => void;
};

export default function SelectCodeTab({
  selection,
  skipped,
  onPicked,
  onError,
  onClear,
}: SelectCodeTabProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const zipInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  // used by all three hidden inputs
  function handleInput(e: ChangeEvent<HTMLInputElement>) {
    const list = e.target.files;
    if (list && list.length > 0) {
      onPicked(filesFromInput(list));
    }
    // reset so the same file can be picked again
    e.target.value = "";
  }

  async function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    try {
      const picked = await filesFromDrop(e.dataTransfer.items);
      onPicked(picked);
    } catch {
      onError("Could not read the dropped items. Use the Choose buttons instead.");
    }
  }

  return (
    <div className="space-y-4">
      {/* hidden inputs, opened by the buttons below */}
      <input
        ref={fileInput}
        type="file"
        multiple
        accept={FILE_ACCEPT}
        className="hidden"
        onChange={handleInput}
      />
      <input
        ref={folderInput}
        type="file"
        className="hidden"
        onChange={handleInput}
        {...({ webkitdirectory: "" } as object)}
      />
      <input
        ref={zipInput}
        type="file"
        accept=".zip"
        className="hidden"
        onChange={handleInput}
      />

      {/* drop zone */}
      <div
        role="group"
        aria-label="Drop zone"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
        }}
        onDrop={handleDrop}
        className={`flex flex-col items-center rounded-lg border-2 border-dashed px-6 py-8 text-center transition ${
          dragging ? "border-saffron bg-saffron/10" : "border-line bg-base/40"
        }`}
      >
        <Upload size={28} className="text-saffron" />
        <p className="mt-3 font-medium">Drag a file, folder, or ZIP here</p>
        <p className="mt-1 text-sm text-muted">or choose one</p>

        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <Button
            variant="outline"
            icon={<FileCode size={16} />}
            onClick={() => fileInput.current?.click()}
          >
            Choose file
          </Button>
          <Button
            variant="outline"
            icon={<FolderOpen size={16} />}
            onClick={() => folderInput.current?.click()}
          >
            Choose folder
          </Button>
          <Button
            variant="outline"
            icon={<Archive size={16} />}
            onClick={() => zipInput.current?.click()}
          >
            Upload ZIP
          </Button>
        </div>

        <p className="mt-4 max-w-md text-xs text-muted">
          ZIP up to 25 MB. Source files up to 2 MB each. Folders skip node_modules, .git, and
          build output.
        </p>
      </div>

      {selection && (
        <SelectionSummary selection={selection} skipped={skipped} onClear={onClear} />
      )}
    </div>
  );
}

// ---------- what the user picked ----------

type SelectionSummaryProps = {
  selection: Submission;
  skipped: number;
  onClear: () => void;
};

function SelectionSummary({ selection, skipped, onClear }: SelectionSummaryProps) {
  const info = describeSubmission(selection);

  let Icon = FileCode;
  if (selection.kind === "zip") Icon = Archive;
  if (selection.kind === "files" && selection.files.length > 1) Icon = FolderOpen;

  return (
    <div className="rounded-lg border border-line bg-base/60 p-4">
      <div className="flex items-start gap-3">
        <Icon size={22} className="mt-0.5 shrink-0 text-saffron" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">{info.title}</p>
          {info.lines.map((line) => (
            <p key={line} className="text-sm text-muted">
              {line}
            </p>
          ))}
        </div>
        <Button variant="ghost" size="icon" aria-label="Remove selection" onClick={onClear}>
          <Trash2 size={16} />
        </Button>
      </div>

      {selection.kind === "files" && selection.files.length > 1 && (
        <ul className="mt-3 space-y-1 border-t border-line pt-3 font-mono text-xs text-muted">
          {selection.files.slice(0, 5).map((f, i) => (
            <li key={`${f.path}-${i}`} className="flex justify-between gap-4">
              <span className="truncate">{f.path}</span>
              <span className="shrink-0">{formatFileSize(f.file.size)}</span>
            </li>
          ))}
          {selection.files.length > 5 && <li>+ {selection.files.length - 5} more</li>}
        </ul>
      )}

      {skipped > 0 && (
        <p className="mt-3 text-xs text-muted">
          {skipped} file(s) skipped: unsupported type, empty, or inside folders like
          node_modules.
        </p>
      )}
    </div>
  );
}