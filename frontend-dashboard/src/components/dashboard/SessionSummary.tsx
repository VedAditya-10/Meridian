import React from 'react';
import { MapPin, UserMinus, Clock, Target, TrendingUp, AlertTriangle } from 'lucide-react';
import { Skeleton } from '../ui';
import type { DashboardMetrics } from '../../types';

interface SessionSummaryProps {
  metrics: DashboardMetrics | null;
  loading: boolean;
}

interface SummaryItem {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  subtitle?: string;
  highlight?: boolean;
}

/**
 * Quick-stats panel showing total exits, currently in-store count,
 * average dwell time, verified/estimated conversions, and queue abandonment.
 */
export const SessionSummary: React.FC<SessionSummaryProps> = ({ metrics, loading }) => {
  const items: SummaryItem[] = [
    {
      label: 'Currently In Store',
      value: metrics?.active_visitor_count ?? 0,
      icon: <MapPin size={16} />,
    },
    {
      label: 'Total Exits',
      value: metrics?.total_exits ?? 0,
      icon: <UserMinus size={16} />,
    },
    {
      label: 'Avg Dwell Time',
      value: metrics ? `${(metrics.avgDwellMinutes ?? 0).toFixed(1)} min` : '—',
      icon: <Clock size={16} />,
      subtitle: 'Completed sessions only'
    },
    {
      label: 'Verified Conversion',
      value: metrics ? `${(metrics.verifiedConversionRate ?? 0).toFixed(1)}%` : '—',
      icon: <Target size={16} />,
      subtitle: 'High confidence matches'
    },
    {
      label: 'Est. Conversion',
      value: metrics ? `${(metrics.estimatedConversionRate ?? 0).toFixed(1)}%` : '—',
      icon: <TrendingUp size={16} />,
      subtitle: 'Includes medium confidence'
    },
    {
      label: 'Queue Abandonment',
      value: metrics ? `${(metrics.queueAbandonmentRate ?? 0).toFixed(1)}%` : '—',
      icon: <AlertTriangle size={16} />,
      subtitle: 'Abandonment rate',
      highlight: (metrics?.queueAbandonmentRate ?? 0) > 30.0
    }
  ];

  return (
    <div className="chart-card frosted-glass" id="quick-stats">
      <h3>Session Summary</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {items.map((item) => (
          <div
            key={item.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              background: 'rgba(255,255,255,0.03)',
              borderRadius: 8,
              border: '1px solid var(--color-border)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: '1.1rem' }}>{item.icon}</span>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '0.82rem', color: 'var(--color-text-secondary)', fontWeight: 500 }}>
                  {item.label}
                </span>
                {item.subtitle && (
                  <span style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
                    {item.subtitle}
                  </span>
                )}
              </div>
            </div>
            {loading ? (
              <Skeleton width="48px" height="20px" />
            ) : (
              <span style={{
                fontWeight: 700,
                fontSize: '1rem',
                color: item.highlight ? '#ef4444' : 'inherit'
              }}>
                {typeof item.value === 'number' ? item.value.toLocaleString() : item.value}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
