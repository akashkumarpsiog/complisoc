import { useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import type { FindingLineage, ScanRun } from "../types";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { Section, StatusBadge } from "../components/Primitives";
import { formatDate } from "../utils/format";
import { ChevronDown, ChevronUp, GitBranch, FileJson, ShieldCheck, Scan, CheckCircle2, XCircle, Loader2 } from "lucide-react";

export function EvidenceLineagePage({ onViewChange }: { onViewChange?: (viewId: string) => void }) {
  const [scanRunId, setScanRunId] = useState("");
  const [findingId, setFindingId] = useState("");
  const [submittedId, setSubmittedId] = useState<number | null>(null);

  const scanRuns = useResource(api.scanRuns.list);

  const findings = useResource(
    () => (scanRunId ? api.findings.list({ scan_run_id: Number(scanRunId) }) : Promise.resolve([])),
    [scanRunId],
  );

  const lineage = useResource<FindingLineage | null>(
    () => {
      if (!submittedId) return Promise.resolve(null);
      return api.findings.lineage(submittedId);
    },
    [submittedId]
  );

  const handleView = () => {
    const id = Number(findingId);
    if (!id) return;
    setSubmittedId(id);
  };

  const handleScanRunChange = (value: string) => {
    setScanRunId(value);
    setFindingId("");
    setSubmittedId(null);
  };

  const findingsList = findings.data ?? [];
  const lineageData = lineage.data ?? null;

  return (
    <Section
      title="Evidence Lineage"
      description="Choose a scan, then a finding, to trace its full compliance evidence chain"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="control"
            value={scanRunId}
            onChange={(e) => handleScanRunChange(e.target.value)}
            disabled={scanRuns.status === "loading"}
          >
            <option value="">1. Choose a scan run</option>
            {(scanRuns.data || []).map((scanRun: ScanRun) => (
              <option key={scanRun.id} value={scanRun.id}>
                Scan #{scanRun.id} - {scanRun.target_environment} - {scanRun.status}
              </option>
            ))}
          </select>
          <select
            className="control"
            value={findingId}
            onChange={(e) => setFindingId(e.target.value)}
            disabled={!scanRunId || findings.status === "loading"}
          >
            <option value="">
              {!scanRunId ? "Select a scan first" : findings.status === "loading" ? "Loading findings..." : `Choose a finding (${findingsList.length} available)`}
            </option>
            {findingsList.slice(0, 100).map((finding) => (
              <option key={finding.id} value={finding.id}>
                #{finding.id} · {finding.severity.toUpperCase()} · {finding.title} · {finding.resource_identifier}
              </option>
            ))}
            {findingsList.length > 100 && (
              <option disabled>…and {findingsList.length - 100} more (refine search)</option>
            )}
          </select>
          <button className="icon-button" disabled={!findingId} onClick={handleView}>
            View lineage
          </button>
        </div>
      }
    >
      {!submittedId ? (
        <div className="text-sm text-muted">
          Start with a scan run, choose one of its findings, then view the evidence lineage.
        </div>
      ) : lineageData ? (
        <LineageView data={lineageData} />
      ) : (
        <ResourceBoundary resource={lineage}>
          {(data) => <LineageView data={data} />}
        </ResourceBoundary>
      )}
    </Section>
  );
}

