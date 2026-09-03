import type { ApiErrorEnvelope, JsonValue } from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryable: boolean;
  readonly details: Record<string, JsonValue>;

  constructor(
    status: number,
    detail: ApiErrorEnvelope["error"],
  ) {
    super(detail.message);
    this.name = "ApiError";
    this.status = status;
    this.code = detail.code;
    this.retryable = detail.retryable;
    this.details = detail.details;
  }
}
