"use client";

import { useId } from "react";

type Props = {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  minLength?: number;
  autoComplete?: string;
  placeholder?: string;
  help?: string;
  errorId?: string;
  invalid?: boolean;
};

export function Field({
  label,
  type = "text",
  value,
  onChange,
  required,
  minLength,
  autoComplete,
  placeholder,
  help,
  errorId,
  invalid,
}: Props) {
  const id = useId();
  const helpId = help ? `${id}-help` : undefined;
  const describedBy = [helpId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm">
        {label}
        {required && (
          <span aria-hidden className="text-red-400 ml-1">
            *
          </span>
        )}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        minLength={minLength}
        autoComplete={autoComplete}
        placeholder={placeholder}
        aria-required={required || undefined}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        className="w-full px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] focus:border-[var(--color-brand-cyan)] outline-none"
      />
      {help && (
        <p id={helpId} className="text-xs text-[var(--color-fg-muted)]">
          {help}
        </p>
      )}
    </div>
  );
}
