import React, { useMemo, useState } from 'react';
import { Inbox } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts';
import { useApiData } from '../../hooks';
import { API_BASE } from '../../constants';

interface ProductEngagementChartProps {
  storeId: string;
}

const CustomTooltip = ({ active, payload, mode }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="custom-recharts-tooltip frosted-glass">
        <p className="tooltip-label" style={{ fontWeight: 600, fontSize: '0.85rem' }}>{data.name}</p>
        <p style={{ color: data.color, fontWeight: 700, fontSize: '0.9rem', marginTop: 4 }}>
          {mode === 'engagement'
            ? `${data.value}% Dwell Density`
            : `₹${data.value.toLocaleString()} GMV`}
        </p>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.72rem', marginTop: 2 }}>
          {data.rawDwell} Dwell Instances
        </p>
      </div>
    );
  }
  return null;
};

export const ProductEngagementChart: React.FC<ProductEngagementChartProps> = ({ storeId }) => {
  const [mode, setMode] = useState<'engagement' | 'revenue'>('engagement');

  const todayStr = useMemo(() => {
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }, []);

  const { data, loading, error } = useApiData<any[]>(
    storeId ? `${API_BASE}/stores/${storeId}/section-performance?date=${todayStr}` : null,
    5000
  );

  const chartData = useMemo(() => {
    if (!data) return [];

    return data
      .map((item: any) => ({
        name: item.productCategory,
        value: mode === 'engagement' ? item.dwellDensityPercent : item.totalGmv,
        rawDwell: item.dwellCount,
        color: mode === 'engagement' ? '#ea580c' : '#f97316',
      }))
      .sort((a: any, b: any) => b.value - a.value);
  }, [data, mode]);

  return (
    <div className="chart-card frosted-glass">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>
          Section Performance
          <span className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 400, display: 'block', marginTop: 2 }}>
            {mode === 'engagement' ? 'Browsing Zone Engagement (% Dwell)' : 'Category Sales GMV (₹)'}
          </span>
        </h3>
        <div className="toggle-group" style={{
          display: 'flex',
          background: 'rgba(255,255,255,0.05)',
          borderRadius: 6,
          padding: 2,
          border: '1px solid var(--color-border)'
        }}>
          <button
            onClick={() => setMode('engagement')}
            style={{
              background: mode === 'engagement' ? 'var(--color-accent)' : 'transparent',
              color: '#fff',
              border: 'none',
              borderRadius: 4,
              padding: '6px 12px',
              fontSize: '0.75rem',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'background 0.2s'
            }}
          >
            Engagement
          </button>
          <button
            onClick={() => setMode('revenue')}
            style={{
              background: mode === 'revenue' ? 'var(--color-accent)' : 'transparent',
              color: '#fff',
              border: 'none',
              borderRadius: 4,
              padding: '6px 12px',
              fontSize: '0.75rem',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'background 0.2s'
            }}
          >
            Revenue
          </button>
        </div>
      </div>
      <div style={{ width: '100%', height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {loading ? (
          <div className="text-muted" style={{ fontSize: '0.875rem' }}>Loading performance data...</div>
        ) : error || chartData.length === 0 ? (
          <div className="no-data-state" style={{ padding: 0 }}>
            <Inbox size={48} style={{ opacity: 0.4 }} />
            <p style={{ fontSize: '0.8rem', marginTop: 8 }}>No section data available.</p>
          </div>
        ) : (
          <ResponsiveContainer style={{ width: '100%', height: '100%' }}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 10, right: 15, left: 10, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />

              <XAxis
                type="number"
                tickFormatter={v => mode === 'engagement' ? `${v}%` : `₹${v}`}
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />

              <YAxis
                type="category"
                dataKey="name"
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                width={100}
              />

              <Tooltip content={<CustomTooltip mode={mode} />} cursor={{ fill: 'rgba(255,255,255,0.02)' }} />

              <Bar
                dataKey="value"
                radius={[0, 4, 4, 0]}
                barSize={16}
                animationDuration={1500}
              >
                {chartData.map((entry: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};
