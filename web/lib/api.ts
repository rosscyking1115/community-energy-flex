// Client-side API helpers. They call the same-origin BFF routes (/api/*), never
// the API origin directly. Design components import these; they never see fetch.

import type {
  Appliance,
  Forecast,
  OptimiseRequest,
  OptimiseResponse,
  Region,
} from "@/lib/types";

/** An API failure that keeps the HTTP status and the raw detail body. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: unknown,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => b?.detail)
      .catch(() => null);
    throw new ApiError(
      res.status,
      detail ?? null,
      typeof detail === "string" ? detail : res.statusText,
    );
  }
  return res.json() as Promise<T>;
}

export function getRegions(): Promise<Region[]> {
  return fetch("/api/regions").then((r) => asJson<Region[]>(r));
}

export function getAppliances(): Promise<Appliance[]> {
  return fetch("/api/appliances").then((r) => asJson<Appliance[]>(r));
}

export function getForecast(regionId: string): Promise<Forecast> {
  return fetch(`/api/forecast/${encodeURIComponent(regionId)}`).then((r) =>
    asJson<Forecast>(r),
  );
}

export function optimise(body: OptimiseRequest): Promise<OptimiseResponse> {
  return fetch("/api/optimise", {
    method: "POST",
    body: JSON.stringify(body),
  }).then((r) => asJson<OptimiseResponse>(r));
}
