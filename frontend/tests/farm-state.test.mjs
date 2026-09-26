import test from "node:test";
import assert from "node:assert/strict";
import {
  transition,
  expire,
  parseEvent,
  baseAgentState,
} from "../src/lib/farm-state.ts";

const agents = [
  {
    id: "a",
    agent_type: "equities",
    status: "idle",
    open_positions: 0,
    valuation_state: "unavailable",
  },
  {
    id: "b",
    agent_type: "options",
    status: "idle",
    open_positions: 1,
    valuation_state: "mock",
  },
];
const now = Date.parse("2026-09-26T12:00:00Z");
const event = (type, source = "a", changes = {}) => ({
  id: "event-1",
  event_type: type,
  source,
  payload: {},
  created_at: new Date(now).toISOString(),
  ...changes,
});

for (const [type, area, state] of [
  ["trade_opened", "agentA", "TRADE_ACTIVE"],
  ["trade_closed", "agentA", "IDLE"],
  ["take_profit_triggered", "agentA", "SUCCESS"],
  ["stop_loss_triggered", "agentA", "LOSS"],
  ["risk_trade_rejected", "agentA", "REJECTED"],
  ["opportunity_discovered", "agentA", "SCANNING"],
  ["opportunity_shortlisted", "research", "ANALYZING"],
  ["ai_analysis_completed", "research", "ANALYZING"],
  ["shadow_review_completed", "shadow", "ANALYZING"],
  ["marketplace_opportunity_created", "marketplace", "ANALYZING"],
  ["price_drop_detected", "marketplace", "ANALYZING"],
  ["market_data_stale", "agentA", "DATA_STALE"],
  ["ai_budget_warning", "research", "WAITING"],
])
  test(`${type} -> ${area} ${state}`, () => {
    const result = transition({}, event(type), agents, now);
    assert.equal(result[area].state, state);
    assert.deepEqual(expire(result, now + 30_000), {});
  });
test("Agent B is independently targeted", () => {
  const result = transition({}, event("trade_opened", "b"), agents, now);
  assert.equal(result.agentB.state, "TRADE_ACTIVE");
  assert.equal(result.agentA, undefined);
});
test("restoration removes stale override; data remains final baseline", () => {
  const stale = transition(
    {},
    event("market_data_stale", "market_data"),
    agents,
    now,
  );
  assert.equal(stale.agentB.state, "DATA_STALE");
  assert.deepEqual(
    transition(
      stale,
      event("market_data_restored", "market_data"),
      agents,
      now,
    ),
    {},
  );
  assert.equal(baseAgentState(agents[1], true, "stale"), "DATA_STALE");
  assert.equal(baseAgentState(agents[1], true, "mock"), "TRADE_ACTIVE");
});
test("completion cannot mask success or stop-loss reaction", () => {
  for (const type of ["take_profit_triggered", "stop_loss_triggered"]) {
    const first = transition({}, event(type), agents, now);
    assert.deepEqual(
      transition(first, event("trade_closed"), agents, now + 1),
      first,
    );
  }
});
test("old replays and future timestamps do not trigger animation", () => {
  for (const stamp of [now - 61_000, now + 10_000])
    assert.deepEqual(
      transition(
        {},
        event("trade_opened", "a", {
          created_at: new Date(stamp).toISOString(),
        }),
        agents,
        now,
      ),
      {},
    );
});
test("disabled, paused, offline and no-data states are truthful", () => {
  assert.equal(baseAgentState(agents[0], true, "mock"), "IDLE");
  assert.equal(
    baseAgentState({ ...agents[0], status: "paused" }, true, "mock"),
    "WAITING",
  );
  assert.equal(baseAgentState(undefined, true), "OFFLINE");
  assert.equal(baseAgentState(agents[1], false), "OFFLINE");
});
test("normalization rejects malformed and unknown events", () => {
  for (const raw of [
    "broken",
    "null",
    JSON.stringify(event("unknown")),
    JSON.stringify(event("trade_opened", "a", { payload: [] })),
    "x".repeat(100001),
  ])
    assert.equal(parseEvent(raw), null);
  assert.equal(
    parseEvent(JSON.stringify(event("trade_opened"))).event_type,
    "trade_opened",
  );
});
test("unrelated events and missing agent IDs do not invent activity", () => {
  assert.deepEqual(transition({}, event("portfolio_updated"), agents, now), {});
  assert.deepEqual(
    transition({}, event("trade_opened", "unknown"), agents, now),
    {},
  );
});
