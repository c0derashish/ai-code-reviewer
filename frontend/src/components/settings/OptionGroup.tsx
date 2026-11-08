import type { ReactNode } from "react";

type Option<T extends string> = {
  value: T;
  label: string;
  icon: ReactNode;
};

type OptionGroupProps<T extends string> = {
  label: string;
  value: T;
  options: Option<T>[];
  onChange: (value: T) => void;
};

export default function OptionGroup<T extends string>({
  label,
  value,
  options,
  onChange,
}: OptionGroupProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="grid grid-cols-2 gap-1 rounded-lg border border-line bg-base/60 p-1"
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm transition ${
              selected ? "bg-saffron/15 text-saffron" : "text-muted hover:text-main"
            }`}
          >
            {option.icon}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}