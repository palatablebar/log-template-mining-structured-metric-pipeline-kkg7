import { useEffect, useRef } from 'react';
import { CHART_COLORS } from '../../constants/palette';
import type { TrendSeriesView } from '../../hooks/useTrendSeries';

interface TrendChartProps {
  series: TrendSeriesView[];
  buckets: string[];
  height?: number;
  mini?: boolean;
  /** 触发折线绘制动画的 key：数据变化时重画一遍 */
  animationKey?: string;
}

const PAD = { top: 18, right: 14, bottom: 22, left: 34 };

/** Canvas2D 趋势图：按模板分组的 5min 桶计数折线 + error 柱。 */
export const TrendChart = ({ series, buckets, height = 240, mini = false, animationKey }: TrendChartProps) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth || 720;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

    const draw = (progress: number) => {
      ctx.clearRect(0, 0, width, height);
      const plotW = width - PAD.left - PAD.right;
      const plotH = height - PAD.top - PAD.bottom;
      const count = Math.max(1, buckets.length);
      const maxValue = Math.max(
        1,
        ...series.flatMap((item) => item.series),
        ...series.flatMap((item) => item.errorSeries),
      );
      const scaleX = (index: number) => PAD.left + (plotW * index) / Math.max(1, count - 1);
      const scaleY = (value: number) => PAD.top + plotH - (plotH * value) / maxValue;

      // 细网格
      ctx.strokeStyle = CHART_COLORS.grid;
      ctx.lineWidth = 1;
      const rows = mini ? 2 : 4;
      for (let row = 0; row <= rows; row += 1) {
        const y = PAD.top + (plotH * row) / rows;
        ctx.beginPath();
        ctx.moveTo(PAD.left, y);
        ctx.lineTo(width - PAD.right, y);
        ctx.stroke();
      }
      ctx.strokeStyle = CHART_COLORS.gridStrong;
      ctx.beginPath();
      ctx.moveTo(PAD.left, PAD.top + plotH);
      ctx.lineTo(width - PAD.right, PAD.top + plotH);
      ctx.stroke();

      // error 柱（低饱和砖色，柱宽 4px）
      series.forEach((item, seriesIndex) => {
        if (seriesIndex > 0) return;
        item.errorSeries.forEach((value, index) => {
          if (!value) return;
          const x = scaleX(index) - 2;
          const y = scaleY(value);
          ctx.fillStyle = 'oklch(0.55 0.16 28 / 0.35)';
          ctx.fillRect(x, y, 4, PAD.top + plotH - y);
        });
      });

      // 折线（逐段绘制，progress 控制 stroke-dashoffset 式生长）
      const strokes = [CHART_COLORS.ink, CHART_COLORS.teal, CHART_COLORS.amberDeep, CHART_COLORS.inkSoft];
      series.forEach((item, seriesIndex) => {
        ctx.strokeStyle = strokes[seriesIndex % strokes.length];
        ctx.lineWidth = seriesIndex === 0 ? 2 : 1.4;
        ctx.beginPath();
        const visible = Math.max(2, Math.floor((count - 1) * progress) + 1);
        item.series.slice(0, visible).forEach((value, index) => {
          const x = scaleX(index);
          const y = scaleY(value);
          if (index === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
        const lastIndex = visible - 1;
        if (lastIndex >= 0) {
          ctx.fillStyle = strokes[seriesIndex % strokes.length];
          ctx.beginPath();
          ctx.arc(scaleX(lastIndex), scaleY(item.series[lastIndex] ?? 0), 2.4, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      // 刻度文字
      ctx.fillStyle = CHART_COLORS.inkSoft;
      ctx.font = '10px "Source Code Pro", monospace';
      ctx.textAlign = 'right';
      ctx.fillText(String(Math.round(maxValue)), PAD.left - 6, PAD.top + 3);
      ctx.fillText('0', PAD.left - 6, PAD.top + plotH + 3);
      ctx.textAlign = 'center';
      const tickIndexes = mini ? [0, count - 1] : [0, Math.floor(count / 3), Math.floor((count * 2) / 3), count - 1];
      tickIndexes.forEach((index) => {
        const label = (buckets[index] ?? '').replace('T', ' ').slice(11, 16);
        if (label) ctx.fillText(label, scaleX(index), height - 6);
      });
    };

    const start = performance.now();
    const duration = prefersReducedMotion() ? 0 : 620;
    const animate = (now: number) => {
      const progress = duration === 0 ? 1 : Math.min(1, (now - start) / duration);
      draw(progress);
      if (progress < 1) frameRef.current = requestAnimationFrame(animate);
    };
    frameRef.current = requestAnimationFrame(animate);

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [series, buckets, height, mini, animationKey]);

  return (
    <div className="chart-wrap">
      <canvas ref={canvasRef} style={{ height }} aria-label="按模板聚合的 5 分钟桶趋势图" />
      {series.length ? (
        <div className="chart-legend">
          {series.slice(0, 4).map((item, index) => (
            <span className="key" key={item.templateId} style={{ color: [CHART_COLORS.ink, CHART_COLORS.teal, CHART_COLORS.amberDeep, CHART_COLORS.inkSoft][index % 4] }}>
              <span className="swatch" />
              {item.service} · {item.templateStr.split(' ').slice(3, 6).join(' ')}
            </span>
          ))}
          <span className="key" style={{ color: CHART_COLORS.brick }}>
            <span className="swatch bar" />
            error 计数
          </span>
        </div>
      ) : null}
    </div>
  );
};

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
