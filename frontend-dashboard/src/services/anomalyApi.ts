import { API_BASE } from '../constants';
import type { Anomaly } from '../types';

export const anomalyApi = {
  /**
   * Fetches the current list of detected anomalies for a store.
   */
  getAnomalies: async (storeId?: string): Promise<Anomaly[]> => {
    const res = await fetch(`${API_BASE}/store/anomalies`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
};
