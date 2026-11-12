import { api } from './client';
import type { AuditEntry, Overview } from '../types/models';

export const metaApi = {
  overview: () => api.get<Overview>('/meta/overview'),
  enums: () => api.get<Record<string, unknown>>('/meta/enums'),
  audit: (limit = 30) => api.get<{ items: AuditEntry[]; total: number }>(`/audit?limit=${limit}`),
};
