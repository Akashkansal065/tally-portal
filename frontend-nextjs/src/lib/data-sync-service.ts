/**
 * Centralized, Permission-Aware Data Synchronization Service
 * 
 * Manages caching, background revalidation, and delta syncing across all data domains.
 * Reads UserPermissions so that field users (sales reps) only fetch and store data
 * they are authorized to access, saving bandwidth, storage, and battery.
 */

import { API_BASE, authHeaders } from '@/lib/utils'
import { UserPermissions } from '@/context/AuthContext'
import {
  getAllCachedCustomers,
  saveAllCachedCustomers,
  mergeCustomerDelta,
  getSyncTimestamp,
  setSyncTimestamp,
  getSyncMetadata,
  getCachedDomainData,
  setCachedDomainData,
} from '@/lib/offline-storage'

export interface SyncReport {
  syncedDomains: string[]
  skippedDomains: string[]
  errors: Record<string, string>
  timestamp: number
}

export interface DomainFreshness {
  domain: string
  lastSyncedAt: number | null
  isStale: boolean
  label: string
}

// Default TTLs per domain (in milliseconds)
export const DOMAIN_TTLS: Record<string, number> = {
  customers: 5 * 60 * 1000,      // 5 mins (delta-synced)
  stocks: 15 * 60 * 1000,        // 15 mins SWR
  reports: 30 * 60 * 1000,       // 30 mins SWR + last-modified check
  ledgers: 15 * 60 * 1000,       // 15 mins SWR
  outstanding: 10 * 60 * 1000,   // 10 mins SWR
  dashboard: 10 * 60 * 1000,     // 10 mins SWR
  localities: 30 * 60 * 1000,    // 30 mins
  recent_visits: 5 * 60 * 1000,  // 5 mins
}

/**
 * Dispatches custom window event so active pages can react immediately without full reload
 */
function notifyDataUpdated(domain: string, extra?: any) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent('mytally:data-updated', {
        detail: { domain, timestamp: Date.now(), ...extra },
      })
    )
  }
}

// ─── Master Permission-Aware Sync Orchestrator ──────────────────────────────

/**
 * Master sync orchestrator — called by OfflineSyncManager on mount and reconnect.
 * STRICTLY inspects permissions: only fetches and caches domains the user can access.
 */
export async function syncAllPermittedDomains(
  token: string,
  permissions: UserPermissions
): Promise<SyncReport> {
  const syncedDomains: string[] = []
  const skippedDomains: string[] = []
  const errors: Record<string, string> = {}

  if (!token) {
    return { syncedDomains, skippedDomains, errors: { auth: 'No token' }, timestamp: Date.now() }
  }

  const tasks: Promise<void>[] = []

  // 1. Customers Domain (Sales reps & Admin)
  if (permissions.showCustomers || permissions.showCheckIn) {
    tasks.push(
      (async () => {
        try {
          await syncCustomersDelta(token)
          syncedDomains.push('customers')
        } catch (e: any) {
          errors['customers'] = e.message || 'Customer sync failed'
        }
      })()
    )
  } else {
    skippedDomains.push('customers')
  }

  // 2. Stock Items Domain
  if (permissions.showStocks) {
    tasks.push(
      (async () => {
        try {
          await syncStockItems(token)
          syncedDomains.push('stocks')
        } catch (e: any) {
          errors['stocks'] = e.message || 'Stock sync failed'
        }
      })()
    )
  } else {
    skippedDomains.push('stocks')
  }

  // 3. Reports Domain (Admin or users with showReports)
  if (permissions.showReports || permissions.isAdmin) {
    tasks.push(
      (async () => {
        try {
          await syncReportsIfChanged(token)
          syncedDomains.push('reports')
        } catch (e: any) {
          errors['reports'] = e.message || 'Reports sync check failed'
        }
      })()
    )
  } else {
    skippedDomains.push('reports')
  }

  // 4. Ledgers Domain
  if (permissions.showLedger) {
    tasks.push(
      (async () => {
        try {
          await syncLedgers(token)
          syncedDomains.push('ledgers')
        } catch (e: any) {
          errors['ledgers'] = e.message || 'Ledger sync failed'
        }
      })()
    )
  } else {
    skippedDomains.push('ledgers')
  }

  // 5. Outstanding / Aging Domain
  if (permissions.showPayments) {
    tasks.push(
      (async () => {
        try {
          await syncOutstanding(token)
          syncedDomains.push('outstanding')
        } catch (e: any) {
          errors['outstanding'] = e.message || 'Outstanding sync failed'
        }
      })()
    )
  } else {
    skippedDomains.push('outstanding')
  }

  // 6. Recent Visits (Check-in domain)
  if (permissions.showCheckIn) {
    tasks.push(
      (async () => {
        try {
          await syncRecentVisits(token)
          syncedDomains.push('recent_visits')
        } catch (e: any) {
          errors['recent_visits'] = e.message || 'Recent visits sync failed'
        }
      })()
    )
  } else {
    skippedDomains.push('recent_visits')
  }

  // 7. Localities & Routes (always synced — lightweight filter metadata)
  tasks.push(
    (async () => {
      try {
        await syncLocalities(token)
        syncedDomains.push('localities')
      } catch (e: any) {
        errors['localities'] = e.message || 'Localities sync failed'
      }
    })()
  )

  await Promise.allSettled(tasks)

  return {
    syncedDomains,
    skippedDomains,
    errors,
    timestamp: Date.now(),
  }
}

