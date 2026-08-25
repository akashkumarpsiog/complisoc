import { severityOrder } from "./utils/format";

export type Severity = (typeof severityOrder)[number];

const severityBar: Record<Severity, string> = {
  critical: "bg-danger",
  high: "bg-orange-500",
  medium: "bg-warning",
  low: "bg-sky-500",
  info: "bg-subtle",
};

const severityBadge: Record<Severity, string> = {
  critical: "border-danger/20 bg-danger-light text-danger-dark",
  high: "border-orange-200 bg-orange-50 text-orange-700",
  medium: "border-warning/20 bg-warning-light text-warning-dark",
  low: "border-sky-200 bg-sky-50 text-sky-700",
  info: "border-line bg-panel text-muted",
};

export function severityBarClass(severity: string): string {
  return severityBar[severity as Severity] ?? "bg-subtle";
}

export function severityBadgeClass(severity: string): string {
  return severityBadge[severity as Severity] ?? "border-line bg-panel text-muted";
}

export type Accent = "brand" | "emerald" | "amber" | "rose" | "slate";

export const accentBar: Record<Accent, string> = {
  brand: "bg-brand-500",
  emerald: "bg-emerald-500",
  amber: "bg-amber-400",
  rose: "bg-rose-500",
  slate: "bg-slate-300",
};

export type ProgressTone = "brand" | "emerald" | "amber" | "rose" | "sky";

export const progressTone: Record<ProgressTone, string> = {
  brand: "bg-brand-500",
  emerald: "bg-emerald-500",
  amber: "bg-amber-400",
  rose: "bg-rose-500",
  sky: "bg-sky-500",
};

export type BarTone = "severity" | ProgressTone;
