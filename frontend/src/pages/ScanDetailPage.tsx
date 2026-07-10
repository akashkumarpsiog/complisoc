import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { AuditBundle, ComplianceReport, ControlMapping, NormalizedFinding, ReviewQueueItem, ScanRunSummary, VerificationRecord } from "../types";
import { Detail } from "../components/Detail";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { DataTable, EmptyState, LoadingState, MetricCard, Section, StatusBadge } from "../components/Primitives";
import { formatDate, formatPercent, severityOrder } from "../utils/format";

const TABS = [
  { id: "summary", label: "Summary" },
  { id: "findings", label: "Findings" },
  { id: "mappings", label: "Mappings" },
  { id: "review", label: "Review" },
  { id: "reports", label: "Reports" },
  { id: "bundle", label: "Audit Bundle" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function ScanDetailPage({ scanRunId, onBack }: { scanRunId: number; onBack: () => void }) {
  const [activeTab, setActiveTab] = useState<TabId>("summary");
  const summaryResource = useResource(() => api.scanRuns.summary(scanRunId));
  const findingsResource = useResource(() => api.findings.list({ scan_run_id: scanRunId }));
  const mappingsResource = useResource(() => api.mappings.list({ scan_run_id: scanRunId }));
  const reviewResource = useResource(api.reviewQueue.list);
  const reportsResource = useResource(api.reports.list);
  const bundlesResource = useResource(api.auditBundles.list);

  const scanFindings = useMemo(() => findingsResource.data || [], [findingsResource.data]);
  const scanMappings = useMemo(() => mappingsResource.data || [], [mappingsResource.data]);
  const reviewForScan = useMemo(() => {
    if (!reviewResource.data || !mappingsResource.data) return [];
    const scanMappingIds = new Set(mappingsResource.data.map((m) => m.id));
    return reviewResource.data.filter((item) => scanMappingIds.has(item.control_mapping_id));
  }, [reviewResource.data, mappingsResource.data]);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <button className="icon-button" onClick={onBack}>
          ← Back
        </button>
        <div>
          <h1 className="text-xl font-semibold text-ink">Scan #{scanRunId}</h1>
          <p className="text-sm text-slate-500">
            {summaryResource.data ? `${summaryResource.data.raw_findings} findings · ${summaryResource.data.mappings} mappings` : "Loading..."}
          </p>
        </div>
      </div>

      <div className="border-b border-line">
        <nav className="flex gap-1 overflow-x-auto" aria-label="Scan tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`shrink-0 border-b-2 px-4 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1 ${
                activeTab === tab.id
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-slate-600 hover:text-slate-900"
              }`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === "summary" && <SummaryTab summary={summaryResource.data} />}
      {activeTab === "findings" && (
        <FindingsTab findings={scanFindings} resource={findingsResource} onRefresh={findingsResource.reload} />
      )}
      {activeTab === "mappings" && (
        <MappingsTab mappings={scanMappings} resource={mappingsResource} scanRunId={scanRunId} />
      )}
      {activeTab === "review" && <ReviewTab items={reviewForScan} resource={reviewResource} onRefresh={reviewResource.reload} />}
      {activeTab === "reports" && (
        <ReportsTab scanRunId={scanRunId} reports={reportsResource.data || []} resource={reportsResource} onRefresh={reportsResource.reload} />
      )}
      {activeTab === "bundle" && (
        <BundleTab scanRunId={scanRunId} bundles={bundlesResource.data || []} resource={bundlesResource} onRefresh={bundlesResource.reload} />
      )}
    </div>
  );
}

function SummaryTab({ summary }: { summary: ScanRunSummary | undefined | null }) {
  if (!summary) {
    return (
      <Section title="Scan Summary">
        <LoadingState label="Loading scan summary" />
      </Section>
    );
  }

  return (
    <Section title="Scan Summary">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Raw findings" value={summary.raw_findings} />
        <MetricCard label="Normalized" value={summary.normalized_findings} />
        <MetricCard label="Mappings" value={summary.mappings} />
        <MetricCard label="Published" value={summary.published_mappings} accent="emerald" />
        <MetricCard label="Manual review" value={summary.manual_review_mappings} accent="amber" />
      </div>
    </Section>
  );
}

function FindingsTab({
  findings,
  resource,
  onRefresh,
}: {
  findings: NormalizedFinding[];
  resource: ReturnType<typeof useResource<NormalizedFinding[]>>;
  onRefresh: () => void;
}) {
  const [severity, setSeverity] = useState("");
  const [scanner, setScanner] = useState("");
  const filtered = useMemo(
    () =>
      findings.filter((item) => {
        return (!severity || item.severity.toLowerCase() === severity.toLowerCase()) && (!scanner || item.scanner_name.toLowerCase().includes(scanner.toLowerCase()));
      }),
    [findings, severity, scanner],
  );

  return (
    <Section
      title="Findings"
      description="Security findings discovered during this scan."
      actions={
        <>
          <select className="control" value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="">All severities</option>
            {severityOrder.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input className="control" placeholder="Filter scanner..." value={scanner} onChange={(e) => setScanner(e.target.value)} />
        </>
      }
    >
      <ResourceBoundary resource={{ ...resource, data: filtered }}>
        {(data) => (
          <DataTable
            columns={["ID", "Severity", "Scanner", "Resource", "Title", "Description"]}
            rows={data.map((finding) => {
              const description = finding.description || "No description";
              return [
                finding.id,
                <StatusBadge value={finding.severity} />,
                finding.scanner_name,
                finding.resource_identifier,
                finding.title,
                <span className="max-w-[320px] truncate" title={description}>{description}</span>,
              ];
            })}
          />
        )}
      </ResourceBoundary>
    </Section>
  );
}

function MappingsTab({ mappings, resource, scanRunId }: { mappings: ControlMapping[]; resource: ReturnType<typeof useResource<ControlMapping[]>>; scanRunId: number }) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = mappings.find((m) => m.id === selectedId) || null;
  const [verification, setVerification] = useState<VerificationRecord[] | null>(null);

  useEffect(() => {
    if (!selected) {
      setVerification(null);
      return;
    }
    void api.mappings.verification(selected.id).then(setVerification);
  }, [selected]);

  const findingMap = useResource(() => api.findings.list({ scan_run_id: scanRunId }));
  const controlMap = useResource(api.controls.list);

  const findingsByTitle = useMemo(() => {
    const map = new Map<number, { title: string; severity: string }>();
    (findingMap.data || []).forEach((f) => map.set(f.id, { title: f.title, severity: f.severity }));
    return map;
  }, [findingMap.data]);

  const controlsByTitle = useMemo(() => {
    const map = new Map<number, { control_id: string; title: string; framework: string }>();
    (controlMap.data || []).forEach((c) => map.set(c.id, { control_id: c.control_id, title: c.title, framework: c.framework_name }));
    return map;
  }, [controlMap.data]);

  return (
    <div className="grid gap-5 2xl:grid-cols-[1fr_420px]">
      <Section title="Mappings" description="Findings mapped to compliance controls for this scan.">
        <ResourceBoundary resource={{ ...resource, data: mappings }}>
          {(data) => (
            <DataTable
              columns={["ID", "Finding", "Control", "Status", "Gemini Score", "Groq Score", "Final Confidence", "Groq Verdict"]}
              rows={data.map((mapping) => {
                const finding = findingsByTitle.get(mapping.normalized_finding_id);
                const control = controlsByTitle.get(mapping.control_catalog_id);
                return [
                  mapping.id,
                  finding ? (
                    <span className="flex items-center gap-2">
                      <StatusBadge value={finding.severity} />
                      <span className="truncate" title={finding.title}>{finding.title}</span>
                    </span>
                  ) : (
                    <span className="text-slate-500">#{mapping.normalized_finding_id}</span>
                  ),
                  control ? (
                    <span className="truncate" title={`${control.framework} - ${control.title}`}>
                      <span className="font-mono text-xs">{control.control_id}</span>
                      <span className="mx-1 text-slate-400">·</span>
                      <span>{control.title}</span>
                    </span>
                  ) : (
                    <span className="text-slate-500">#{mapping.control_catalog_id}</span>
                  ),
                  <StatusBadge value={mapping.mapping_status} />,
                  formatPercent(mapping.gemini_confidence),
                  formatPercent(mapping.groq_agreement_value),
                  formatPercent(mapping.final_confidence),
                  <StatusBadge value={mapping.verification_status || "pending"} />,
                ];
              })}
            />
          )}
        </ResourceBoundary>
      </Section>
      <Section title="Mapping Detail">
        {selected ? (
          <div className="space-y-3">
            <Detail label="Mapping" value={selected.id} />
            {(() => {
              const finding = findingsByTitle.get(selected.normalized_finding_id);
              return finding ? (
                <div className="space-y-1">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Finding</div>
                  <div className="flex items-center gap-2">
                    <StatusBadge value={finding.severity} />
                    <span className="text-sm font-medium">{finding.title}</span>
                  </div>
                </div>
              ) : (
                <Detail label="Finding" value={`#${selected.normalized_finding_id}`} />
              );
            })()}
            {(() => {
              const control = controlsByTitle.get(selected.control_catalog_id);
              return control ? (
                <div className="space-y-1">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Control</div>
                  <div className="text-sm">
                    <span className="font-mono text-xs">{control.control_id}</span>
                    <span className="mx-1 text-slate-400">·</span>
                    <span className="font-medium">{control.title}</span>
                    <div className="text-xs text-slate-500">{control.framework}</div>
                  </div>
                </div>
              ) : (
                <Detail label="Control" value={`#${selected.control_catalog_id}`} />
              );
            })()}
            <Detail label="Gemini Score" value={formatPercent(selected.gemini_confidence)} />
            <Detail label="Groq Score" value={formatPercent(selected.groq_agreement_value)} />
            <Detail label="Final Confidence" value={formatPercent(selected.final_confidence)} />
            <Detail label="AI Verdict" value={<StatusBadge value={selected.mapping_status} />} />
            <Detail label="Model" value={selected.mapping_model} />
            <Detail label="Rationale" value={selected.rationale || "n/a"} />
            <h3 className="pt-2 text-sm font-semibold">Verification</h3>
            {verification ? (
              <DataTable
                columns={["ID", "Result", "Agreement", "Model", "Explanation"]}
                rows={verification.map((record) => [record.id, <StatusBadge value={record.result} />, formatPercent(record.agreement_value), record.verification_model, record.explanation || "n/a"])}
              />
            ) : (
              <LoadingState label="Loading verification" />
            )}
          </div>
        ) : (
          <EmptyState label="Select a mapping to see details." />
        )}
      </Section>
    </div>
  );
}

