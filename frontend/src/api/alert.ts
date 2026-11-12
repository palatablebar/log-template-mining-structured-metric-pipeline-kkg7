import { api, queryString } from './client';
import type { AlertEvent, AlertRule, ScanResult } from '../types/models';

export interface AlertListResponse {
  items: AlertEvent[];
  total: number;
  stats: { total: number; firing: number; acknowledged: number; silenced: number; resolved: number };
}

export const alertApi = {
  rules: () => api.get<{ items: AlertRule[]; total: number }>('/alerts/rules'),
  createRule: (payload: Record<string, unknown>) => api.post<{ id: number; message: string }>('/alerts/rules', payload),
  updateRule: (id: number, payload: Record<string, unknown>) =>
    api.patch<{ id: number; message: string }>(`/alerts/rules/${id}`, payload),
  events: (status?: string) => api.get<AlertListResponse>(`/alerts/events${queryString({ status, limit: 100 })}`),
  scan: () => api.post<ScanResult>('/alerts/scan'),
  ack: (id: number, payload: { note: string; silence_minutes?: number }) =>
    api.post<{ item: AlertEvent; message: string }>(`/alerts/events/${id}/ack`, payload),
  silence: (id: number, payload: { minutes: number; note: string }) =>
    api.post<{ item: AlertEvent; message: string }>(`/alerts/events/${id}/silence`, payload),
  formula: () => api.get<Record<string, unknown>>('/alerts/formula'),
};
