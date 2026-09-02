import { expect, test } from "@playwright/test";

import { mockProject, projectView } from "./helpers";

test("validation candidates are selected by server IDs without duplicates", async ({ page }) => {
  await mockProject(
    page,
    projectView({
      phase: "awaiting_validation_selection",
      allowed_commands: ["select_validations"],
      validation_candidates: [
        {
          candidate_id: "v1",
          rank: 1,
          priority: "critical",
          rationale: "核心机制",
          addresses_claims: ["分层压缩"],
          task: { name: "消融实验" },
        },
        {
          candidate_id: "v2",
          rank: 2,
          priority: "high",
          rationale: "稳健性",
          addresses_claims: ["分层压缩"],
          task: { name: "重复运行" },
        },
      ],
    }),
  );
  await page.goto("/?project=e2e-project");
  await expect(page.getByRole("heading", { name: "补充实验" })).toBeVisible();
  await page.getByRole("checkbox", { name: "消融实验" }).check();
  await page.getByRole("checkbox", { name: "重复运行" }).check();
  await expect(page.getByRole("checkbox", { name: "消融实验" })).toHaveCount(1);
  await page.getByRole("button", { name: "确认选择" }).click();
});

test("plan revision decision is a separate complete path", async ({ page }) => {
  await mockProject(
    page,
    projectView({
      phase: "awaiting_plan_revision_decision",
      allowed_commands: ["decide_plan_revision"],
    }),
  );
  await page.goto("/?project=e2e-project");
  await expect(page.getByRole("heading", { name: "方案修订" })).toBeVisible();
  await expect(page.getByRole("button", { name: "按建议修订" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "带风险继续" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "结束项目" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "确认修订方向" })).toHaveCount(0);
});
