import { API_BASE } from '../constants';

export interface Camera {
  id: string;
  store_id: string;
  name: string;
  camera_type: 'rtsp_stream' | 'video_file' | 'webcam';
  rtsp_url?: string | null;
  video_file_path?: string | null;
  status: 'active' | 'inactive' | 'error';
  position_index?: number | null;
  created_at: string;
  updated_at: string;
}

export interface Zone {
  id: string;
  store_id: string;
  name: string;
  zone_type: 'ENTRY_LINE' | 'DISPLAY' | 'AISLE' | 'QUEUE';
  polygon: {
    camera_ids: string[];
    points: { x: number; y: number }[];
  };
  product_category?: string | null;
  is_active: boolean;
  created_at: string;
}

export const cameraApi = {
  fetchCameras: async (): Promise<Camera[]> => {
    const res = await fetch(`${API_BASE}/cameras`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  addCamera: async (payload: Partial<Camera>): Promise<Camera> => {
    const res = await fetch(`${API_BASE}/cameras`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  updateCamera: async (id: string, payload: Partial<Camera>): Promise<Camera> => {
    const res = await fetch(`${API_BASE}/cameras/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  deleteCamera: async (id: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/cameras/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },

  testCameraConnection: async (id: string): Promise<{ status: string; detail?: string }> => {
    const res = await fetch(`${API_BASE}/cameras/${id}/test`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  fetchCameraZones: async (cameraId: string): Promise<Zone[]> => {
    const res = await fetch(`${API_BASE}/cameras/${cameraId}/zones`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },

  createCameraZone: async (cameraId: string, payload: Partial<Zone>): Promise<Zone> => {
    const res = await fetch(`${API_BASE}/cameras/${cameraId}/zones`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  updateZone: async (id: string, payload: Partial<Zone>): Promise<Zone> => {
    const res = await fetch(`${API_BASE}/zones/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  deleteZone: async (id: string): Promise<void> => {
    const res = await fetch(`${API_BASE}/zones/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
  },
};
