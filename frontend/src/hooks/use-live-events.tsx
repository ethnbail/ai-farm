"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import type { LiveEvent } from "@/lib/types";

const LiveContext = createContext({
  status: "Connecting",
  lastHeartbeat: null as string | null,
});
const businessEvents = [
  "trade_opened",
  "trade_closed",
  "stop_loss_triggered",
  "take_profit_triggered",
  "portfolio_updated",
  "agent_status_changed",
  "risk_trade_rejected",
  "position_reduced",
  "market_regime_changed",
  "opportunity_discovered",
  "opportunity_shortlisted",
  "ai_analysis_completed",
  "ai_budget_warning",
  "shadow_review_completed",
  "market_data_stale",
  "market_data_restored",
  "marketplace_opportunity_created",
];

// One connection across route transitions. EventSource resumes business events by ID.
export function LiveEventsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [status, setStatus] = useState("Connecting");
  const [lastHeartbeat, setLastHeartbeat] = useState<string | null>(null);
  useEffect(() => {
    const source = new EventSource(`${API_URL}/api/events`);
    let receivedAt = Date.now();
    source.addEventListener("heartbeat", (message: MessageEvent<string>) => {
      try {
        const event = JSON.parse(message.data) as LiveEvent;
        if (event.event_type !== "heartbeat" || !event.created_at) return;
        receivedAt = Date.now();
        setLastHeartbeat(event.created_at);
        setStatus("Live");
      } catch {
        setStatus("Invalid event");
      }
    });
    const refresh = () => window.dispatchEvent(new Event("ai-farm:update"));
    for (const event of businessEvents) source.addEventListener(event, refresh);
    source.onerror = () => setStatus("Reconnecting");
    const timer = setInterval(() => {
      if (Date.now() - receivedAt > 90_000) setStatus("Waiting for heartbeat");
    }, 5_000);
    return () => {
      source.close();
      clearInterval(timer);
    };
  }, []);
  return (
    <LiveContext.Provider value={{ status, lastHeartbeat }}>
      {children}
    </LiveContext.Provider>
  );
}

export function useLiveEvents() {
  return useContext(LiveContext);
}
