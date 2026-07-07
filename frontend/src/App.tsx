import { useCallback, useState } from "react";
import { api } from "./services/api";
import { useResource } from "./hooks/useResource";
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
  const health = useResource(api.health);
  const readiness = useResource(api.readiness);

  const refreshChrome = useCallback(() => {
    void health.reload();
    void readiness.reload();
  }, [health, readiness]);

  return (
    <Layout
      view={view}
      apiStatus={health.data?.status || health.status}
      dbStatus={readiness.data?.database || readiness.status}
      onViewChange={setView}
      onRefresh={refreshChrome}
    >
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
