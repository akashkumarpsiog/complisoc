import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { BarList, DataTable, MetricCard, Section, StatusBadge } from "../components/Primitives";
import { severityOrder } from "../utils/format";

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
          {(data) => <MetricCard label="Control coverage" value={`${data.covered_controls}/${data.total_controls}`} detail="Published mapped controls" />}
        </ResourceBoundary>
        <ResourceBoundary resource={gap}>
          {(data) => <MetricCard label="Manual review" value={data.manual_review_mappings} detail="Mappings awaiting decision" />}
        </ResourceBoundary>
        <ResourceBoundary resource={gap}>
          {(data) => <MetricCard label="Rejected" value={data.rejected_mappings} detail="Mappings not accepted" />}
        </ResourceBoundary>
        <ResourceBoundary resource={backlog}>
          {(data) => <MetricCard label="Backlog" value={data.items.length} detail="Remediation queue items" />}
        </ResourceBoundary>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Section title="Severity Distribution">
          <ResourceBoundary resource={severity}>
            {(data) => (
              <BarList
                values={Object.fromEntries(
                  severityOrder.filter((key) => data.severity_counts[key] !== undefined).map((key) => [key, data.severity_counts[key]]),
                )}
              />
            )}
          </ResourceBoundary>
        </Section>

        <Section title="Historical Trends">
          <ResourceBoundary resource={trends}>
            {(data) => (
              <BarList values={Object.fromEntries(data.trends.map((item) => [`scan ${item.scan_run_id}`, item.published + item.manual_review]))} />
            )}
          </ResourceBoundary>
        </Section>
      </div>

      <Section title="Compliance Gap Summary">
        <ResourceBoundary resource={gap}>
          {(data) => <DataTable columns={["Manual Review", "Rejected"]} rows={[[data.manual_review_mappings, data.rejected_mappings]]} />}
        </ResourceBoundary>
      </Section>

      <Section title="Remediation Backlog">
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
