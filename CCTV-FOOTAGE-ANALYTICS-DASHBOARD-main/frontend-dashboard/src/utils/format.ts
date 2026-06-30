/**
 * Formats a duration in seconds into "Xm Ys" notation.
 * e.g. formatTime(125) → "2m 5s"
 */
export function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

/**
 * Formats a number as a percentage string with 1 decimal place.
 * e.g. formatPercent(42.5678) → "42.6%"
 */
export function formatPercent(n: number): string {
  return `${n.toFixed(1)}%`;
}

/**
 * Formats a number as a USD currency string.
 * e.g. formatCurrency(1234.5) → "$1,234.50"
 */
export function formatCurrency(val: number): string {
  return `$${val.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
