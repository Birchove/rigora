import { expect, test } from "@playwright/test";

import { createLiveProject, mockProject, projectView } from "./helpers";

const api = "http://127.0.0.1:8000/api/v1";

async function projectJson(page: { request: { get: (url: string) => Promise<{ json: () => Promise<Record<string, unknown>> }> } }, projectId: string) {
  return (await page.request.get(`${api}/projects/${projectId}`)).json();
}

async function dispatch(
  page: { request: { post: (url: string, options: { data: object }) => Promise<{ status: () => number; json: () => Promise<Record<string, unknown>> }> } },
  projectId: string,
  body: Record<string, unknown>,
) {
  const current = await projectJson(page, projectId);
  const response = await page.request.post(`${api}/projects/${projectId}/commands`, {
    data: {
      project_id: projectId,
      command_id: crypto.randomUUID(),
      expected_version: current.version,
      ...body,
    },
  });
  if (response.status() === 202) {
    await expect
      .poll(async () => ((await projectJson(page, projectId)).active_run ?? null), {
        timeout: 60_000,
      })
      .toBeNull();
  }
  return response;
}

test("demo idea reaches working after plan confirmation", async ({ page }) => {
  const created = await createLiveProject(page);
  await dispatch(page, created.project_id, {
    type: "submit_idea",
    idea: {
      original_idea: "评估分层状态压缩对长对话恢复稳定性的作用",
      domain: "computer_science",
    },
  });
  await dispatch(page, created.project_id, { type: "run_plan" });
  await dispatch(page, created.project_id, { type: "run_check" });
  await dispatch(page, created.project_id, {
    type: "decide_plan",
    decision: { decision: "accept" },
  });
  await page.goto(`/?project=${created.project_id}`);
  await expect(page.getByRole("heading", { name: "实验问答" })).toBeVisible({
    timeout: 20_000,
  });
});

test("plan confirmation action is the server-allowed gate", async ({ page }) => {
  await mockProject(
    page,
    projectView({
      phase: "awaiting_plan_decision",
      allowed_commands: ["decide_plan"],
      plan_candidates: [
        { candidate_id: "candidate-1", disposition: "ready", focus_hint: "稳健性" },
      ],
    }),
  );
  await page.goto("/?project=e2e-project");
  await expect(page.getByRole("heading", { name: "研究方案" })).toBeVisible();
  await page.getByRole("button", { name: "确认此方案" }).click();
});

test("range refinement stays at clarification until resubmitted", async ({ page }) => {
  await mockProject(
    page,
    projectView({
      phase: "awaiting_idea_refinement",
      allowed_commands: ["submit_refinement"],
    }),
  );
  await page.goto("/?project=e2e-project");
  await expect(page.getByRole("heading", { name: "补充研究边界" })).toBeVisible();
  await expect(page.getByRole("button", { name: "提交补充说明" })).toBeEnabled();
});

test("rejected idea keeps a reviewable reason card", async ({ page }) => {
  await mockProject(
    page,
    projectView({ phase: "rejected", allowed_commands: [] }),
  );
  await page.goto("/?project=e2e-project");
  await expect(page.getByRole("heading", { name: "Idea 审查结果" })).toBeVisible();
});

test("writing guidance is shown after completion", async ({ page }) => {
  await mockProject(
    page,
    projectView({ phase: "completed", allowed_commands: ["archive_project"] }),
  );
  await page.goto("/?project=e2e-project");
  await expect(page.getByRole("heading", { name: "写作规划" })).toBeVisible();
  await expect(page.getByText("不生成完整论文正文")).toBeVisible();
});
