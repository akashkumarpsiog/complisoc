import { useState } from "react";
import { Layout } from "./components/Layout";
import type { ViewId } from "./navigation";
import { OverviewPage } from "./pages/OverviewPage";
import { ScanRunsPage } from "./pages/ScanRunsPage";
import { FindingsPage } from "./pages/FindingsPage";
import { MappingsPage } from "./pages/MappingsPage";
import { ControlsPage } from "./pages/ControlsPage";
import { ReviewPage } from "./pages/ReviewPage";
import { ReportsPage } from "./pages/ReportsPage";
import { AuditBundlesPage } from "./pages/AuditBundlesPage";

export function App() {
  const [view, setView] = useState<ViewId>("overview");

  return (
    <Layout view={view} onViewChange={setView}>
      {view === "overview" && <OverviewPage />}
      {view === "scan-runs" && <ScanRunsPage />}
      {view === "findings" && <FindingsPage />}
      {view === "mappings" && <MappingsPage />}
      {view === "controls" && <ControlsPage />}
      {view === "review" && <ReviewPage />}
      {view === "reports" && <ReportsPage />}
      {view === "bundles" && <AuditBundlesPage />}
    </Layout>
  );
}
