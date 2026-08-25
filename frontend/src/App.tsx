import { useState } from "react";
import { Layout } from "./components/Layout";
import type { ViewId } from "./navigation";
import { OverviewPage } from "./pages/OverviewPage";
import { ScanRunsPage } from "./pages/ScanRunsPage";
import { ScanDetailPage } from "./pages/ScanDetailPage";
import { ControlsPage } from "./pages/ControlsPage";
import { ReviewPage } from "./pages/ReviewPage";
import { ReportsPage } from "./pages/ReportsPage";
import { AuditBundlesPage } from "./pages/AuditBundlesPage";
import { ComplianceDriftPage } from "./pages/ComplianceDriftPage";
import { EvidenceLineagePage } from "./pages/EvidenceLineagePage";

export function App() {
  const [view, setView] = useState<ViewId>("overview");
  const [selectedScanId, setSelectedScanId] = useState<number | null>(null);

  const handleViewChange = (id: ViewId) => {
    setView(id);
    if (id !== "scan-detail") {
      setSelectedScanId(null);
    }
  };

  const handleSelectScan = (id: number) => {
    setSelectedScanId(id);
    setView("scan-detail");
  };

  return (
      <Layout view={view} onViewChange={handleViewChange}>
        {view === "overview" && <OverviewPage onViewChange={handleViewChange} />}
        {view === "scan-runs" && <ScanRunsPage onSelectScan={handleSelectScan} />}
        {view === "scan-detail" && selectedScanId !== null && (
          <ScanDetailPage scanRunId={selectedScanId} onBack={() => handleViewChange("scan-runs")} />
        )}
        {view === "scan-detail" && selectedScanId === null && <ScanRunsPage onSelectScan={handleSelectScan} />}
        {view === "compliance-drift" && <ComplianceDriftPage />}
        {view === "evidence-lineage" && <EvidenceLineagePage />}
        {view === "controls" && <ControlsPage />}
        {view === "review" && <ReviewPage />}
        {view === "reports" && <ReportsPage />}
        {view === "audit-bundles" && <AuditBundlesPage />}
      </Layout>
  );
}
