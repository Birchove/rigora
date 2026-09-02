import type { Page } from "@playwright/test";

export type Phase =
  | "awaiting_idea"
  | "awaiting_idea_refinement"
  | "planning"
  | "checking_key_insight"
  | "awaiting_plan_decision"
  | "working"
  | "awaiting_result_record"
  | "completing"
  | "awaiting_validation_selection"
  | "awaiting_plan_revision_decision"
  | "completed"
  | "rejected"
  | "check_loop_exhausted"
  | "awaiting_working_context";

export function projectView(overrides: Record<string, unknown> = {}) {
  return {
    project_id: "e2e-project",
    title: "E2E 研究",
    domain: "computer_science",
    version: 1,
    phase: "awaiting_idea" as Phase,
    is_demo: true,
    allowed_commands: ["submit_idea"],
    last_event_sequence: 1,
    ...overrides,
  };
}

export async function mockProject(page: Page, view: ReturnType<typeof projectView>) {
  await page.route("**/api/v1/projects**", async (route) => {
    const request = route.request();
    const url = request.url();
    if (url.includes("/events")) {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "",
      });
      return;
    }
    if (request.method() === "GET" && /\/projects\/[^/?]+(?:\?|$)/.test(url)) {
      await route.fulfill({ json: view });
      return;
    }
    if (request.method() === "GET" && url.includes("/projects") && !url.includes("/commands")) {
      await route.fulfill({ json: [view] });
      return;
    }
    await route.continue();
  });
}

export async function createLiveProject(page: Page) {
  const response = await page.request.post("http://127.0.0.1:8000/api/v1/projects", {
    data: { title: `E2E ${Date.now()}`, domain: "computer_science" },
  });
  return response.json();
}
