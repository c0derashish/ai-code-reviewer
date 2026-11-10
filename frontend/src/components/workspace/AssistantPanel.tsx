import { Bot } from "lucide-react";
import EmptyState from "../common/EmptyState";

export default function AssistantPanel() {
  return (
    <EmptyState icon={<Bot size={28} />} title="AI Assistant is not connected">
      Ask questions about your code here once the backend is ready.
    </EmptyState>
  );
}