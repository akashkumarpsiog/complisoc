import { useMemo } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { Section } from "../components/Primitives";
import { TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle2, Info } from "lucide-react";

interface ComplianceMetricsData {
  findings_count: number;
  high_critical_findings: number;
  high_critical_pct: number;
  published_pct: number;
  published_mappings: number;
  total_mappings: number;
  avg_confidence: number;
  review_queue: number;
}

interface Insight {
  type: "success" | "warning" | "info" | "danger";
  title: string;
  message: string;
}

export function ComplianceScoreCard() {
  const aiMetrics = useResource(api.dashboard.aiMetrics);
  const gap = useResource(api.dashboard.gap);
  const severity = useResource(api.dashboard.severity);

  const metricsData = useMemo((): ComplianceMetricsData | null => {
    if (!aiMetrics.data || !gap.data || !severity.data) return null;
    const totalMappings = aiMetrics.data.total_mappings || 0;
    const publishedPct = totalMappings
      ? (aiMetrics.data.published_mappings / totalMappings) * 100
      : 0;
    const severityCounts = severity.data.severity_counts;
    const findingsCount = Object.values(severityCounts).reduce((total, count) => total + count, 0);
    const highCriticalFindings = (severityCounts.high || 0) + (severityCounts.critical || 0);
    return {
      findings_count: findingsCount,
      high_critical_findings: highCriticalFindings,
      high_critical_pct: findingsCount ? (highCriticalFindings / findingsCount) * 100 : 0,
      published_pct: publishedPct,
      published_mappings: aiMetrics.data.published_mappings,
      total_mappings: totalMappings,
      avg_confidence: (aiMetrics.data.avg_final_confidence ?? 0) * 100,
      review_queue: gap.data.manual_review_mappings,
    };
  }, [aiMetrics.data, gap.data, severity.data]);

  return (
    <Section title="Compliance Metrics" description="Independent signals about findings, control mappings, and review status">
      <ResourceBoundary resource={{ ...aiMetrics, status: aiMetrics.data ? "success" : aiMetrics.status, error: aiMetrics.error }}>
            {() => (
              <ResourceBoundary resource={{ ...gap, status: gap.data ? "success" : gap.status, error: gap.error }}>
                {() => (
                  <ResourceBoundary resource={{ ...severity, status: severity.data ? "success" : severity.status, error: severity.error }}>
                    {() => metricsData ? (
                      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                        <Metric accent="sky" label="Findings" value={metricsData.findings_count} detail="Recorded normalized findings" description="Total security findings currently recorded from scanners. Findings represent detected issues, not compliance status." />
                        <Metric accent="emerald" label="Avg Confidence" value={`${metricsData.avg_confidence.toFixed(0)}%`} detail="Final AI mapping confidence" description="Average final confidence assigned to AI-generated control mappings after validation and verification. It indicates how strongly the mapping workflow supports the selected control, not organizational compliance." />
                        <Metric accent="brand" label="Published Mappings" value={`${metricsData.published_pct.toFixed(0)}%`} detail={`${metricsData.published_mappings} of ${metricsData.total_mappings} mappings`} description="Percentage of generated control mappings that passed validation and verification and were published automatically." />
                        <Metric accent="amber" label="Review Queue" value={metricsData.review_queue} detail="Mappings awaiting human review" description="Number of mappings awaiting human review because they did not meet the publication threshold or require manual validation." />
                        <Metric accent="rose" label="High/Critical Findings" value={metricsData.high_critical_findings} detail={`${metricsData.high_critical_pct.toFixed(0)}% of recorded findings`} description="Number of currently recorded high- and critical-severity security findings. These represent the highest-priority issues requiring attention." />
                      </div>
                    ) : (
                      <div className="text-sm text-muted">Loading metrics...</div>
                    )}
                  </ResourceBoundary>
                )}
              </ResourceBoundary>
            )}
      </ResourceBoundary>
    </Section>
  );
}

