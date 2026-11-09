import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

type AuthFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "email" | "password";
  error?: string;
  autoComplete?: string;
  placeholder?: string;
  autoFocus?: boolean;
};

export default function AuthField({
  id,
  label,
  value,
  onChange,
  type = "text",
  error,
  autoComplete,
  placeholder,
  autoFocus,
}: AuthFieldProps) {
  const [shown, setShown] = useState(false);
  const isPassword = type === "password";

  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>

      <div className="relative">
        <input
          id={id}
          type={isPassword && shown ? "text" : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          placeholder={placeholder}
          autoFocus={autoFocus}
          spellCheck={false}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          className={`w-full rounded-md border border-line bg-base/50 px-4 py-3 text-sm text-main placeholder:text-muted focus:border-saffron focus:outline-none aria-invalid:border-danger ${
            isPassword ? "pr-11" : ""
          }`}
        />

        {isPassword && (
          <button
            type="button"
            aria-label={shown ? "Hide password" : "Show password"}
            aria-pressed={shown}
            onClick={() => setShown(!shown)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-main"
          >
            {shown ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        )}
      </div>

      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}