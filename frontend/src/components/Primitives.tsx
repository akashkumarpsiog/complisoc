import type { ReactNode, CSSProperties } from "react";
import { Fragment, useState } from "react";
import { AlertCircle, ChevronDown, ChevronUp, Inbox, Loader2, RefreshCw, ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react";
import { accentBar, progressTone, severityBarClass, severityBadgeClass, type Accent, type BarTone, type ProgressTone } from "../theme";

export function staggerStyle(index: number, baseMs = 60): CSSProperties {
  return { animationDelay: `${index * baseMs}ms` };
}

export function Section({
  title,
  description,
  actions,
  children,
  className,
  collapsible = false,
  defaultOpen = true,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className={`panel shadow-sm animate-slide-up ${className || ""}`}>
      <div className="section-header">
        <div>
          <h2 className="section-title">{title}</h2>
          {description ? <p className="section-description">{description}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">{actions}
          {collapsible ? (
            <button
              className="icon-button h-8 w-8 !px-0 !border-0 text-subtle hover:text-ink hover:bg-panel-hover"
              onClick={() => setOpen((value) => !value)}
              aria-expanded={open}
              aria-label={`${open ? "Collapse" : "Expand"} ${title}`}
            >
              {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          ) : null}
        </div>
      </div>
      {(!collapsible || open) ? (
        <div className="p-5 transition-all duration-300 ease-in-out">
          {children}
        </div>
      ) : null}
    </section>
  );
}

export function DonutChart({
  value,
  total,
  label,
  accent = "brand",
  size = 120,
}: {
  value: number;
  total: number;
  label: string;
  accent?: Accent;
  size?: number;
}) {
  const pct = total > 0 ? value / total : 0;
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct);
  const center = size / 2;
  const strokeColor = accentColor[accent];

  return (
    <div className="flex flex-col items-center gap-3 animate-scale-in">
      <div className="relative">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle cx={center} cy={center} r={radius} fill="none" stroke="#f1f3f5" strokeWidth="6" />
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={strokeColor}
            strokeWidth="6"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform={`rotate(-90 ${center} ${center})`}
            style={{ transition: "stroke-dashoffset 1s var(--ease-out-expo)" }}
          />
          <text x={center} y={center + 5} textAnchor="middle" className="fill-ink text-xl font-bold" style={{ fontFamily: "Inter, sans-serif" }}>
            {Math.round(pct * 100)}%
          </text>
        </svg>
      </div>
      <span className="text-xs font-semibold uppercase tracking-wider text-subtle">{label}</span>
    </div>
  );
}

const accentColor: Record<Accent, string> = {
  brand: "#0fa67a",
  emerald: "#10b981",
  amber: "#f59e0b",
  rose: "#f43f5e",
  slate: "#94a3b8",
};

export function MetricCard({
  label,
  value,
  detail,
  accent = "brand",
  progress,
  className,
}: {
  label: string;
  value: string | number;
  detail?: string;
  accent?: Accent;
  progress?: number;
  className?: string;
}) {
  return (
    <div
      className={`panel relative overflow-hidden p-5 animate-slide-up transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:border-brand-200 group ${className || ""}`}
      style={staggerStyle(0)}
    >
      <div className={`absolute inset-x-0 top-0 h-1 ${accentBar[accent]} rounded-t-xl opacity-80 group-hover:opacity-100 transition-opacity duration-200`} aria-hidden />
      <div className="text-xs font-bold uppercase tracking-wider text-subtle mb-2">{label}</div>
      <div className="text-3xl font-bold tracking-tight text-ink tabular-nums">{value}</div>
      {progress !== undefined ? (
        <div className="mt-4">
          <ProgressBar value={progress} tone={accent === "slate" ? "sky" : (accent as ProgressTone)} />
        </div>
      ) : null}
      {detail ? <div className="mt-2 text-sm text-muted leading-relaxed">{detail}</div> : null}
    </div>
  );
}

export function ProgressBar({ value, tone = "brand" }: { value?: number; tone?: ProgressTone }) {
  const pct = Math.max(0, Math.min(100, Math.round((value ?? 0) * 100)));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-panel" role="progressbar" aria-valuenow={pct}>
      <div className={`h-full rounded-full transition-all duration-500 ease-out ${progressTone[tone]}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function StatusBadge({ value, className }: { value?: string | null; className?: string }) {
  const normalized = (value || "unknown").toLowerCase();
  const tone =
    normalized.includes("published") || normalized.includes("completed") || normalized.includes("agree")
      ? "border-success/20 bg-success-light text-success-dark"
      : normalized.includes("manual") || normalized.includes("pending")
        ? "border-warning/20 bg-warning-light text-warning-dark"
        : normalized.includes("failed") || normalized.includes("rejected") || normalized.includes("disagree")
          ? "border-danger/20 bg-danger-light text-danger-dark"
          : "border-line bg-panel text-muted";
  return (
    <span className={`inline-flex min-h-[1.5rem] items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-all duration-150 ${tone} ${className || ""}`}>
      {value || "unknown"}
    </span>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex min-h-32 flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-line-strong bg-panel/50 p-6">
      <div className="relative">
        <Loader2 className="h-6 w-6 animate-spin text-brand-500" aria-hidden />
      </div>
      <div className="w-full max-w-xs space-y-2.5">
        <div className="skeleton h-2 w-2/5 rounded" />
        <div className="skeleton h-2 w-full rounded" />
        <div className="skeleton h-2 w-4/5 rounded" />
        <div className="skeleton h-2 w-3/5 rounded" />
      </div>
      <span className="text-xs font-medium text-subtle tracking-wide uppercase">{label}</span>
    </div>
  );
}

export function EmptyState({ label, icon }: { label: string; icon?: ReactNode }) {
  return (
    <div className="flex min-h-32 flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-line-strong bg-panel/50 p-6 text-center animate-fade-in">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-panel-hover text-subtle">
        {icon || <Inbox className="h-5 w-5" aria-hidden />}
      </div>
      <p className="text-sm text-muted font-medium">{label}</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex min-h-32 flex-col items-center justify-center gap-4 rounded-xl border border-danger/20 bg-danger-light p-6 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-danger/10 text-danger">
        <AlertCircle className="h-5 w-5" aria-hidden />
      </div>
      <p className="text-sm font-medium text-danger-dark max-w-sm">{message}</p>
      <button className="secondary-button !border-danger/20 !text-danger-dark hover:!bg-danger/5" onClick={onRetry}>
        <RefreshCw className="h-4 w-4" aria-hidden />
        Retry
      </button>
    </div>
  );
}

export function DataTable({ columns, rows, expandableRows }: { columns: ReactNode[]; rows: ReactNode[][]; expandableRows?: (ReactNode | null)[] }) {
  if (rows.length === 0) {
    return <EmptyState label="No records found." icon={<Inbox className="h-5 w-5" aria-hidden />} />;
  }
  return (
    <div className="overflow-x-auto -mx-5">
      <table className="w-full min-w-[960px] table-fixed border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line-strong bg-panel/60 text-xs font-bold uppercase tracking-wider text-subtle">
            {columns.map((column, idx) => (
              <th className="overflow-hidden px-5 py-3 select-none first:pl-5 last:pr-5" key={idx}>
                <span className="inline-flex items-center gap-1.5 cursor-pointer hover:text-ink transition-colors duration-150 group">
                  {column}
                  <span className="flex flex-col">
                    <ChevronUp className={`h-2.5 w-2.5 transition-all duration-150 ${idx === 0 ? "opacity-100 text-brand-500" : "opacity-30 group-hover:opacity-70 text-subtle"}`} aria-hidden />
                    <ChevronDown className={`h-2.5 w-2.5 -mt-0.5 transition-all duration-150 ${idx === 1 ? "opacity-100 text-brand-500" : "opacity-30 group-hover:opacity-70 text-subtle"}`} aria-hidden />
                  </span>
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row, rowIndex) => (
            <Fragment key={rowIndex}>
              <tr className="data-table-row animate-fade-in" style={staggerStyle(rowIndex)}>
                {row.map((cell, cellIndex) => (
                  <td className="overflow-hidden px-5 py-3 align-top break-words first:pl-5 last:pr-5 text-ink/90" key={`${rowIndex}-${cellIndex}`}>
                    {cell}
                  </td>
                ))}
              </tr>
              {expandableRows?.[rowIndex] ? (
                <tr className="bg-panel/40 animate-fade-in" style={staggerStyle(rowIndex)}>
                  <td colSpan={columns.length} className="px-5 py-4 first:pl-5 last:pr-5">
                    <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
                      {expandableRows[rowIndex]}
                    </div>
                  </td>
                </tr>
              ) : null}
            </Fragment>
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
    return <EmptyState label="No chart data available." icon={<MoreHorizontal className="h-5 w-5" aria-hidden />} />;
  }
  return (
    <div className="space-y-4">
      {entries.map(([label, value]) => {
        const barClass = tone === "severity" ? severityBarClass(label) : progressTone[tone];
        const pct = (value / max) * 100;
        return (
          <div className="grid grid-cols-[140px_1fr_48px] items-center gap-4 text-sm" key={label}>
            <span className="truncate font-semibold capitalize text-ink/80">{label}</span>
            <div className="h-2.5 overflow-hidden rounded-full bg-panel">
              <div className={`h-2.5 rounded-full transition-all duration-500 ease-out ${barClass}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-right font-bold tabular-nums text-ink/80">{value}</span>
          </div>
        );
      })}
    </div>
  );
}