function Metric({ accent, label, value, detail, description }: { accent: "brand" | "sky" | "emerald" | "amber" | "rose"; label: string; value: string | number; detail: string; description: string }) {
  const styles = {
    brand: "border-brand-200 bg-brand-50/60 text-brand-700",
    sky: "border-sky-200 bg-sky-50/60 text-sky-700",
    emerald: "border-emerald-200 bg-emerald-50/60 text-emerald-700",
    amber: "border-amber-200 bg-amber-50/60 text-amber-700",
    rose: "border-rose-200 bg-rose-50/60 text-rose-700",
  };
  return (
    <div className={`rounded-lg border p-4 ${styles[accent]}`}>
      <div className="text-sm font-medium">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-ink">{value}</div>
      <div className="mt-1 text-xs font-medium text-muted">{detail}</div>
      <p className="mt-3 text-xs leading-5 text-muted">{description}</p>
    </div>
  );
}

export function ComplianceInsightsPanel() {
  const coverage = useResource(api.dashboard.coverage);
  const aiMetrics = useResource(api.dashboard.aiMetrics);
  const gap = useResource(api.dashboard.gap);
  const trends = useResource(api.dashboard.trends);

  const insights = useMemo((): Insight[] => {
    const results: Insight[] = [];
    if (!coverage.data || !aiMetrics.data || !gap.data) return results;

    const coveragePct = coverage.data.total_controls
      ? (coverage.data.covered_controls / coverage.data.total_controls) * 100
      : 0;
    if (coveragePct >= 80) {
      results.push({ type: "success", title: "Strong coverage", message: `${coveragePct.toFixed(0)}% of controls have published mappings.` });
    } else if (coveragePct < 50) {
      results.push({ type: "warning", title: "Low coverage", message: `Only ${coveragePct.toFixed(0)}% of controls are covered. Consider scanning additional resources.` });
    }

    const totalMappings = aiMetrics.data.total_mappings || 0;
    const publishedPct = totalMappings ? (aiMetrics.data.published_mappings / totalMappings) * 100 : 0;
    if (publishedPct >= 70) {
      results.push({ type: "success", title: "High mapping quality", message: `${publishedPct.toFixed(0)}% of mappings are published.` });
    }

    if (gap.data.manual_review_mappings > 10) {
      results.push({ type: "warning", title: "Review backlog", message: `${gap.data.manual_review_mappings} mappings require manual review.` });
    }
    if (gap.data.rejected_mappings > 5) {
      results.push({ type: "danger", title: "Rejected mappings", message: `${gap.data.rejected_mappings} mappings were rejected. Investigate root causes.` });
    }

    const avgConf = (aiMetrics.data.avg_final_confidence ?? 0) * 100;
    if (avgConf >= 70) {
      results.push({ type: "success", title: "High confidence", message: `Average mapping confidence is ${avgConf.toFixed(0)}%.` });
    } else if (avgConf < 50 && avgConf > 0) {
      results.push({ type: "warning", title: "Low confidence", message: `Average mapping confidence is ${avgConf.toFixed(0)}%. Consider reviewing AI model performance.` });
    }

    if (trends.data && trends.data.trends.length >= 2) {
      const recent = trends.data.trends[trends.data.trends.length - 1];
      const previous = trends.data.trends[trends.data.trends.length - 2];
      if (recent.published > previous.published) {
        results.push({ type: "success", title: "Improving trend", message: "Published mappings increased in the latest scan." });
      } else if (recent.manual_review > previous.manual_review) {
        results.push({ type: "info", title: "Review pressure", message: "Manual review items increased in the latest scan." });
      }
    }

    if (results.length === 0) {
      results.push({ type: "info", title: "No significant insights", message: "Run more scans to generate actionable insights." });
    }

    return results;
  }, [coverage.data, aiMetrics.data, gap.data, trends.data]);

  const iconMap = {
    success: <CheckCircle2 className="h-4 w-4 text-success-dark" />,
    warning: <AlertTriangle className="h-4 w-4 text-warning-dark" />,
    danger: <AlertTriangle className="h-4 w-4 text-danger-dark" />,
    info: <Info className="h-4 w-4 text-brand-600" />,
  };

  return (
    <Section title="Compliance Insights" description="Automated observations about your compliance posture">
      <div className="space-y-3">
        {insights.length === 0 ? (
          <div className="text-sm text-muted">Analyzing data...</div>
        ) : (
          insights.map((insight, idx) => (
            <div key={idx} className="flex items-start gap-3 rounded-lg border border-line bg-panel/40 p-3">
              <span className="mt-0.5 shrink-0">{iconMap[insight.type]}</span>
              <div>
                <div className="text-sm font-semibold text-ink">{insight.title}</div>
                <div className="text-sm text-muted">{insight.message}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </Section>
  );
}
