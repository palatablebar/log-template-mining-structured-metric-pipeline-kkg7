import { api, queryString } from './client';
import type { ParseRule, Source } from '../types/models';

export const sourceApi = {
  list: () => api.get<{ items: Source[]; total: number }>('/sources'),
  create: (payload: { name: string; service: string; log_format: string; rate_per_min: number; host_group: string; description: string }) =>
    api.post<{ id: number; message: string }>('/sources', payload),
  update: (id: number, payload: Record<string, unknown>) => api.patch<{ id: number; message: string }>(`/sources/${id}`, payload),
  rules: (sourceId?: number) => api.get<{ items: ParseRule[]; total: number }>(`/parse-rules${queryString({ source_id: sourceId })}`),
  createRule: (sourceId: number, payload: { name: string; pattern: string; field_names: string[]; priority: number }) =>
    api.post<{ id: number; message: string }>(`/sources/${sourceId}/parse-rules`, payload),
  updateRule: (ruleId: number, payload: Record<string, unknown>) =>
    api.patch<{ id: number; message: string }>(`/parse-rules/${ruleId}`, payload),
};
