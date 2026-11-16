import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const output = fileURLToPath(new URL("../../docs/", import.meta.url));
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1600, height: 1250 },
    deviceScaleFactor: 1,
  });
  await page.goto(process.env.TRIALPULSE_DEMO_URL || "http://127.0.0.1:5173");
  await page.getByText("Execution complete").waitFor();
  await page
    .locator(".trial-card")
    .filter({ hasText: "DEMO-001" })
    .locator(".trial-toggle")
    .click();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: output + "dashboard.png", fullPage: true });
  await page.getByRole("button", { name: "Benchmark lab" }).click();
  await page.locator(".benchmark-bars").waitFor();
  await page.screenshot({ path: output + "benchmark.png", fullPage: true });
  await page.getByRole("button", { name: "Protocol sandbox" }).click();
  await page.getByLabel("Maximum patient age").fill("85");
  await page.getByLabel("Minimum eGFR").fill("30");
  await page.waitForFunction(
    () =>
      document.querySelector(".sandbox-results")?.getAttribute("aria-busy") ===
      "false",
  );
  await page.screenshot({ path: output + "sandbox.png", fullPage: true });
  console.log(`Saved dashboard, benchmark, and sandbox images to ${output}`);
} finally {
  await browser.close();
}
