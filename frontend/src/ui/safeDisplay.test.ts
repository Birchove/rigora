import { describe, expect, it } from "vitest";

import { safeHttpUrl, stripHtml } from "./safeDisplay";

describe("safeDisplay", () => {
  it("strips html tags from untrusted text", () => {
    expect(stripHtml("<script>alert(1)</script>hello")).toBe("alert(1)hello");
  });

  it("keeps only http and https urls", () => {
    expect(safeHttpUrl("https://example.com/a")).toBe("https://example.com/a");
    expect(safeHttpUrl("javascript:alert(1)")).toBeNull();
    expect(safeHttpUrl("data:text/html,hi")).toBeNull();
  });
});
