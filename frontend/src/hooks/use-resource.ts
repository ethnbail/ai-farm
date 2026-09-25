"use client";

import { useEffect, useState } from "react";
import { getJson } from "@/lib/api";

export function useResource<T>(path: string) {
  const [state, setState] = useState<{ data?: T; error?: string }>({});

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
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
        if (!controller.signal.aborted) timer = setTimeout(load, 15_000);
      }
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [path]);

  return state;
}
