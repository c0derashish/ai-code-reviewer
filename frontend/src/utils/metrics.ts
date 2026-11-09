// Simple counts from text. Real numbers, no guessing.
export function getTextMetrics(text: string) {
  const all = text === "" ? [] : text.split("\n");
  const blankLines = all.filter((line) => line.trim() === "").length;

  return {
    lines: all.length,
    codeLines: all.length - blankLines,
    blankLines,
    bytes: new Blob([text]).size,
  };
}