import { createContext, useContext, useState } from "react";
import type { ReactNode } from "react";
import { readSetting, saveSetting } from "../utils/storage";

export type WorkspaceLayout = "single" | "tabs";

const LAYOUTS = ["single", "tabs"] as const;
const STORAGE_KEY = "vedix-layout";

type WorkspaceContextValue = {
  layout: WorkspaceLayout;
  setLayout: (layout: WorkspaceLayout) => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [layout, setLayoutState] = useState<WorkspaceLayout>(() =>
    readSetting(STORAGE_KEY, LAYOUTS, "single")
  );

  function setLayout(next: WorkspaceLayout) {
    setLayoutState(next);
    saveSetting(STORAGE_KEY, next);
  }

  return (
    <WorkspaceContext.Provider value={{ layout, setLayout }}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return value;
}