// ─── Domain Sync & Load Implementations ───────────────────────────────────────

/**
 * 1. CUSTOMERS: Delta sync with since_ts tracking
 */
export async function syncCustomersDelta(token: string): Promise<any[]> {
  const sinceTs = await getSyncTimestamp('customers')

  // If we have never synced before, do a full initial fetch
  if (!sinceTs) {
    const res = await fetch(`${API_BASE}/customers?location_status=all&sort_by=name`, {
      headers: authHeaders(token),
    })
    if (!res.ok) throw new Error(`Customers fetch failed: ${res.status}`)
    const data = await res.json()
    const custList = data.customers || []
    await saveAllCachedCustomers(custList)
    const serverTs = data.server_ts || new Date().toISOString()
    await setSyncTimestamp('customers', serverTs, custList.length)
    notifyDataUpdated('customers', { count: custList.length })
    return custList
  }

  // Delta request: only ask for changes since sinceTs
  const deltaRes = await fetch(`${API_BASE}/customers/delta?since_ts=${encodeURIComponent(sinceTs)}`, {
    headers: authHeaders(token),
  })

  if (!deltaRes.ok) throw new Error(`Customers delta failed: ${deltaRes.status}`)
  const delta = await deltaRes.json()

  // Full refresh requested by server (e.g. > 24 hours stale)
  if (delta.full_refresh_required) {
    const res = await fetch(`${API_BASE}/customers?location_status=all&sort_by=name`, {
      headers: authHeaders(token),
    })
    if (!res.ok) throw new Error(`Customers full fetch failed: ${res.status}`)
    const data = await res.json()
    const custList = data.customers || []
    await saveAllCachedCustomers(custList)
    await setSyncTimestamp('customers', delta.server_ts || new Date().toISOString(), custList.length)
    notifyDataUpdated('customers', { count: custList.length })
    return custList
  }

  const updated = delta.updated_customers || []
  const deleted = delta.deleted_ids || []

  if (updated.length > 0 || deleted.length > 0) {
    const all = await mergeCustomerDelta(updated, deleted)
    await setSyncTimestamp('customers', delta.server_ts, all.length)
    notifyDataUpdated('customers', { updatedCount: updated.length, deletedCount: deleted.length })
    return all
  }

  // Nothing changed, refresh sync timestamp
  await setSyncTimestamp('customers', delta.server_ts)
  return await getAllCachedCustomers()
}

/**
 * Caller function for Customers page: returns cached instantly, then syncs delta silently.
 */
