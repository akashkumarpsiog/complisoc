import type { LucideIcon } from "lucide-react";
import { Activity, Archive, ClipboardCheck, FileJson, Gauge, ShieldCheck } from "lucide-react";

export type ViewId = "overview" | "scan-runs" | "scan-detail" | "controls" | "review";

export interface NavItem {
  id: ViewId;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const navigation: NavItem[] = [
  { id: "overview", label: "Overview", description: "Compliance posture at a glance", icon: Gauge },
  { id: "scan-runs", label: "Scan Runs", description: "Run and manage scans", icon: Activity },
  { id: "controls", label: "Controls", description: "Reference control catalog", icon: ShieldCheck },
  { id: "review", label: "Review Queue", description: "Mappings awaiting decision", icon: ClipboardCheck },
];
