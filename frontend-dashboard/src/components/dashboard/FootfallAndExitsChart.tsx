import React, { useMemo } from 'react';
import { Inbox } from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';
import { useApiData } from '../../hooks';
import { API_BASE } from '../../constants';
import type { DashboardMetrics } from '../../types';

interface FootfallAndExitsChartProps {
  storeId: string;
  metrics: DashboardMetrics | null;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="custom-recharts-tooltip frosted-glass">
        <p className="tooltip-label">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} style={{ color: entry.color, fontWeight: 600, fontSize: '0.85rem' }}>
            {entry.name}: {entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const calculatePeakHour = (data: any[]): string => {
  if (!data || data.length === 0) return '—';
  let maxEntries = -1;
  let peakTime = '—';

  for (const bucket of data) {
    if (bucket.Entries > maxEntries) {
      maxEntries = bucket.Entries;
      peakTime = bucket.time;
    }
  }
  return maxEntries > 0 ? peakTime : '—';
};

export const FootfallAndExitsChart: React.FC<FootfallAndExitsChartProps> = ({ storeId, metrics }) => {
  const { data, loading, error } = useApiData<any[]>(
    storeId ? `${API_BASE}/dashboard/store/${storeId}/hourly-traffic` : null
  );

  const chartData = useMemo(() => {
    if (!data) return [];
    return data;
  }, [data]);

  return (
    <div className="chart-card frosted-glass">
      <h3>
        Store Traffic Flow
        <span className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 400 }}>
          Today (Entries vs Exits)
        </span>
      </h3>

      {metrics && (
        <div className="summary-bar" style={{
          display: 'flex',
          justifyContent: 'space-around',
          padding: '10px 14px',
          background: 'rgba(255,255,255,0.02)',
          borderRadius: 8,
          border: '1px solid var(--color-border)',
          margin: '12px 0 16px 0'
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)' }}>Total Entries</span>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, marginTop: 4 }}>{metrics.totalFootfall ?? 0}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)' }}>Total Exits</span>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, marginTop: 4 }}>{metrics.totalExits ?? 0}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)' }}>Net Occupancy</span>
            <span style={{
              fontSize: '0.9rem',
              fontWeight: 700,
              marginTop: 4,
              color: ((metrics.totalFootfall ?? 0) - (metrics.totalExits ?? 0)) >= 0 ? '#10b981' : '#ef4444'
            }}>
              {((metrics.totalFootfall ?? 0) - (metrics.totalExits ?? 0)) >= 0
                ? `+${(metrics.totalFootfall ?? 0) - (metrics.totalExits ?? 0)}`
                : `${(metrics.totalFootfall ?? 0) - (metrics.totalExits ?? 0)}`}
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)' }}>Peak Hour</span>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, marginTop: 4 }}>
              {calculatePeakHour(chartData)}
            </span>
          </div>
        </div>
      )}
      <div style={{ width: '100%', height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {loading ? (
          <div className="text-muted" style={{ fontSize: '0.875rem' }}>Loading traffic flow data...</div>
        ) : error || chartData.length === 0 ? (
          <div className="no-data-state" style={{ padding: 0 }}>
            <Inbox size={48} style={{ opacity: 0.4 }} />
            <p style={{ fontSize: '0.8rem', marginTop: 8 }}>No traffic data recorded for this store yet.</p>
          </div>
        ) : (
          <ResponsiveContainer style={{ width: '100%', height: '100%' }}>
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorEntries" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ea580c" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#ea580c" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorExits" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorInStore" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ea580c" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ea580c" stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />

              <XAxis
                dataKey="time"
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                dy={10}
              />

              <YAxis
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />

              <Tooltip content={<CustomTooltip />} />

              <Area
                type="monotone"
                dataKey="InStore"
                name="In Store"
                stroke="#ea580c"
                strokeWidth={3}
                fillOpacity={1}
                fill="url(#colorInStore)"
                animationDuration={1500}
              />

              <Area
                type="monotone"
                dataKey="Entries"
                name="Entries"
                stroke="#ea580c"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#colorEntries)"
                animationDuration={1500}
              />

              <Area
                type="monotone"
                dataKey="Exits"
                name="Exits"
                stroke="#ef4444"
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#colorExits)"
                animationDuration={1500}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};
