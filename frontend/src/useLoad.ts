import { useCallback, useEffect, useRef, useState } from "react";
import { errorText } from "./errors";

type Result<T> = { key: string; version: number; data?: T; error?: string };

// Loads data for `key`. Previous data stays visible while a reload runs,
// and reload() refreshes after a change.
export function useLoad<T>(key: string, loader: () => Promise<T>) {
  const [result, setResult] = useState<Result<T> | null>(null);
  const [version, setVersion] = useState(0);
  const loaderRef = useRef(loader);

  useEffect(() => {
    loaderRef.current = loader;
  });

  useEffect(() => {
    let cancelled = false;
    loaderRef.current().then(
      (data) => {
        if (!cancelled) setResult({ key, version, data });
      },
      (err: unknown) => {
        if (cancelled) return;
        setResult((prev) => ({
          key,
          version,
          data: prev !== null && prev.key === key ? prev.data : undefined,
          error: errorText(err),
        }));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [key, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const current = result !== null && result.key === key ? result : null;
  const fresh = current !== null && current.version === version;
  return {
    data: current?.data,
    error: fresh ? current?.error : undefined,
    loading: !fresh,
    reload,
  };
}
