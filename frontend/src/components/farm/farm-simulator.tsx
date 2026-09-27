"use client";
import { useState } from "react";
import { useFarm } from "./farm-store";
import type { EventType } from "@/lib/types";
import type { SceneMetrics } from "./farm-scene";

const events: EventType[] = [
  "trade_opened",
  "trade_closed",
  "take_profit_triggered",
  "stop_loss_triggered",
  "opportunity_discovered",
  "opportunity_shortlisted",
  "risk_trade_rejected",
  "ai_analysis_completed",
  "shadow_review_completed",
  "marketplace_opportunity_created",
  "marketplace_listing_imported",
  "marketplace_strong_candidate",
  "marketplace_price_drop",
  "marketplace_duplicate_detected",
  "marketplace_listing_passed",
  "marketplace_item_bought",
  "marketplace_item_sold",
  "marketplace_inventory_aging",
  "marketplace_analysis_updated",
  "price_drop_detected",
  "market_data_stale",
  "market_data_restored",
  "ai_budget_warning",
];
export default function FarmSimulator({
  metrics,
}: {
  metrics: SceneMetrics | null;
}) {
  const farm = useFarm();
  const [target, setTarget] = useState("equities");
  if (process.env.NODE_ENV !== "development") return null;
  const agent = farm.agents.find((a) => a.agent_type === target);
  return (
    <details className="farm-debug">
      <summary>DEVELOPMENT ONLY · Farm Event Simulator</summary>
      <p>
        Local visual rehearsal only. No API writes, trades, balance changes or
        AI calls.
      </p>
      <label>
        Event target{" "}
        <select value={target} onChange={(e) => setTarget(e.target.value)}>
          <option value="equities">Agent A</option>
          <option value="options">Agent B</option>
        </select>
      </label>
      <div>
        {events.map((type) => (
          <button
            key={type}
            disabled={!agent}
            onClick={() =>
              farm.simulate({
                id: crypto.randomUUID(),
                source: agent!.id,
                event_type: type,
                created_at: new Date().toISOString(),
                payload: {
                  agent_id: agent!.id,
                  message: "Development visual rehearsal",
                },
              })
            }
          >
            {type}
          </button>
        ))}
        <button onClick={farm.resetSimulation}>Reset rehearsal</button>
      </div>
      <pre>
        {JSON.stringify(
          {
            states: farm.states,
            lastEvent: farm.lastEvent?.event_type,
            renderer: metrics ? "WebGL ready" : "Starting",
            ...metrics,
          },
          null,
          2,
        )}
      </pre>
    </details>
  );
}
