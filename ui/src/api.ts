import type { CrewSummary } from "./types";

export const SUMMARY_PATH = "/apps/dues-banshee/api/summary";
export const DEMO_SUMMARY_PATH = "/apps/dues-banshee/api/summary?today=2026-11-12";

export type SummaryResult =
  | { kind: "error"; code: string }
  | { kind: "data"; summary: CrewSummary };

export interface SummaryApi {
  get: (path: string) => Promise<unknown>;
}

const REQUEST_FAILED: SummaryResult = { kind: "error", code: "request_failed" };

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// The error code in `{"error": "<code>"}`, or null when the value has no string `error`.
function errorCode(value: unknown): string | null {
  return isObject(value) && typeof value.error === "string" ? value.error : null;
}

export async function loadSummary(api: SummaryApi, demo: boolean): Promise<SummaryResult> {
  let body: unknown;
  try {
    body = await api.get(demo ? DEMO_SUMMARY_PATH : SUMMARY_PATH);
  } catch (err) {
    // useAppApi throws an error carrying the response body as an unparsed string.
    const raw = isObject(err) ? err.body : undefined;
    if (typeof raw === "string") {
      try {
        const code = errorCode(JSON.parse(raw));
        if (code !== null) return { kind: "error", code };
      } catch {
        // not JSON: fall through
      }
    }
    return REQUEST_FAILED;
  }

  const code = errorCode(body);
  if (code !== null) return { kind: "error", code };
  if (isObject(body) && Array.isArray(body.tombstones)) {
    return { kind: "data", summary: body as unknown as CrewSummary };
  }
  return REQUEST_FAILED;
}
