import { create } from 'zustand';
import { alertApi } from '../api/alert';
import type { AlertEvent, AlertRule, ScanResult } from '../types/models';

interface AlertState {
  rules: AlertRule[];
  alerts: AlertEvent[];
  stats: { total: number; firing: number; acknowledged: number; silenced: number; resolved: number };
  lastScan: ScanResult | null;
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
  scan: () => Promise<ScanResult>;
}

const emptyStats = { total: 0, firing: 0, acknowledged: 0, silenced: 0, resolved: 0 };

export const useAlertStore = create<AlertState>((set, get) => ({
  rules: [],
  alerts: [],
  stats: emptyStats,
  lastScan: null,
  loading: false,
  error: null,
  load: async () => {
    set({ loading: true, error: null });
    try {
      const [rules, alerts] = await Promise.all([alertApi.rules(), alertApi.events()]);
      set({ rules: rules.items, alerts: alerts.items, stats: alerts.stats, loading: false });
    } catch (error) {
      set({ loading: false, error: error instanceof Error ? error.message : '告警加载失败' });
    }
  },
  scan: async () => {
    set({ loading: true, error: null });
    try {
      const result = await alertApi.scan();
      set({ lastScan: result, loading: false });
      await get().load();
      return result;
    } catch (error) {
      set({ loading: false, error: error instanceof Error ? error.message : '扫描失败' });
      throw error;
    }
  },
}));
