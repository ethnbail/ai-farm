"use client";

import Link from "next/link";
import { Badge, ConnectionNotice, Metric } from "@/components/ui";
import {
  amount,
  MarketBanner,
  Positions,
  rate,
  TradeHistory,
} from "@/components/trading";
import { useResource } from "@/hooks/use-resource";
import { money, percent } from "@/lib/format";
import type { Agent, Performance, Portfolio } from "@/lib/types";

export function AgentDetail({ id }: { id: string }) {
  const agent = useResource<Agent>(`/api/agents/${id}`);
  const account = useResource<Portfolio>(`/api/agents/${id}/portfolio`);
  const metrics = useResource<Performance>(`/api/agents/${id}/performance`);
  const a = agent.data,
    p = account.data,
    m = metrics.data;
  return (
    <>
      <Link href="/" className="text-sm text-green hover:underline">
        ← Back to the farm
      </Link>
      <ConnectionNotice error={agent.error} />
      {!a ? (
        <div className="panel mt-8">
          <h1 className="text-2xl font-semibold">
            {agent.error === "Not found"
              ? "Agent not found"
              : agent.error
                ? "Agent unavailable"
                : "Loading agent…"}
          </h1>
        </div>
      ) : (
        <>
          <div className="my-8 flex items-center justify-between">
            <div>
              <p className="eyebrow">
                {a.agent_type === "equities" ? "Equities / ETFs" : "Options"} ·
                Paper only
              </p>
              <h1 className="mt-3 text-4xl font-semibold">{a.name}</h1>
            </div>
            <Badge active={a.status === "running"}>{a.status}</Badge>
          </div>
          <MarketBanner />
          <section className="panel" aria-label="Agent statistics">
            <ConnectionNotice error={account.error ?? metrics.error} />
            <dl className="grid grid-cols-2 gap-8 md:grid-cols-3 xl:grid-cols-4">
              <Metric
                label="Starting balance"
                value={money(a.starting_balance)}
              />
              <Metric label="Current equity" value={money(a.current_balance)} />
              <Metric label="Cash" value={amount(p?.cash_balance)} />
              <Metric label="Market value" value={amount(p?.market_value)} />
              <Metric
                label="Total return"
                value={`${money(a.total_return)} (${percent(a.total_return_percent)})`}
              />
              <Metric label="Realized P&L" value={amount(p?.realized_pnl)} />
              <Metric
                label="Unrealized P&L"
                value={amount(p?.unrealized_pnl)}
              />
              <Metric label="Win rate" value={rate(m?.win_rate)} />
              <Metric label="Total trades" value={a.total_trades} />
              <Metric label="Open positions" value={a.open_positions} />
              <Metric label="Completed trades" value={a.completed_trades} />
              <Metric
                label="Maximum drawdown"
                value={rate(m?.max_drawdown_percent)}
              />
            </dl>
            <p className="mt-6 text-xs text-muted">
              Valuation: {(p?.valuation_state ?? "unavailable").toUpperCase()}{" "}
              DATA. {m?.statistics_note}
            </p>
          </section>
          <Positions id={id} />
          <TradeHistory id={id} />
          <section
            className="panel mt-5"
            aria-label="Performance and benchmarks"
          >
            <h2 className="text-xl font-semibold">Performance & benchmarks</h2>
            <dl className="mt-5 grid grid-cols-2 gap-6 md:grid-cols-4">
              <Metric
                label="Winners / losers"
                value={m ? `${m.winning_trades} / ${m.losing_trades}` : "N/A"}
              />
              <Metric
                label="Average winner"
                value={amount(m?.average_winner)}
              />
              <Metric label="Average loser" value={amount(m?.average_loser)} />
              <Metric label="Expectancy" value={amount(m?.expectancy)} />
              <Metric label="Profit factor" value={m?.profit_factor ?? "N/A"} />
              <Metric
                label="Current drawdown"
                value={rate(m?.current_drawdown_percent)}
              />
              <Metric label="Best trade" value={amount(m?.best_trade)} />
              <Metric label="Worst trade" value={amount(m?.worst_trade)} />
              <Metric label="Exposure" value={rate(m?.exposure_percent)} />
              <Metric
                label="Average holding time"
                value={
                  m?.average_holding_seconds == null
                    ? "N/A"
                    : `${m.average_holding_seconds.toFixed(0)} seconds`
                }
              />
              <Metric label="Sharpe / Sortino" value="N/A" />
              <Metric
                label={
                  m?.benchmark?.name ??
                  (a.agent_type === "equities"
                    ? "SPY benchmark"
                    : "Options baseline")
                }
                value={rate(m?.benchmark?.total_return_percent)}
              />
            </dl>
            <p className="mt-5 text-xs text-muted">
              Benchmark:{" "}
              {(m?.benchmark?.data_state ?? "unavailable").toUpperCase()} DATA.
              SPY starts at the first observed quote, not an invented price
              history. Sharpe/Sortino need a suitable return series. Fixture
              results are not evidence of profitability.
            </p>
          </section>
        </>
      )}
    </>
  );
}
