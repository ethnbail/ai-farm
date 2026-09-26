import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

// Preserve Phase 1–3 regression coverage against the unchanged 2D dashboard.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("ai-farm:3d", "false"));
});

test("Phase 3 defaults expose regime and disabled AI without invented spend", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("region", { name: "Market intelligence", exact: true }),
  ).toContainText("UNKNOWN");
  const usage = page.getByRole("region", { name: "AI Usage", exact: true });
  await expect(usage).toContainText("Disabled");
  await expect(usage).toContainText("Daily remaining");
  await expect(usage).toContainText("$0.00");
  await expect(usage).toContainText("deterministic-only");
});

test("live backend agents, details, and SSE heartbeat", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Room to grow." }),
  ).toBeVisible();
  for (const name of ["Agent A", "Agent B"]) {
    const card = page.getByRole("link", { name: `View ${name} details` });
    await expect(card).toBeVisible();
    await expect(card).toContainText("$1,000.00");
  }
  await expect(page.getByTestId("realtime-status")).toHaveText("Live", {
    timeout: 20_000,
  });
  await expect(page.getByText("Last heartbeat at")).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath("dashboard.png"),
    fullPage: true,
  });
  for (const name of ["Agent A", "Agent B"]) {
    await page.getByRole("link", { name: `View ${name} details` }).click();
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "No trades yet" }),
    ).toBeVisible();
    await expect(page.getByText("$0.00 (0.00%)")).toBeVisible();
    await page.getByRole("link", { name: "Back to the farm" }).click();
  }
  expect(errors).toEqual([]);
});

test("mobile layout fits and explains inactive marketplace", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("link", { name: "View Agent A details" }),
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: "ZIP code" })).toBeDisabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: test.info().outputPath("mobile.png"),
    fullPage: true,
  });
});

test("backend failure is visible and never presented as zero balances", async ({
  page,
}) => {
  await page.route("**/api/agents", (route) => route.abort());
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Agents unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "View Agent A details" }),
  ).toHaveCount(0);
});

test("research and Marketplace stream live, with explainable Shadow and options details", async ({
  page,
  request,
}) => {
  test.skip(
    process.env.PAPER_E2E !== "1",
    "Requires a disposable seeded database",
  );
  test.setTimeout(60_000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    const original = window.setTimeout.bind(window);
    window.setTimeout = ((
      handler: TimerHandler,
      delay?: number,
      ...args: unknown[]
    ) =>
      original(
        handler,
        delay === 15_000 ? 600_000 : delay,
        ...args,
      )) as typeof window.setTimeout;
  });
  await page.goto("/");
  await expect(page.getByTestId("realtime-status")).toHaveText("Live");
  await expect(
    page.getByText("No research yet.", { exact: false }),
  ).toBeVisible();
  const backend = path.resolve(process.cwd(), "../backend");
  for (const args of [["research", "--demo"], ["marketplace-fixture"]]) {
    execFileSync(
      path.join(backend, ".venv/bin/python"),
      ["-m", "app.workers.cli", ...args],
      {
        cwd: backend,
        env: {
          ...process.env,
          AI_ENABLED: "false",
          ENABLE_DEVELOPMENT_ACTIONS: "true",
        },
        timeout: 30_000,
      },
    );
  }
  await expect(
    page.getByRole("region", { name: "Market intelligence", exact: true }),
  ).toContainText("BULL TREND", { timeout: 8_000 });
  await expect(page.getByRole("link", { name: "FARM research" })).toBeVisible({
    timeout: 8_000,
  });
  await expect(page.getByRole("link", { name: "Test oak desk" })).toBeVisible({
    timeout: 8_000,
  });
  await page.getByRole("link", { name: "FARM research" }).click();
  await expect(
    page.getByRole("heading", { name: "Shadow objections" }),
  ).toBeVisible();
  await expect(
    page.getByText("Live event coverage is unavailable", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Ranked option contracts" }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "OI", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: test.info().outputPath("phase3-research.png"),
    fullPage: true,
  });
  await page.goto("/");
  await page.getByRole("link", { name: "Test oak desk" }).click();
  await expect(
    page.getByText("Estimates only", { exact: false }).first(),
  ).toBeVisible();
  await expect(page.getByText("48.00", { exact: true })).toBeVisible();
  const agents = (await (
    await request.get("http://127.0.0.1:8000/api/agents")
  ).json()) as { id: string; name: string }[];
  await page.goto(`/agents/${agents.find((a) => a.name === "Agent B")!.id}`);
  await page
    .getByText("Latest analysis and Shadow review", { exact: false })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ranked option contracts" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Agent Intelligence" }),
  ).toContainText("Win rate N/A");
  expect(errors).toEqual([]);
});

