export const severityOrder = ["critical", "high", "medium", "low", "info"];

export function formatDate(value?: string | null) {
  if (!value) return "n/a";
  return new Date(value).toLocaleString();
}

export function formatPercent(value?: number | null) {
  if (value === undefined || value === null) return "n/a";
  return `${Math.round(value * 100)}%`;
}

