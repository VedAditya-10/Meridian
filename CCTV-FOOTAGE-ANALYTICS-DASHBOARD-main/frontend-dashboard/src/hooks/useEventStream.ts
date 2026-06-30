import { useState, useEffect } from 'react';
import { dashboardApi } from '../services';
import type { LiveEvent, CameraStatus } from '../types';

interface UseEventStreamResult {
  events: LiveEvent[];
  cameraStatuses: Record<string, CameraStatus>;
  liveDetections: Record<
    string,
    { id: string; top: string; left: string; width: string; height: string; timestamp: number }[]
  >;
}

/**
 * Subscribes to the store SSE dashboard stream and parses:
 *   - telemetry      → live detection bounding boxes per camera
 *   - domain_event   → human-readable event log entries
 *   - pipeline_status → camera processing status & progress
 *
 * Automatically closes the SSE connection on unmount or when `storeId` changes.
 * Stale detections (older than 3 s) are purged on a 1-second tick.
 */
export function useEventStream(storeId: string): UseEventStreamResult {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [liveDetections, setLiveDetections] = useState<
    Record<
      string,
      { id: string; top: string; left: string; width: string; height: string; timestamp: number }[]
    >
  >({});
  const [cameraStatuses, setCameraStatuses] = useState<Record<string, CameraStatus>>({});

  // SSE subscription
  useEffect(() => {
    const sse = dashboardApi.openStream(storeId);

    sse.addEventListener('telemetry', (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      const camId: string = data.camera_id;
      const bbox = typeof data.bbox === 'string' ? JSON.parse(data.bbox) : data.bbox;
      const fw = parseFloat(data.frame_width) || 1920;
      const fh = parseFloat(data.frame_height) || 1080;

      const top    = `${(bbox.y1 / fh) * 100}%`;
      const left   = `${(bbox.x1 / fw) * 100}%`;
      const width  = `${((bbox.x2 - bbox.x1) / fw) * 100}%`;
      const height = `${((bbox.y2 - bbox.y1) / fh) * 100}%`;
      const vid    = `#V-${(data.visitor_id as string).substring(0, 4).toUpperCase()}`;

      setLiveDetections((prev) => {
        const next = { ...prev };
        // Move visitor to current camera
        for (const c of Object.keys(next)) {
          next[c] = (next[c] || []).filter((d) => d.id !== vid);
        }
        next[camId] = [
          ...(next[camId] || []).filter((d) => d.id !== vid),
          { id: vid, top, left, width, height, timestamp: Date.now() },
        ];
        return next;
      });
    });

    sse.addEventListener('domain_event', (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      const vid  = `#V-${(data.visitor_id as string).substring(0, 4).toUpperCase()}`;
      const type: string = data.event_type;

      let detail = `Visitor ${vid} — ${type.replace(/_/g, ' ')}`;
      if (data.metadata?.detail) {
        detail = data.metadata.detail;
      } else if (type === 'ENTRY') {
        detail = `Visitor ${vid} entered the store`;
      } else if (type === 'EXIT') {
        detail = `Visitor ${vid} exited the store`;
      } else if (type === 'ZONE_ENTER') {
        const zoneName = data.metadata?.zone_name || 'a zone';
        detail = `Visitor ${vid} entered ${zoneName}`;
      } else if (type === 'ZONE_DWELL') {
        const zoneName  = data.metadata?.zone_name || 'zone';
        const dwellSecs = data.metadata?.dwell_duration_seconds;
        detail = dwellSecs
          ? `Visitor ${vid} dwelling in ${zoneName} (${Math.round(dwellSecs)}s)`
          : `Visitor ${vid} dwelling in ${zoneName}`;
      } else if (type === 'BILLING_QUEUE_JOIN') {
        detail = `Visitor ${vid} stepped up to Billing Counter`;
      } else if (type === 'BILLING_QUEUE_ABANDON') {
        detail = `Visitor ${vid} left the Billing Counter`;
      }

      const newEvent: LiveEvent = {
        id:         `${Date.now()}-${Math.random()}`,
        event_type: type,
        detail,
        time:       new Date().toLocaleTimeString(),
      };

      setEvents((prev) => [newEvent, ...prev].slice(0, 30));
    });

    sse.addEventListener('pipeline_status', (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      setCameraStatuses((prev) => ({
        ...prev,
        [data.camera_id]: {
          status:   data.status as CameraStatus['status'],
          progress: parseFloat(data.progress) || 0,
        },
      }));
    });

    return () => sse.close();
  }, [storeId]);

  // Purge detections older than 3 s
  useEffect(() => {
    const iv = setInterval(() => {
      setLiveDetections((prev) => {
        const now     = Date.now();
        const next    = { ...prev };
        let changed   = false;
        for (const c of Object.keys(next)) {
          const filtered = (next[c] || []).filter((d) => now - d.timestamp < 3000);
          if (filtered.length !== (next[c] || []).length) {
            next[c] = filtered;
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }, 1000);
    return () => clearInterval(iv);
  }, []);

  return { events, cameraStatuses, liveDetections };
}
