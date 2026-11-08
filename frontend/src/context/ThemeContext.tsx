import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { readSetting, saveSetting } from "../utils/storage";

export type Theme = "dark" | "light";

const THEMES = ["dark", "light"] as const;
const STORAGE_KEY = "vedix-theme"; // same key as in index.html

type ThemeContextValue = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() =>
    readSetting(STORAGE_KEY, THEMES, "dark")
  );

  // put the theme on <html>, CSS colors follow
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  function setTheme(next: Theme) {
    setThemeState(next);
    saveSetting(STORAGE_KEY, next);
  }

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider");
  return value;
}