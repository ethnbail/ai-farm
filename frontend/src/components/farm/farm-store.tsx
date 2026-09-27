"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { getJson } from "@/lib/api";
import { useLiveEvents } from "@/hooks/use-live-events";
import type { Agent, Health, LiveEvent, MarketStatus } from "@/lib/types";
import {
  areas,
  baseAgentState,
  expire,
  transition,
  type Area,
  type FarmState,
  type Motions,
} from "@/lib/farm-state";

export interface Listing {
  status?: string;
  active?: boolean;
  id: string;
  title: string;
  source: string;
  details: Record<string, unknown>;
  analyses: { analysis: Record<string, unknown> }[];
}
export interface Usage {
  enabled: boolean;
  daily_spend: string;
  monthly_spend: string;
  daily_remaining: string;
  monthly_remaining: string;
  monthly_budget?: string | null;
  calls: number;
}
export interface Regime {
  regime: string;
  data_mode: string;
  data_timestamp: string | null;
}
type Cache = Record<string, { data?: unknown; error?: string }>;
const routes = [
  "/api/agents",
  "/health",
  "/api/market/status",
  "/api/market/regime",
  "/api/ai/usage",
  "/api/research?latest_scan=true&limit=6",
  "/api/marketplace/opportunities?limit=100",
  "/api/watchlists",
  "/api/activity?limit=8",
  "/api/marketplace/inventory",
];

function useFarmStore() {
  const live = useLiveEvents();
  const [cache, setCache] = useState<Cache>({});
  const cacheRef = useRef(cache);
  const [motions, setMotions] = useState<Motions>({});
  const [lastEvent, setLastEvent] = useState<LiveEvent | null>(null);
  const [simulating, setSimulating] = useState(false);
  useEffect(() => {
    cacheRef.current = cache;
  }, [cache]);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let loading = false,
      pending = false;
    async function load() {
      clearTimeout(timer);
      if (loading) {
        pending = true;
        return;
      }
      loading = true;
      const batch: Cache = {};
      const read = async (path: string) => {
        try {
          batch[path] = { data: await getJson(path, controller.signal) };
        } catch {
          batch[path] = {
            ...cacheRef.current[path],
            error: "Unavailable — last known data only",
          };
        }
      };
      await Promise.all(routes.map(read));
      const agents = batch["/api/agents"]?.data as Agent[] | undefined;
      await Promise.all(
        (agents ?? []).flatMap((a) =>
          ["portfolio", "positions", "performance", "intelligence"].map(
            (section) => read(`/api/agents/${a.id}/${section}`),
          ),
        ),
      );
      if (!controller.signal.aborted) {
        setCache((previous) => ({ ...previous, ...batch }));
        timer = setTimeout(load, pending ? 100 : 15_000);
      }
      loading = false;
      pending = false;
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
  }, []);
  const dispatch = useCallback((event: LiveEvent, simulated = false) => {
    const agents = cacheRef.current["/api/agents"]?.data as Agent[] | undefined;
    setLastEvent(event);
    setSimulating(simulated);
    setMotions((previous) =>
      transition(previous, event, agents ?? [], Date.now(), simulated),
    );
  }, []);
  useEffect(() => {
    const listener = (e: Event) =>
      dispatch((e as CustomEvent<LiveEvent>).detail);
    window.addEventListener("ai-farm:event", listener);
    const timer = setInterval(
      () =>
        setMotions((previous) =>
          Object.keys(previous).length
            ? expire(previous, Date.now())
            : previous,
        ),
      1000,
    );
    return () => {
      window.removeEventListener("ai-farm:event", listener);
      clearInterval(timer);
    };
  }, [dispatch]);
  function get<T>(path: string): T | undefined {
    return cache[path]?.data as T | undefined;
  }
  const agents = get<Agent[]>("/api/agents") ?? [];
  const health = cache["/health"]?.error ? undefined : get<Health>("/health");
  const usage = get<Usage>("/api/ai/usage");
  const market = cache["/api/market/status"]?.error
    ? undefined
    : get<MarketStatus>("/api/market/status");
  const online =
    !cache["/health"]?.error &&
    !cache["/api/agents"]?.error &&
    health?.database === "ok" &&
    live.status === "Live";
  const states = Object.fromEntries(
    areas.map((area) => [area, "IDLE"]),
  ) as Record<Area, FarmState>;
  states.agentA = baseAgentState(
    agents.find((a) => a.agent_type === "equities"),
    online,
    market?.data_state ?? "unavailable",
  );
  states.agentB = baseAgentState(
    agents.find((a) => a.agent_type === "options"),
    online,
    market?.data_state ?? "unavailable",
  );
  states.treasury = online && health?.redis === "ok" ? "IDLE" : "OFFLINE";
  states.analytics = health?.redis === "ok" ? "IDLE" : "WAITING";
  states.research = cache["/api/research?latest_scan=true&limit=6"]?.error
    ? "OFFLINE"
    : usage?.enabled &&
        (Number(usage.daily_remaining) <= 0 ||
          (usage.monthly_budget != null &&
            Number(usage.monthly_remaining) <= 0))
      ? "WAITING"
      : "IDLE";
  states.marketplace = cache["/api/marketplace/opportunities?limit=100"]?.error
    ? "OFFLINE"
    : "IDLE";
  for (const area of areas)
    if (motions[area] && (online || motions[area]?.simulated))
      states[area] = motions[area]!.state;
  return {
    get,
    cache,
    agents,
    health,
    market,
    live,
    states,
    motions,
    lastEvent,
    simulating,
    simulate: (event: LiveEvent) => {
      if (process.env.NODE_ENV === "development") dispatch(event, true);
    },
    resetSimulation: () => {
      setMotions({});
      setSimulating(false);
    },
  };
}

const FarmContext = createContext<ReturnType<typeof useFarmStore> | null>(null);
export function FarmProvider({ children }: { children: React.ReactNode }) {
  const store = useFarmStore();
  return <FarmContext.Provider value={store}>{children}</FarmContext.Provider>;
}
export function useFarm() {
  const store = useContext(FarmContext);
  if (!store) throw new Error("FarmProvider is required");
  return store;
}
