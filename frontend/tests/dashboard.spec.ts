import { expect, test } from "@playwright/test";

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
