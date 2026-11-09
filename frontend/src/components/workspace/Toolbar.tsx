import { Link } from "react-router-dom";
import {
  Columns3,
  FileSearch,
  FolderSearch,
  PanelLeft,
  PanelRight,
  PanelTop,
} from "lucide-react";
import type { ReactNode } from "react";
import Button from "../common/Button";
import Logo from "../common/Logo";
import SettingsMenu from "../settings/SettingsMenu";
import { useWorkspace } from "../../context/WorkspaceContext";
import { getLanguageLabel } from "../../utils/language";
import type { AnalysisScope, AnalysisStatus } from "../../types";
import ProfileMenu from "../settings/ProfileMenu";

const STATUS_LABEL: Record<AnalysisStatus, string> = {
  not_started: "Not analysed",
  running: "Analysing",
  done: "Analysed",
  failed: "Analysis failed",
};

type ToolbarProps = {
  projectName: string;
  languageId: string;
  multiFile: boolean;
  onAnalyse: (scope: AnalysisScope) => void;
  onToggleExplorer?: () => void; // small screens only
  onToggleReview?: () => void; // small screens only
};

const STATUS_DOT: Record<AnalysisStatus, string> = {
  not_started: "bg-muted",
  running: "animate-pulse bg-saffron",
  done: "bg-ok",
  failed: "bg-danger",
};

function LayoutToggle() {
  const { layout, setLayout } = useWorkspace();

  function buttonClass(active: boolean) {
    return `rounded-md p-2 transition ${
      active ? "bg-saffron/15 text-saffron" : "text-muted hover:text-main"
    }`;
  }

  return (
    <div
      role="group"
      aria-label="Workspace layout"
      className="hidden items-center rounded-lg border border-line p-0.5 sm:flex"
    >
      <button
        type="button"
        title="Single screen"
        aria-label="Single screen"
        aria-pressed={layout === "single"}
        className={buttonClass(layout === "single")}
        onClick={() => setLayout("single")}
      >
        <Columns3 size={16} />
      </button>
      <button
        type="button"
        title="Tab view"
        aria-label="Tab view"
        aria-pressed={layout === "tabs"}
        className={buttonClass(layout === "tabs")}
        onClick={() => setLayout("tabs")}
      >
        <PanelTop size={16} />
      </button>
    </div>
  );
}

type AnalyseButtonProps = {
  icon: ReactNode;
  label: string;
  disabled: boolean;
  onClick: () => void;
};

function AnalyseButton({ icon, label, disabled, onClick }: AnalyseButtonProps) {
  return (
    <button
      type="button"
      title={disabled ? "Analysis is running" : label}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-md border border-saffron/50 px-3 py-2 text-sm text-saffron transition hover:bg-saffron/10 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {icon}
      <span className="hidden xl:inline">{label}</span>
    </button>
  );
}

export default function Toolbar({
  projectName,
  languageId,
  multiFile,
  onAnalyse,
  onToggleExplorer,
  onToggleReview,
}: ToolbarProps) {
  const { analysisStatus } = useWorkspace();

  return (
    <header className="relative z-20 flex shrink-0 items-center gap-3 px-3 py-2">
      {/* glass layer sits behind, so the settings menu can blur too */}
      <div
        aria-hidden="true"
        className="glass-panel pointer-events-none absolute inset-0 -z-10 border-b"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-linear-to-r from-transparent via-saffron to-transparent opacity-60"
      />
      <Link to="/" aria-label="Back to landing page">
        <Logo />
      </Link>

      <span className="hidden h-5 w-px bg-line sm:block" />

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <span className="truncate text-sm font-medium">{projectName}</span>
        <span className="hidden shrink-0 rounded border border-line px-2 py-0.5 text-xs text-muted sm:inline">
          {getLanguageLabel(languageId)}
        </span>
        <span className="hidden shrink-0 items-center gap-1.5 text-xs text-muted md:flex">
          <span className={`h-2 w-2 rounded-full ${STATUS_DOT[analysisStatus]}`} />
          {STATUS_LABEL[analysisStatus]}
        </span>
      </div>

      <AnalyseButton
        icon={<FileSearch size={16} />}
        label="Analyse file"
        disabled={analysisStatus === "running"}
        onClick={() => onAnalyse("file")}
      />
      {multiFile && (
        <AnalyseButton
          icon={<FolderSearch size={16} />}
          label="Analyse project"
          disabled={analysisStatus === "running"}
          onClick={() => onAnalyse("project")}
        />
      )}

      {onToggleExplorer && (
        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle file explorer"
          className="lg:hidden"
          onClick={onToggleExplorer}
        >
          <PanelLeft size={18} />
        </Button>
      )}
      {onToggleReview && (
        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle AI review"
          className="lg:hidden"
          onClick={onToggleReview}
        >
          <PanelRight size={18} />
        </Button>
      )}

      <LayoutToggle />
      <ProfileMenu />
      <SettingsMenu />
    </header>
  );
}