export async function loadCustomers(
  token: string,
  options?: { forceFullRefresh?: boolean }
): Promise<{ customers: any[]; fromCache: boolean }> {
  const cached = await getAllCachedCustomers()

  // If forced full refresh
  if (options?.forceFullRefresh) {
    const res = await fetch(`${API_BASE}/customers?location_status=all&sort_by=name`, {
      headers: authHeaders(token),
    })
    if (res.ok) {
      const data = await res.json()
      const custList = data.customers || []
      await saveAllCachedCustomers(custList)
      await setSyncTimestamp('customers', data.server_ts || new Date().toISOString(), custList.length)
      notifyDataUpdated('customers', { count: custList.length })
      return { customers: custList, fromCache: false }
    }
  }

  // If cache exists, trigger background delta revalidation and return cache immediately
  if (cached && cached.length > 0) {
    syncCustomersDelta(token).catch(err => {
      console.warn('[DataSync] Background customer delta sync failed:', err)
    })
    return { customers: cached, fromCache: true }
  }

  // Cold cache: fetch full list synchronously
  try {
    const fresh = await syncCustomersDelta(token)
    return { customers: fresh, fromCache: false }
  } catch {
    return { customers: cached || [], fromCache: true }
  }
}

/**
 * 2. STOCKS: 15-minute SWR Cache
 */
export async function syncStockItems(token: string): Promise<any[]> {
  const res = await fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) })
  if (!res.ok) throw new Error(`Stock fetch failed: ${res.status}`)
  const items = await res.json()
  const list = Array.isArray(items) ? items : []
  await setCachedDomainData('stocks', list, DOMAIN_TTLS.stocks)
  notifyDataUpdated('stocks', { count: list.length })
  return list
}

export async function loadStockItems(
  token: string,
  forceRefresh?: boolean
): Promise<{ items: any[]; fromCache: boolean }> {
  const cached = await getCachedDomainData<any[]>('stocks')

  if (!forceRefresh && cached && cached.data) {
    if (cached.isStale) {
      // Revalidate in background
      syncStockItems(token).catch(err => console.warn('[DataSync] Stock revalidation failed:', err))
    }
    return { items: cached.data, fromCache: true }
  }

  try {
    const fresh = await syncStockItems(token)
    return { items: fresh, fromCache: false }
  } catch {
    return { items: cached?.data || [], fromCache: true }
  }
}

/**
 * 3. REPORTS: Lightweight last-modified check before 12 fetches
 */
export interface ReportsLastModified {
  last_voucher_at: string | null
  voucher_count: number
  last_stock_movement_at: string | null
}

export async function checkReportsLastModified(token: string): Promise<ReportsLastModified | null> {
  try {
    const res = await fetch(`${API_BASE}/reports/last-modified`, { headers: authHeaders(token) })
    if (res.ok) return await res.json()
  } catch (err) {
    console.warn('[DataSync] Reports last-modified check failed:', err)
  }
  return null
}

export async function syncReportsIfChanged(token: string): Promise<boolean> {
  const lastMod = await checkReportsLastModified(token)
  if (!lastMod) return false

  const meta = await getSyncMetadata('reports')
  const cachedLastVoucher = meta?.extra?.last_voucher_at
  const cachedCount = meta?.extra?.voucher_count

  // If nothing has changed in the database, skip fetching
  if (
    cachedLastVoucher &&
    cachedLastVoucher === lastMod.last_voucher_at &&
    cachedCount === lastMod.voucher_count
  ) {
    return false // Up to date
  }

  // Stale or changed: save new metadata
  await setSyncTimestamp('reports', lastMod.last_voucher_at || new Date().toISOString(), lastMod.voucher_count, lastMod)
  notifyDataUpdated('reports', { lastModified: lastMod })
  return true
}

/**
 * Cached Reports Data Loader for reports page
 */
