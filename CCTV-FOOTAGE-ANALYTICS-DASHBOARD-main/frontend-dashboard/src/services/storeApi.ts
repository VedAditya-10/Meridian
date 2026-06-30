import { API_BASE } from '../constants';
import type { Store } from '../types';

export interface MeridianStoreResponse {
  id: string;
  name: string;
  address?: string | null;
  phone?: string | null;
  location?: string | null;
  timezone: string;
  min_engaged_dwell_seconds: number;
  max_cameras: number;
  cameras: number;
  created_at: string;
  updated_at: string;
}

export function mapStoreResponse(data: MeridianStoreResponse): Store {
  return {
    id: data.id,
    name: data.name,
    cameras: data.cameras,
    location: data.location ?? data.address ?? '',
    address: data.address ?? undefined,
    phone: data.phone ?? undefined,
    timezone: data.timezone,
    max_cameras: data.max_cameras,
  };
}

export async function fetchMeridianStore(): Promise<Store | null> {
  const res = await fetch(`${API_BASE}/store`);
  if (!res.ok) return null;
  const data: MeridianStoreResponse = await res.json();
  return mapStoreResponse(data);
}

export async function updateMeridianStore(payload: Partial<Store>): Promise<Store> {
  const res = await fetch(`${API_BASE}/store`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  const data: MeridianStoreResponse = await res.json();
  return mapStoreResponse(data);
}

export async function clearAnalyticsData(confirmString: string): Promise<void> {
  const res = await fetch(`${API_BASE}/store/data`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: confirmString }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
}
