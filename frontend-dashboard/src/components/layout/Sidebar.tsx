import React, { useState, useEffect } from 'react';
import {
  LayoutDashboard,
  Video,
  Flame,
  AlertTriangle,
  Upload,
  Settings,
  Eye,
  MapPin
} from 'lucide-react';
import { API_BASE } from '../../constants';
import type { Store } from '../../types';

interface NavItem {
  id: string;
  icon: React.ReactNode;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview', icon: <LayoutDashboard size={18} />, label: 'Overview' },
  { id: 'cameras', icon: <Video size={18} />, label: 'Live Feeds' },
  { id: 'heatmaps', icon: <Flame size={18} />, label: 'Zone Heatmaps' },
  { id: 'anomalies', icon: <AlertTriangle size={18} />, label: 'Anomalies' },
];

interface SidebarProps {
  activeRoute: string;
  onNavigate: (route: string) => void;
  store: Store;
}

const EyeIcon = () => (
  <Eye size={22} strokeWidth={2.5} color="var(--color-accent)" />
);

/**
 * Meridian sidebar: brand, store summary, navigation, pipeline status.
 */
export const Sidebar: React.FC<SidebarProps> = ({
  activeRoute,
  onNavigate,
  store,
}) => {
  const [activeCamsCount, setActiveCamsCount] = useState<number>(0);

  useEffect(() => {
    const fetchActiveCount = async () => {
      try {
        const res = await fetch(`${API_BASE}/pipeline/status`);
        if (res.ok) {
          const data = await res.json();
          const active = data.filter((j: { status: string }) => j.status === 'PROCESSING').length;
          setActiveCamsCount(active);
        }
      } catch {
        // ignore
      }
    };
    fetchActiveCount();
    const interval = setInterval(fetchActiveCount, 5000);
    return () => clearInterval(interval);
  }, []);

  const locationLabel = store.address || store.location || 'No address set';

  return (
    <aside className="sidebar frosted-glass">
      <div className="brand-header">
        <div className="brand-logo-glow">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <EyeIcon />
          </div>
        </div>
        <h1 className="brand-text">Meridian</h1>
      </div>

      <div className="store-selector-widget">
        <label>Store</label>
        <div
          style={{
            fontSize: '0.9rem',
            fontWeight: 600,
            color: 'var(--color-text-primary)',
            marginTop: 4,
          }}
        >
          {store.name}
        </div>
        <div
          style={{
            fontSize: '0.72rem',
            color: 'var(--color-text-muted)',
            marginTop: 4,
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <MapPin size={12} className="text-muted" />
          {locationLabel} · {store.cameras}/{store.max_cameras ?? 6} cams
        </div>
      </div>

      <nav className="nav-menu" aria-label="Main navigation">
        <div className="nav-section-label">Input</div>
        <button
          id="nav-video-input"
          className={`nav-button ${activeRoute === 'video-input' ? 'active' : ''}`}
          onClick={() => onNavigate('video-input')}
          aria-current={activeRoute === 'video-input' ? 'page' : undefined}
        >
          <span className="icon"><Upload size={18} /></span>
          Video Input
        </button>

        <div className="nav-section-label">Analytics</div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            id={`nav-${item.id}`}
            className={`nav-button ${activeRoute === item.id ? 'active' : ''}`}
            onClick={() => onNavigate(item.id)}
            aria-current={activeRoute === item.id ? 'page' : undefined}
          >
            <span className="icon">{item.icon}</span>
            {item.label}
          </button>
        ))}

        <div className="nav-section-label">Settings</div>
        <button
          id="nav-store-management"
          className={`nav-button ${activeRoute === 'store-management' ? 'active' : ''}`}
          onClick={() => onNavigate('store-management')}
          aria-current={activeRoute === 'store-management' ? 'page' : undefined}
        >
          <span className="icon"><Settings size={18} /></span>
          Store Settings
        </button>
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-badge">
          <div className="pulse-indicator healthy" />
          {activeCamsCount > 0 ? `${activeCamsCount} Pipeline Active` : 'Pipeline Idle'}
        </div>
      </div>
    </aside>
  );
};
