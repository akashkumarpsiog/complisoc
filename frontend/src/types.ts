export type Status = "idle" | "loading" | "success" | "error";

export interface ScanRun {
  id: number;
  target_environment: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ScanRunSummary {
  scan_run_id: number;
  status: string;
  raw_findings: number;
  normalized_findings: number;
  mappings: number;
  published_mappings: number;
  manual_review_mappings: number;
}

export interface RawFindingInput {
  scanner_name: string;
  scanner_finding_id: string;
  raw_json: Record<string, unknown>;
}

export interface ScannerFailureInput {
  scanner_name: string;
  error_message: string;
}

export interface NormalizedFinding {
  id: number;
  raw_finding_id: number;
  scanner_name: string;
  finding_type: string;
  resource_type: string;
  resource_identifier: string;
  severity: string;
  title: string;
  description?: string | null;
  metadata_json?: Record<string, unknown> | null;
  timestamp?: string | null;
}

export interface ControlMapping {
  id: number;
  normalized_finding_id: number;
  candidate_control_id: number;
  control_catalog_id: number;
  rank: number;
  mapping_model: string;
  prompt_version: string;
  rationale?: string | null;
  gemini_confidence?: number | null;
  verification_status?: string | null;
  final_confidence?: number | null;
  mapping_status: string;
}

export interface VerificationRecord {
  id: number;
  control_mapping_id: number;
  verification_model: string;
  prompt_version: string;
  result: string;
  explanation?: string | null;
  timestamp?: string | null;
}

export interface Control {
  id: number;
  framework_name: string;
  framework_version: string;
  control_id: string;
  control_family: string;
  title: string;
  description: string;
  objective?: string | null;
  evidence_examples?: string[] | null;
  scanner_signals?: string[] | null;
  keywords?: string[] | null;
  source_url: string;
  active_status: boolean;
}

export interface ReviewQueueItem {
  id: number;
  control_mapping_id: number;
  status: string;
  reviewer_id?: string | null;
  review_reason_code: string;
  comments?: string | null;
  reviewed_at?: string | null;
}

export interface ComplianceReport {
  id: number;
  scan_run_id: number;
  report_type: string;
  generated_by: string;
  generated_at?: string | null;
  content_path?: string | null;
  content_hash?: string | null;
}

export interface AuditBundle {
  id: number;
  scan_run_id: number;
  generated_at?: string | null;
  bundle_path?: string | null;
  checksum: string;
}

export interface DashboardCoverage {
  covered_controls: number;
  total_controls: number;
}

export interface DashboardSeverity {
  severity_counts: Record<string, number>;
}

export interface DashboardGap {
  manual_review_mappings: number;
  rejected_mappings: number;
}

export interface RemediationBacklog {
  items: Array<{
    mapping_id: number;
    status: string;
    severity: string;
    resource_identifier: string;
    control_id: string;
    control_title: string;
  }>;
}

export interface DashboardTrend {
  trends: Array<{
    scan_run_id: number;
    created_at: string;
    published: number;
    manual_review: number;
  }>;
}

export interface ScannerInfo {
  name: string;
  available: boolean;
}

export interface ScanRequest {
  target: string;
  scanners?: string[];
  framework?: string;
}
