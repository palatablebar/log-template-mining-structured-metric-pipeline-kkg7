/** 图表取色（与 tokens.css 的 oklch 保持一致，Canvas 需要具体字符串）。 */
export const CHART_COLORS = {
  ink: 'oklch(0.32 0.03 210)',
  inkSoft: 'oklch(0.46 0.025 210)',
  grid: 'oklch(0.86 0.014 225)',
  gridStrong: 'oklch(0.78 0.016 225)',
  amber: 'oklch(0.72 0.14 75)',
  amberDeep: 'oklch(0.62 0.14 65)',
  teal: 'oklch(0.52 0.05 205)',
  brick: 'oklch(0.55 0.16 28)',
  paper: 'oklch(0.965 0.012 230)',
};

export const SERIES_STROKES = [CHART_COLORS.ink, CHART_COLORS.teal, CHART_COLORS.amberDeep, CHART_COLORS.inkSoft];
