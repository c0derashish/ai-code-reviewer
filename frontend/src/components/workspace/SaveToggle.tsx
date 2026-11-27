import { History } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useWorkspace } from "../../context/WorkspaceContext";

// A switch next to the Analyse buttons. Only signed-in users see it, because only their analyses can be saved.
export default function SaveToggle() {
  const { user } = useAuth();
  const { saveToHistory, setSaveToHistory } = useWorkspace();

  if (!user) return null;

  return (
    <button
      type="button"
      role="switch"
      aria-checked={saveToHistory}
      onClick={() => setSaveToHistory(!saveToHistory)}
      title={
        saveToHistory
          ? "Analyses are saved to your history. Click to stop saving."
          : "Analyses are not saved. Click to save them to your history."
      }
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm transition ${
        saveToHistory ? "border-saffron/50 text-saffron" : "border-line text-muted hover:text-main"
      }`}
    >
      <History size={16} />
      <span className="hidden xl:inline">{saveToHistory ? "Saving" : "Not saving"}</span>
    </button>
  );
}