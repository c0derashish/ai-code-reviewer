import { useEffect } from "react";
import type { ReactNode } from "react";
import { X } from "lucide-react";
import ChakraMark from "../common/ChakraMark";
import Button from "../common/Button";

type ModalProps = {
  title: string;
  onClose: () => void;
  children: ReactNode;
  narrow?: boolean;
};

export default function Modal({ title, onClose, children, narrow = false }: ModalProps) {
  // close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-md"
      onMouseDown={(e) => {
        // only when the click lands on the dark area itself
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`modal-in max-h-full w-full overflow-y-auto rounded-xl border border-line bg-panel/90 shadow-2xl backdrop-blur-xl ${
          narrow ? "max-w-lg" : "max-w-2xl"
        }`}
      >
        {/* thin saffron line on top */}
        <div className="h-px bg-linear-to-r from-transparent via-saffron to-transparent" />

        <div className="flex items-center justify-between px-6 pt-5">
          <div className="flex items-center gap-3 text-saffron">
            <ChakraMark size={24} />
            <h2 className="text-lg font-semibold text-main">{title}</h2>
          </div>
          <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
            <X size={18} />
          </Button>
        </div>

        <div className="px-6 pb-6 pt-4">{children}</div>
      </div>
    </div>
  );
}