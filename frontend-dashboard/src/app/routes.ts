/**
 * Route configuration for the application.
 * Each entry maps a route ID to its metadata.
 */
export interface RouteConfig {
  id: string;
  icon: string;
  label: string;
}

export const ROUTES: RouteConfig[] = [
  { id: 'video-input', icon: '📹', label: 'Video Input' },
  { id: 'overview',  icon: '📊', label: 'Overview' },
  { id: 'cameras',   icon: '🎥', label: 'Live Feeds' },
  { id: 'heatmaps',  icon: '🔥', label: 'Zone Heatmaps' },
  { id: 'anomalies', icon: '⚠️', label: 'Anomalies' },
  { id: 'store-management', icon: '⚙️', label: 'Store Settings' },
] as const;

export type RouteId = typeof ROUTES[number]['id'];
