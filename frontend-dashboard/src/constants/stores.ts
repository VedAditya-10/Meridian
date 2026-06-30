import type { Store } from '../types';

/** Offline fallback when the backend is unreachable. */
export const DEFAULT_STORE: Store = {
  id: 'a1b2c3d4-0001-4000-8000-000000000001',
  name: 'My Store',
  cameras: 0,
  location: '',
  address: '',
  phone: '',
  timezone: 'Asia/Kolkata',
  max_cameras: 6,
};


