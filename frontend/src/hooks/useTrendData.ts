import { useMemo } from "react";
import type { TrendBucket } from "../types";

export interface TrendPoint {
  time:   string;
  score:  number | null;
  drift:  number;
  events: number;
}

/**
 * Converts raw TrendBucket[] from the dashboard summary API into
 * chart-ready TrendPoint[]. No random data — null scores are kept
 * as null so the chart renders gaps instead of fake values.
 */
export function useTrendData(buckets: TrendBucket[]): TrendPoint[] {
  return useMemo(
    () =>
      buckets.map((b) => ({
        time:   b.time,
        score:  b.score,
        drift:  0,
        events: 0,
      })),
    [buckets]
  );
}
