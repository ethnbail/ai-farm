"use client";

import Link from "next/link";
import { Badge, ConnectionNotice, Icon, Metric } from "@/components/ui";
import { useResource } from "@/hooks/use-resource";
import { money, percent } from "@/lib/format";
import type { Agent, Trade } from "@/lib/types";

export function AgentDetail({ id }: { id: string }) {
  const agent = useResource<Agent>(`/api/agents/${id}`);
  const trades = useResource<Trade[]>(`/api/agents/${id}/trades`);
  return (
    <>
      <Link href="/" className="text-sm text-green hover:underline">
        ← Back to the farm
      </Link>
      <ConnectionNotice error={agent.error} />
      {!agent.data ? (
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
                {agent.data.agent_type === "equities"
                  ? "Equities / ETFs"
                  : "Options"}{" "}
                · Paper only
              </p>
              <h1 className="mt-3 text-4xl font-semibold">{agent.data.name}</h1>
            </div>
            <Badge active={agent.data.status === "running"}>
              {agent.data.status}
            </Badge>
          </div>
          <section className="panel" aria-label="Agent statistics">
            <dl className="grid grid-cols-2 gap-8 md:grid-cols-3">
              <Metric
                label="Starting balance"
                value={money(agent.data.starting_balance)}
              />
              <Metric
                label="Current balance"
                value={money(agent.data.current_balance)}
              />
              <Metric
                label="Total return"
                value={`${money(agent.data.total_return)} (${percent(agent.data.total_return_percent)})`}
              />
              <Metric label="Total trades" value={agent.data.total_trades} />
              <Metric label="Open trades" value={agent.data.open_trades} />
              <Metric
                label="Completed trades"
                value={agent.data.completed_trades}
              />
            </dl>
          </section>
          <section className="panel mt-5" aria-labelledby="trade-history">
            <h2 id="trade-history" className="text-xl font-semibold">
              Trade history
            </h2>
            <ConnectionNotice error={trades.error} />
            {!trades.data && !trades.error && (
              <p className="py-8 text-muted">Loading trade history…</p>
            )}
            {trades.data?.length === 0 && (
              <div className="flex flex-col items-center py-16 text-center">
                <span className="icon-tile">
                  <Icon kind="sprout" />
                </span>
                <h3 className="mt-5 text-xl font-medium">No trades yet</h3>
                <p className="mt-2 max-w-md text-sm leading-6 text-muted">
                  This agent is resting. When paper trading is introduced, its
                  positions and reasoning will appear here.
                </p>
              </div>
            )}
            {!!trades.data?.length && (
              <div className="mt-6 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="mb-4 text-left text-muted">
                    Most recent 50 trades. Trade replay is planned for a later
                    phase.
                  </caption>
                  <thead>
                    <tr>
                      {[
                        "Company / ticker",
                        "Entry",
                        "Quantity",
                        "Stop loss",
                        "Target",
                        "Exit",
                        "P/L",
                        "Status",
                        "Reasoning",
                      ].map((label) => (
                        <th
                          key={label}
                          className="whitespace-nowrap border-b border-line p-3 font-medium"
                        >
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {trades.data.map((trade) => (
                      <tr key={trade.id}>
                        <td className="p-3">
                          {trade.company_name}
                          <span className="block text-muted">
                            {trade.symbol}
                          </span>
                        </td>
                        <td className="p-3">{money(trade.entry_price)}</td>
                        <td className="p-3">{trade.quantity}</td>
                        <td className="p-3">{money(trade.stop_loss)}</td>
                        <td className="p-3">{money(trade.take_profit)}</td>
                        <td className="p-3">{money(trade.exit_price)}</td>
                        <td className="p-3">{money(trade.realized_pnl)}</td>
                        <td className="p-3">{trade.status}</td>
                        <td className="p-3">{trade.reasoning ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}
