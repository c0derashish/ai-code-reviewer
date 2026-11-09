import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FolderOpen } from "lucide-react";
import Button from "../components/common/Button";
import EmptyState from "../components/common/EmptyState";
import CodeEditor from "../components/editor/CodeEditor";
import ReviewPanel from "../components/review/ReviewPanel";
import AssistantPanel from "../components/workspace/AssistantPanel";
import BottomPanel from "../components/workspace/BottomPanel";
import ExplorerPanel from "../components/workspace/ExplorerPanel";
import MetricsPanel from "../components/workspace/MetricsPanel";
import Toolbar from "../components/workspace/Toolbar";
import HeroBackground from "../components/landing/HeroBackground";
import { useWorkspace } from "../context/WorkspaceContext";
import type { Issue } from "../types";

const TABS = ["Code", "Review", "Metrics", "AI Assistant"] as const;
type TabName = (typeof TABS)[number];
type Drawer = "explorer" | "review" | null;

export default function WorkspacePage() {
  const navigate = useNavigate();
  const { layout, project, activeFile, selectFile, updateFile, requestAnalysis, openIssue } =
    useWorkspace();
  const [activeTab, setActiveTab] = useState<TabName>("Code");
  const [drawer, setDrawer] = useState<Drawer>(null);

  // opened /workspace without uploading anything (or refreshed the page)
  if (!project || !activeFile) {
    return (
      <div className="relative flex h-full items-center justify-center bg-base text-main">
        <HeroBackground />
        <EmptyState icon={<FolderOpen size={32} />} title="No project open">
          <p>Upload code or connect a repository first.</p>
          <Button className="mt-4" onClick={() => navigate("/")}>
            Back to start
          </Button>
        </EmptyState>
      </div>
    );
  }

  const single = layout === "single";
  const multiFile = project.files.length > 1;
  const showCode = single || activeTab === "Code";
  const showExplorer = multiFile && showCode;

  // is a drawer visible right now? (small screens only)
  const drawerActive =
    (drawer === "explorer" && showExplorer) || (drawer === "review" && single);

  function toggleDrawer(name: "explorer" | "review") {
    setDrawer(drawer === name ? null : name);
  }

  function handleSelect(path: string) {
    selectFile(path);
    setDrawer(null);
  }

  // clicked an issue: open file + line, show the code, close any drawer
  function handleOpenIssue(issue: Issue) {
    openIssue(issue);
    setActiveTab("Code");
    setDrawer(null);
  }

  // Below 1024px the side panels slide over the editor. From 1024px they sit in the row.
  const explorerClass = `${
    drawer === "explorer" ? "fixed inset-y-0 left-0 z-40 flex w-72" : "hidden lg:flex"
  } glass-panel shrink-0 flex-col border-r lg:static lg:w-60`;

  const reviewClass = `${
    drawer === "review" ? "fixed inset-y-0 right-0 z-40 flex w-80 max-w-full" : "hidden lg:flex"
  } glass-panel shrink-0 flex-col border-l lg:static lg:w-80`;

  return (
    <div className="relative flex h-full flex-col bg-base text-main">
      <HeroBackground />

      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
        <Toolbar
          projectName={project.name}
          languageId={activeFile.language}
          multiFile={multiFile}
          onAnalyse={requestAnalysis}
          onToggleExplorer={showExplorer ? () => toggleDrawer("explorer") : undefined}
          onToggleReview={single ? () => toggleDrawer("review") : undefined}
        />

        {!single && (
          <div
            role="tablist"
            className="glass-panel flex shrink-0 gap-1 overflow-x-auto border-b px-2"
          >
            {TABS.map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
                className={`whitespace-nowrap border-b-2 px-4 py-2 text-sm transition ${
                  activeTab === tab
                    ? "border-saffron text-saffron"
                    : "border-transparent text-muted hover:text-main"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        )}

        <div className="relative flex min-h-0 flex-1">
          {drawerActive && (
            <div
              className="fixed inset-0 z-30 bg-black/50 lg:hidden"
              onClick={() => setDrawer(null)}
            />
          )}

          {showExplorer && (
            <aside className={explorerClass}>
              <ExplorerPanel
                projectName={project.name}
                paths={project.files.map((f) => f.path)}
                activePath={activeFile.path}
                onSelect={handleSelect}
              />
            </aside>
          )}

          {showCode && (
            <div className="flex min-w-0 flex-1 flex-col">
              <CodeEditor
                file={activeFile}
                onChange={(content) => updateFile(activeFile.path, content)}
              />
              <BottomPanel />
            </div>
          )}

          {single && (
            <aside className={reviewClass}>
              <ReviewPanel onOpenIssue={handleOpenIssue} />
            </aside>
          )}

          {!single && activeTab === "Review" && (
            <div className="flex min-w-0 flex-1 flex-col">
              <ReviewPanel onOpenIssue={handleOpenIssue} />
            </div>
          )}

          {!single && activeTab === "Metrics" && (
            <div className="min-w-0 flex-1 overflow-auto">
              <MetricsPanel file={activeFile} files={project.files} />
            </div>
          )}

          {!single && activeTab === "AI Assistant" && (
            <div className="min-w-0 flex-1">
              <AssistantPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}