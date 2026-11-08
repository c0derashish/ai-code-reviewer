import type { ReactNode } from "react";
import { Info, TriangleAlert } from "lucide-react";

type NoticeProps = {
  kind: "error" | "info";
  children: ReactNode;
};

export default function Notice({ kind, children }: NoticeProps) {
  const isError = kind === "error";

  return (
    <div
      role={isError ? "alert" : "status"}
      className={`flex items-start gap-2 rounded-md border px-3 py-2.5 text-sm ${
        isError
          ? "border-danger/40 bg-danger/10 text-danger"
          : "border-info/40 bg-info/10 text-info"
      }`}
    >
      {isError ? (
        <TriangleAlert size={18} className="mt-0.5 shrink-0" />
      ) : (
        <Info size={18} className="mt-0.5 shrink-0" />
      )}
      <div className="min-w-0 break-words">{children}</div>
    </div>
  );
}