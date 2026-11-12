import { api, queryString } from './client';
import type { EventPage, TemplateAggregate, TrendPayload } from '../types/models';

export const eventApi = {
  search: (params: {
    template_id?: number;
    source_id?: number;
    level?: string;
    search?: string;
    pending_only?: boolean;
    page?: number;
    page_size?: number;
  } = {}) => api.get<EventPage>(`/events${queryString(params)}`),
  trend: (buckets = 36, templateId?: number) => api.get<TrendPayload>(`/events/trend${queryString({ buckets, template_id: templateId })}`),
  aggregate: (top = 12) => api.get<{ items: TemplateAggregate[]; total: number }>(`/events/aggregate${queryString({ top })}`),
  levels: (templateId?: number) =>
    api.get<{ items: Array<{ level: string; count: number; ratio: number }> }>(`/events/levels${queryString({ template_id: templateId })}`),
};
