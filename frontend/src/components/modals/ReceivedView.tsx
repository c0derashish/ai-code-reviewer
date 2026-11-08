import { CircleCheck } from "lucide-react";
import Button from "../common/Button";
import Notice from "../common/Notice";
import type { Submission } from "../../types";
import { describeSubmission } from "../../services/uploadService";

type ReceivedViewProps = {
  submission: Submission;
  onClose: () => void;
};

export default function ReceivedView({ submission, onClose }: ReceivedViewProps) {
  const info = describeSubmission(submission);

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <CircleCheck size={22} className="mt-0.5 shrink-0 text-ok" />
        <div className="min-w-0">
          <p className="font-semibold">Code received</p>
          <p className="truncate text-sm">{info.title}</p>
          {info.lines.map((line) => (
            <p key={line} className="text-sm text-muted">
              {line}
            </p>
          ))}
        </div>
      </div>

      <Notice kind="info">
        The workspace and analysis are not connected yet. Nothing was uploaded or sent anywhere.
      </Notice>

      <div className="flex justify-end">
        <Button onClick={onClose}>Close</Button>
      </div>
    </div>
  );
}