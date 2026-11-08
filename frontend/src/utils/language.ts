export type Language = {
  id: string;
  label: string;
  extensions: string[];
};

export const LANGUAGES: Language[] = [
  { id: "python", label: "Python", extensions: ["py"] },
  { id: "javascript", label: "JavaScript", extensions: ["js", "jsx", "mjs", "cjs"] },
  { id: "typescript", label: "TypeScript", extensions: ["ts", "tsx"] },
  { id: "java", label: "Java", extensions: ["java"] },
  { id: "c", label: "C", extensions: ["c", "h"] },
  { id: "cpp", label: "C++", extensions: ["cpp", "cc", "hpp"] },
  { id: "csharp", label: "C#", extensions: ["cs"] },
  { id: "go", label: "Go", extensions: ["go"] },
  { id: "rust", label: "Rust", extensions: ["rs"] },
  { id: "ruby", label: "Ruby", extensions: ["rb"] },
  { id: "php", label: "PHP", extensions: ["php"] },
  { id: "swift", label: "Swift", extensions: ["swift"] },
  { id: "kotlin", label: "Kotlin", extensions: ["kt"] },
  { id: "html", label: "HTML", extensions: ["html", "htm", "vue"] },
  { id: "css", label: "CSS", extensions: ["css"] },
  { id: "scss", label: "SCSS", extensions: ["scss"] },
  { id: "json", label: "JSON", extensions: ["json"] },
  { id: "yaml", label: "YAML", extensions: ["yml", "yaml"] },
  { id: "markdown", label: "Markdown", extensions: ["md"] },
  { id: "sql", label: "SQL", extensions: ["sql"] },
  { id: "shell", label: "Shell", extensions: ["sh"] },
  { id: "xml", label: "XML", extensions: ["xml"] },
  { id: "plaintext", label: "Plain text", extensions: ["txt", "toml"] },
];

// every file extension we accept, e.g. ["py", "js", "jsx", ...]
export const SUPPORTED_EXTENSIONS = LANGUAGES.flatMap((lang) => lang.extensions);

// "app.py" -> "py"
export function getExtension(fileName: string): string {
  const dot = fileName.lastIndexOf(".");
  if (dot === -1) return "";
  return fileName.slice(dot + 1).toLowerCase();
}

// "app.py" -> "python". Unknown extension -> null
export function getLanguageFromFileName(fileName: string): string | null {
  const ext = getExtension(fileName);
  for (const lang of LANGUAGES) {
    if (lang.extensions.includes(ext)) return lang.id;
  }
  return null;
}

// "python" -> "Python"
export function getLanguageLabel(id: string): string {
  return LANGUAGES.find((lang) => lang.id === id)?.label ?? "Plain text";
}

// Guess language from pasted code. First matching rule wins.
// Order matters: C# before Java, Java before Go, TypeScript before JavaScript.
const RULES: [string, RegExp][] = [
  ["php", /<\?php/],
  ["html", /<!doctype html|<html[\s>]/i],
  ["cpp", /#include\s*<(iostream|vector|string|map)>|std::|\bcout\b/],
  ["c", /#include\s*<[\w./]+\.h>|\bint\s+main\s*\(/],
  ["csharp", /\busing\s+System\b|\bnamespace\s+\w+|Console\.WriteLine/],
  ["java", /\bpublic\s+(static\s+)?(class|void)\b|System\.out\.|^\s*import\s+java\./m],
  ["go", /^\s*package\s+\w+|\bfunc\s+\w+\(|fmt\.\w+\(/m],
  ["rust", /\bfn\s+\w+\s*\(|\blet\s+mut\b|\buse\s+std::/],
  ["typescript", /\binterface\s+\w+\s*\{|:\s*(string|number|boolean)\b|\btype\s+\w+\s*=/],
  ["javascript", /\bconsole\.log\(|\bconst\s+\w+\s*=|=>|\bfunction\s+\w+\s*\(|\brequire\(/],
  ["python", /^\s*(def\s+\w+\(|from\s+\w+\s+import\b|import\s+\w+\s*$|class\s+\w+.*:\s*$)|\bprint\(/m],
  ["sql", /\b(select\s[\s\S]+\sfrom|insert\s+into|create\s+table)\b/i],
  ["shell", /^#!\/bin\/(ba)?sh/],
];

export function detectLanguageFromCode(code: string): string {
  const text = code.trim();
  if (text === "") return "plaintext";

  // JSON: only if it really parses
  if (text.startsWith("{") || text.startsWith("[")) {
    try {
      JSON.parse(text);
      return "json";
    } catch {
      // not JSON, keep checking
    }
  }

  for (const [id, pattern] of RULES) {
    if (pattern.test(text)) return id;
  }
  return "plaintext";
}