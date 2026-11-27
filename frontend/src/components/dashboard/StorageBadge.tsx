import type { Storage } from "../../types/history";

export default function StorageBadge({ storage }: { storage: Storage }) {
  const full = storage === "full";

  return (
    <span
      className={`inline-flex rounded border px-2 py-0.5 text-xs font-medium ${
        full ? "border-ok/40 bg-ok/15 text-ok" : "border-warn/40 bg-warn/15 text-warn"
      }`}
    >
      {full ? "Saved" : "Link only"}
    </span>
  );
}