import type { Agent, LiveEvent } from "./types";

export const areas = [
  "agentA",
  "agentB",
  "marketplace",
  "research",
  "shadow",
  "treasury",
  "analytics",
] as const;
export type Area = (typeof areas)[number];
export type FarmState =
  | "IDLE"
  | "SCANNING"
  | "ANALYZING"
  | "WAITING"
  | "TRADE_ACTIVE"
  | "SUCCESS"
  | "LOSS"
  | "REJECTED"
  | "DATA_STALE"
  | "OFFLINE";
export const buildings: Record<
  Area,
  {
    name: string;
    subtitle: string;
    position: [number, number, number];
    color: string;
  }
> = {
  agentA: {
    name: "Agent A",
    subtitle: "Equity barn",
    position: [-6, 0, 2],
    color: "#ae6650",
  },
  agentB: {
    name: "Agent B",
    subtitle: "Options observatory",
    position: [5, 0, -3.5],
    color: "#647f79",
  },
  marketplace: {
    name: "Marketplace",
    subtitle: "Trading post",
    position: [6, 0, 4.5],
    color: "#c79953",
  },
  research: {
    name: "Research",
    subtitle: "The reading room",
    position: [-4.5, 0, -5],
    color: "#839365",
  },
  shadow: {
    name: "Shadow",
    subtitle: "Review perch",
    position: [-9, 0, -2.8],
    color: "#657080",
  },
  treasury: {
    name: "Treasury",
    subtitle: "Paper accounts & health",
    position: [0, 0, 0],
    color: "#e1c7a0",
  },
  analytics: {
    name: "Analytics",
    subtitle: "Signal windmill",
    position: [0.3, 0, -7],
    color: "#9e9474",
  },
};
export const eventTypes = [
  "heartbeat",
  "trade_opened",
  "trade_closed",
  "take_profit_triggered",
  "stop_loss_triggered",
  "opportunity_discovered",
  "opportunity_shortlisted",
  "ai_analysis_completed",
  "shadow_review_completed",
  "risk_trade_rejected",
  "risk_limit_triggered",
  "portfolio_updated",
  "position_reduced",
  "agent_status_changed",
  "marketplace_opportunity_created",
  "marketplace_deal_found",
  "price_drop_detected",
  "market_data_stale",
  "market_data_restored",
  "ai_budget_warning",
  "market_regime_changed",
];

export function parseEvent(raw: string): LiveEvent | null {
  if (raw.length > 100_000) return null;
  try {
    const e = JSON.parse(raw);
    if (
      !e ||
      typeof e.id !== "string" ||
      typeof e.source !== "string" ||
      !eventTypes.includes(e.event_type) ||
      typeof e.created_at !== "string" ||
      !Number.isFinite(Date.parse(e.created_at)) ||
      !e.payload ||
      typeof e.payload !== "object" ||
      Array.isArray(e.payload)
    )
      return null;
    return e as LiveEvent;
  } catch {
    return null;
  }
}

export interface Motion {
  state: FarmState;
  started: number;
  until: number;
  event: string;
  simulated: boolean;
  target?: Area;
}
export type Motions = Partial<Record<Area, Motion>>;

export function agentArea(event: LiveEvent, agents: Agent[]): Area | null {
  const a = agents.find(
    (a) => a.id === event.source || a.id === event.payload.agent_id,
  );
  return a ? (a.agent_type === "equities" ? "agentA" : "agentB") : null;
}

// Pure, bounded transitions. No prices, orders, network calls or random decisions.
export function transition(
  previous: Motions,
  event: LiveEvent,
  agents: Agent[],
  now: number,
  simulated = false,
): Motions {
  if (
    !simulated &&
    (now - Date.parse(event.created_at) > 60_000 ||
      Date.parse(event.created_at) - now > 5_000)
  )
    return previous;
  const next = { ...previous };
  const target = agentArea(event, agents);
  const set = (area: Area, state: FarmState, duration = 6500) => {
    const old = previous[area];
    if (
      event.event_type === "trade_closed" &&
      old &&
      old.until > now &&
      ["SUCCESS", "LOSS"].includes(old.state)
    )
      return;
    next[area] = {
      state,
      started: now,
      until: now + duration,
      event: event.event_type,
      simulated,
      target: target ?? undefined,
    };
  };
  switch (event.event_type) {
    case "trade_opened":
      if (target) set(target, "TRADE_ACTIVE");
      break;
    case "trade_closed":
      if (target) set(target, "IDLE");
      break;
    case "take_profit_triggered":
      if (target) set(target, "SUCCESS");
      break;
    case "stop_loss_triggered":
      if (target) set(target, "LOSS");
      break;
    case "risk_trade_rejected":
    case "risk_limit_triggered":
      if (target) set(target, "REJECTED");
      break;
    case "opportunity_discovered":
      if (target) set(target, "SCANNING");
      set("research", "SCANNING");
      break;
    case "opportunity_shortlisted":
      set("research", "ANALYZING");
      if (target) set(target, "WAITING");
      break;
    case "ai_analysis_completed":
      set("research", "ANALYZING");
      break;
    case "shadow_review_completed":
      set("shadow", "ANALYZING", 8500);
      break;
    case "marketplace_opportunity_created":
    case "marketplace_deal_found":
    case "price_drop_detected":
      set("marketplace", "ANALYZING");
      break;
    case "market_data_stale":
      for (const area of target
        ? [target]
        : (["agentA", "agentB", "research"] as Area[]))
        set(area, "DATA_STALE", 20_000);
      break;
    case "market_data_restored":
      for (const area of target
        ? [target]
        : (["agentA", "agentB", "research"] as Area[]))
        delete next[area];
      break;
    case "ai_budget_warning":
      set("research", "WAITING", 12_000);
      break;
  }
  return next;
}

export function expire(motions: Motions, now: number): Motions {
  return Object.fromEntries(
    Object.entries(motions).filter(([, m]) => m.until > now),
  );
}

export function baseAgentState(
  agent: Agent | undefined,
  online: boolean,
  marketState?: string,
): FarmState {
  if (!online || !agent || agent.status === "error") return "OFFLINE";
  if (
    marketState === "stale" ||
    marketState === "unavailable" ||
    (agent.open_positions > 0 &&
      ["stale", "unavailable"].includes(agent.valuation_state))
  )
    return "DATA_STALE";
  if (agent.open_positions > 0) return "TRADE_ACTIVE";
  if (agent.status === "running") return "SCANNING";
  return agent.status === "paused" ? "WAITING" : "IDLE";
}
