import React, { useEffect, useRef, useState } from "react";
import { C } from "../../styles/tokens";

interface ScoreRingProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
  showGrade?: boolean;
}

function scoreColor(score: number): string {
  if (score >= 90) return C.green;
  if (score >= 75) return C.yellow;
  if (score >= 60) return C.orange;
  return C.red;
}

function scoreGrade(score: number): string {
  if (score >= 95) return "A+";
  if (score >= 90) return "A";
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 60) return "D";
  return "F";
}

export const ScoreRing: React.FC<ScoreRingProps> = ({
  score,
  size = 140,
  strokeWidth = 9,
  label = "SCORE",
  showGrade = true,
}) => {
  const [animScore, setAnimScore] = useState(0);
  const rafRef = useRef<number>();

  // Animate score on mount / change
  useEffect(() => {
    const start = animScore;
    const end = score;
    const duration = 1200;
    const startTime = performance.now();

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimScore(start + (end - start) * eased);
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [score]); // eslint-disable-line react-hooks/exhaustive-deps

  const cx = size / 2;
  const cy = size / 2;
  const outerR = (size - strokeWidth) / 2;
  const innerR = outerR - strokeWidth - 4;
  const outerCirc = 2 * Math.PI * outerR;
  const innerCirc = 2 * Math.PI * innerR;
  const outerProgress = (animScore / 100) * outerCirc;
  const innerProgress = (animScore / 100) * 0.85 * innerCirc; // inner ring slightly offset
  const color = scoreColor(score);
  const grade = scoreGrade(score);

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{ overflow: "visible" }}
    >
      <defs>
        <filter id="ring-glow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <linearGradient id={`ring-grad-${score}`} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor={color} stopOpacity="1" />
          <stop offset="100%" stopColor={color} stopOpacity="0.6" />
        </linearGradient>
      </defs>

      {/* Outer track */}
      <circle
        cx={cx} cy={cy} r={outerR}
        fill="none"
        stroke={`${color}15`}
        strokeWidth={strokeWidth}
        transform={`rotate(-90 ${cx} ${cy})`}
      />
      {/* Outer progress */}
      <circle
        cx={cx} cy={cy} r={outerR}
        fill="none"
        stroke={`url(#ring-grad-${score})`}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={`${outerProgress} ${outerCirc}`}
        transform={`rotate(-90 ${cx} ${cy})`}
        filter="url(#ring-glow)"
        style={{ transition: "stroke-dasharray 0.05s linear" }}
      />

      {/* Inner track */}
      <circle
        cx={cx} cy={cy} r={innerR}
        fill="none"
        stroke={`${color}08`}
        strokeWidth={strokeWidth - 3}
        transform={`rotate(-90 ${cx} ${cy})`}
      />
      {/* Inner progress (decorative) */}
      <circle
        cx={cx} cy={cy} r={innerR}
        fill="none"
        stroke={`${color}35`}
        strokeWidth={strokeWidth - 3}
        strokeLinecap="round"
        strokeDasharray={`${innerProgress} ${innerCirc}`}
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transition: "stroke-dasharray 0.05s linear" }}
      />

      {/* Score text */}
      <text
        x={cx} y={cy - 8}
        textAnchor="middle" dominantBaseline="middle"
        fill={color}
        fontSize={size * 0.22}
        fontWeight={800}
        fontFamily="'JetBrains Mono', 'Fira Code', monospace"
        letterSpacing="-1"
      >
        {Math.round(animScore)}
      </text>

      {/* Label */}
      <text
        x={cx} y={cy + size * 0.13}
        textAnchor="middle" dominantBaseline="middle"
        fill={C.textMuted}
        fontSize={size * 0.085}
        fontWeight={500}
        fontFamily="'Inter', sans-serif"
        letterSpacing="2"
      >
        {label}
      </text>

      {/* Grade badge */}
      {showGrade && (
        <>
          <rect
            x={cx - 14} y={cy + size * 0.22}
            width={28} height={16}
            rx={4}
            fill={`${color}20`}
            stroke={`${color}50`}
            strokeWidth={1}
          />
          <text
            x={cx} y={cy + size * 0.22 + 8}
            textAnchor="middle" dominantBaseline="middle"
            fill={color}
            fontSize={size * 0.09}
            fontWeight={700}
            fontFamily="'Inter', sans-serif"
          >
            {grade}
          </text>
        </>
      )}
    </svg>
  );
};
