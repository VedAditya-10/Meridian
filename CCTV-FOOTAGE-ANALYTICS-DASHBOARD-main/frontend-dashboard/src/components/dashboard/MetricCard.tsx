import React from 'react';
import { Skeleton } from '../ui';

interface MetricCardProps {
  id: string;
  icon: string;
  title: string;
  value: string;
  positive?: boolean;
  delta?: string;
  loading?: boolean;
  warning?: boolean;
}

const getSvgIcon = (iconName: string) => {
  const strokeWidth = 2.5;
  const size = 16;
  const color = "currentColor";
  
  if (iconName === '🚪' || iconName.includes('door') || iconName.includes('footfall')) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
        <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
        <polyline points="10 17 15 12 10 7" />
        <line x1="15" y1="12" x2="3" y2="12" />
      </svg>
    );
  }
  if (iconName === '🧑‍🤝‍🧑' || iconName.includes('user') || iconName.includes('visitor')) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    );
  }
  if (iconName === '🛒' || iconName.includes('cart') || iconName.includes('transaction')) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="8" cy="21" r="1" />
        <circle cx="19" cy="21" r="1" />
        <path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12" />
      </svg>
    );
  }
  if (iconName === '💰' || iconName.includes('gmv') || iconName.includes('money')) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="1" x2="12" y2="23" />
        <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
      </svg>
    );
  }
  if (iconName === '💳' || iconName.includes('conversion') || iconName.includes('rate')) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    );
  }
  if (iconName === '🛍️' || iconName.includes('basket') || iconName.includes('value')) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" />
        <line x1="3" y1="6" x2="21" y2="6" />
        <path d="M16 10a4 4 0 0 1-8 0" />
      </svg>
    );
  }
  return <span>{iconName}</span>;
};

/**
 * A single KPI metric card with horizontal layout, dynamic SVG icons,
 * and clear left-border accent highlights.
 */
export const MetricCard: React.FC<MetricCardProps> = ({
  id,
  icon,
  title,
  value,
  positive,
  delta,
  loading,
  warning,
}) => {
  const leftBorderColor = warning ? 'var(--color-warning)' : positive ? 'var(--color-success)' : 'var(--color-accent)';

  return (
    <div
      className={`metric-card frosted-glass ${warning ? 'warning' : positive ? 'success-card' : ''}`}
      id={id}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        borderLeft: `3px solid ${leftBorderColor}`,
        borderTop: 'none',
        borderRight: 'none',
        borderBottom: 'none',
        padding: '16px 20px',
        boxShadow: 'none'
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 36,
        height: 36,
        borderRadius: '50%',
        background: warning ? 'rgba(245, 158, 11, 0.1)' : positive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(234, 88, 12, 0.12)',
        color: leftBorderColor,
        flexShrink: 0
      }}>
        {getSvgIcon(icon)}
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1 }}>
        <h3 style={{ margin: 0, fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)', fontWeight: 600 }}>
          {title}
        </h3>
        {loading ? (
          <div style={{ marginTop: 4 }}><Skeleton height="24px" width="60%" /></div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <div
              className={`metric-value ${positive ? 'positive' : ''} ${warning ? 'text-warning' : ''}`}
              style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'monospace', letterSpacing: '-0.02em', lineSpacing: 1 }}
            >
              {value}
            </div>
            {delta && (
              <span
                className="metric-delta"
                style={{
                  fontSize: '0.68rem',
                  fontWeight: 600,
                  padding: '2px 6px',
                  borderRadius: 4,
                  background: positive ? 'rgba(16, 185, 129, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                  color: positive ? 'var(--color-success)' : 'var(--color-text-muted)',
                  marginTop: 0,
                  display: 'inline-flex'
                }}
              >
                {delta}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
