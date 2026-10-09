import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("welcome and every workspace view pass automated WCAG checks", async ({
  page,
}) => {
  await page.goto("/");
  const scan = async () => {
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(
      result.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          summary: n.failureSummary,
        })),
      })),
    ).toEqual([]);
  };
  await scan();
  await page.getByRole("button", { name: "Enter Workspace" }).click();
  for (const view of [
    "Overview",
    "Document Imports",
    "Match Review",
    "Entity Directory",
    "Graph Explorer",
    "Evidence Library",
    "Cases",
    "Audit History",
    "Settings",
  ]) {
    await page.getByRole("button", { name: view, exact: true }).click();
    await scan();
  }
});