export async function loadReportsData(
  token: string,
  fromDate?: string,
  toDate?: string,
  forceRefresh?: boolean
): Promise<{ data: any | null; fromCache: boolean; needsFetch: boolean }> {
  const cacheKey = `reports_${fromDate || 'all'}_${toDate || 'all'}`
  const cached = await getCachedDomainData<any>(cacheKey)

  if (!forceRefresh && cached && cached.data && !cached.isStale) {
    return { data: cached.data, fromCache: true, needsFetch: false }
  }

  return { data: cached?.data || null, fromCache: Boolean(cached?.data), needsFetch: true }
}

export async function saveReportsData(
  cacheKeySuffix: string,
  data: any
): Promise<void> {
  const cacheKey = `reports_${cacheKeySuffix}`
  await setCachedDomainData(cacheKey, data, DOMAIN_TTLS.reports)
}

/**
 * 4. LEDGERS: 15-minute SWR Cache
 */
export async function syncLedgers(token: string): Promise<any[]> {
  const res = await fetch(`${API_BASE}/ledgers`, { headers: authHeaders(token) })
  if (!res.ok) throw new Error(`Ledgers fetch failed: ${res.status}`)
  const ledgers = await res.json()
  const list = Array.isArray(ledgers) ? ledgers : []
  await setCachedDomainData('ledgers', list, DOMAIN_TTLS.ledgers)
  notifyDataUpdated('ledgers', { count: list.length })
  return list
}

export async function loadLedgers(
  token: string,
  forceRefresh?: boolean
): Promise<{ ledgers: any[]; fromCache: boolean }> {
  const cached = await getCachedDomainData<any[]>('ledgers')

  if (!forceRefresh && cached && cached.data) {
    if (cached.isStale) {
      syncLedgers(token).catch(err => console.warn('[DataSync] Ledgers revalidation failed:', err))
    }
    return { ledgers: cached.data, fromCache: true }
  }

  try {
    const fresh = await syncLedgers(token)
    return { ledgers: fresh, fromCache: false }
  } catch {
    return { ledgers: cached?.data || [], fromCache: true }
  }
}

/**
 * 5. OUTSTANDING / AGING: 10-minute SWR Cache
 */
export async function syncOutstanding(token: string): Promise<any> {
  const res = await fetch(`${API_BASE}/payment/aging/dashboard`, { headers: authHeaders(token) })
  if (!res.ok) throw new Error(`Outstanding fetch failed: ${res.status}`)
  const data = await res.json()
  await setCachedDomainData('outstanding', data, DOMAIN_TTLS.outstanding)
  notifyDataUpdated('outstanding')
  return data
}

export async function loadOutstanding(
  token: string,
  forceRefresh?: boolean
): Promise<{ data: any | null; fromCache: boolean }> {
  const cached = await getCachedDomainData<any>('outstanding')

  if (!forceRefresh && cached && cached.data) {
    if (cached.isStale) {
      syncOutstanding(token).catch(err => console.warn('[DataSync] Outstanding revalidation failed:', err))
    }
    return { data: cached.data, fromCache: true }
  }

  try {
    const fresh = await syncOutstanding(token)
    return { data: fresh, fromCache: false }
  } catch {
    return { data: cached?.data || null, fromCache: true }
  }
}

/**
 * 6. RECENT VISITS: 5-minute SWR Cache
 */
export async function syncRecentVisits(token: string): Promise<any[]> {
  const res = await fetch(`${API_BASE}/visits/recent`, { headers: authHeaders(token) })
  if (!res.ok) throw new Error(`Recent visits fetch failed: ${res.status}`)
  const visits = await res.json()
  const list = Array.isArray(visits) ? visits : []
  await setCachedDomainData('recent_visits', list, DOMAIN_TTLS.recent_visits)
  notifyDataUpdated('recent_visits', { count: list.length })
  return list
}

export async function loadRecentVisits(
  token: string,
  forceRefresh?: boolean
): Promise<{ visits: any[]; fromCache: boolean }> {
  const cached = await getCachedDomainData<any[]>('recent_visits')

  if (!forceRefresh && cached && cached.data) {
    if (cached.isStale) {
      syncRecentVisits(token).catch(err => console.warn('[DataSync] Recent visits revalidation failed:', err))
    }
    return { visits: cached.data, fromCache: true }
  }

  try {
    const fresh = await syncRecentVisits(token)
    return { visits: fresh, fromCache: false }
  } catch {
    return { visits: cached?.data || [], fromCache: true }
  }
}

