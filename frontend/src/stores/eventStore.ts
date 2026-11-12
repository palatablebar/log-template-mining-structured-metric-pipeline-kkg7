import { create } from 'zustand';
import { eventApi } from '../api/event';
import type { EventPage, TemplateAggregate, TrendPayload } from '../types/models';

interface EventState {
  page: EventPage | null;
  trend: TrendPayload | null;
  aggregate: TemplateAggregate[];
  filters: { templateId: number | null; level: string; search: string; pendingOnly: boolean; buckets: number };
  loading: boolean;
  error: string | null;
  loadPage: (page?: number) => Promise<void>;
  loadTrend: () => Promise<void>;
  loadAggregate: () => Promise<void>;
  setFilters: (patch: Partial<EventState['filters']>) => void;
}

const initialFilters = { templateId: null, level: '', search: '', pendingOnly: false, buckets: 36 };

export const useEventStore = create<EventState>((set, get) => ({
  page: null,
  trend: null,
  aggregate: [],
  filters: { ...initialFilters },
  loading: false,
  error: null,
  loadPage: async (page = 1) => {
    const { templateId, level, search, pendingOnly } = get().filters;
    set({ loading: true, error: null });
    try {
      const response = await eventApi.search({
        template_id: templateId ?? undefined,
        level: level || undefined,
        search: search || undefined,
        pending_only: pendingOnly || undefined,
        page,
        page_size: 25,
      });
      set({ page: response, loading: false });
    } catch (error) {
      set({ loading: false, error: error instanceof Error ? error.message : '事件加载失败' });
    }
  },
  loadTrend: async () => {
    try {
      const { templateId, buckets } = get().filters;
      const response = await eventApi.trend(buckets, templateId ?? undefined);
      set({ trend: response });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '趋势加载失败' });
    }
  },
  loadAggregate: async () => {
    try {
      const response = await eventApi.aggregate(12);
      set({ aggregate: response.items });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '聚合加载失败' });
    }
  },
  setFilters: (patch) => {
    set({ filters: { ...get().filters, ...patch } });
    void get().loadPage(1);
    void get().loadTrend();
  },
}));
