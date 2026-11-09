import Notice from "../common/Notice";
import type { ProjectFile } from "../../types";
import { formatFileSize } from "../../utils/format";
import { getLanguageLabel } from "../../utils/language";
import { getTextMetrics } from "../../utils/metrics";

type MetricsPanelProps = {
  file: ProjectFile;
  files: ProjectFile[];
};

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="glass-panel rounded-lg border p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 font-mono text-xl font-semibold">{value}</p>
    </div>
  );
}

export default function MetricsPanel({ file, files }: MetricsPanelProps) {
  const stats = getTextMetrics(file.content);
  const totalLines = files.reduce((sum, f) => sum + getTextMetrics(f.content).lines, 0);

  return (
    <div className="space-y-5 p-4">
      <div>
        <h2 className="mb-3 truncate font-mono text-sm font-medium">{file.path}</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          <Stat label="Lines" value={stats.lines} />
          <Stat label="Code lines" value={stats.codeLines} />
          <Stat label="Blank lines" value={stats.blankLines} />
          <Stat label="Size" value={formatFileSize(stats.bytes)} />
          <Stat label="Language" value={getLanguageLabel(file.language)} />
        </div>
      </div>

      {files.length > 1 && (
        <div>
          <h2 className="mb-3 text-sm font-medium">Whole project</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            <Stat label="Files" value={files.length} />
            <Stat label="Total lines" value={totalLines} />
          </div>
        </div>
      )}

      <Notice kind="info">
        Complexity, maintainability, and security scores need analysis. The backend is not
        connected yet.
      </Notice>
    </div>
  );
}