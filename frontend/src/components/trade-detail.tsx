"use client";

import Link from "next/link";
import { Badge, ConnectionNotice, Metric } from "@/components/ui";
import {
  amount,
  DataTable,
  MarketBanner,
  price,
  rate,
  timestamp,
} from "@/components/trading";
import { useResource } from "@/hooks/use-resource";
import type { TradeDetailData } from "@/lib/types";

function Snapshot({ value }: { value: Record<string, unknown> | null }) {
  if (!value)
    return (
      <p className="mt-4 text-muted">No recorded snapshot (legacy trade).</p>
    );
  return (
    <dl className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Object.entries(value).map(([key, item]) => (
        <div key={key} className="min-w-0">
          <dt className="text-xs uppercase tracking-wide text-muted">
            {key.replaceAll("_", " ")}
          </dt>
          <dd className="mt-1 break-words text-sm">
            {item == null
              ? "N/A"
              : typeof item === "object"
                ? JSON.stringify(item)
                : String(item)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function TradeDetail({ id }: { id: string }) {
  const { data: t, error } = useResource<TradeDetailData>(`/api/trades/${id}`);
  return (
    <>
      <Link
        href={t ? `/agents/${t.agent_id}` : "/"}
        className="text-sm text-green hover:underline"
      >
        ← Back to agent
      </Link>
      <ConnectionNotice error={error} />
      {!t ? (
        <h1 className="my-8 text-3xl">
          {error === "Not found"
            ? "Trade not found"
            : error
              ? "Trade unavailable"
              : "Loading trade…"}
        </h1>
      ) : (
        <>
          <div className="my-8 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="eyebrow">
                {t.company_name} · {t.asset_type}
              </p>
              <h1 className="mt-3 break-all text-3xl font-semibold">
                {t.symbol}
              </h1>
            </div>
            <Badge>{t.status}</Badge>
          </div>
          <MarketBanner />
          <section className="panel" aria-label="Trade details">
            <h2 className="text-xl font-semibold">Trade details</h2>
            <dl className="mt-5 grid grid-cols-2 gap-6 md:grid-cols-4">
              <Metric
                label="Side / quantity"
                value={`${t.side} / ${t.quantity}`}
              />
              <Metric
                label="Requested price"
                value={price(t.requested_price)}
              />
              <Metric label="Entry fill" value={price(t.entry_price)} />
              <Metric label="Exit fill" value={price(t.exit_price)} />
              <Metric label="Stop loss" value={price(t.stop_loss)} />
              <Metric label="Take profit" value={price(t.take_profit)} />
              <Metric label="Realized P&L" value={amount(t.realized_pnl)} />
              <Metric
                label="Realized return"
                value={rate(t.realized_return_percent)}
              />
              <Metric label="Position size" value={amount(t.position_size)} />
              <Metric
                label="Equity at entry"
                value={amount(t.account_equity_at_entry)}
              />
              <Metric label="Allocation" value={rate(t.percent_allocated)} />
              <Metric
                label="Maximum planned loss"
                value={amount(t.maximum_planned_loss)}
              />
            </dl>
            <p className="mt-6 text-sm">
              Strategy: {t.strategy_name ?? "N/A"} · Version{" "}
              {t.strategy_version ?? "N/A"}
            </p>
            <p className="mt-2 text-sm">
              Reasoning: {t.reasoning ?? "Not recorded"}
            </p>
            <p className="mt-2 text-sm">
              Outcome:{" "}
              {t.exit_reason?.replaceAll("_", " ") ?? "Position still open"}
            </p>
            <p className="mt-2 text-sm">
              Recorded data mode:{" "}
              {(t.market_data_mode ?? "unavailable").toUpperCase()} DATA
            </p>
            <p className="mt-2 text-xs text-muted">
              Entered {timestamp(t.entry_time)} · Exited{" "}
              {timestamp(t.exit_time)} · Quote {timestamp(t.data_timestamp)}
            </p>
          </section>
          <section className="panel mt-5" aria-label="Risk calculation">
            <h2 className="text-xl font-semibold">Risk calculation</h2>
            <Snapshot value={t.risk_calculation} />
          </section>
          <section className="panel mt-5" aria-label="Trade Replay">
            <h2 className="text-xl font-semibold">Trade Replay</h2>
            <p className="mt-3 text-sm text-muted">
              Immutable entry snapshot and event timeline. Historical chart
              replay is not implemented. Options IV and Greeks below are
              recorded entry values, not recalculated estimates.
            </p>
            <Snapshot value={t.entry_snapshot} />
            <h3 className="mt-8 font-semibold">Simulated fills</h3>
            {!t.fills.length ? (
              <p className="mt-3 text-muted">
                No fills recorded for this legacy trade.
              </p>
            ) : (
              <DataTable
                label="Recorded fills"
                headers={[
                  "Time",
                  "Action",
                  "Quantity",
                  "Requested",
                  "Fill",
                  "Notional",
                  "Bid / ask",
                  "Slippage",
                  "Data",
                ]}
              >
                {t.fills.map((f) => (
                  <tr key={f.id}>
                    <td className="p-3 whitespace-nowrap">
                      {timestamp(f.timestamp)}
                    </td>
                    <td className="p-3">{f.action}</td>
                    <td className="p-3">{f.quantity}</td>
                    <td className="p-3">{price(f.requested_price)}</td>
                    <td className="p-3">{price(f.price)}</td>
                    <td className="p-3">{amount(f.notional)}</td>
                    <td className="p-3 whitespace-nowrap">
                      {price(f.bid)} / {price(f.ask)}
                    </td>
                    <td className="p-3">{amount(f.estimated_slippage)}</td>
                    <td className="p-3">
                      {f.market_data_mode.toUpperCase()}
                      <span className="block text-xs">
                        {timestamp(f.data_timestamp)}
                      </span>
                    </td>
                  </tr>
                ))}
              </DataTable>
            )}
            <h3 className="mt-8 font-semibold">Timeline</h3>
            <ol className="mt-4 space-y-3">
              {t.timeline.map((event) => (
                <li
                  key={event.id}
                  className="border-l-2 border-line pl-4 text-sm"
                >
                  <strong>{event.event_type.replaceAll("_", " ")}</strong>
                  <p>{String(event.payload.message ?? "")}</p>
                  <time className="text-xs text-muted">
                    {timestamp(event.created_at)}
                  </time>
                </li>
              ))}
            </ol>
            {!t.timeline.length && (
              <p className="mt-3 text-muted">No recorded events.</p>
            )}
          </section>
        </>
      )}
    </>
  );
}
