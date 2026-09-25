// Decimal amounts arrive as strings to preserve backend precision.
export interface Agent {
  id: string;
  name: string;
  agent_type: "equities" | "options";
  starting_balance: string;
  current_balance: string;
  total_return: string;
  total_return_percent: string;
  total_trades: number;
  open_trades: number;
  completed_trades: number;
  status: "idle" | "running" | "paused" | "error";
  created_at: string;
}

export interface Trade {
  id: string;
  agent_id: string;
  asset_type: string;
  symbol: string;
  company_name: string;
  side: string;
  quantity: string;
  entry_price: string;
  stop_loss: string | null;
  take_profit: string | null;
  exit_price: string | null;
  realized_pnl: string | null;
  status: string;
  entry_time: string;
  exit_time: string | null;
  reasoning: string | null;
}

export interface Marketplace {
  status: "not_configured";
  zip_code: string | null;
  radius_miles: number | null;
  opportunities_found: number;
}

export interface AIUsage {
  status: "disabled";
  monthly_budget_usd: string | null;
  amount_used_usd: string | null;
  model_calls: number | null;
}

export interface Health {
  status: "ok" | "degraded";
  backend: "ok";
  database: "ok" | "unavailable";
  redis: "ok" | "unavailable";
}

export type EventType =
  | "heartbeat"
  | "trade_opened"
  | "trade_closed"
  | "marketplace_deal_found"
  | "price_drop_detected"
  | "agent_status_changed"
  | "risk_limit_triggered";

export interface LiveEvent {
  id: string;
  event_type: EventType;
  source: string;
  payload: Record<string, unknown>;
  created_at: string;
}