function ReviewTab({ items, resource, onRefresh }: { items: ReviewQueueItem[]; resource: ReturnType<typeof useResource<ReviewQueueItem[]>>; onRefresh: () => void }) {
  const [comment, setComment] = useState("Reviewed from frontend.");

  async function decide(id: number, action: "approve" | "reject") {
    if (action === "approve") {
      await api.reviewQueue.approve(id, comment);
    } else {
      await api.reviewQueue.reject(id, comment);
    }
    await onRefresh();
  }

  return (
    <Section
      title="Review Queue"
      description="Low-confidence or uncertain mappings for this scan require explicit human review."
      actions={<input className="control w-72" value={comment} onChange={(e) => setComment(e.target.value)} />}
    >
      <ResourceBoundary resource={{ ...resource, data: items }}>
        {(data) => (
          <DataTable
            columns={["ID", "Mapping", "Status", "Reason", "Reviewed", "Decision"]}
            rows={data.map((item) => [
              item.id,
              item.control_mapping_id,
              <StatusBadge value={item.status} />,
              item.review_reason_code,
              formatDate(item.reviewed_at),
              item.status === "pending" ? (
                <div className="flex gap-2">
                  <button className="icon-button" onClick={() => decide(item.id, "approve")}>
                    Approve
                  </button>
                  <button className="icon-button" onClick={() => decide(item.id, "reject")}>
                    Reject
                  </button>
                </div>
              ) : (
                <span className="text-xs text-slate-500">Closed</span>
              ),
            ])}
          />
        )}
      </ResourceBoundary>
    </Section>
  );
}

