import type { LucideIcon } from "lucide-react";
import { Activity, Archive, ClipboardCheck, FileJson, Gauge, GitBranch, ShieldCheck } from "lucide-react";

export type ViewId = "overview" | "scan-runs" | "scan-detail" | "controls" | "review" | "reports" | "audit-bundles" | "compliance-drift" | "evidence-lineage";

export interface NavItem {
  id: ViewId;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const navigation: NavItem[] = [
  { id: "overview", label: "Overview", description: "Compliance posture at a glance", icon: Gauge },
  { id: "scan-runs", label: "Scan Runs", description: "Run and manage scans", icon: Activity },
  { id: "compliance-drift", label: "Compliance Drift", description: "Compare scan runs over time", icon: GitBranch },
  { id: "evidence-lineage", label: "Evidence Lineage", description: "Trace finding evidence chain", icon: ShieldCheck },
  { id: "controls", label: "Controls", description: "Reference control catalog", icon: ShieldCheck },
  { id: "review", label: "Review Queue", description: "Mappings awaiting decision", icon: ClipboardCheck },
  { id: "reports", label: "Reports", description: "Generate engineering and leadership reports", icon: FileJson },
  { id: "audit-bundles", label: "Audit Bundles", description: "Evidence package generation and export", icon: Archive },
];
