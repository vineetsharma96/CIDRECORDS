import { test, expect } from "@playwright/test";
import path from "node:path";

test("seed, import, reconcile, commit, explore evidence at a single URL", async ({
  page,
  request,
}) => {
  await request.post("http://127.0.0.1:8000/api/demo/seed");
  const consoleErrors: string[] = [];
  page.on("pageerror", (e) => consoleErrors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "See the connections. Keep the context.",
    }),
  ).toBeVisible();
  await page.screenshot({
    path: "tmp/verification/welcome-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Enter Workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Investigation Overview" }),
  ).toBeVisible();
  await expect(
    page.getByText("Neo4j Connected", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "tmp/verification/dashboard-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Document Imports", exact: true })
    .click();
  await page
    .locator("#upload-file")
    .setInputFiles(
      path.resolve("test_data/historical_documents/mixed_import.csv"),
    );
  await page.getByRole("button", { name: "Upload & Extract" }).click();
  await expect(
    page.getByRole("heading", { name: "mixed_import.csv", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Oren Vale", exact: true }),
  ).toBeVisible({ timeout: 60000 });
  await page
    .getByRole("button", { name: "Correct Extraction", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save Corrected Extraction", exact: true })
    .click();
  await expect(page.locator(".correction-form")).toBeVisible();
  await expect(page.locator('input[name="review-reason"]')).toBeFocused();
  await page
    .getByRole("button", { name: "Correct Extraction", exact: true })
    .click();
  await page
    .locator('input[name="review-reason"]')
    .fill("Reviewed synthetic source evidence; commit safe proposals.");
  await page.screenshot({
    path: "tmp/verification/review-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Commit Reviewed Changes" }).click();
  await expect(
    page.getByText(
      "Supported changes committed. Uncertain records remain in review.",
      { exact: true },
    ),
  ).toBeVisible({ timeout: 60000 });
  await page
    .getByRole("button", { name: "Entity Directory", exact: true })
    .click();
  await expect(
    page.locator(".directory").getByText("Oren Vale", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "View Profile" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page
    .getByRole("button", { name: "Graph Explorer", exact: true })
    .click();
  await expect(
    page.getByText("Every Connection Has a Source", { exact: true }),
  ).toBeVisible();
  await page.getByText("Keyboard Entity & Relationship List").click();
  await page.locator(".node-list").first().getByRole("button").first().click();
  await expect(
    page.getByRole("button", { name: "Expand Neighbours" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Expand Neighbours" }).click();
  await page.screenshot({
    path: "tmp/verification/graph-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Evidence Library", exact: true })
    .click();
  await page.locator(".evidence-item").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText("Original Value", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open Original File" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Audit History", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Undo / Split" }).first(),
  ).toBeVisible();
  expect(page.url()).toBe("http://127.0.0.1:3000/");
  expect(consoleErrors).toEqual([]);
});

test("mobile layout, keyboard focus and reduced motion", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to Content" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Enter Workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Investigation Overview" }),
  ).toBeVisible();
  await page.screenshot({
    path: "tmp/verification/dashboard-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Document Imports", exact: true })
    .click();
  await expect(page.locator("#upload-file")).toBeVisible();
  expect(page.url()).toBe("http://127.0.0.1:3000/");
  expect(
    await page.evaluate(
      () =>
        getComputedStyle(document.querySelector(".view:not([hidden])")!)
          .animationName,
    ),
  ).toBe("none");
});