function ReportsTab({ scanRunId, reports, resource, onRefresh }: { scanRunId: number; reports: ComplianceReport[]; resource: ReturnType<typeof useResource<ComplianceReport[]>>; onRefresh: () => void }) {
  const scanReports = reports.filter((r) => r.scan_run_id === scanRunId);
  const [creating, setCreating] = useState<"engineering" | "leadership" | null>(null);
  const [cooldowns, setCooldowns] = useState<Record<string, number>>({});

  async function create(type: "engineering" | "leadership") {
    if (creating || Date.now() < (cooldowns[type] || 0)) return;
    setCreating(type);
    try {
      await api.reports.create(type, scanRunId);
      setCooldowns((prev) => ({ ...prev, [type]: Date.now() + 5000 }));
      await onRefresh();
    } finally {
      setCreating(null);
    }
  }

  return (
    <Section
      title="Reports"
      description="Generate engineering or leadership reports for this scan."
      actions={
        <div className="flex gap-2">
          <button className="icon-button" disabled={Boolean(creating) || Date.now() < (cooldowns.engineering || 0)} onClick={() => create("engineering")}>
            {creating === "engineering" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
            {creating === "engineering" ? "Generating..." : "Generate engineering"}
          </button>
          <button className="icon-button" disabled={Boolean(creating) || Date.now() < (cooldowns.leadership || 0)} onClick={() => create("leadership")}>
            {creating === "leadership" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
            {creating === "leadership" ? "Generating..." : "Generate leadership"}
          </button>
        </div>
      }
    >
      <ResourceBoundary resource={{ ...resource, data: scanReports }}>
        {(data) => (
          <DataTable
            columns={["ID", "Type", "Generated", "Hash", "Download"]}
            rows={data.map((report) => [
              report.id,
              report.report_type,
              formatDate(report.generated_at),
              report.content_hash || "n/a",
              <a className="icon-button" href={api.reports.downloadUrl(report.id)}>
                Download
              </a>,
            ])}
          />
        )}
      </ResourceBoundary>
    </Section>
  );
}

function BundleTab({ scanRunId, bundles, resource, onRefresh }: { scanRunId: number; bundles: AuditBundle[]; resource: ReturnType<typeof useResource<AuditBundle[]>>; onRefresh: () => void }) {
  const scanBundles = bundles.filter((b) => b.scan_run_id === scanRunId);

  async function create() {
    await api.auditBundles.create(scanRunId);
    await onRefresh();
  }

  return (
    <Section
      title="Audit Bundles"
      description="Exportable audit evidence with full lineage for this scan."
      actions={
        <button className="icon-button" onClick={create}>
          Generate bundle
        </button>
      }
    >
      <ResourceBoundary resource={{ ...resource, data: scanBundles }}>
        {(data) => (
          <DataTable
            columns={["ID", "Generated", "Checksum", "Download"]}
            rows={data.map((bundle) => [
              bundle.id,
              formatDate(bundle.generated_at),
              bundle.checksum,
              <a className="icon-button" href={api.auditBundles.downloadUrl(bundle.id)}>
                Download
              </a>,
            ])}
          />
        )}
      </ResourceBoundary>
    </Section>
  );
}
