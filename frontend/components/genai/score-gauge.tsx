"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

export function ScoreGauge({
  score,
  label = "Overall",
  max = 100,
}: {
  score: number;
  label?: string;
  max?: number;
}) {
  const pct = Math.max(0, Math.min(1, score / max));
  const radius = 64;
  const circ = 2 * Math.PI * radius;
  const dash = circ * pct;

  // Tint by score band — semantic, used sparingly.
  const color =
    pct >= 0.75 ? "hsl(var(--accent))"
    : pct >= 0.5 ? "hsl(var(--info))"
    : "hsl(var(--warning))";

  return (
    <div className="flex flex-col items-center justify-center gap-2">
      <svg width="180" height="180" viewBox="0 0 180 180">
        <circle
          cx="90"
          cy="90"
          r={radius}
          fill="none"
          stroke="hsl(var(--surface-2))"
          strokeWidth="10"
        />
        <circle
          cx="90"
          cy="90"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}
          transform="rotate(-90 90 90)"
          style={{ transition: "stroke-dasharray 600ms ease-out" }}
        />
        <text
          x="90"
          y="86"
          textAnchor="middle"
          fontFamily="JetBrains Mono, ui-monospace"
          fontSize="34"
          fontWeight={500}
          fill="hsl(var(--text))"
        >
          {score}
        </text>
        <text
          x="90"
          y="108"
          textAnchor="middle"
          fontFamily="Inter, ui-sans-serif"
          fontSize="11"
          fill="hsl(var(--text-muted))"
          letterSpacing="0.04em"
        >
          / {max}
        </text>
      </svg>
      <span className="text-2xs font-medium text-text-dim">
        {label}
      </span>
    </div>
  );
}

export function AuditRadar({
  data,
}: {
  data: Array<{ axis: string; score: number }>;
}) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="78%">
          <PolarGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
          <PolarAngleAxis
            dataKey="axis"
            stroke="hsl(var(--text-muted))"
            tick={{ fontSize: 11, fontFamily: "Inter" }}
          />
          <PolarRadiusAxis
            domain={[0, 100]}
            tick={false}
            stroke="hsl(var(--border))"
            axisLine={false}
          />
          <Radar
            name="score"
            dataKey="score"
            stroke="hsl(var(--accent))"
            fill="hsl(var(--accent))"
            fillOpacity={0.18}
            strokeWidth={2}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}