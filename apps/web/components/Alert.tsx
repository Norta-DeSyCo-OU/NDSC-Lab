type Props = {
  kind?: "info" | "warn" | "error" | "success";
  children: React.ReactNode;
  id?: string;
};

const STYLES: Record<NonNullable<Props["kind"]>, string> = {
  info: "border-[var(--color-brand-blue-2)] text-[var(--color-fg)]",
  warn: "border-yellow-500 text-yellow-200",
  error: "border-red-500 text-red-300",
  success: "border-emerald-500 text-emerald-300",
};

export function Alert({ kind = "info", children, id }: Props) {
  return (
    <div
      id={id}
      role={kind === "error" ? "alert" : "status"}
      aria-live={kind === "error" ? "assertive" : "polite"}
      className={`border ${STYLES[kind]} bg-[var(--color-bg-panel)] rounded px-3 py-2 text-sm`}
    >
      {children}
    </div>
  );
}
