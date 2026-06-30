export interface ZoneHeatmapData {
  zone_id: string;
  zone_name: string;
  dwell_time_density: number;
  unique_visitors: number;
}

export interface HeatmapData {
  store_id: string;
  zones: ZoneHeatmapData[];
}
