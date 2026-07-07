import { severityOrder } from "./utils/format";

export type Severity = (typeof severityOrder)[number];

const severityBar: Record<Severity, string> = {
  critical: "bg-rose-600",
  high: "bg-orange-500",
  medium: "bg-amber-400",
  low: "bg-sky-500",
  info: "bg-slate-400",
};

const severityBadge: Record<Severity, string> = {
  critical: "border-rose-200 bg-rose-50 text-rose-700",
  high: "border-orange-200 bg-orange-50 text-orange-700",
  medium: "border-amber-200 bg-amber-50 text-amber-800",
  low: "border-sky-200 bg-sky-50 text-sky-700",
  info: "border-slate-200 bg-slate-50 text-slate-600",
};

export function severityBarClass(severity: string): string {
  return severityBar[severity as Severity] ?? "bg-slate-400";
}

export function severityBadgeClass(severity: string): string {
  return severityBadge[severity as Severity] ?? "border-slate-200 bg-slate-50 text-slate-600";
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
