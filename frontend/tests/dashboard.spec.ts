import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

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
