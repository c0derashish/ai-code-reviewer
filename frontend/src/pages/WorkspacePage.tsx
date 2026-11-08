import { useState } from "react";
import { Link } from "react-router-dom";
import Logo from "../components/common/Logo";
import SettingsMenu from "../components/settings/SettingsMenu";
import { useTheme } from "../context/ThemeContext";
import { useWorkspace } from "../context/WorkspaceContext";

const TABS = ["Code", "Review", "Metrics", "AI Assistant"];

function Box({ title }: { title: string }) {
  return (
    <div className="flex min-h-40 items-center justify-center rounded-lg border border-line bg-panel p-4 text-muted">
      {title}
    </div>
  );
}

export default function WorkspacePage() {
  const { theme } = useTheme();
  const { layout } = useWorkspace();
  const [activeTab, setActiveTab] = useState("Code");

  return (
    <div className="flex h-full flex-col bg-base text-main">
      <header className="flex items-center justify-between border-b border-line bg-panel px-4 py-2.5">
        <Link to="/" aria-label="Back to landing page">
          <Logo />
        </Link>
        <SettingsMenu />
      </header>

      <main className="flex-1 space-y-4 overflow-auto p-4">
        <p className="text-sm text-muted">
          Temporary page. Theme: <b className="text-main">{theme}</b>. Layout:{" "}
          <b className="text-main">{layout}</b>.
        </p>

        {layout === "single" ? (
          <div className="grid gap-4 lg:grid-cols-[240px_1fr_320px]">
            <Box title="File explorer" />
            <Box title="Code editor" />
            <Box title="AI review" />
          </div>
        ) : (
          <div className="space-y-4">
            <div role="tablist" className="flex gap-1 border-b border-line">
              {TABS.map((tab) => (
                <button
                  key={tab}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm transition ${
                    activeTab === tab
                      ? "border-b-2 border-saffron text-saffron"
                      : "text-muted hover:text-main"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
            <Box title={activeTab} />
          </div>
        )}
      </main>
    </div>
  );
}