test("paper lifecycle updates both agents via SSE and preserves replay", async ({
  page,
  context,
  request,
}) => {
  test.skip(
    process.env.PAPER_E2E !== "1",
    "Opt in against a disposable seeded database with PAPER_E2E=1",
  );
  test.setTimeout(60_000);
  const backend = path.resolve(process.cwd(), "../backend");
  const demo = (stage: string) =>
    execFileSync(
      path.join(backend, ".venv/bin/python"),
      ["-m", "app.workers.cli", "demo", "--stage", stage],
      {
        cwd: backend,
        env: { ...process.env, ENABLE_DEVELOPMENT_ACTIONS: "true" },
        timeout: 15_000,
      },
    );
  const response = await request.get("http://127.0.0.1:8000/api/agents");
  const agents = (await response.json()) as { id: string; name: string }[];
  const a = agents.find((a) => a.name === "Agent A")!;
  const b = agents.find((a) => a.name === "Agent B")!;
  const optionsPage = await context.newPage();
  // Suppress the 15-second polling fallback: changes below must come from SSE.
  for (const tab of [page, optionsPage])
    await tab.addInitScript(() => {
      const original = window.setTimeout.bind(window);
      window.setTimeout = ((
        handler: TimerHandler,
        delay?: number,
        ...args: unknown[]
      ) =>
        original(
          handler,
          delay === 15_000 ? 600_000 : delay,
          ...args,
        )) as typeof window.setTimeout;
    });
  await page.goto(`/agents/${a.id}`);
  await optionsPage.goto(`/agents/${b.id}`);
  await expect(
    page.getByText("No open positions.", { exact: false }),
  ).toBeVisible();
  await expect(
    optionsPage.getByText("No open positions.", { exact: false }),
  ).toBeVisible();
  demo("entry");
  await expect(page.getByTestId("position")).toContainText("NVDA", {
    timeout: 8_000,
  });
  await expect(optionsPage.getByTestId("position")).toContainText("FARM", {
    timeout: 8_000,
  });
  await expect(
    page.getByRole("region", { name: "Agent statistics" }),
  ).toContainText("$999.93");
  await expect(
    optionsPage.getByRole("region", { name: "Agent statistics" }),
  ).toContainText("$998.85");
  await expect(optionsPage.getByTestId("position")).toContainText(
    "Entry delta",
  );
  await optionsPage.setViewportSize({ width: 390, height: 844 });
  expect(
    await optionsPage.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await optionsPage.screenshot({
    path: test.info().outputPath("options-position.png"),
    fullPage: true,
  });
  demo("mark");
  await expect(page.getByTestId("position")).toContainText("$100.9900", {
    timeout: 8_000,
  });
  await expect(optionsPage.getByTestId("position")).toContainText("$0.1700", {
    timeout: 8_000,
  });
  demo("exit");
  await expect(page.getByTestId("position")).toHaveCount(0, { timeout: 8_000 });
  await expect(optionsPage.getByTestId("position")).toHaveCount(0, {
    timeout: 8_000,
  });
  await expect(
    page.getByRole("region", { name: "Agent statistics" }),
  ).toContainText("$1,005.88");
  await expect(
    optionsPage.getByRole("region", { name: "Agent statistics" }),
  ).toContainText("$1,010.59");
  await page.getByRole("link", { name: "NVDA", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Trade Replay" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Recorded fills" }),
  ).toContainText("$105.9370");
  await expect(
    page.getByText("take profit triggered", { exact: true }),
  ).toBeVisible();
  await optionsPage.getByRole("link", { name: /^FARM_/ }).click();
  await expect(
    optionsPage.getByRole("heading", { name: "Trade Replay" }),
  ).toBeVisible();
  await expect(
    optionsPage.getByRole("region", { name: "Trade Replay", exact: true }),
  ).toContainText("gamma");
  await expect(
    optionsPage.getByRole("region", { name: "Trade details" }),
  ).toContainText("$10.59");
  await optionsPage.screenshot({
    path: test.info().outputPath("option-replay.png"),
    fullPage: true,
  });
  await page.goto("/");
  await expect(
    page.getByRole("link", { name: "View Agent A details" }),
  ).toContainText("$1,005.88");
  await expect(
    page.getByRole("link", { name: "View Agent B details" }),
  ).toContainText("$1,010.59");
  await expect(
    page.getByRole("heading", { name: "Recent Activity" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Paper trading environment" }),
  ).toContainText("MOCK DATA");
});

test("market provider failure is explicit", async ({ page }) => {
  await page.route("**/api/market/provider-status", (route) =>
    route.fulfill({
      json: {
        provider: "tradier",
        effective_provider: "tradier",
        state: "unavailable",
        message: "Market provider rate limit hit",
      },
    }),
  );
  await page.goto("/");
  await expect(
    page.getByRole("region", { name: "Market intelligence", exact: true }),
  ).toContainText("Market provider rate limit hit");
});
