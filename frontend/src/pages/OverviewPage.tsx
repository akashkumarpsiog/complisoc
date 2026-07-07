import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { BarList, DataTable, MetricCard, ProgressBar, Section, StatusBadge } from "../components/Primitives";

export function OverviewPage() {
  const coverage = useResource(api.dashboard.coverage);
  const severity = useResource(api.dashboard.severity);
  const gap = useResource(api.dashboard.gap);
  const backlog = useResource(api.dashboard.backlog);
  const trends = useResource(api.dashboard.trends);

  return (
    <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ResourceBoundary resource={coverage}>
          {(data) => (
            <MetricCard
              label="Control coverage"
              value={`${data.covered_controls}/${data.total_controls}`}
              detail="Published mapped controls"
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

      <div className="grid gap-5 xl:grid-cols-2">
        <Section title="Severity Distribution" description="Findings by normalized severity">
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

        <Section title="Historical Trends" description="Published vs. manual-review per scan">
          <ResourceBoundary resource={trends}>
            {(data) => (
              <BarList
                tone="brand"
                values={Object.fromEntries(
                  data.trends
                    .slice()
                    .reverse()
                    .map((item) => [`scan ${item.scan_run_id}`, item.published + item.manual_review]),
                )}
              />
            )}
          </ResourceBoundary>
        </Section>
      </div>

      <Section title="Compliance Gap Summary" description="Where mapping decisions are unresolved">
        <ResourceBoundary resource={gap}>
          {(data) => (
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <DataTable columns={["Manual Review", "Rejected"]} rows={[[data.manual_review_mappings, data.rejected_mappings]]} />
              </div>
              <div className="space-y-3">
                <GapMeter label="Manual review" value={data.manual_review_mappings} tone="amber" />
                <GapMeter label="Rejected" value={data.rejected_mappings} tone="rose" />
              </div>
            </div>
          )}
        </ResourceBoundary>
      </Section>

      <Section title="Remediation Backlog" description="Mappings routed to remediation">
        <ResourceBoundary resource={backlog}>
          {(data) => (
            <DataTable
              columns={["Mapping", "Status", "Severity", "Resource", "Control"]}
              rows={data.items.map((item) => [
                item.mapping_id,
                <StatusBadge value={item.status} />,
                item.severity,
                item.resource_identifier,
                `${item.control_id} ${item.control_title}`,
              ])}
            />
          )}
        </ResourceBoundary>
      </Section>
    </>
  );
}

function GapMeter({ label, value, tone }: { label: string; value: number; tone: "amber" | "rose" }) {
  const max = Math.max(value, 1);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="font-semibold tabular-nums text-slate-600">{value}</span>
      </div>
      <ProgressBar value={value / max} tone={tone} />
    </div>
  );
}
