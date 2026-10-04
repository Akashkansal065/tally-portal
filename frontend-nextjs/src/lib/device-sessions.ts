import { API_BASE, authHeaders } from '@/lib/utils'

/** A signed-in (or signed-out) device, as returned by the backend's session endpoints. */
export interface DeviceSession {
  session_id: number
  user_id: number
  username?: string
  device_id: string | null
  client_type: 'web' | 'android' | 'ios' | 'sync-agent' | 'api' | null
  device_type: 'mobile' | 'tablet' | 'desktop' | null
  device_name: string
  os_name: string | null
  browser_name: string | null
  app_version: string | null
  ip_address: string | null
  created_at: string | null
  last_active_at: string | null
  expires_at: string | null
  revoked_at: string | null
  revoke_reason: string | null
  revoked_by_user_id: number | null
  is_current: boolean
  is_blocked: boolean
  is_active_now: boolean
  /** Signed in before device tracking; no device details */
  legacy: boolean
}

export interface BlockedDevice {
  blocked_device_id: number
  user_id: number
  device_id: string
  device_name: string | null
  client_type: string | null
  device_type: string | null
  reason: string | null
  blocked_by_user_id: number | null
  blocked_by: string | null
  created_at: string | null
}

export interface CompanySessionSummary {
  total: number
  active_now: number
  mobile: number
  tablet: number
  desktop: number
  sync_agent: number
  older_sessions: number
}

async function request<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers: { ...authHeaders(token), ...(init.headers || {}) } })
  if (!res.ok) {
    let message = `Request failed (HTTP ${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
    } catch {}
    throw new Error(message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ── self-service ──
export const listMySessions = (token: string) =>
  request<DeviceSession[]>(token, '/auth/me/sessions', { cache: 'no-store' })
export const revokeMySession = (token: string, sessionId: number) =>
  request<{ revoked: number; was_current: boolean }>(token, `/auth/me/sessions/${sessionId}/revoke`, { method: 'POST' })
export const revokeMyOtherSessions = (token: string) =>
  request<{ revoked: number }>(token, '/auth/me/sessions/revoke-others', { method: 'POST' })

// ── admin ──
export const listUserSessions = (token: string, userId: number, status: 'active' | 'all' = 'active') =>
  request<DeviceSession[]>(token, `/admin/users/${userId}/sessions?status=${status}`, { cache: 'no-store' })
export const adminRevokeSession = (token: string, sessionId: number) =>
  request<{ revoked: number }>(token, `/admin/sessions/${sessionId}/revoke`, { method: 'POST' })
export const adminRevokeAllSessions = (token: string, userId: number) =>
  request<{ revoked: number }>(token, `/admin/users/${userId}/sessions/revoke-all`, {
    method: 'POST',
    body: JSON.stringify({ keep_current: true }),
  })
export const adminBlockDevice = (token: string, sessionId: number, reason?: string) =>
  request<{ revoked: number; blocked_device_id: number }>(token, `/admin/sessions/${sessionId}/block`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason?.trim() || null }),
  })
export const listBlockedDevices = (token: string, userId: number) =>
  request<BlockedDevice[]>(token, `/admin/users/${userId}/blocked-devices`, { cache: 'no-store' })
export const unblockDevice = (token: string, blockedDeviceId: number) =>
  request<void>(token, `/admin/blocked-devices/${blockedDeviceId}`, { method: 'DELETE' })

export interface CompanySessionFilters {
  q?: string
  deviceType?: string
  clientType?: string
  activeNow?: boolean
  includeOlder?: boolean
}

export const listCompanySessions = (token: string, filters: CompanySessionFilters = {}) => {
  const params = new URLSearchParams()
  if (filters.q?.trim()) params.set('q', filters.q.trim())
  if (filters.deviceType) params.set('device_type', filters.deviceType)
  if (filters.clientType) params.set('client_type', filters.clientType)
  if (filters.activeNow) params.set('active_now', 'true')
  if (filters.includeOlder) params.set('include_older', 'true')
  const query = params.toString()
  return request<{ summary: CompanySessionSummary; sessions: DeviceSession[] }>(
    token, `/admin/sessions${query ? `?${query}` : ''}`, { cache: 'no-store' }
  )
}

/** "Active now", "5 min ago", "3 days ago", or a date for older activity. */
export function lastActiveLabel(session: Pick<DeviceSession, 'is_active_now' | 'last_active_at'>): string {
  if (session.is_active_now) return 'Active now'
  return relativeTime(session.last_active_at) ?? 'Not used since tracking began'
}

export function relativeTime(iso: string | null): string | null {
  if (!iso) return null
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return null
  const seconds = Math.round((Date.now() - then) / 1000)
  const rtf = new Intl.RelativeTimeFormat('en-IN', { numeric: 'auto' })
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return rtf.format(-Math.round(seconds / 60), 'minute')
  if (seconds < 86400) return rtf.format(-Math.round(seconds / 3600), 'hour')
  if (seconds < 86400 * 30) return rtf.format(-Math.round(seconds / 86400), 'day')
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export const CLIENT_LABELS: Record<string, string> = {
  web: 'Web',
  android: 'Android app',
  ios: 'iOS app',
  'sync-agent': 'Sync Agent',
  api: 'API',
}

export const REVOKE_REASON_LABELS: Record<string, string> = {
  logout: 'Signed out',
  self_revoke: 'Signed out from another device',
  admin_revoke: 'Signed out by an admin',
  admin_revoke_all: 'Signed out by an admin (all devices)',
  blocked: 'Device blocked',
  password_change: 'Password changed',
  deactivated: 'Account deactivated',
  replaced: 'Signed in again on this device',
  device_limit: 'Device limit reached',
}
