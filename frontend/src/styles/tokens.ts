/** Enterprise Cybersecurity Platform — Design System Tokens */

export const C = {
  // Backgrounds — layered depth
  bg:          "#030712",
  bgAlt:       "#060b18",
  surface:     "#0a0f1e",
  surface2:    "#0d1426",
  surface3:    "#111827",
  surfaceHover:"#141d30",

  // Borders
  border:      "#1e2d45",
  borderMid:   "#243552",
  borderGlow:  "#2a4a7f",

  // Brand accents
  cyan:        "#06b6d4",
  cyanBright:  "#22d3ee",
  cyanDim:     "#0891b2",
  cyanGlow:    "#06b6d440",

  // Status colors — calibrated for dark backgrounds
  green:       "#10b981",
  greenBright: "#34d399",
  greenDim:    "#059669",
  greenGlow:   "#10b98130",

  yellow:      "#f59e0b",
  yellowBright:"#fbbf24",
  yellowDim:   "#d97706",

  orange:      "#f97316",
  orangeDim:   "#ea580c",

  red:         "#ef4444",
  redBright:   "#f87171",
  redDim:      "#dc2626",
  redGlow:     "#ef444430",

  purple:      "#8b5cf6",
  purpleBright:"#a78bfa",
  purpleDim:   "#7c3aed",
  purpleGlow:  "#8b5cf630",

  blue:        "#3b82f6",
  blueDim:     "#2563eb",

  // Typography
  text:        "#f1f5f9",
  textSub:     "#cbd5e1",
  textDim:     "#94a3b8",
  textMuted:   "#475569",
  textFaint:   "#334155",
} as const;

export type ColorToken = (typeof C)[keyof typeof C];

export const SEVERITY_COLOR: Record<string, string> = {
  critical:    C.red,
  high:        C.orange,
  medium:      C.yellow,
  low:         C.green,
  info:        C.cyan,
  informational: C.cyan,
};

export const SEVERITY_GLOW: Record<string, string> = {
  critical:    C.redGlow,
  high:        `${C.orange}30`,
  medium:      `${C.yellow}25`,
  low:         C.greenGlow,
  info:        C.cyanGlow,
};

// Animation timing
export const ANIM = {
  fast:   "0.12s ease",
  normal: "0.2s ease",
  slow:   "0.35s ease",
  spring: "0.4s cubic-bezier(0.34,1.56,0.64,1)",
} as const;

// Spacing scale (px)
export const SPACE = {
  xs:  4,
  sm:  8,
  md:  14,
  lg:  20,
  xl:  28,
  xxl: 40,
} as const;

// Border radius
export const RADIUS = {
  sm:  6,
  md:  10,
  lg:  14,
  xl:  20,
  full: 9999,
} as const;

// Shadows
export const SHADOW = {
  card:   "0 4px 24px rgba(0,0,0,0.5), 0 1px 0 rgba(255,255,255,0.03) inset",
  panel:  "0 8px 32px rgba(0,0,0,0.6)",
  glow:   (color: string) => `0 0 20px ${color}40, 0 0 40px ${color}20`,
  subtle: "0 2px 8px rgba(0,0,0,0.4)",
} as const;
