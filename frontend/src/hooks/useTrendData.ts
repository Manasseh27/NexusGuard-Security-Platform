import { useState, useEffect, useRef } from "react";

interface TrendPoint {
  time: string;
  score: number;
  drift: number;
  events: number;
}

/** Generates and live-updates a 24-point trend dataset. */
export function useTrendData(baseScore: number, points = 24): TrendPoint[] {
  const [data, setData] = useState<TrendPoint[]>(() => generateTrend(baseScore, points));
  const baseRef = useRef(baseScore);

  useEffect(() => {
    baseRef.current = baseScore;
  }, [baseScore]);

  // Regenerate when base score changes significantly
  useEffect(() => {
    setData(generateTrend(baseScore, points));
  }, [Math.round(baseScore / 5)]); // eslint-disable-line react-hooks/exhaustive-deps

  // Live tick — append new point every 30s
  useEffect(() => {
    const interval = setInterval(() => {
      setData((prev) => {
        const last = prev[prev.length - 1];
        const newScore = Math.max(60, Math.min(100,
          last.score + (Math.random() - 0.48) * 1.5
        ));
        const now = new Date();
        const newPoint: TrendPoint = {
          time: `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`,
          score: Math.round(newScore * 10) / 10,
          drift: Math.max(0, Math.round(last.drift + (Math.random() - 0.5) * 3)),
          events: Math.max(0, Math.round(last.events + (Math.random() - 0.4) * 5)),
        };
        return [...prev.slice(1), newPoint];
      });
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  return data;
}

function generateTrend(base: number, points: number): TrendPoint[] {
  const now = new Date();
  return Array.from({ length: points }, (_, i) => {
    const hoursAgo = points - 1 - i;
    const t = new Date(now.getTime() - hoursAgo * 3600_000);
    const variance = (Math.random() - 0.5) * 8;
    const score = Math.max(60, Math.min(100, base + variance));
    return {
      time: `${String(t.getHours()).padStart(2, "0")}:00`,
      score: Math.round(score * 10) / 10,
      drift: Math.max(0, Math.round(Math.random() * 20)),
      events: Math.max(0, Math.round(Math.random() * 80 + 10)),
    };
  });
}
