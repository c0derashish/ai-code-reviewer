import type { Monaco } from "@monaco-editor/react";

export function defineVedixThemes(monaco: Monaco) {
  monaco.editor.defineTheme("vedix-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#00000000",
      "editor.foreground": "#f2f2f2",
      "editorGutter.background": "#00000000",
      "minimap.background": "#06060620",
      "editorLineNumber.foreground": "#5c5c5c",
      "editorLineNumber.activeForeground": "#ff9933",
      "editor.lineHighlightBackground": "#ff993312",
      "editor.selectionBackground": "#ff993340",
      "editorCursor.foreground": "#ff9933",
      "editorWidget.background": "#0b0b0b",
      "editorStickyScroll.background": "#0b0b0bf5",
      "editorStickyScrollHover.background": "#1a1208f5",
      "editorStickyScroll.border": "#ff993340",
      "editorStickyScroll.shadow": "#00000066",

      // scrollbars + minimap slider
      "scrollbarSlider.background": "#ff993338",
      "scrollbarSlider.hoverBackground": "#ff993366",
      "scrollbarSlider.activeBackground": "#ff993399",
      "minimapSlider.background": "#ff993326",
      "minimapSlider.hoverBackground": "#ff993345",
      "minimapSlider.activeBackground": "#ff993366",
      "editorOverviewRuler.border": "#00000000",
      "editorOverviewRuler.background": "#06060620",
    },
  });

  monaco.editor.defineTheme("vedix-light", {
    base: "vs",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#00000000",
      "editor.foreground": "#111111",
      "editorGutter.background": "#00000000",
      "minimap.background": "#f6f6f6",
      "editorLineNumber.foreground": "#9a9a9a",
      "editorLineNumber.activeForeground": "#d9660a",
      "editor.lineHighlightBackground": "#d9660a12",
      "editor.selectionBackground": "#d9660a30",
      "editorCursor.foreground": "#d9660a",
      "editorWidget.background": "#ffffff",
      "editorStickyScroll.background": "#f4f4f4f5",
      "editorStickyScrollHover.background": "#fbeedef5",
      "editorStickyScroll.border": "#d9660a40",
      "editorStickyScroll.shadow": "#00000026",

      // scrollbars + minimap slider
      "scrollbarSlider.background": "#d9660a40",
      "scrollbarSlider.hoverBackground": "#d9660a70",
      "scrollbarSlider.activeBackground": "#d9660aa0",
      "minimapSlider.background": "#d9660a30",
      "minimapSlider.hoverBackground": "#d9660a50",
      "minimapSlider.activeBackground": "#d9660a70",
      "editorOverviewRuler.border": "#00000000",
      "editorOverviewRuler.background": "#f6f6f6",
    },
  });
}