import { create } from 'zustand';
import { sourceApi } from '../api/source';
import type { ParseRule, Source } from '../types/models';

interface SourceState {
  sources: Source[];
  rules: ParseRule[];
  selectedId: number | null;
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
  loadRules: (sourceId?: number) => Promise<void>;
  select: (sourceId: number) => void;
}

export const useSourceStore = create<SourceState>((set, get) => ({
  sources: [],
  rules: [],
  selectedId: null,
  loading: false,
  error: null,
  load: async () => {
    set({ loading: true, error: null });
    try {
      const response = await sourceApi.list();
      const selected = get().selectedId ?? response.items[0]?.id ?? null;
      set({ sources: response.items, selectedId: selected, loading: false });
    } catch (error) {
      set({ loading: false, error: error instanceof Error ? error.message : '日志源加载失败' });
    }
  },
  loadRules: async (sourceId) => {
    try {
      const response = await sourceApi.rules(sourceId);
      set({ rules: response.items });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '解析规则加载失败' });
    }
  },
  select: (sourceId) => {
    set({ selectedId: sourceId });
    void get().loadRules(sourceId);
  },
}));
