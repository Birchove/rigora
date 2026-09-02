import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { mockProject, projectView } from "./helpers";

const phases = [
  "awaiting_idea",
  "awaiting_idea_refinement",
  "planning",
  "awaiting_plan_decision",
  "working",
  "awaiting_result_record",
  "awaiting_validation_selection",
  "completed",
  "rejected",
] as const;

test("project workspace passes axe and keyboard focus on interactive phases", async ({
  page,
}) => {
  for (const phase of phases) {
    await mockProject(
      page,
      projectView({
        phase,
        allowed_commands:
          phase === "awaiting_idea"
            ? ["submit_idea"]
            : phase === "awaiting_plan_decision"
              ? ["decide_plan"]
              : [],
      }),
    );
    await page.goto("/?project=e2e-project");
    await expect(page.getByRole("main")).toBeVisible();
    const results = await new AxeBuilder({ page })
      .disableRules(["region", "color-contrast", "aria-prohibited-attr"])
      .analyze();
    expect(results.violations, phase).toEqual([]);
  }
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
});

test("narrow layout exposes drawer and respects reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await mockProject(page, projectView({ phase: "working", allowed_commands: [] }));
  await page.goto("/?project=e2e-project");
  await page.getByRole("button", { name: "项目", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "研究项目" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "证据", exact: true }).click();
  await expect(page.getByRole("complementary", { name: "证据" })).toBeVisible();
});
