"use client";

import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";

export function useResource<T>(path: string) {
  const [state, setState] = useState<{ data?: T; error?: string }>({});

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let loading = false;
    let pending = false;
    async function load() {
      clearTimeout(timer);
      if (loading) {
        pending = true;
        return;
      }
      loading = true;
      try {
        const data = await getJson<T>(path, controller.signal);
        if (!controller.signal.aborted) setState({ data });
      } catch (error) {
        if (!controller.signal.aborted) {
          setState((previous) => ({
            ...previous,
            error:
              error instanceof Error ? error.message : "Connection unavailable",
          }));
        }
      } finally {
        loading = false;
        if (!controller.signal.aborted)
          timer = setTimeout(load, pending ? 100 : 15_000);
        pending = false;
      }
    }
    const refresh = () => {
      clearTimeout(timer);
      timer = setTimeout(load, 100);
    };
    window.addEventListener("ai-farm:update", refresh);
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
      window.removeEventListener("ai-farm:update", refresh);
    };
  }, [path]);

  return state;
}
