import { useCallback, useEffect, useRef, useState } from "react";
import type { Status } from "../types";

export interface ResourceState<T> {
  data: T | null;
  status: Status;
  error: string | null;
  reload: (quiet?: boolean) => Promise<void>;
  setData: (value: T | null) => void;
}

export function useResource<T>(load: () => Promise<T>, deps: unknown[] = []): ResourceState<T> {
  const [data, setData] = useState<T | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const loadingRef = useRef(false);

  const reload = useCallback(async (quiet = false) => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    if (!quiet) {
      setStatus("loading");
      setError(null);
    }
    try {
      setData(await load());
      setStatus("success");
    } catch (err) {
      if (!quiet) {
        setError(err instanceof Error ? err.message : "Request failed.");
        setStatus("error");
      }
    } finally {
      loadingRef.current = false;
    }
  }, deps);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, status, error, reload, setData };
}
