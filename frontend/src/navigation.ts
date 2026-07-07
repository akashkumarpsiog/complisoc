import type { LucideIcon } from "lucide-react";
import { Activity, Archive, ClipboardCheck, FileJson, Gauge, GitBranch, Search, ShieldCheck } from "lucide-react";

export type ViewId = "overview" | "scan-runs" | "findings" | "mappings" | "controls" | "review" | "reports" | "bundles";

export interface NavItem {
  id: ViewId;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const navigation: NavItem[] = [
  { id: "overview", label: "Overview", description: "Compliance posture at a glance", icon: Gauge },
  { id: "scan-runs", label: "Scan Runs", description: "Ingest and trace scan runs", icon: Activity },
  { id: "findings", label: "Findings", description: "Normalized security findings", icon: Search },
  { id: "mappings", label: "Mappings", description: "Findings mapped to controls", icon: GitBranch },
  { id: "controls", label: "Controls", description: "Reference control catalog", icon: ShieldCheck },
  { id: "review", label: "Review Queue", description: "Mappings awaiting decision", icon: ClipboardCheck },
  { id: "reports", label: "Reports", description: "Engineering and leadership reports", icon: FileJson },
  { id: "bundles", label: "Audit Bundles", description: "Exportable audit evidence", icon: Archive },
];
