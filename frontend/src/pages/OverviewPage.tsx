import type { ViewId } from "../navigation";
import { useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { BarList, DataTable, DonutChart, ProgressBar, Section, StatusBadge, staggerStyle } from "../components/Primitives";
import { ControlDrillDownDrawer, RemediationSuggestionPanel } from "../components/DashboardDetails";
import { ComplianceScoreCard } from "../components/ComplianceScore";
import { formatPercent } from "../utils/format";

export function OverviewPage({ onViewChange }: { onViewChange?: (viewId: ViewId) => void }) {
  const [selectedControlId, setSelectedControlId] = useState<number | null>(null);
  const [showAllTrends, setShowAllTrends] = useState(false);
  const coverage = useResource(api.dashboard.coverage);
  const severity = useResource(api.dashboard.severity);
  const gap = useResource(api.dashboard.gap);
  const backlog = useResource(api.dashboard.backlog);
  const trends = useResource(api.dashboard.trends);

  const visibleTrends = showAllTrends ? trends.data?.trends : trends.data?.trends.slice(-5);

  return (
    <>
      <ComplianceScoreCard />

      <div className="grid gap-5 xl:grid-cols-3">
        <ResourceBoundary resource={coverage}>
          {(data) => (
            <Section
              title="Control Coverage"
              description="Published mappings vs. total control catalog"
              className="xl:col-span-1"
            >
              <div className="flex flex-col items-center gap-5">
                <DonutChart
                  value={data.covered_controls}
                  total={data.total_controls}
                  label="Controls with findings"
                  accent="emerald"
                  size={160}
                />
                <div className="text-center">
                  <p className="text-sm text-muted leading-relaxed">
                    {data.total_controls - data.covered_controls} controls have <span className="font-semibold text-ink">no published mapping</span>
                  </p>
                </div>
              </div>
            </Section>
          )}
        </ResourceBoundary>

        <Section title="Severity Distribution" description="Findings by normalized severity" className="xl:col-span-2">
          <ResourceBoundary resource={severity}>
            {(data) => (
              <BarList
                tone="severity"
                values={Object.fromEntries(
                  Object.entries(data.severity_counts).sort((a, b) => b[1] - a[1]),
                )}
              />
            )}
          </ResourceBoundary>
        </Section>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Section title="Mapping Workflow History" description="Findings and mapping outcomes per scan" className="xl:col-span-1" collapsible>
          <ResourceBoundary resource={trends}>
            {(data) => (
              <div className="space-y-4">
                {(visibleTrends || []).slice().reverse().map((item) => (
                  <div key={item.scan_run_id} className="space-y-2 animate-slide-up" style={staggerStyle(item.scan_run_id % 5)}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-semibold text-ink">Scan #{item.scan_run_id}</span>
                      <span className="text-xs text-subtle font-medium">{new Date(item.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-center">
                        <span className="text-lg font-bold text-sky-700 tabular-nums">{item.findings}</span>
                        <span className="block text-xs font-medium text-sky-700/70 mt-0.5">Findings</span>
                      </div>
                      <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-center">
                        <span className="text-lg font-bold text-rose-700 tabular-nums">{item.high_critical_findings}</span>
                        <span className="block text-xs font-medium text-rose-700/70 mt-0.5">High/Critical</span>
                      </div>
                      <div className="rounded-lg border border-success/20 bg-success-light p-3 text-center">
                        <span className="text-lg font-bold text-success-dark tabular-nums">{item.published}</span>
                        <span className="block text-xs font-medium text-success/70 mt-0.5">Published</span>
                      </div>
                      <div className="rounded-lg border border-warning/20 bg-warning-light p-3 text-center">
                        <span className="text-lg font-bold text-warning-dark tabular-nums">{item.manual_review}</span>
                        <span className="block text-xs font-medium text-warning/70 mt-0.5">Review</span>
                      </div>
                    </div>
                  </div>
                ))}
                {trends.data && trends.data.trends.length > 5 && (
                  <button className="text-sm font-semibold text-brand-600 hover:text-brand-700 transition-colors duration-150" onClick={() => setShowAllTrends(!showAllTrends)}>
                    {showAllTrends ? "Show less" : `Show all ${trends.data.trends.length} scans`}
                  </button>
                )}
              </div>
            )}
          </ResourceBoundary>
        </Section>

        <Section title="Compliance Gap Summary" description="Where mapping decisions are unresolved" className="xl:col-span-1">
          <ResourceBoundary resource={gap}>
            {(data) => (
              <div className="space-y-5">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <DataTable
                        columns={["Manual Review", "Rejected"]}
                        rows={[[data.manual_review_mappings, data.rejected_mappings]]}
                      />
                    </div>
                    <div className="space-y-4">
                      <GapMeter label="Manual review" value={data.manual_review_mappings} max={Math.max(data.manual_review_mappings + data.rejected_mappings, 1)} tone="amber" />
                      <GapMeter label="Rejected" value={data.rejected_mappings} max={Math.max(data.manual_review_mappings + data.rejected_mappings, 1)} tone="rose" />
                    </div>
                  </div>

                {data.failed_controls && data.failed_controls.length > 0 ? (
                  <div>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-subtle mb-3">Failed controls by status</h3>
                    <DataTable
                      columns={["Status", "Control ID", "Control Title", "Count"]}
                      rows={data.failed_controls.map((item) => [
                        <StatusBadge key={`status-${item.control_catalog_id}`} value={item.status} />,
                        <button key={`id-${item.control_catalog_id}`} className="font-semibold text-brand-600 hover:text-brand-700 underline-offset-2 hover:underline transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500 rounded" onClick={() => setSelectedControlId(item.control_catalog_id ?? null)}>{item.control_id}</button>,
                        item.control_title,
                        item.count,
                      ])}
                    />
                  </div>
                ) : null}
              </div>
            )}
          </ResourceBoundary>
        </Section>
      </div>

      <Section title="Remediation Backlog" description="Mappings routed to remediation" collapsible>
        <ResourceBoundary resource={backlog}>
          {(data) => (
            <div className="space-y-4">
              {data.items.length > 0 ? (
                <>
                  <DataTable
                    columns={["Mapping", "Status", "Severity", "Resource", "Control", "Gemini", "Groq"]}
                    rows={data.items.map((item) => [
                      item.mapping_id,
                      <StatusBadge key={`status-${item.mapping_id}`} value={item.status} />,
                      item.severity,
                      item.resource_identifier,
                      <button key={`control-${item.mapping_id}`} className="text-left font-semibold text-brand-600 hover:text-brand-700 underline-offset-2 hover:underline transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500 rounded" onClick={() => setSelectedControlId(item.control_catalog_id)}>{item.control_id} {item.control_title}</button>,
                      formatPercent(item.gemini_confidence),
                      formatPercent(item.groq_agreement_value),
                    ])}
                    expandableRows={data.items.map((item) => (
                      <RemediationSuggestionPanel key={`guide-${item.mapping_id}`} item={item} />
                    ))}
                  />
                  {data.total > data.items.length && (
                    <p className="text-sm text-muted">
                      Showing {data.items.length} of {data.total} items. {onViewChange ? (
                        <button className="font-semibold text-brand-600 hover:text-brand-700 underline-offset-2 hover:underline transition-colors duration-150" onClick={() => onViewChange("review")}>View all {data.total} items in Review Queue &rarr;</button>
                      ) : (
                        <span className="font-semibold text-brand-600">View all {data.total} items in Review Queue &rarr;</span>
                      )}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted">No remediation items in the backlog.</p>
              )}
            </div>
          )}
        </ResourceBoundary>
      </Section>

      <ControlDrillDownDrawer key={selectedControlId ?? "closed"} controlId={selectedControlId} onClose={() => setSelectedControlId(null)} />
    </>
  );
}

function GapMeter({ label, value, max, tone }: { label: string; value: number; max: number; tone: "amber" | "rose" }) {
  const pct = max > 0 ? value / max : 0;
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-semibold text-ink">{label}</span>
        <span className="text-sm font-bold tabular-nums text-ink">{value}</span>
      </div>
      <ProgressBar value={pct} tone={tone} />
    </div>
  );
}
