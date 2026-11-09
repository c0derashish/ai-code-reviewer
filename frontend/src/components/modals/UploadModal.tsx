import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Code, FolderOpen, LoaderCircle, Upload } from "lucide-react";
import Modal from "./Modal";
import SelectCodeTab from "./SelectCodeTab";
import CodeHereTab from "./CodeHereTab";
import Button from "../common/Button";
import Notice from "../common/Notice";
import { useWorkspace } from "../../context/WorkspaceContext";
import type { PickedFile, Submission } from "../../types";
import { buildProject, checkPastedCode, processPicked } from "../../services/uploadService";
import { detectLanguageFromCode } from "../../utils/language";

type Tab = "select" | "code";

type UploadModalProps = {
  onClose: () => void;
};

function tabClass(active: boolean) {
  return `flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium transition ${
    active ? "bg-saffron/15 text-saffron" : "text-muted hover:text-main"
  }`;
}

export default function UploadModal({ onClose }: UploadModalProps) {
  const navigate = useNavigate();
  const { openProject } = useWorkspace();

  const [tab, setTab] = useState<Tab>("select");
  const [selection, setSelection] = useState<Submission | null>(null);
  const [skipped, setSkipped] = useState(0);
  const [code, setCode] = useState("");
  const [languageChoice, setLanguageChoice] = useState("auto");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // language actually used: the user's choice, or our best guess
  const language = useMemo(
    () => (languageChoice === "auto" ? detectLanguageFromCode(code) : languageChoice),
    [code, languageChoice]
  );

  function handlePicked(picked: PickedFile[]) {
    const result = processPicked(picked);
    setSelection(result.selection);
    setSkipped(result.skipped);
    setError(result.error);
  }

  function handleClear() {
    setSelection(null);
    setSkipped(0);
    setError(null);
  }

  function switchTab(next: Tab) {
    setTab(next);
    setError(null);
  }

  function handleCodeChange(next: string) {
    setCode(next);
    setError(null);
  }

  async function handleSubmit() {
    let submission: Submission;

    if (tab === "select") {
      if (!selection) {
        setError("Choose a file, folder, or ZIP first.");
        return;
      }
      submission = selection;
    } else {
      const problem = checkPastedCode(code);
      if (problem) {
        setError(problem);
        return;
      }
      submission = { kind: "paste", code, language };
    }

    setError(null);
    setLoading(true);
    try {
      const project = await buildProject(submission);
      openProject(project);
      navigate("/workspace");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read the files. Try again.");
      setLoading(false);
    }
  }

  return (
    <Modal title="Upload your code" onClose={onClose}>
      {/* the two options */}
      <div role="tablist" className="mb-4 flex gap-1 rounded-lg border border-line bg-base/60 p-1">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "select"}
          className={tabClass(tab === "select")}
          onClick={() => switchTab("select")}
        >
          <FolderOpen size={16} />
          Select code
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "code"}
          className={tabClass(tab === "code")}
          onClick={() => switchTab("code")}
        >
          <Code size={16} />
          Code here
        </button>
      </div>

      {tab === "select" ? (
        <SelectCodeTab
          selection={selection}
          skipped={skipped}
          onPicked={handlePicked}
          onError={setError}
          onClear={handleClear}
        />
      ) : (
        <CodeHereTab
          code={code}
          languageChoice={languageChoice}
          language={language}
          onCodeChange={handleCodeChange}
          onLanguageChange={setLanguageChoice}
        />
      )}

      {error && (
        <div className="mt-4">
          <Notice kind="error">{error}</Notice>
        </div>
      )}

      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          disabled={loading}
          icon={
            loading ? <LoaderCircle size={16} className="animate-spin" /> : <Upload size={16} />
          }
          onClick={handleSubmit}
        >
          {loading ? "Reading files" : "Open in workspace"}
        </Button>
      </div>
    </Modal>
  );
}