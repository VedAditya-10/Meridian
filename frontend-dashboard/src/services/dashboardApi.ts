import { API_BASE } from '../constants';
import type { DashboardMetrics, FunnelData } from '../types';

export const dashboardApi = {
  /**
   * Fetches aggregated KPI metrics for a store.
   */
  getMetrics: async (storeId?: string): Promise<DashboardMetrics> => {
    const res = await fetch(`${API_BASE}/dashboard/store`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  /**
   * Fetches the conversion funnel steps for a store.
   */
  getFunnel: async (storeId?: string): Promise<FunnelData> => {
    const res = await fetch(`${API_BASE}/dashboard/funnel`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  /**
   * Returns a live SSE EventSource for the store dashboard stream.
   * Caller is responsible for closing it.
   */
  openStream: (storeId?: string): EventSource =>
    new EventSource(`${API_BASE}/dashboard/store/stream`),
};
