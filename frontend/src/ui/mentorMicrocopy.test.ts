import { describe, expect, it } from "vitest";

import { MENTOR_MICROCOPY } from "./mentorMicrocopy";

describe("MENTOR_MICROCOPY", () => {
  it("limits mentor tone to non-substantive UI states", () => {
    expect(MENTOR_MICROCOPY).toEqual({
      inputTooLong: "这么多内容我可不会假装一眼看完。请拆分或上传文件。",
      validationRequired: "至少先决定这一轮做什么。空着可不算选择。",
      runCheckingEvidence: "正在核对证据，先别急着催。",
    });
    expect(MENTOR_MICROCOPY).not.toHaveProperty("reviewDecision");
    expect(MENTOR_MICROCOPY).not.toHaveProperty("riskExplanation");
  });
});
