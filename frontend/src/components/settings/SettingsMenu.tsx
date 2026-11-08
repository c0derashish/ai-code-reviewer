import { useEffect, useRef, useState } from "react";
import { Columns3, Moon, PanelTop, Settings, Sun, X } from "lucide-react";
import Button from "../common/Button";
import OptionGroup from "./OptionGroup";
import { useTheme } from "../../context/ThemeContext";
import type { Theme } from "../../context/ThemeContext";
import { useWorkspace } from "../../context/WorkspaceContext";
import type { WorkspaceLayout } from "../../context/WorkspaceContext";

const LAYOUT_HELP: Record<WorkspaceLayout, string> = {
  single: "Explorer, editor, and review side by side.",
  tabs: "One panel at a time: Code, Review, Metrics, AI Assistant.",
};

export default function SettingsMenu() {
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const { theme, setTheme } = useTheme();
  const { layout, setLayout } = useWorkspace();

  // while open: close on outside click or Escape
  useEffect(() => {
    if (!open) return;

    function handleClick(e: MouseEvent) {
      if (wrapper.current && !wrapper.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  return (
    <div ref={wrapper} className="relative">
      <Button
        variant="ghost"
        size="icon"
        aria-label="Settings"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <Settings size={20} />
      </Button>

      {open && (
        <div
          role="dialog"
          aria-label="Settings"
          className="modal-in absolute right-0 top-full z-30 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-line bg-raised/95 p-4 shadow-2xl backdrop-blur-xl"
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold">Settings</h2>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Close settings"
              onClick={() => setOpen(false)}
            >
              <X size={16} />
            </Button>
          </div>

          <div className="space-y-5">
            <div>
              <p className="mb-2 text-sm font-medium">Theme</p>
              <OptionGroup<Theme>
                label="Theme"
                value={theme}
                onChange={setTheme}
                options={[
                  { value: "dark", label: "Dark", icon: <Moon size={16} /> },
                  { value: "light", label: "Light", icon: <Sun size={16} /> },
                ]}
              />
              <p className="mt-2 text-xs text-muted">
                Applies to workspace and account pages. The landing page always stays dark.
              </p>
            </div>

            <div>
              <p className="mb-2 text-sm font-medium">Workspace layout</p>
              <OptionGroup<WorkspaceLayout>
                label="Workspace layout"
                value={layout}
                onChange={setLayout}
                options={[
                  { value: "tabs", label: "Tab view", icon: <PanelTop size={16} /> },
                  { value: "single", label: "Single screen", icon: <Columns3 size={16} /> },
                ]}
              />
              <p className="mt-2 text-xs text-muted">{LAYOUT_HELP[layout]}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}