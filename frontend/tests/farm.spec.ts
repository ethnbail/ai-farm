import { expect, test, type Page } from "@playwright/test";

async function eventTransport(page: Page) {
  await page.addInitScript(() => {
    const state = window as unknown as {
      farmSources: EventTarget[];
      activeStreams: number;
      peakStreams: number;
    };
    state.farmSources = [];
    state.activeStreams = 0;
    state.peakStreams = 0;
    class Source extends EventTarget {
      timer: ReturnType<typeof setInterval>;
      onerror = null;
      constructor() {
        super();
        state.farmSources.push(this);
        state.activeStreams++;
        state.peakStreams = Math.max(state.peakStreams, state.activeStreams);
        const heartbeat = () =>
          this.dispatchEvent(
            new MessageEvent("heartbeat", {
              data: JSON.stringify({
                id: "heartbeat",
                event_type: "heartbeat",
                source: "backend",
                payload: { status: "alive" },
                created_at: new Date().toISOString(),
              }),
            }),
          );
        this.timer = setInterval(heartbeat, 200);
      }
      close() {
        clearInterval(this.timer);
        state.activeStreams--;
      }
    }
    window.EventSource = Source as unknown as typeof EventSource;
  });
}
async function send(
  page: Page,
  type: string,
  source: string,
  id = crypto.randomUUID(),
) {
  await page.evaluate(
    ({ type, source, id }) => {
      const state = window as unknown as { farmSources: EventTarget[] };
      state.farmSources.at(-1)!.dispatchEvent(
        new MessageEvent(type, {
          data: JSON.stringify({
            id,
            event_type: type,
            source,
            payload: { agent_id: source },
            created_at: new Date().toISOString(),
          }),
        }),
      );
    },
    { type, source, id },
  );
}

