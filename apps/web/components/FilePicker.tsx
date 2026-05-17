"use client";

import { useRef } from "react";

/**
 * A clearly-button-shaped file picker. The native `<input type="file">` is
 * visually hidden but kept in the DOM for form semantics and keyboard access;
 * a styled `<label>` triggers the picker. Shows the chosen filename next to
 * the button so the user has feedback before submitting.
 */
export function FilePicker({
  id,
  accept,
  file,
  onChange,
  buttonLabel = "Choose file",
  placeholder = "No file selected",
  disabled,
}: {
  id: string;
  accept?: string;
  file: File | null;
  onChange: (f: File | null) => void;
  buttonLabel?: string;
  placeholder?: string;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="inline-flex items-center gap-2 flex-wrap">
      <label
        htmlFor={id}
        className={
          "inline-flex items-center gap-1 px-3 py-1.5 rounded text-sm font-medium border border-[var(--color-brand-cyan)] text-[var(--color-brand-cyan)] hover:bg-[var(--color-brand-cyan)] hover:text-black transition-colors cursor-pointer select-none " +
          (disabled ? "opacity-60 pointer-events-none" : "")
        }
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        {buttonLabel}
      </label>
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={accept}
        disabled={disabled}
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        className="sr-only"
      />
      <span
        className={
          "text-xs " +
          (file ? "text-[var(--color-fg-base)]" : "text-[var(--color-fg-muted)] italic")
        }
        aria-live="polite"
      >
        {file ? file.name : placeholder}
      </span>
      {file && (
        <button
          type="button"
          onClick={() => {
            onChange(null);
            if (inputRef.current) inputRef.current.value = "";
          }}
          className="text-xs underline text-[var(--color-fg-muted)] hover:text-red-300"
        >
          Clear
        </button>
      )}
    </div>
  );
}
