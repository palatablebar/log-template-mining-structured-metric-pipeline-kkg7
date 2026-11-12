import { api, queryString } from './client';
import type { Template } from '../types/models';

export const templateApi = {
  list: (params: { status?: string; source_id?: number; search?: string; include_noise?: boolean } = {}) =>
    api.get<{ items: Template[]; total: number }>(`/templates${queryString(params)}`),
  detail: (id: number) => api.get<Template & { samples: Array<{ raw_line: string; level: string; event_time: string }> }>(`/templates/${id}`),
  confirm: (id: number) => api.post<{ id: number; status: string; message: string }>(`/templates/${id}/confirm`),
  markNoise: (id: number) => api.post<{ id: number; status: string; message: string }>(`/templates/${id}/noise`),
};
