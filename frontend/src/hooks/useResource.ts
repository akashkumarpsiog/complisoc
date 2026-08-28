import { useCallback, useEffect, useRef, useState } from "react";
import type { Status } from "../types";

export interface ResourceState<T> {
  data: T | null;
  status: Status;
  error: string | null;
  reload: () => Promise<void>;
  setData: (value: T | null) => void;
}

export function useResource<T>(load: () => Promise<T>, deps: unknown[] = []): ResourceState<T> {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const loadingRef = useRef(false);

  const reload = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setStatus("loading");
    setError(null);
    try {
      setData(await load());
      setStatus("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
      setStatus("error");
    } finally {
      loadingRef.current = false;
    }
  }, deps);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, status, error, reload, setData };
}
