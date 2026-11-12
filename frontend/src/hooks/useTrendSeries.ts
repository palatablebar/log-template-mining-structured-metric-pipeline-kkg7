import { useMemo } from 'react';
import type { TrendPayload } from '../types/models';

export interface TrendSeriesView {
  templateId: number;
  templateStr: string;
  service: string;
  series: number[];
  errorSeries: number[];
  total: number;
  peak: number;
}

/** 把后端趋势 payload 转成图表要的矩阵，并算出峰值（用于纵向刻度）。 */
export const useTrendSeries = (payload: TrendPayload | null, limit = 6) =>
  useMemo(() => {
    if (!payload) return { series: [] as TrendSeriesView[], max: 0, buckets: [] as string[] };
    const series: TrendSeriesView[] = payload.series.slice(0, limit).map((item) => ({
      templateId: item.template_id,
      templateStr: item.template_str,
      service: item.service,
      series: item.series,
      errorSeries: item.error_series,
      total: item.total,
      peak: item.peak,
    }));
    const max = series.reduce((acc, item) => Math.max(acc, ...item.series, ...item.errorSeries), 0);
    return { series, max, buckets: payload.buckets };
  }, [payload, limit]);
