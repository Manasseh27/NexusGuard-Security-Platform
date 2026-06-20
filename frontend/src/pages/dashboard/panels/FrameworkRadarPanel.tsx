import React from "react";
import {
  RadarChart, Radar, PolarGrid,
  PolarAngleAxis, ResponsiveContainer, Tooltip,
} from "recharts";
import { Panel, CyberTooltip } from "../../../components/widgets";
import { C } from "../../../styles/tokens";

interface RadarDataPoint {
  subject:  string;
  score:    number;
  fullMark: number;
}

interface FrameworkRadarPanelProps {
  data: RadarDataPoint[];
}

export const FrameworkRadarPanel: React.FC<FrameworkRadarPanelProps> = ({ data }) => {
  const avg = data.length
    ? Math.round(data.reduce((a, d) => a + d.score, 0) / data.length)
    : 0;

  return (
    <Panel
      title="Framework Coverage"
      subtitle={`avg ${avg}%`}
      accent={C.purple}
    >
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={data} margin={{ top: 8, right: 16, left: 16, bottom: 8 }}>
          <defs>
            <linearGradient id="radarFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor={C.purple} stopOpacity={0.4} />
              <stop offset="100%" stopColor={C.purple} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <PolarGrid
            stroke={`${C.border}80`}
            gridType="polygon"
          />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: C.textMuted, fontSize: 9, fontWeight: 500 }}
          />
          <Tooltip content={<CyberTooltip />} />
          <Radar
            dataKey="score"
            stroke={C.purple}
            fill="url(#radarFill)"
            strokeWidth={2}
            dot={{ fill: C.purple, r: 3, strokeWidth: 0 }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </Panel>
  );
};