/**
 * 7. LOCALITIES & ROUTES: 30-minute Cache
 */
export async function syncLocalities(token: string): Promise<any> {
  const res = await fetch(`${API_BASE}/customers/localities`, { headers: authHeaders(token) })
  if (!res.ok) throw new Error(`Localities fetch failed: ${res.status}`)
  const data = await res.json()
  await setCachedDomainData('localities', data, DOMAIN_TTLS.localities)
  notifyDataUpdated('localities')
  return data
}

export async function loadLocalities(
  token: string,
  forceRefresh?: boolean
): Promise<{ data: any | null; fromCache: boolean }> {
  const cached = await getCachedDomainData<any>('localities')

  if (!forceRefresh && cached && cached.data && !cached.isStale) {
    return { data: cached.data, fromCache: true }
  }

  try {
    const fresh = await syncLocalities(token)
    return { data: fresh, fromCache: false }
  } catch {
    return { data: cached?.data || null, fromCache: true }
  }
}

/**
 * 8. DASHBOARD SUMMARY & ANALYTICS: 10-minute SWR Cache
 */
export async function loadDashboardSummary(
  token: string,
  fromDate?: string,
  toDate?: string,
  forceRefresh?: boolean
): Promise<{ data: any | null; fromCache: boolean }> {
  const cacheKey = `dashboard_${fromDate || 'all'}_${toDate || 'all'}`
  const cached = await getCachedDomainData<any>(cacheKey)

  if (!forceRefresh && cached && cached.data) {
    if (cached.isStale) {
      // Revalidate in background
      let url = `${API_BASE}/reports/dashboard-summary`
      const q: string[] = []
      if (fromDate) q.push(`from_date=${fromDate}`)
      if (toDate) q.push(`to_date=${toDate}`)
      if (q.length) url += `?${q.join('&')}`
      fetch(url, { headers: authHeaders(token) })
        .then(r => (r.ok ? r.json() : null))
        .then(fresh => {
          if (fresh) setCachedDomainData(cacheKey, fresh, DOMAIN_TTLS.dashboard)
        })
        .catch(() => {})
    }
    return { data: cached.data, fromCache: true }
  }

  try {
    let url = `${API_BASE}/reports/dashboard-summary`
    const q: string[] = []
    if (fromDate) q.push(`from_date=${fromDate}`)
    if (toDate) q.push(`to_date=${toDate}`)
    if (q.length) url += `?${q.join('&')}`
    const res = await fetch(url, { headers: authHeaders(token) })
    if (res.ok) {
      const fresh = await res.json()
      await setCachedDomainData(cacheKey, fresh, DOMAIN_TTLS.dashboard)
      return { data: fresh, fromCache: false }
    }
  } catch {}

  return { data: cached?.data || null, fromCache: true }
}

// ─── Freshness Inspection Helper ─────────────────────────────────────────────

/**
 * Returns human-readable freshness status for a given domain
 */
export async function getDomainFreshness(domain: string): Promise<DomainFreshness> {
  const meta = await getSyncMetadata(domain)
  if (!meta || !meta.lastSyncedAt) {
    return { domain, lastSyncedAt: null, isStale: true, label: 'Not cached' }
  }

  const ageMs = Date.now() - meta.lastSyncedAt
  const ttl = DOMAIN_TTLS[domain] || (15 * 60 * 1000)
  const isStale = ageMs > ttl

  const minutes = Math.floor(ageMs / 60000)
  let label = ''
  if (minutes < 1) label = 'Just now'
  else if (minutes < 60) label = `${minutes}m ago`
  else {
    const hours = Math.floor(minutes / 60)
    label = `${hours}h ago`
  }

  return { domain, lastSyncedAt: meta.lastSyncedAt, isStale, label }
}
