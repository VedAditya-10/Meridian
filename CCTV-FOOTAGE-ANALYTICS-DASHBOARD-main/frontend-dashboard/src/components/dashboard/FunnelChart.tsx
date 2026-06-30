import React from 'react';
import { Inbox } from 'lucide-react';
import { Skeleton } from '../ui';
import { FUNNEL_COLORS } from '../../constants';
import type { FunnelData } from '../../types';

interface FunnelChartProps {
  data: FunnelData | null;
  loading: boolean;
}

/**
 * Horizontal bar funnel chart with drop-off labels and conversion badges.
 */
export const FunnelChart: React.FC<FunnelChartProps> = ({ data, loading }) => {
  const funnelMax = data?.steps?.[0]?.visitor_count || 1;

  return (
    <div className="chart-card frosted-glass" id="funnel-chart">
      <h3>
        Conversion Funnel
        <span className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 400 }}>
          Last 24h (Entries → Dwells → checkouts)
        </span>
      </h3>

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} height="48px" />
          ))}
        </div>
      ) : !data || !data.steps || data.steps.length === 0 ? (
        <div className="no-data-state" style={{ height: 180 }}>
          <Inbox size={48} className="icon" style={{ opacity: 0.4 }} />
          <p style={{ fontSize: '0.8rem', marginTop: 8 }}>No conversion funnel data available yet.</p>
        </div>
      ) : (
        <div className="funnel-chart" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {data.steps.map((step, i) => {
            const conversionPct = (step.visitor_count / funnelMax) * 100;
            return (
              <div className="funnel-step" key={step.step_name} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div className="funnel-step-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="funnel-step-name" style={{ fontWeight: 600, fontSize: '0.85rem' }}>{step.step_name}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span className="funnel-step-count" style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.9rem' }}>
                      {step.visitor_count.toLocaleString()}
                    </span>
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        color: FUNNEL_COLORS[i],
                        background: `${FUNNEL_COLORS[i]}15`,
                        border: `1px solid ${FUNNEL_COLORS[i]}30`,
                        padding: '2px 6px',
                        borderRadius: 4
                      }}
                    >
                      {conversionPct.toFixed(0)}%
                    </span>
                  </div>
                </div>
                <div className="funnel-bar-bg" style={{ height: 8, background: 'rgba(255, 255, 255, 0.03)', borderRadius: 4, overflow: 'hidden' }}>
                  <div
                    className="funnel-bar-fill"
                    style={{
                      height: '100%',
                      width: `${conversionPct}%`,
                      background: FUNNEL_COLORS[i],
                      borderRadius: 4,
                      transition: 'width 1s ease-out'
                    }}
                  />
                </div>
                {step.conversion_rate_from_previous !== null &&
                  step.conversion_rate_from_previous !== undefined && (
                    <div className="funnel-drop" style={{ fontSize: '0.7rem', color: 'var(--color-red)', fontWeight: 500, display: 'flex', justifyContent: 'flex-end', marginTop: 2 }}>
                      ↓ {(100 - step.conversion_rate_from_previous).toFixed(1)}% drop-off
                    </div>
                  )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
