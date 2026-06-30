import React from 'react';
import { getHeatColor, getZoneTypeMeta, inferZoneType } from '../../utils';
import { ZONE_TYPE_COLORS } from '../../constants';
import type { ZoneHeatmapData } from '../../types';

interface HeatmapCardProps {
  zone: ZoneHeatmapData;
  rank?: number;
}

/**
 * Individual zone heatmap card showing dwell density, visitor count,
 * a heat bar, and a zone-type badge with inferred type colouring.
 */
export const HeatmapCard: React.FC<HeatmapCardProps> = ({ zone, rank }) => {
  const zType     = zone.zone_type || inferZoneType(zone.zone_name);
  const meta      = getZoneTypeMeta(zType);
  const heatColor = getHeatColor(zone.dwell_time_density);

  // Background intensity: scale rgba(accent, 0.02) to rgba(accent, 0.15) based on dwell_time_density
  const densityAlpha = 0.02 + zone.dwell_time_density * 0.13;
  const customBg = `rgba(234, 88, 12, ${densityAlpha})`;
  const borderGlowStyle = rank === 1 ? {
    boxShadow: '0 0 20px rgba(234, 88, 12, 0.25)',
    borderColor: 'var(--color-accent)',
    background: 'var(--color-accent-glow)'
  } : {
    borderColor: `${meta.color}30`,
    background: meta.bg || customBg
  };

  return (
    <div
      className="heatmap-zone-card frosted-glass"
      id={`zone-${zone.zone_id}`}
      style={{
        ...borderGlowStyle,
        position: 'relative'
      }}
    >
      {rank && (
        <span
          className="heatmap-rank-badge"
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            fontSize: '0.72rem',
            fontWeight: 700,
            padding: '2px 6px',
            borderRadius: 4,
            background: rank === 1 ? 'rgba(239, 68, 68, 0.15)' : 'rgba(255, 255, 255, 0.06)',
            color: rank === 1 ? 'var(--color-danger)' : 'var(--color-text-muted)',
            border: rank === 1 ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid rgba(255, 255, 255, 0.06)'
          }}
        >
          {rank === 1 ? '🔥 #1 Hottest' : `#${rank}`}
        </span>
      )}
      
      <span
        className="zone-type-badge"
        style={{ background: `${meta.color}20`, color: meta.color }}
      >
        {meta.label}
      </span>
      <div className="zone-name" style={{ marginTop: 8 }}>{zone.zone_name}</div>
      <div className="zone-density-label" style={{ color: heatColor, margin: '8px 0' }}>
        {(zone.dwell_time_density * 100).toFixed(0)}%
      </div>
      <div className="zone-visitors-label" style={{ marginBottom: 12 }}>{zone.unique_visitors} unique visitors</div>
      <div className="zone-heat-bar">
        <div
          className="zone-heat-fill"
          style={{ width: `${zone.dwell_time_density * 100}%`, background: heatColor }}
        />
      </div>
    </div>
  );
};

/**
 * Colour legend for zone types displayed above the heatmap grid.
 */
export const HeatmapLegend: React.FC = () => (
  <div style={{ display: 'flex', gap: 20, marginBottom: 8, flexWrap: 'wrap' }}>
    {Object.entries(ZONE_TYPE_COLORS).map(([type, meta]) => (
      <div
        key={type}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: '0.75rem',
          color: 'var(--color-text-muted)',
        }}
      >
        <div
          style={{ width: 10, height: 10, borderRadius: 3, background: meta.color, opacity: 0.8 }}
        />
        {meta.label}
      </div>
    ))}
  </div>
);
