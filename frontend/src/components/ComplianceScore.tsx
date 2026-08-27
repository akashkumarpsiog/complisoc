import { useMemo } from "react";
import { api } from "../services/api";
import { useResource } from "../hooks/useResource";
import { ResourceBoundary } from "../components/ResourceBoundary";
import { Section } from "../components/Primitives";
import { TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle2, Info } from "lucide-react";

interface ComplianceScoreData {
  score: number;
  coverage_pct: number;
  published_pct: number;
  avg_confidence: number;
  gap_count: number;
}

interface Insight {
  type: "success" | "warning" | "info" | "danger";
  title: string;
  message: string;
}

export function ComplianceScoreCard() {
  const coverage = useResource(api.dashboard.coverage);
  const aiMetrics = useResource(api.dashboard.aiMetrics);
  const gap = useResource(api.dashboard.gap);

  const scoreData = useMemo((): ComplianceScoreData | null => {
    if (!coverage.data || !aiMetrics.data) return null;
    const coveragePct = coverage.data.total_controls
      ? (coverage.data.covered_controls / coverage.data.total_controls) * 100
      : 0;
    const totalMappings = aiMetrics.data.total_mappings || 0;
    const publishedPct = totalMappings
      ? (aiMetrics.data.published_mappings / totalMappings) * 100
      : 0;
    const avgConfidence = ((aiMetrics.data.avg_final_confidence ?? 0) * 100);
    const gapCount = (gap.data?.manual_review_mappings || 0) + (gap.data?.rejected_mappings || 0);
    const score = Math.round((coveragePct * 0.4) + (publishedPct * 0.3) + (avgConfidence * 0.3));
    return { score, coverage_pct: coveragePct, published_pct: publishedPct, avg_confidence: avgConfidence, gap_count: gapCount };
  }, [coverage.data, aiMetrics.data, gap.data]);

  const accent = scoreData && scoreData.score >= 70 ? "emerald" : scoreData && scoreData.score >= 40 ? "amber" : "rose";

  return (
    <Section title="Compliance Posture Score" description="Overall compliance health based on coverage, mapping quality, and confidence">
      <ResourceBoundary resource={{ ...coverage, status: coverage.data ? "success" : coverage.status, error: coverage.error }}>
        {() => (
          <ResourceBoundary resource={{ ...aiMetrics, status: aiMetrics.data ? "success" : aiMetrics.status, error: aiMetrics.error }}>
            {() => scoreData ? (
              <div className="flex items-center gap-6">
                <div className={`flex h-20 w-20 items-center justify-center rounded-2xl ${accent === "emerald" ? "bg-success-light" : accent === "amber" ? "bg-warning-light" : "bg-danger-light"}`}>
                  <span className={`text-3xl font-bold ${accent === "emerald" ? "text-success-dark" : accent === "amber" ? "text-warning-dark" : "text-danger-dark"}`}>
                    {scoreData.score}
                  </span>
                </div>
                <div className="flex-1 space-y-2">
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <div className="text-subtle font-medium">Coverage</div>
                      <div className="font-semibold text-ink">{scoreData.coverage_pct.toFixed(0)}%</div>
                    </div>
                    <div>
                      <div className="text-subtle font-medium">Published</div>
                      <div className="font-semibold text-ink">{scoreData.published_pct.toFixed(0)}%</div>
                    </div>
                    <div>
                      <div className="text-subtle font-medium">Avg Confidence</div>
                      <div className="font-semibold text-ink">{scoreData.avg_confidence.toFixed(0)}%</div>
                    </div>
                  </div>
                  <div className="text-xs text-subtle">
                    Weighted: 40% coverage + 30% published + 30% confidence
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted">Calculating score...</div>
            )}
          </ResourceBoundary>
        )}
      </ResourceBoundary>
    </Section>
  );
}

export function AutomatedInsightsPanel() {
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
    <Section title="Automated Insights" description="AI-generated observations about your compliance posture">
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
