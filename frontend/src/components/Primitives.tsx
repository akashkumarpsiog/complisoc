import type { ReactNode } from "react";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { accentBar, progressTone, severityBarClass, type Accent, type BarTone, type ProgressTone } from "../theme";

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
    <section className="panel">
      <div className="flex flex-col gap-3 border-b border-line px-4 py-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          {description ? <p className="mt-1 text-sm text-slate-500">{description}</p> : null}
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
  accent = "brand",
  progress,
}: {
  label: string;
  value: string | number;
  detail?: string;
  accent?: Accent;
  progress?: number;
}) {
  return (
    <div className="panel relative overflow-hidden p-4">
      <span className={`absolute inset-x-0 top-0 h-1 ${accentBar[accent]}`} aria-hidden />
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-3xl font-semibold tracking-tight text-ink tabular-nums">{value}</div>
      {progress !== undefined ? (
        <div className="mt-3">
          <ProgressBar value={progress} tone={accent === "slate" ? "sky" : (accent as ProgressTone)} />
        </div>
      ) : null}
      {detail ? <div className="mt-2 text-sm text-slate-600">{detail}</div> : null}
    </div>
  );
}

export function ProgressBar({ value, tone = "brand" }: { value?: number; tone?: ProgressTone }) {
  const pct = Math.max(0, Math.min(100, Math.round((value ?? 0) * 100)));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={pct}>
      <div className={`h-full rounded-full transition-all duration-500 ${progressTone[tone]}`} style={{ width: `${pct}%` }} />
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
          : "border-slate-200 bg-slate-50 text-slate-600";
  return (
    <span className={`inline-flex min-h-6 items-center rounded-md border px-2 text-xs font-medium ${tone}`}>
      {value || "unknown"}
    </span>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-28 items-center justify-center gap-2 rounded-lg border border-dashed border-line bg-panel text-sm text-slate-600">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex min-h-28 items-center justify-center rounded-lg border border-dashed border-line bg-panel text-sm text-slate-600">
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex min-h-28 flex-col items-center justify-center gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-center text-sm text-rose-800">
      <AlertCircle className="h-5 w-5" aria-hidden />
      <span>{message}</span>
      <button className="icon-button border-rose-200 bg-white text-rose-800" onClick={onRetry}>
        <RefreshCw className="h-4 w-4" aria-hidden />
        Retry
      </button>
    </div>
  );
}

export function DataTable({ columns, rows }: { columns: string[]; rows: ReactNode[][] }) {
  if (rows.length === 0) {
    return <EmptyState label="No records found." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line bg-panel text-xs font-semibold uppercase tracking-wide text-slate-500">
            {columns.map((column) => (
              <th className="px-3 py-2" key={column}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr className="border-b border-line transition-colors last:border-0 hover:bg-panel/60" key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td className="max-w-[320px] px-3 py-2 align-top break-words" key={`${rowIndex}-${cellIndex}`}>
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

export function BarList({ values, tone = "brand" }: { values: Record<string, number>; tone?: BarTone }) {
  const entries = Object.entries(values);
  const max = Math.max(1, ...entries.map(([, value]) => value));
  if (entries.length === 0) {
    return <EmptyState label="No chart data available." />;
  }
  return (
    <div className="space-y-3">
      {entries.map(([label, value]) => {
        const barClass = tone === "severity" ? severityBarClass(label) : progressTone[tone];
        const pct = (value / max) * 100;
        return (
          <div className="grid grid-cols-[120px_1fr_44px] items-center gap-3 text-sm" key={label}>
            <span className="truncate font-medium capitalize text-slate-700">{label}</span>
            <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
              <div className={`h-2.5 rounded-full ${barClass}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-right font-semibold tabular-nums text-slate-600">{value}</span>
          </div>
        );
      })}
    </div>
  );
}
