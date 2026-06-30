export interface FunnelStep {
  step_name: string;
  visitor_count: number;
  conversion_rate_from_previous: number | null;
}

export interface FunnelData {
  store_id: string;
  steps: FunnelStep[];
}
