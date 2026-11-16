import { expect, test } from "@playwright/test";

test("screens a patient, opens a citation, switches patient and filters matches", async ({
  page,
}) => {
  test.setTimeout(45_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("Execution complete")).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    page.getByRole("heading", { name: "Alexandra Morgan" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Inspect raw FHIR" }).click();
  await expect(page.getByRole("dialog")).toContainText("P-4092");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByLabel("Search trials").fill("DEMO-003");
  await expect(page.locator(".trial-card")).toHaveCount(1);
  await page.getByLabel("Search trials").clear();
  await page.getByLabel("Patient record").selectOption("P-2187");
  await expect(page.getByRole("heading", { name: "James Chen" })).toBeVisible();
  await expect(page.getByText("Execution complete")).toBeVisible({
    timeout: 15_000,
  });
  const citation = page.locator(".evidence-links button").first();
  await citation.click();
  await expect(page.getByRole("dialog")).toContainText("resourceType");
  await page.getByRole("button", { name: "Close evidence inspector" }).click();
  expect(errors).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("shows honest benchmark labels and a responsive protocol sandbox", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Benchmark lab" }).click();
  await expect(
    page.getByText("Synthetic fixture · 3 topics (not TREC)"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Precision@5", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Precision@5", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Protocol sandbox" }).click();
  await expect(page.getByText("Baseline pool")).toBeVisible();
  await page.getByLabel("Maximum patient age").fill("85");
  await page.getByLabel("Minimum eGFR").fill("30");
  await expect(page.locator(".sandbox-results")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  const delta = Number(await page.locator(".pool-delta strong").innerText());
  expect(delta).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Reset to baseline" }).click();
  await expect(page.locator(".pool-delta strong")).toHaveText("0");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
