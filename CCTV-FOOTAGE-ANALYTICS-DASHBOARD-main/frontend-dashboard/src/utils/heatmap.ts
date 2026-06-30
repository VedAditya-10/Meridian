import { ZONE_TYPE_COLORS } from '../constants';

/**
 * Maps a dwell_time_density [0..1] value to a heat colour (blue → amber → red).
 */
export function getHeatColor(density: number): string {
  if (density < 0.33) return `rgba(249, 115, 22, ${0.4 + density})`;
  if (density < 0.66) return `rgba(245, 158, 11, ${0.5 + density * 0.5})`;
  return `rgba(239, 68, 68, ${0.6 + density * 0.4})`;
}

/**
 * Returns the colour/label metadata for a given zone type string.
 * Falls back to DISPLAY if the type is unknown.
 */
export function getZoneTypeMeta(zoneType?: string) {
  const type = zoneType?.toUpperCase() ?? 'DISPLAY';
  return ZONE_TYPE_COLORS[type] ?? ZONE_TYPE_COLORS['DISPLAY'];
}

/**
 * Infers a zone type key (QUEUE | AISLE | ENTRY_LINE | DISPLAY) from the
 * zone's human-readable name, since the heatmap API does not return a type field.
 */
export function inferZoneType(name: string): string {
  const n = name.toLowerCase();
  if (
    n.includes('queue') ||
    n.includes('billing') ||
    n.includes('checkout') ||
    n.includes('payment')
  )
    return 'QUEUE';
  if (n.includes('aisle')) return 'AISLE';
  if (
    n.includes('entrance') ||
    n.includes('entry') ||
    n.includes('gate') ||
    n.includes('door')
  )
    return 'ENTRY_LINE';
  return 'DISPLAY';
}
