import { api } from './client';
import type { MinePreview } from '../types/models';

export const importApi = {
  sample: async (): Promise<string> => {
    const response = await fetch('/api/imports/sample');
    if (!response.ok) throw new Error(`样本下载失败: ${response.status}`);
    return response.text();
  },
  sampleMeta: () => api.get<Record<string, unknown>>('/imports/sample/meta'),
  mine: (text: string) => api.post<MinePreview>('/imports/mine', { text, apply: false }),
  apply: (text: string) => api.post<MinePreview>('/imports/apply', { text }),
};
