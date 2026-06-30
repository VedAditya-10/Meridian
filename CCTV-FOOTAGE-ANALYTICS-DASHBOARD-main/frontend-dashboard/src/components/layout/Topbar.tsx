import React, { useState, useEffect } from 'react';

interface TopbarProps {
  activeRoute: string;
  storeName: string;
  timezone: string;
}

const RefreshIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
    <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
    <path d="M16 16h5v5" />
  </svg>
);

const BellIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
    <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
  </svg>
);

/**
 * Application top bar: page context, live timezone-aware clock, relative refreshed timer, system health dot.
 */
export const Topbar: React.FC<TopbarProps> = ({ activeRoute, storeName, timezone }) => {
  const [localTime, setLocalTime] = useState<string>('');
  const [refreshedSeconds, setRefreshedSeconds] = useState<number>(0);

  // Timezone-adjusted live clock
  useEffect(() => {
    const updateTime = () => {
      try {
        const options: Intl.DateTimeFormatOptions = {
          timeZone: timezone,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        };
        const formatter = new Intl.DateTimeFormat([], options);
        setLocalTime(formatter.format(new Date()));
      } catch {
        setLocalTime(new Date().toLocaleTimeString());
      }
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, [timezone]);

  // Refresh interval timer
  useEffect(() => {
    setRefreshedSeconds(0);
    const interval = setInterval(() => {
      setRefreshedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [activeRoute, storeName]);

  const getBreadcrumb = () => {
    const routeLabels: Record<string, string> = {
      'video-input': 'Input / Video Source',
      'overview': 'Analytics / Overview',
      'cameras': 'Analytics / Live Feeds',
      'heatmaps': 'Analytics / Zone Heatmaps',
      'anomalies': 'Analytics / Anomalies',
      'store-management': 'Settings / Store Settings'
    };
    return routeLabels[activeRoute] || 'Analytics';
  };

  const getRefreshLabel = () => {
    if (refreshedSeconds < 5) return 'Updated just now';
    return `Updated ${refreshedSeconds}s ago`;
  };

  return (
    <header className="topbar">
      {/* Left: Breadcrumbs / Context */}
      <div className="breadcrumb-area" style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-text-muted)' }}>
          {getBreadcrumb()}
        </span>
        <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
          {storeName}
        </span>
      </div>

      {/* Center: Live Store Clock */}
      <div className="store-clock" style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--color-bg-secondary)', padding: '5px 12px', borderRadius: 6, border: '1px solid var(--color-border)' }}>
        <span style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-muted)', fontWeight: 600 }}>
          Store Time
        </span>
        <span style={{ fontSize: '0.8rem', fontFamily: 'monospace', fontWeight: 700, color: 'var(--color-accent)' }}>
          {localTime || 'Initializing...'}
        </span>
      </div>

      {/* Right: Operational Status & Controls */}
      <div className="user-controls" style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <div className="system-health" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
            {getRefreshLabel()}
          </span>
          <div style={{ height: 12, width: 1, background: 'var(--color-border)' }} />
          <div className="pulse-indicator healthy" />
          <span className="health-text" style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-success)' }}>
            Operational
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button className="icon-btn" id="btn-refresh" title="Reset refresh timer" aria-label="Refresh data" onClick={() => setRefreshedSeconds(0)}>
            <RefreshIcon />
          </button>
          <button
            className="icon-btn"
            id="btn-notifications"
            title="Notifications"
            aria-label="Notifications"
          >
            <BellIcon />
          </button>
          <div className="avatar-circle" title="Platform Manager">
            PM
          </div>
        </div>
      </div>
    </header>
  );
};
