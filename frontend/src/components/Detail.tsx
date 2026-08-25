import type { ReactNode } from "react";

export function Detail({ label, value, className }: { label: string; value: ReactNode; className?: string }) {
  return (
    <div className={`grid grid-cols-[140px_1fr] gap-3 border-b border-line py-3 text-sm last:border-0 ${className || ""}`}>
      <dt className="text-sm font-semibold text-subtle uppercase tracking-wider">{label}</dt>
      <dd className="min-w-0 break-words text-ink font-medium leading-relaxed">{value}</dd>
    </div>
  );
}
