import { create } from 'zustand';
import { templateApi } from '../api/template';
import type { Template } from '../types/models';

interface TemplateState {
  templates: Template[];
  selected: Template | null;
  filter: { status: string; search: string };
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
  select: (template: Template) => void;
  setFilter: (patch: Partial<{ status: string; search: string }>) => void;
}

export const useTemplateStore = create<TemplateState>((set, get) => ({
  templates: [],
  selected: null,
  filter: { status: '', search: '' },
  loading: false,
  error: null,
  load: async () => {
    set({ loading: true, error: null });
    try {
      const { status, search } = get().filter;
      const response = await templateApi.list({ status: status || undefined, search: search || undefined });
      set({ templates: response.items, loading: false });
      if (response.items.length && !get().selected) set({ selected: response.items[0] });
    } catch (error) {
      set({ loading: false, error: error instanceof Error ? error.message : '模板加载失败' });
    }
  },
  select: (template) => set({ selected: template }),
  setFilter: (patch) => set({ filter: { ...get().filter, ...patch } }),
}));
