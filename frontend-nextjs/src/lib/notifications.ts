import { API_BASE, authHeaders } from '@/lib/utils'

/*
 * In-app notifications. The server stores where each one leads (`link`), so the bell, the Notifications
 * page and push messages all open the same screen. Notifications can come from any company the person can
 * open; opening one switches to its company first.
 */

export interface AppNotification {
  id: number
  company_id: number
  user_id: number
  type: string
  category: string
  title: string
  message: string
  reference_id?: string | null
  reference_type?: string | null
  link: string
  group_count: number
  is_read: boolean
  created_at?: string | null
  /** Approval notifications only: 'pending' while a decision is needed, then 'approved' or 'rejected' */
  decision?: 'pending' | 'approved' | 'rejected' | null
}

export interface NotificationPreference {
  category: string
  label: string
  description: string
  can_turn_off: boolean
  delivery: Delivery
}

export type Delivery = 'all' | 'in_app' | 'off'

export const NOTIFICATION_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'unread', label: 'Unread' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'attendance', label: 'Attendance' },
  { id: 'orders', label: 'Orders' },
  { id: 'expenses', label: 'Expenses' },
  { id: 'visits', label: 'Check-ins' },
  { id: 'alerts', label: 'Alerts' },
  { id: 'security', label: 'Security' },
] as const

export type NotificationFilter = (typeof NOTIFICATION_FILTERS)[number]['id']

/** Fired whenever notifications are read, deleted or decided, so the bell badge and open lists refresh. */
export const NOTIFICATIONS_CHANGED = 'mytally:notifications-changed'

export function announceNotificationsChanged() {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED))
}

async function call<T>(token: string, path: string, init?: RequestInit & { companyId?: number }): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders(token) }
  if (init?.companyId) headers['X-Company-ID'] = String(init.companyId)
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {}
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export function listNotifications(token: string, filter: NotificationFilter, limit: number, offset = 0) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (filter === 'unread') params.set('unread_only', 'true')
  else if (filter !== 'all') params.set('category', filter)
  return call<AppNotification[]>(token, `/notifications?${params}`)
}

export const getNotification = (token: string, id: number) => call<AppNotification>(token, `/notifications/${id}`)
export const getUnreadCount = (token: string) => call<{ count: number }>(token, '/notifications/unread-count')
export const markNotificationRead = (token: string, id: number) =>
  call(token, `/notifications/${id}/read`, { method: 'PATCH' })
export const markAllNotificationsRead = (token: string) => call(token, '/notifications/read-all', { method: 'PATCH' })
export const deleteNotification = (token: string, id: number) => call(token, `/notifications/${id}`, { method: 'DELETE' })
export const clearAllNotifications = (token: string) => call(token, '/notifications/clear-all', { method: 'DELETE' })
export const getNotificationPreferences = (token: string) =>
  call<NotificationPreference[]>(token, '/notifications/preferences')
export const updateNotificationPreference = (token: string, category: string, delivery: Delivery) =>
  call<NotificationPreference[]>(token, '/notifications/preferences', {
    method: 'PUT',
    body: JSON.stringify({ category, delivery }),
  })

/** True for approval notifications that still need a decision. */
export const needsDecision = (n: AppNotification) => n.decision === 'pending'

/** Approve or reject the attendance or expense behind an approval notification, in that notification's company. */
export async function decide(token: string, n: AppNotification, decision: 'approve' | 'reject', reason?: string) {
  const id = n.reference_id
  const opts = { method: 'POST', companyId: n.company_id }
  if (n.type === 'attendance_approval') {
    return call(token, `/attendance/admin/${decision}/${id}`, { ...opts, body: JSON.stringify({ reason: reason || null }) })
  }
  if (n.type === 'expense_created') {
    return call(token, `/expenses/${id}/status`, {
      ...opts,
      method: 'PUT',
      body: JSON.stringify({ status: decision === 'approve' ? 'approved' : 'rejected', reason: reason || null }),
    })
  }
  throw new Error('This notification has nothing to approve')
}

export function formatTimeAgo(value?: string | null): string {
  if (!value) return ''
  // The API sends naive timestamps in UTC
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`)
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000))
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
