import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import Button from "../common/Button";
import ProblemsList from "./ProblemsList";
import { useWorkspace } from "../../context/WorkspaceContext";
import { API_CONFIGURED } from "../../services/api";

const TABS = ["Problems", "Analysis logs", "Terminal"] as const;
type TabName = (typeof TABS)[number];

export default function BottomPanel() {
  const { logs, issues, analysisStatus } = useWorkspace();
  const [open, setOpen] = useState(true);
  const [tab, setTab] = useState<TabName>("Problems");

  // when a NEW log line arrives, show the logs tab
  const lastCount = useRef(logs.length);
  useEffect(() => {
    if (logs.length > lastCount.current) {
      setTab("Analysis logs");
      setOpen(true);
    }
    lastCount.current = logs.length;
  }, [logs.length]);

  function pick(next: TabName) {
    setTab(next);
    setOpen(true);
  }

  return (
    <section aria-label="Bottom panel" className="glass-panel shrink-0 border-t">
      <div className="flex items-center justify-between pr-1">
        <div role="tablist" className="flex overflow-x-auto">
          {TABS.map((name) => {
            const active = open && tab === name;
            return (
              <button
                key={name}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => pick(name)}
                className={`whitespace-nowrap border-b-2 px-4 py-2 text-xs transition ${
                  active
                    ? "border-saffron text-main"
                    : "border-transparent text-muted hover:text-main"
                }`}
              >
                {name === "Problems" && issues.length > 0
                  ? `Problems (${issues.length})`
                  : name}
              </button>
            );
          })}
        </div>

        <Button
          variant="ghost"
          size="icon"
          aria-label={open ? "Collapse panel" : "Expand panel"}
          onClick={() => setOpen(!open)}
        >
          {open ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </Button>
      </div>

      {open && (
        <div className="h-40 overflow-auto border-t border-line p-3 text-sm">
          {tab === "Problems" && <ProblemsList />}

          {tab === "Analysis logs" && (
            <div className="space-y-1 font-mono text-xs text-muted">
              {logs.map((line, index) => (
                <p key={index}>{line}</p>
              ))}
              {!API_CONFIGURED && (
                <p>Backend is not connected. Set VITE_API_BASE_URL to enable analysis.</p>
              )}
              {API_CONFIGURED && analysisStatus === "not_started" && <p>Analysis not started.</p>}
            </div>
          )}

          {tab === "Terminal" && (
            <p className="text-muted">
              Terminal is planned for the desktop app. Not available yet.
            </p>
          )}
        </div>
      )}
    </section>
  );
}