test("3D farm renders with real backend, paper label, clickable buildings and unchanged balances", async ({
  page,
  request,
}) => {
  const before = await (
    await request.get("http://127.0.0.1:8000/api/agents")
  ).json();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByTestId("farm-stage")).toHaveAttribute(
    "data-renderer",
    "ready",
    { timeout: 30_000 },
  );
  await expect(
    page.getByText("Simulated accounts only · No real money"),
  ).toBeVisible();
  await expect(page.getByTestId("realtime-status")).toHaveText("Live");
  await expect(
    page
      .getByRole("navigation", { name: "Farm buildings" })
      .getByRole("button"),
  ).toHaveCount(7);
  await page
    .getByRole("button", { name: "Focus Agent A", exact: true })
    .click();
  await expect(
    page.getByRole("complementary", { name: "Agent A details" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open full Agent A detail" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close building details" }).click();
  await page.getByRole("button", { name: "Reset camera" }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(1500); // Let the smooth overview camera settle for the artifact.
  await page.screenshot({
    path: test.info().outputPath("farm-desktop.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
  expect(
    await (await request.get("http://127.0.0.1:8000/api/agents")).json(),
  ).toEqual(before);
});

test("one event dispatcher drives both agents, Shadow, packages, stale/restore and does not write", async ({
  page,
  request,
}) => {
  await eventTransport(page);
  const agents = (await (
    await request.get("http://127.0.0.1:8000/api/agents")
  ).json()) as { id: string; agent_type: string }[];
  const writes: string[] = [];
  page.on("request", (r) => {
    if (!["GET", "HEAD"].includes(r.method())) writes.push(r.url());
  });
  await page.goto("/");
  await expect(page.getByTestId("building-agentA")).toHaveAttribute(
    "data-state",
    "IDLE",
  );
  const a = agents.find((a) => a.agent_type === "equities")!.id,
    b = agents.find((a) => a.agent_type === "options")!.id;
  for (const [type, source, area, state] of [
    ["trade_opened", a, "agentA", "TRADE_ACTIVE"],
    ["trade_opened", b, "agentB", "TRADE_ACTIVE"],
    ["take_profit_triggered", a, "agentA", "SUCCESS"],
    ["stop_loss_triggered", b, "agentB", "LOSS"],
    ["risk_trade_rejected", a, "agentA", "REJECTED"],
    ["ai_analysis_completed", a, "research", "ANALYZING"],
    ["shadow_review_completed", a, "shadow", "ANALYZING"],
    [
      "marketplace_opportunity_created",
      "marketplace",
      "marketplace",
      "ANALYZING",
    ],
    ["market_data_stale", "market_data", "agentA", "DATA_STALE"],
  ]) {
    await send(page, type, source);
    await expect(page.getByTestId(`building-${area}`)).toHaveAttribute(
      "data-state",
      state,
    );
  }
  await send(page, "market_data_restored", "market_data");
  await expect(page.getByTestId("building-agentA")).toHaveAttribute(
    "data-state",
    "IDLE",
  );
  await expect(page.getByTestId("building-agentB")).toHaveAttribute(
    "data-state",
    "IDLE",
  );
  expect(
    await page.evaluate(
      () => (window as unknown as { peakStreams: number }).peakStreams,
    ),
  ).toBe(1);
  expect(writes).toEqual([]);
  const duplicate = crypto.randomUUID();
  await send(page, "trade_opened", a, duplicate);
  await send(page, "stop_loss_triggered", a, duplicate);
  await expect(page.getByTestId("building-agentA")).toHaveAttribute(
    "data-state",
    "TRADE_ACTIVE",
  );
  await page.getByTestId("building-agentA").click();
  await page.getByRole("link", { name: "Open full Agent A detail" }).click();
  expect(
    await page.evaluate(
      () => (window as unknown as { peakStreams: number }).peakStreams,
    ),
  ).toBe(1);
});

test("keyboard navigation, focus return and treasury display", async ({
  page,
}) => {
  await page.goto("/");
  const button = page.getByTestId("building-treasury");
  await button.focus();
  await page.keyboard.press("Enter");
  const panel = page.getByRole("complementary", { name: "Treasury details" });
  await expect(panel).toBeFocused();
  await expect(panel).toContainText("Display-only totals");
  await expect(panel).toContainText("Combined paper equity");
  await page.keyboard.press("Escape");
  await expect(button).toBeFocused();
});

test("2D preference retains the previous dashboard", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Switch to 2D" }).click();
  await expect(
    page.getByRole("region", { name: "Market intelligence", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("farm-stage")).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Explore in 3D" }),
  ).toBeVisible();
});

test("system reduced motion never mounts a canvas", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByText("Reduced motion is on.", { exact: false }),
  ).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "View Agent A details" }),
  ).toBeVisible();
});

test("WebGL unavailable falls back without losing live data", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      this: HTMLCanvasElement,
      ...args: Parameters<typeof original>
    ) {
      if (String(args[0]).startsWith("webgl")) return null;
      return original.apply(this, args);
    } as typeof original;
  });
  await page.goto("/");
  await expect(
    page.getByText("WebGL unavailable.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "View Agent B details" }),
  ).toBeVisible();
});

test("mobile farm fits, bottom sheet works and production has no simulator", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByTestId("farm-stage")).toHaveAttribute(
    "data-renderer",
    "ready",
    { timeout: 30_000 },
  );
  await page.getByTestId("building-marketplace").click();
  await expect(
    page.getByRole("complementary", { name: "Marketplace details" }),
  ).toContainText("not purchases");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Close building details" }).click();
  await page.getByRole("button", { name: "Reset camera" }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: test.info().outputPath("farm-mobile.png"),
    fullPage: true,
  });
  await expect(
    page.getByText("DEVELOPMENT ONLY · Farm Event Simulator"),
  ).toHaveCount(0);
});

test("WebGL context loss restores the complete 2D dashboard", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByTestId("farm-stage")).toHaveAttribute(
    "data-renderer",
    "ready",
    { timeout: 30_000 },
  );
  await page.locator("canvas").evaluate((canvas: HTMLCanvasElement) => {
    canvas
      .getContext("webgl2")
      ?.getExtension("WEBGL_lose_context")
      ?.loseContext();
  });
  await expect(
    page.getByText("WebGL context lost.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "View Agent A details" }),
  ).toBeVisible();
});
