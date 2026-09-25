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
  open_positions: number;
  valuation_state: string;
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
  realized_return_percent: string | null;
  exit_reason: string | null;
  strategy_name: string | null;
  strategy_version: string | null;
  market_data_mode: string | null;
  data_timestamp: string | null;
  requested_price: string | null;
  fill_price: string | null;
  position_size: string | null;
  account_equity_at_entry: string | null;
  percent_allocated: string | null;
  maximum_planned_loss: string | null;
  entry_snapshot: Record<string, unknown> | null;
  risk_calculation: Record<string, unknown> | null;
}

export interface Position {
  id: string;
  trade_id: string;
  asset_type: string;
  company_name: string;
  symbol: string;
  quantity: number;
  average_entry_price: string;
  current_price: string;
  market_value: string;
  unrealized_pnl: string;
  return_percent: string;
  stop_loss: string;
  take_profit: string;
  opened_at: string;
  data_state: string;
  underlying_symbol: string | null;
  option_type: string | null;
  strike: string | null;
  expiration: string | null;
  dte: number | null;
  entry_iv: string | null;
  entry_delta: string | null;
  entry_gamma: string | null;
  entry_theta: string | null;
  entry_vega: string | null;
  bid: string | null;
  ask: string | null;
  data_timestamp: string | null;
}

export interface Portfolio {
  cash_balance: string;
  equity: string;
  market_value: string;
  realized_pnl: string;
  unrealized_pnl: string;
  valuation_state: string;
  updated_at: string;
}

export interface Performance {
  win_rate: string | null;
  max_drawdown_percent: string;
  current_drawdown_percent: string;
  winning_trades: number;
  losing_trades: number;
  average_winner: string | null;
  average_loser: string | null;
  expectancy: string | null;
  profit_factor: string | null;
  best_trade: string | null;
  worst_trade: string | null;
  exposure_percent: string;
  average_holding_seconds: number | null;
  sharpe: string | null;
  sortino: string | null;
  statistics_note: string | null;
  benchmark: {
    name: string;
    data_state: string;
    total_return_percent: string | null;
  } | null;
}

export interface MarketStatus {
  trading_mode: string;
  session: string;
  data_state: string;
  provider: string;
  execution_enabled: boolean;
  data_timestamp: string | null;
}

export interface Fill {
  id: string;
  action: string;
  quantity: number;
  requested_price: string | null;
  price: string;
  notional: string;
  estimated_slippage: string;
  bid: string;
  ask: string;
  timestamp: string;
  data_timestamp: string;
  market_data_mode: string;
}
export interface TradeDetailData extends Trade {
  fills: Fill[];
  timeline: LiveEvent[];
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
  | "risk_limit_triggered"
  | "risk_trade_rejected"
  | "portfolio_updated"
  | "stop_loss_triggered"
  | "take_profit_triggered"
  | "position_reduced";

export interface LiveEvent {
  id: string;
  event_type: EventType;
  source: string;
  payload: Record<string, unknown>;
  created_at: string;
}
