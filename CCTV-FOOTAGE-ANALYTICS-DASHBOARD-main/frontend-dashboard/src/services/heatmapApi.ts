import { API_BASE } from '../constants';
import type { HeatmapData } from '../types';

export const heatmapApi = {
  /**
   * Fetches zone heatmap dwell-density data for a store.
   */
  getHeatmap: async (storeId?: string): Promise<HeatmapData> => {
    const res = await fetch(`${API_BASE}/heatmaps/zones`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
};
