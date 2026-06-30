export interface DashboardMetrics {
  footfall: number;
  uniqueVisitors: number;
  transactions: number;
  gmv: number;
  conversionRate: number;
  averageBasketValue: number;
  total_exits?: number;
  active_visitor_count?: number;
  
  // New metrics
  totalFootfall: number;
  engagedVisitors: number;
  verifiedConversionRate: number;
  estimatedConversionRate: number;
  queueAbandonmentRate: number;
  avgDwellMinutes: number;
}
