export type Status = "idle" | "loading" | "success" | "error";

export interface ScannerExecution {
  id: number;
  scan_run_id: number;
  scanner_name: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
}

export interface ScanRun {
  id: number;
  target_environment: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  archived_at?: string | null;
  scanner_executions?: ScannerExecution[];
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
  groq_agreement_value?: number | null;
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
  agreement_value?: number | null;
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
  severity?: string | null;
  control_id?: string | null;
  scan_run_id?: number | null;
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
  manifest_path?: string | null;
  checksum: string;
}

export interface DashboardCloudFindings {
  alerts: number;
  recommendations: number;
  secure_scores: number;
}

export interface DashboardCoverage {
  covered_controls: number;
  total_controls: number;
}

export interface DashboardSeverity {
  severity_counts: Record<string, number>;
}

export interface FailedControlDrilldown {
  control_catalog_id?: number;
  control_id: string;
  control_title: string;
  count: number;
  status: string;
}

export interface DashboardGap {
  manual_review_mappings: number;
  rejected_mappings: number;
  failed_controls?: FailedControlDrilldown[];
}

export interface RemediationBacklog {
  items: Array<{
    mapping_id: number;
    control_catalog_id: number;
    status: string;
    severity: string;
    resource_identifier: string;
    control_id: string;
    control_title: string;
    gemini_confidence: number | null;
    groq_agreement_value: number | null;
  }>;
  total: number;
}

export interface RemediationSuggestion {
  mapping_id: number;
  steps: string[];
  source: "groq" | "deterministic_fallback";
}

export interface ControlDrillDown {
  control: {
    id: number;
    framework_name: string;
    control_id: string;
    title: string;
    description: string;
  };
  items: RemediationBacklog["items"];
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
  kind?: string | null;
  label?: string | null;
  description?: string | null;
  required_inputs?: string[] | null;
  missing_config?: string[] | null;
  scope?: string | null;
}

export interface ScanRequest {
  target: string;
  scan_profile?: string;
  framework?: string;
}

export interface BulkReviewDecision {
  item_ids: number[];
  reviewer_id?: string | null;
  comments?: string | null;
  action: "approve" | "reject";
}

export interface DashboardAIMetrics {
  total_mappings: number;
  published_mappings: number;
  manual_review_mappings: number;
  avg_gemini_confidence: number | null;
  avg_groq_agreement: number | null;
  avg_final_confidence: number | null;
  agreement_rate: number | null;
  manual_review_rate: number | null;
}

export interface ScanDiff {
  previous_scan_id: number | null;
  current_scan_id: number;
  previous_finding_count: number;
  current_finding_count: number;
  new_count: number;
  resolved_count: number;
  unchanged_count: number;
  net_change: number;
  new_findings: Array<{
    fingerprint: string;
    scanner_name: string;
    finding_type: string;
    resource_type: string;
    resource_identifier: string;
    severity: string;
    title: string;
    first_seen: string | null;
    last_seen: string | null;
    status: string;
    control_ids: string[];
  }>;
  resolved_findings: Array<{
    fingerprint: string;
    scanner_name: string;
    finding_type: string;
    resource_type: string;
    resource_identifier: string;
    severity: string;
    title: string;
    first_seen: string | null;
    last_seen: string | null;
    status: string;
    control_ids: string[];
  }>;
  unchanged_findings: Array<{
    fingerprint: string;
    scanner_name: string;
    finding_type: string;
    resource_type: string;
    resource_identifier: string;
    severity: string;
    title: string;
    first_seen: string | null;
    last_seen: string | null;
    status: string;
    control_ids: string[];
  }>;
  severity_new: Record<string, number>;
  severity_resolved: Record<string, number>;
  new_control_ids: string[];
  resolved_control_ids: string[];
}

export interface FindingLineage {
  scan_run: {
    id: number | null;
    target_environment: string | null;
    status: string | null;
    started_at: string | null;
    completed_at: string | null;
    created_at: string | null;
  } | null;
  raw_finding: {
    id: number | null;
    scanner_finding_id: string | null;
    scanner_name: string | null;
    raw_json: Record<string, unknown> | null;
    created_at: string | null;
  } | null;
  normalized_finding: {
    id: number;
    scanner_name: string;
    finding_type: string;
    resource_type: string;
    resource_identifier: string;
    severity: string;
    title: string;
    description: string | null;
    timestamp: string | null;
    metadata_json: Record<string, unknown> | null;
  };
  mappings: Array<{
    mapping_id: number;
    control_catalog_id: number | null;
    control_id: string | null;
    framework_name: string | null;
    control_title: string | null;
    mapping_status: string;
    gemini_confidence: number | null;
    final_confidence: number | null;
    verification_status: string | null;
    groq_agreement_value: number | null;
    rationale: string | null;
    created_at: string | null;
    verification_records: Array<{
      id: number;
      result: string;
      explanation: string | null;
      agreement_value: number | null;
      verification_model: string;
      timestamp: string | null;
    }>;
  }>;
}