function LineageView({ data }: { data: FindingLineage }) {
  const [expandedMapping, setExpandedMapping] = useState<number | null>(null);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 text-sm font-semibold text-subtle">
        <Scan className="h-4 w-4" aria-hidden />
        Scan Run
      </div>
      {data.scan_run ? (
        <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-subtle">Scan run ID</div>
              <div className="mt-1 text-sm font-semibold text-ink">#{data.scan_run.id}</div>
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-subtle">Environment</div>
              <div className="mt-1 text-sm text-ink">{data.scan_run.target_environment}</div>
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-subtle">Status</div>
              <div className="mt-1"><StatusBadge value={data.scan_run.status} /></div>
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-subtle">Created</div>
              <div className="mt-1 text-sm text-ink">{formatDate(data.scan_run.created_at)}</div>
            </div>
          </div>
        </div>
      ) : (
        <EmptyLineageCard label="Scan run not found" />
      )}

      <div className="flex items-center gap-3 text-sm font-semibold text-subtle">
        <FileJson className="h-4 w-4" aria-hidden />
        Raw Finding
      </div>
      {data.raw_finding ? (
        <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-subtle">Raw finding ID</div>
              <div className="mt-1 text-sm font-semibold text-ink">#{data.raw_finding.id}</div>
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-subtle">Scanner finding ID</div>
              <div className="mt-1 text-sm font-mono text-ink">{data.raw_finding.scanner_finding_id}</div>
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-subtle">Scanner</div>
              <div className="mt-1 text-sm text-ink">{data.raw_finding.scanner_name}</div>
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-subtle">Created</div>
              <div className="mt-1 text-sm text-ink">{formatDate(data.raw_finding.created_at)}</div>
            </div>
          </div>
          {data.raw_finding.raw_json && (
            <details className="mt-4">
              <summary className="cursor-pointer text-xs font-semibold text-brand-600 hover:text-brand-700">Raw JSON evidence</summary>
              <pre className="mt-2 overflow-x-auto rounded-lg bg-panel p-4 text-xs text-muted">
                {JSON.stringify(data.raw_finding.raw_json, null, 2)}
              </pre>
            </details>
          )}
        </div>
      ) : (
        <EmptyLineageCard label="Raw finding not found" />
      )}

      <div className="flex items-center gap-3 text-sm font-semibold text-subtle">
        <GitBranch className="h-4 w-4" aria-hidden />
        Normalized Finding
      </div>
      <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-subtle">Finding ID</div>
            <div className="mt-1 text-sm font-semibold text-ink">#{data.normalized_finding.id}</div>
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-subtle">Scanner</div>
            <div className="mt-1 text-sm text-ink">{data.normalized_finding.scanner_name}</div>
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-subtle">Severity</div>
            <div className="mt-1"><StatusBadge value={data.normalized_finding.severity} /></div>
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-subtle">Resource</div>
            <div className="mt-1 text-sm font-mono text-ink">{data.normalized_finding.resource_identifier}</div>
          </div>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-subtle">Title</div>
            <div className="mt-1 text-sm text-ink">{data.normalized_finding.title}</div>
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-subtle">Description</div>
            <div className="mt-1 text-sm text-muted">{data.normalized_finding.description || "n/a"}</div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 text-sm font-semibold text-subtle">
        <ShieldCheck className="h-4 w-4" aria-hidden />
        Control Mappings
      </div>
      {data.mappings.length === 0 ? (
        <EmptyLineageCard label="No control mappings yet" />
      ) : (
        <div className="space-y-3">
          {data.mappings.map((mapping) => (
            <div key={mapping.mapping_id} className="rounded-xl border border-line bg-white shadow-sm overflow-hidden">
              <button
                className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left hover:bg-panel-hover transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-brand-500"
                onClick={() => setExpandedMapping((prev) => (prev === mapping.mapping_id ? null : mapping.mapping_id))}
                aria-expanded={expandedMapping === mapping.mapping_id}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ink">Mapping #{mapping.mapping_id}</span>
                    <StatusBadge value={mapping.mapping_status} />
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {mapping.framework_name} {mapping.control_id} · {mapping.control_title}
                  </div>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted">
                  <span>Confidence: {mapping.final_confidence !== null && mapping.final_confidence !== undefined ? `${(mapping.final_confidence * 100).toFixed(0)}%` : "n/a"}</span>
                  {expandedMapping === mapping.mapping_id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </div>
              </button>
              {expandedMapping === mapping.mapping_id && (
                <div className="border-t border-line px-5 py-4 space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-subtle">Gemini confidence</div>
                      <div className="mt-1 text-sm text-ink">{mapping.gemini_confidence !== null && mapping.gemini_confidence !== undefined ? `${(mapping.gemini_confidence * 100).toFixed(1)}%` : "n/a"}</div>
                    </div>
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-subtle">Groq agreement</div>
                      <div className="mt-1 text-sm text-ink">{mapping.groq_agreement_value !== null && mapping.groq_agreement_value !== undefined ? `${(mapping.groq_agreement_value * 100).toFixed(1)}%` : "n/a"}</div>
                    </div>
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-subtle">Verification status</div>
                      <div className="mt-1"><StatusBadge value={mapping.verification_status} /></div>
                    </div>
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-subtle">Created</div>
                      <div className="mt-1 text-sm text-ink">{formatDate(mapping.created_at)}</div>
                    </div>
                  </div>
                  {mapping.rationale && (
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-subtle">Rationale</div>
                      <p className="mt-1 text-sm text-muted leading-relaxed">{mapping.rationale}</p>
                    </div>
                  )}

                  <div>
                    <div className="text-xs font-bold uppercase tracking-wider text-subtle mb-2">Verification records</div>
                    {mapping.verification_records.length === 0 ? (
                      <p className="text-sm text-muted">No verification records.</p>
                    ) : (
                      <div className="space-y-2">
                        {mapping.verification_records.map((vr) => (
                          <div key={vr.id} className="rounded-lg border border-line bg-panel/40 p-4">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold text-ink">Verification #{vr.id}</span>
                                <StatusBadge value={vr.result} />
                              </div>
                              <span className="text-xs text-muted">{formatDate(vr.timestamp)}</span>
                            </div>
                            {vr.explanation && (
                              <p className="mt-2 text-sm text-muted leading-relaxed">{vr.explanation}</p>
                            )}
                            <div className="mt-2 text-xs text-muted">
                              Model: {vr.verification_model} · Agreement: {vr.agreement_value !== null && vr.agreement_value !== undefined ? `${(vr.agreement_value * 100).toFixed(1)}%` : "n/a"}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyLineageCard({ label }: { label: string }) {
  return (
    <div className="flex min-h-24 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line-strong bg-panel/50 p-6 text-center">
      <p className="text-sm text-muted font-medium">{label}</p>
    </div>
  );
}
