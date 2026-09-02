import { expect, test } from "@playwright/test";

import { mockProject, projectView } from "./helpers";

const stages = [
  ["experiment_in_progress", "实验问答", ["send_working_message"]],
  ["main_experiment_completed", "实验结果", ["record_main_result"]],
  ["validation_in_progress", "实验问答", ["send_working_message"]],
  ["research_completed", "写作规划", ["archive_project"]],
] as const;

test("four forward stages skip plan loop chrome", async ({ page }) => {
  for (const [stage, heading, commands] of stages) {
    const phase =
      stage === "main_experiment_completed"
        ? "awaiting_result_record"
        : stage === "research_completed"
          ? "completed"
          : "working";
    await mockProject(
      page,
      projectView({
        project_id: `forward-${stage}`,
        phase,
        allowed_commands: [...commands],
      }),
    );
    await page.goto(`/?project=forward-${stage}`);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expect(page.getByRole("button", { name: "生成研究方案" })).toHaveCount(0);
  }
});
