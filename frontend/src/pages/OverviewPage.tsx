import { useState } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { BarList, DataTable, DonutChart, MetricCard, ProgressBar, Section, StatusBadge } from "../components/Primitives";
import { ControlDrillDownDrawer, RemediationSuggestionPanel } from "../components/DashboardDetails";
import { formatPercent } from "../utils/format";

export function OverviewPage({ onViewChange }: { onViewChange?: (viewId: string) => void }) {
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
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <ResourceBoundary resource={coverage}>
          {(data) => (
            <MetricCard
              label="Control coverage"
              value={`${data.covered_controls}/${data.total_controls}`}
              detail={`${Math.round((data.covered_controls / data.total_controls) * 100)}% of controls covered`}
              accent="emerald"
              progress={data.total_controls ? data.covered_controls / data.total_controls : 0}
            />
          )}
        </ResourceBoundary>
        <ResourceBoundary resource={gap}>
          {(data) => (
            <MetricCard label="Manual review" value={data.manual_review_mappings} detail="Mappings awaiting decision" accent="amber" />
          )}
        </ResourceBoundary>
        <ResourceBoundary resource={gap}>
          {(data) => <MetricCard label="Rejected" value={data.rejected_mappings} detail="Mappings not accepted" accent="rose" />}
        </ResourceBoundary>
        <ResourceBoundary resource={backlog}>
          {(data) => <MetricCard label="Backlog" value={data.items.length} detail="Remediation queue items" accent="brand" />}
        </ResourceBoundary>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <ResourceBoundary resource={coverage}>
          {(data) => (
            <Section
              title="Control Coverage"
              description="Published mappings vs. total control catalog"
              className="xl:col-span-1"
            >
              <div className="flex flex-col items-center gap-4">
                <DonutChart
                  value={data.covered_controls}
                  total={data.total_controls}
                  label="Coverage"
                  accent="emerald"
                  size={140}
                />
                <div className="text-center">
                  <p className="text-sm text-slate-600">
                    {data.total_controls - data.covered_controls} controls have <span className="font-medium text-slate-800">no published mapping</span>
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
        <Section title="Historical Trends" description="Published vs. manual-review per scan" className="xl:col-span-1" collapsible>
          <ResourceBoundary resource={trends}>
            {(data) => (
              <div className="space-y-3">
                {(visibleTrends || []).slice().reverse().map((item: { scan_run_id: number; published: number; manual_review: number; created_at: string }) => (
                  <div key={item.scan_run_id} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-slate-700">Scan #{item.scan_run_id}</span>
                      <span className="text-xs text-slate-500">{new Date(item.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-center">
                      <div>
                        <span className="text-lg font-semibold text-emerald-600 tabular-nums">{item.published}</span>
                        <span className="block text-xs text-slate-500">Published</span>
                      </div>
                      <div>
                        <span className="text-lg font-semibold text-amber-600 tabular-nums">{item.manual_review}</span>
                        <span className="block text-xs text-slate-500">Review</span>
                      </div>
                    </div>
                  </div>
                ))}
                {trends.data && trends.data.trends.length > 5 && (
                  <button className="text-sm font-medium text-brand-700 hover:text-brand-800" onClick={() => setShowAllTrends(!showAllTrends)}>
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
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <DataTable columns={["Manual Review", "Rejected"]} rows={[[data.manual_review_mappings, data.rejected_mappings]]} />
                  </div>
                  <div className="space-y-3">
                    <GapMeter label="Manual review" value={data.manual_review_mappings} max={Math.max(data.manual_review_mappings + data.rejected_mappings, 1)} tone="amber" />
                    <GapMeter label="Rejected" value={data.rejected_mappings} max={Math.max(data.manual_review_mappings + data.rejected_mappings, 1)} tone="rose" />
                  </div>
                </div>

                {data.failed_controls && data.failed_controls.length > 0 ? (
                  <div>
                    <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Failed controls by status</h3>
                    <DataTable
                      columns={["Status", "Control ID", "Control Title", "Count"]}
                      rows={data.failed_controls.map((item) => [
                        <StatusBadge value={item.status} />,
                        <button className="font-medium text-brand-700 underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-brand-500" onClick={() => setSelectedControlId(item.control_catalog_id ?? null)}>{item.control_id}</button>,
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
                    columns={["Mapping", "Status", "Severity", "Resource", "Control", "Gemini", "Groq", "Guidance"]}
                    rows={data.items.map((item) => [
                      item.mapping_id,
                      <StatusBadge value={item.status} />,
                      item.severity,
                      item.resource_identifier,
                      <button className="text-left font-medium text-brand-700 underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-brand-500" onClick={() => setSelectedControlId(item.control_catalog_id)}>{item.control_id} {item.control_title}</button>,
                      formatPercent(item.gemini_confidence),
                      formatPercent(item.groq_agreement_value),
                      <RemediationSuggestionPanel item={item} />,
                    ])}
                  />
                  {data.total > data.items.length && (
                    <p className="text-sm text-slate-500">
                      Showing {data.items.length} of {data.total} items. {onViewChange ? (
                        <button className="font-medium text-brand-700 underline-offset-2 hover:underline" onClick={() => onViewChange("review")}>View all {data.total} items in Review Queue &rarr;</button>
                      ) : (
                        <span className="font-medium text-brand-700">View all {data.total} items in Review Queue &rarr;</span>
                      )}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-slate-500">No remediation items in the backlog.</p>
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
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="font-semibold tabular-nums text-slate-600">{value}</span>
      </div>
      <ProgressBar value={pct} tone={tone} />
    </div>
  );
}
