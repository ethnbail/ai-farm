import { expect, test } from "@playwright/test";

test("development simulator replays every major event without backend writes", async ({
  page,
  request,
}) => {
  test.skip(
    process.env.FARM_DEV_E2E !== "1",
    "Requires npm run dev and FARM_DEV_E2E=1",
  );
  const before = await (
    await request.get("http://127.0.0.1:8000/api/agents")
  ).json();
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes(":8000/") && !["GET", "HEAD"].includes(r.method()))
      writes.push(r.url());
  });
  await page.goto("/");
  await expect(page.getByTestId("farm-stage")).toHaveAttribute(
    "data-renderer",
    "ready",
    { timeout: 60_000 },
  );
  await page
    .getByText("DEVELOPMENT ONLY · Farm Event Simulator", { exact: true })
    .click();
  for (const target of ["equities", "options"]) {
    await page.getByLabel("Event target").selectOption(target);
    const agent = target === "equities" ? "agentA" : "agentB";
    for (const [event, area, state] of [
      ["trade_opened", agent, "TRADE_ACTIVE"],
      ["trade_closed", agent, "IDLE"],
      ["take_profit_triggered", agent, "SUCCESS"],
      ["stop_loss_triggered", agent, "LOSS"],
      ["opportunity_discovered", agent, "SCANNING"],
      ["opportunity_shortlisted", "research", "ANALYZING"],
      ["risk_trade_rejected", agent, "REJECTED"],
      ["ai_analysis_completed", "research", "ANALYZING"],
      ["shadow_review_completed", "shadow", "ANALYZING"],
      ["marketplace_opportunity_created", "marketplace", "ANALYZING"],
      ["marketplace_listing_imported", "marketplace", "ANALYZING"],
      ["marketplace_strong_candidate", "marketplace", "ANALYZING"],
      ["marketplace_price_drop", "marketplace", "ANALYZING"],
      ["marketplace_analysis_updated", "marketplace", "ANALYZING"],
      ["marketplace_duplicate_detected", "marketplace", "WAITING"],
      ["marketplace_inventory_aging", "marketplace", "WAITING"],
      ["marketplace_listing_passed", "marketplace", "IDLE"],
      ["marketplace_item_bought", "marketplace", "TRADE_ACTIVE"],
      ["marketplace_item_sold", "marketplace", "SUCCESS"],
      ["price_drop_detected", "marketplace", "ANALYZING"],
      ["market_data_stale", agent, "DATA_STALE"],
      ["market_data_restored", agent, "IDLE"],
      ["ai_budget_warning", "research", "WAITING"],
    ]) {
      await page.getByRole("button", { name: event, exact: true }).click();
      await expect(page.getByTestId(`building-${area}`)).toHaveAttribute(
        "data-state",
        state,
      );
    }
    await page
      .getByRole("button", { name: "Reset rehearsal", exact: true })
      .click();
  }
  expect(writes).toEqual([]);
  expect(
    await (await request.get("http://127.0.0.1:8000/api/agents")).json(),
  ).toEqual(before);
});
