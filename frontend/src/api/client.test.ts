import { describe, expect, it, vi } from "vitest";

import { ApiError, createClient } from "./client";
import type { SubmitIdeaCommand } from "./types";

const command: SubmitIdeaCommand = {
  type: "submit_idea",
  command_id: "command-1",
  expected_version: 3,
  idea: {
    original_idea: "研究一种更稳健的代码检索方法",
    domain: "computer science",
    available_resources: [],
    unavailable_resources: [],
    other_constraints: [],
  },
};

describe("ResearchMentorClient", () => {
  it("sends command identity and project id in the JSON body", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ command_id: "command-1", run_id: "run-1" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await createClient(fetcher).dispatchCommand("project-1", command);

    expect(fetcher).toHaveBeenCalledWith(
      "/api/v1/projects/project-1/commands",
      expect.objectContaining({ method: "POST" }),
    );
    const request = fetcher.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(request.body as string)).toMatchObject({
      project_id: "project-1",
      command_id: "command-1",
      expected_version: 3,
    });
  });

  it("maps a non-2xx error envelope to ApiError", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "stale_project_version",
            message: "项目已更新。",
            retryable: false,
            details: { current_version: 4 },
          },
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      ),
    );

    const request = createClient(fetcher).getProject("project-1");

    await expect(request).rejects.toEqual(
      expect.objectContaining<ApiError>({
        name: "ApiError",
        code: "stale_project_version",
        message: "项目已更新。",
        retryable: false,
        status: 409,
        details: { current_version: 4 },
      }),
    );
  });
});
