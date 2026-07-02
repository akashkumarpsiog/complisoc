import type { ReactNode } from "react";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";

export function Section({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel rounded-lg">
      <div className="flex flex-col gap-3 border-b border-line px-4 py-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          {description ? <p className="mt-1 text-sm text-slate-600">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <div className="panel rounded-lg p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink">{value}</div>
      {detail ? <div className="mt-1 text-sm text-slate-600">{detail}</div> : null}
    </div>
  );
}

export function StatusBadge({ value }: { value?: string | null }) {
  const normalized = (value || "unknown").toLowerCase();
  const tone =
    normalized.includes("published") || normalized.includes("completed") || normalized.includes("agree")
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : normalized.includes("manual") || normalized.includes("pending")
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : normalized.includes("failed") || normalized.includes("rejected") || normalized.includes("disagree")
          ? "border-rose-200 bg-rose-50 text-rose-700"
          : "border-slate-200 bg-slate-50 text-slate-700";
  return (
    <span className={`inline-flex min-h-6 items-center rounded-md border px-2 text-xs font-medium ${tone}`}>
      {value || "unknown"}
    </span>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-28 items-center justify-center gap-2 rounded-md border border-dashed border-line bg-panel text-sm text-slate-600">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex min-h-28 items-center justify-center rounded-md border border-dashed border-line bg-panel text-sm text-slate-600">
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex min-h-28 flex-col items-center justify-center gap-3 rounded-md border border-rose-200 bg-rose-50 p-4 text-center text-sm text-rose-800">
      <AlertCircle className="h-5 w-5" aria-hidden />
      <span>{message}</span>
      <button className="icon-button border-rose-200 bg-white text-rose-800" onClick={onRetry}>
        <RefreshCw className="h-4 w-4" aria-hidden />
        Retry
      </button>
    </div>
  );
}

export function DataTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: ReactNode[][];
}) {
  if (rows.length === 0) {
    return <EmptyState label="No records found." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line bg-panel text-xs font-semibold uppercase text-slate-500">
            {columns.map((column) => (
              <th className="px-3 py-2" key={column}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr className="border-b border-line last:border-0" key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td className="max-w-[320px] px-3 py-2 align-top" key={`${rowIndex}-${cellIndex}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BarList({ values }: { values: Record<string, number> }) {
  const entries = Object.entries(values);
  const max = Math.max(1, ...entries.map(([, value]) => value));
  if (entries.length === 0) {
    return <EmptyState label="No chart data available." />;
  }
  return (
    <div className="space-y-3">
      {entries.map(([label, value]) => (
        <div className="grid grid-cols-[110px_1fr_40px] items-center gap-3 text-sm" key={label}>
          <span className="truncate font-medium text-slate-700">{label}</span>
          <div className="h-2 rounded-full bg-slate-100">
            <div className="h-2 rounded-full bg-sky-600" style={{ width: `${(value / max) * 100}%` }} />
          </div>
          <span className="text-right text-slate-600">{value}</span>
        </div>
      ))}
    </div>
  );
}
