/**
 * API base URL — configured via VITE_API_BASE_URL environment variable.
 * For local development: set in frontend-dashboard/.env
 * For production: set in your hosting provider's environment config (Vercel, Railway, etc.)
 *
 * Falls back to localhost:8000 only in dev when the env var is not set.
 */
export const API_BASE: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
