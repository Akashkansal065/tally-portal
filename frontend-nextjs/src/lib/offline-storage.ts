/**
 * Offline Storage & Synchronization Helper for Field Sales
 * Provides offline caching for Customer Directory and an Offline Check-In Queue.
 */

export interface CachedCustomerDirectory {
  customers: any[]
  localities: any[]
  routes: string[]
  cachedAt: number
}

export interface OfflineCheckIn {
  id: string
  ledger_id?: number | null
  customer_profile_id?: number | null
  custom_shop_name?: string | null
  shop_name?: string | null
  latitude: number
  longitude: number
  comments?: string | null
  photo_base64?: string | null
  queued_at: string
}

const STORAGE_KEYS = {
  DIRECTORY: 'mytally_offline_customers_v1',
  PENDING_CHECKINS: 'mytally_pending_checkins_v1',
}

// ─── Directory Cache ─────────────────────────────────────────────────────────

export function saveOfflineDirectory(data: {
  customers: any[]
  localities?: any[]
  routes?: string[]
}): void {
  if (typeof window === 'undefined') return
  try {
    const payload: CachedCustomerDirectory = {
      customers: data.customers || [],
      localities: data.localities || [],
      routes: data.routes || [],
      cachedAt: Date.now(),
    }
    localStorage.setItem(STORAGE_KEYS.DIRECTORY, JSON.stringify(payload))
  } catch (err) {
    console.warn('Failed to cache directory to localStorage:', err)
  }
}

export function getOfflineDirectory(): CachedCustomerDirectory | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.DIRECTORY)
    if (!raw) return null
    return JSON.parse(raw) as CachedCustomerDirectory
  } catch (err) {
    console.warn('Failed to read offline directory cache:', err)
    return null
  }
}

// ─── Check-In Queue ──────────────────────────────────────────────────────────

export function getPendingCheckIns(): OfflineCheckIn[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.PENDING_CHECKINS)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (err) {
    console.warn('Failed to read pending check-ins:', err)
    return []
  }
}

export function queueOfflineCheckIn(item: Omit<OfflineCheckIn, 'id' | 'queued_at'>): OfflineCheckIn {
  const current = getPendingCheckIns()
  const queued: OfflineCheckIn = {
    ...item,
    id: `offline_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    queued_at: new Date().toISOString(),
  }
  const updated = [queued, ...current]
  try {
    localStorage.setItem(STORAGE_KEYS.PENDING_CHECKINS, JSON.stringify(updated))
  } catch (err) {
    console.warn('Failed to queue offline checkin:', err)
  }
  return queued
}

export function removePendingCheckIn(id: string): void {
  const current = getPendingCheckIns()
  const updated = current.filter((c) => c.id !== id)
  try {
    localStorage.setItem(STORAGE_KEYS.PENDING_CHECKINS, JSON.stringify(updated))
  } catch (err) {
    console.warn('Failed to update pending check-ins:', err)
  }
}

export async function syncPendingCheckIns(
  apiBase: string,
  authHeaders: (token?: any) => Record<string, string>,
  token?: string | null
): Promise<{ synced: number; failed: number }> {
  const pending = getPendingCheckIns()
  if (pending.length === 0) return { synced: 0, failed: 0 }

  let synced = 0
  let failed = 0

  for (const item of pending) {
    try {
      const payload = {
        ledger_id: item.ledger_id || null,
        customer_profile_id: item.customer_profile_id || null,
        custom_shop_name: item.custom_shop_name || item.shop_name || null,
        latitude: item.latitude,
        longitude: item.longitude,
        comments: item.comments ? `${item.comments} [Queued Offline: ${new Date(item.queued_at).toLocaleTimeString()}]` : `[Queued Offline: ${new Date(item.queued_at).toLocaleTimeString()}]`,
        photo_base64: item.photo_base64 || null,
      }

      const res = await fetch(`${apiBase}/visits/check-in`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (res.ok) {
        removePendingCheckIn(item.id)
        synced++
      } else {
        failed++
      }
    } catch (err) {
      console.warn(`Failed to sync check-in ${item.id}:`, err)
      failed++
    }
  }

  return { synced, failed }
}
