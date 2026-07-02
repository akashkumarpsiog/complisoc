import type { ReactNode } from "react";
import type { ResourceState } from "../hooks/useResource";
import { EmptyState, ErrorState, LoadingState } from "./Primitives";

export function ResourceBoundary<T>({
  resource,
  emptyLabel = "No data returned.",
  children,
}: {
  resource: Pick<ResourceState<T>, "data" | "status" | "error" | "reload">;
  emptyLabel?: string;
  children: (data: T) => ReactNode;
}) {
  if (resource.status === "idle" || resource.status === "loading") {
    return <LoadingState />;
  }
  if (resource.status === "error") {
    return <ErrorState message={resource.error || "Request failed."} onRetry={resource.reload} />;
  }
  if (resource.data === null) {
    return <EmptyState label={emptyLabel} />;
  }
  return <>{children(resource.data)}</>;
}
