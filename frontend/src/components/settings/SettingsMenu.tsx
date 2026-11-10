import { Columns3, LogOut, Moon, PanelTop, Settings, Sun, X } from "lucide-react";
import Button from "../common/Button";
import OptionGroup from "./OptionGroup";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../context/ThemeContext";
import type { Theme } from "../../context/ThemeContext";
import { useWorkspace } from "../../context/WorkspaceContext";
import type { WorkspaceLayout } from "../../context/WorkspaceContext";
import { usePopover } from "../../hooks/usePopover";

const LAYOUT_HELP: Record<WorkspaceLayout, string> = {
  single: "Explorer, editor, and review side by side.",
  tabs: "One panel at a time: Code, Review, Metrics, AI Assistant.",
};

export default function SettingsMenu() {
  const { open, setOpen, ref } = usePopover();
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const { layout, setLayout } = useWorkspace();

  return (
    <div ref={ref} className="relative">
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
          className="modal-in glass-panel absolute right-0 top-full z-30 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border p-4 shadow-2xl [--glass-alpha:70%]"
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
              <p className="mt-2 text-xs text-muted">Applies to every page.</p>
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

            {user && (
              <div className="border-t border-line pt-3">
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    logout();
                  }}
                  className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition hover:bg-saffron/10 hover:text-saffron"
                >
                  <LogOut size={16} />
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}