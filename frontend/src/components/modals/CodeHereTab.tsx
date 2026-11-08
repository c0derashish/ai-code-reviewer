import Editor from "@monaco-editor/react";
import { LANGUAGES, getLanguageLabel } from "../../utils/language";

type CodeHereTabProps = {
  code: string;
  languageChoice: string; // "auto" or a language id
  language: string; // language actually used
  onCodeChange: (code: string) => void;
  onLanguageChange: (choice: string) => void;
};

export default function CodeHereTab({
  code,
  languageChoice,
  language,
  onCodeChange,
  onLanguageChange,
}: CodeHereTabProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="language-select" className="text-sm text-muted">
          Language
        </label>
        <select
          id="language-select"
          value={languageChoice}
          onChange={(e) => onLanguageChange(e.target.value)}
          className="rounded-md border border-line bg-base px-3 py-2 text-sm text-main"
        >
          <option value="auto">Auto-detect</option>
          {LANGUAGES.map((lang) => (
            <option key={lang.id} value={lang.id}>
              {lang.label}
            </option>
          ))}
        </select>

        {languageChoice === "auto" && (
          <span className="text-sm text-muted">
            Detected: {getLanguageLabel(language)} (best guess)
          </span>
        )}
      </div>

      <div className="relative overflow-hidden rounded-lg border border-line">
        <Editor
          height="280px"
          theme="vs-dark"
          language={language}
          value={code}
          onChange={(value) => onCodeChange(value ?? "")}
          loading={<p className="text-sm text-muted">Loading editor</p>}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "'JetBrains Mono Variable', ui-monospace, monospace",
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 4,
          }}
        />
        {code === "" && (
          <p className="pointer-events-none absolute left-14 top-1.5 font-mono text-[13px] text-muted">
            Paste or write code here
          </p>
        )}
      </div>
    </div>
  );
}