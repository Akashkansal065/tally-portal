/**
 * Offline Storage & Synchronization Engine for Field Operations (MyTally)
 * Provides IndexedDB-backed offline queue for Check-Ins, Orders, Payments, and Expenses,
 * with canvas photo compression, safe retry, duplicate prevention, and cache management.
 */

export interface OfflineQueueItem {
  id: string // Client-generated unique ID: offline_{type}_{timestamp}_{random}
  type: 'check_in' | 'order' | 'payment' | 'expense'
  shop_name: string
  amount?: number
  payload: any
  created_at: string
  attempts: number
  last_attempt?: string
  last_error?: string
  status: 'pending' | 'syncing' | 'failed' | 'synced'
  synced_at?: string
}

export interface CachedCustomerDirectory {
  customers: any[]
  localities: any[]
  routes: string[]
  cachedAt: number
}

// Legacy CheckIn interface for backward compatibility
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

const DB_NAME = 'mytally_offline_v2'
const DB_VERSION = 1
const STORE_QUEUE = 'queue'
const STORE_CACHE = 'cache'

const LEGACY_STORAGE_KEYS = {
  DIRECTORY: 'mytally_offline_customers_v1',
  PENDING_CHECKINS: 'mytally_pending_checkins_v1',
}

// ─── IndexedDB Connection Factory ──────────────────────────────────────────

let dbPromise: Promise<IDBDatabase> | null = null

/** Open the versioned IndexedDB used for queued transactions and cached masters. */
export function getOfflineDb(): Promise<IDBDatabase> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('IndexedDB is not available server-side'))
  }

  if (dbPromise) return dbPromise

  dbPromise = new Promise<IDBDatabase>((resolve, reject) => {
    try {
      const request = indexedDB.open(DB_NAME, DB_VERSION)

      request.onupgradeneeded = (event) => {
        const db = request.result
        // Store for queued transactions
        if (!db.objectStoreNames.contains(STORE_QUEUE)) {
          const queueStore = db.createObjectStore(STORE_QUEUE, { keyPath: 'id' })
          queueStore.createIndex('status', 'status', { unique: false })
          queueStore.createIndex('type', 'type', { unique: false })
          queueStore.createIndex('created_at', 'created_at', { unique: false })
        }
        // Store for general cache (directory, price lists, masters)
        if (!db.objectStoreNames.contains(STORE_CACHE)) {
          db.createObjectStore(STORE_CACHE, { keyPath: 'key' })
        }
      }

      request.onsuccess = () => {
        const db = request.result
        // Trigger one-time migration from legacy localStorage if present
        migrateLegacyStorage(db).finally(() => resolve(db))
      }

      request.onerror = () => {
        console.error('Failed to open IndexedDB:', request.error)
        reject(request.error)
      }
    } catch (err) {
      reject(err)
    }
  })

  return dbPromise
}

// Migrate legacy localStorage items to IndexedDB
async function migrateLegacyStorage(db: IDBDatabase): Promise<void> {
  if (typeof window === 'undefined') return
  try {
    const rawCheckins = localStorage.getItem(LEGACY_STORAGE_KEYS.PENDING_CHECKINS)
    if (rawCheckins) {
      const items: OfflineCheckIn[] = JSON.parse(rawCheckins)
      if (Array.isArray(items) && items.length > 0) {
        const tx = db.transaction(STORE_QUEUE, 'readwrite')
        const store = tx.objectStore(STORE_QUEUE)
        for (const item of items) {
          const queueItem: OfflineQueueItem = {
            id: item.id || `offline_check_in_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
            type: 'check_in',
            shop_name: item.shop_name || item.custom_shop_name || 'Customer Shop',
            payload: {
              ledger_id: item.ledger_id || null,
              customer_profile_id: item.customer_profile_id || null,
              custom_shop_name: item.custom_shop_name || item.shop_name || null,
              latitude: item.latitude,
              longitude: item.longitude,
              comments: item.comments || null,
              photo_base64: item.photo_base64 || null,
            },
            created_at: item.queued_at || new Date().toISOString(),
            attempts: 0,
            status: 'pending',
          }
          store.put(queueItem)
        }
        localStorage.removeItem(LEGACY_STORAGE_KEYS.PENDING_CHECKINS)
      }
    }
  } catch (err) {
    console.warn('Migration from localStorage skipped or failed:', err)
  }
}

// ─── Image Compression Utility ─────────────────────────────────────────────

/**
 * Compresses a base64 image data URL to stay under max dimension and JPEG quality.
 * Prevents base64 payloads from blowing up storage or upload bandwidth.
 */
export async function compressPhoto(
  dataUrl: string,
  maxWidth = 1280,
  maxHeight = 1280,
  quality = 0.72
): Promise<string> {
  if (typeof window === 'undefined' || !dataUrl || !dataUrl.startsWith('data:image')) {
    return dataUrl
  }

  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => {
      let width = img.width
      let height = img.height

      if (width > maxWidth || height > maxHeight) {
        if (width / height > maxWidth / maxHeight) {
          height = Math.round((height * maxWidth) / width)
          width = maxWidth
        } else {
          width = Math.round((width * maxHeight) / height)
          height = maxHeight
        }
      }

      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        resolve(dataUrl)
        return
      }

      ctx.drawImage(img, 0, 0, width, height)
      const compressed = canvas.toDataURL('image/jpeg', quality)
      resolve(compressed)
    }
    img.onerror = () => resolve(dataUrl)
    img.src = dataUrl
  })
}

// ─── Event Notifications for React UI ───────────────────────────────────────

function notifyQueueChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('mytally:offline-queue-changed'))
  }
}

// ─── Unified Queue Operations ──────────────────────────────────────────────

/** Add a transaction to the offline queue, compressing an attached photo first. */
export async function queueOfflineItem(item: {
  type: OfflineQueueItem['type']
  shop_name: string
  amount?: number
  payload: any
}): Promise<OfflineQueueItem> {
  const db = await getOfflineDb()
  const id = `offline_${item.type}_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`

  // Compress photo if present in payload
  const cleanPayload = { ...item.payload }
  if (cleanPayload.photo_base64 && typeof cleanPayload.photo_base64 === 'string') {
    cleanPayload.photo_base64 = await compressPhoto(cleanPayload.photo_base64)
  }

  const queueItem: OfflineQueueItem = {
    id,
    type: item.type,
    shop_name: item.shop_name || 'General Customer',
    amount: item.amount,
    payload: cleanPayload,
    created_at: new Date().toISOString(),
    attempts: 0,
    status: 'pending',
  }

  return new Promise<OfflineQueueItem>((resolve, reject) => {
    const tx = db.transaction(STORE_QUEUE, 'readwrite')
    const store = tx.objectStore(STORE_QUEUE)
    const req = store.add(queueItem)

    req.onsuccess = () => {
      notifyQueueChanged()
      resolve(queueItem)
    }
    req.onerror = () => reject(req.error)
  })
}

/** Read queued transactions, optionally filtering by type or synchronization status. */
export async function getOfflineQueue(filter?: {
  type?: OfflineQueueItem['type']
  status?: OfflineQueueItem['status']
}): Promise<OfflineQueueItem[]> {
  try {
    const db = await getOfflineDb()
    return new Promise<OfflineQueueItem[]>((resolve, reject) => {
      const tx = db.transaction(STORE_QUEUE, 'readonly')
      const store = tx.objectStore(STORE_QUEUE)
      const req = store.getAll()

      req.onsuccess = () => {
        let items: OfflineQueueItem[] = req.result || []
        if (filter?.type) {
          items = items.filter((i) => i.type === filter.type)
        }
        if (filter?.status) {
          items = items.filter((i) => i.status === filter.status)
        }
        // Newest first
        items.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        resolve(items)
      }
      req.onerror = () => reject(req.error)
    })
  } catch (err) {
    console.warn('Failed to retrieve offline queue:', err)
    return []
  }
}

/** Remove one queued transaction by its client-generated identifier. */
export async function removeOfflineItem(id: string): Promise<void> {
  const db = await getOfflineDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_QUEUE, 'readwrite')
    const store = tx.objectStore(STORE_QUEUE)
    const req = store.delete(id)
    req.onsuccess = () => {
      notifyQueueChanged()
      resolve()
    }
    req.onerror = () => reject(req.error)
  })
}

/** Delete successfully synchronized transactions from the local queue. */
export async function clearSyncedItems(): Promise<void> {
  const db = await getOfflineDb()
  const all = await getOfflineQueue()
  const synced = all.filter((i) => i.status === 'synced')

  const tx = db.transaction(STORE_QUEUE, 'readwrite')
  const store = tx.objectStore(STORE_QUEUE)
  for (const item of synced) {
    store.delete(item.id)
  }
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => {
      notifyQueueChanged()
      resolve()
    }
    tx.onerror = () => reject(tx.error)
  })
}

/** Persist queue status, retry metadata, and any server error for an item. */
export async function updateItemStatus(
  id: string,
  status: OfflineQueueItem['status'],
  errorMsg?: string
): Promise<void> {
  const db = await getOfflineDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_QUEUE, 'readwrite')
    const store = tx.objectStore(STORE_QUEUE)
    const getReq = store.get(id)

    getReq.onsuccess = () => {
      const item: OfflineQueueItem | undefined = getReq.result
      if (!item) {
        resolve()
        return
      }
      item.status = status
      item.last_attempt = new Date().toISOString()
      if (status === 'syncing') {
        item.attempts += 1
      }
      if (status === 'synced') {
        item.synced_at = new Date().toISOString()
        item.last_error = undefined
      }
      if (errorMsg) {
        item.last_error = errorMsg
      }
      const putReq = store.put(item)
      putReq.onsuccess = () => {
        notifyQueueChanged()
        resolve()
      }
      putReq.onerror = () => reject(putReq.error)
    }
    getReq.onerror = () => reject(getReq.error)
  })
}

// ─── Single Item Sync Engine with Duplicate Protection ───────────────────────

/**
 * Submit one queued transaction with an idempotency header.
 * A conflict response is considered successful because the server already
 * accepted the same client-generated item.
 */
export async function syncSingleItem(
  item: OfflineQueueItem,
  apiBase: string,
  authHeaders: (token?: any) => Record<string, string>,
  token?: string | null
): Promise<{ success: boolean; error?: string }> {
  // Guard against parallel execution of the same item
  if (item.status === 'syncing') {
    return { success: false, error: 'Item is already currently syncing' }
  }

  await updateItemStatus(item.id, 'syncing')

  try {
    let endpoint = ''
    let payload = { ...item.payload }

    if (item.type === 'check_in') {
      endpoint = `${apiBase}/visits/check-in`
      payload.comments = payload.comments
        ? `${payload.comments} [Queued Offline: ${new Date(item.created_at).toLocaleTimeString()}]`
        : `[Queued Offline: ${new Date(item.created_at).toLocaleTimeString()}]`
    } else if (item.type === 'order') {
      endpoint = `${apiBase}/temporders`
    } else if (item.type === 'payment') {
      endpoint = `${apiBase}/payment/collect`
    } else if (item.type === 'expense') {
      endpoint = `${apiBase}/expenses`
    } else {
      throw new Error(`Unknown item type: ${item.type}`)
    }

    const headers = {
      ...authHeaders(token),
      'Content-Type': 'application/json',
      'X-Client-Id': item.id, // Deduplication / idempotency header
    }

    const res = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      let detail = `Server responded with HTTP ${res.status}`
      try {
        const errJson = await res.json()
        detail = errJson.detail || detail
      } catch {
        // use status string
      }
      // If server returns 409 Conflict, it was already accepted
      if (res.status === 409) {
        await updateItemStatus(item.id, 'synced')
        return { success: true }
      }
      await updateItemStatus(item.id, 'failed', detail)
      return { success: false, error: detail }
    }

    // Successfully synced
    await updateItemStatus(item.id, 'synced')
    return { success: true }
  } catch (err: any) {
    const errorMsg = err.message || 'Network unreachable'
    await updateItemStatus(item.id, 'failed', errorMsg)
    return { success: false, error: errorMsg }
  }
}

// ─── Batch Sync Engine ───────────────────────────────────────────────────────

/** Synchronize pending and previously failed items sequentially with progress callbacks. */
export async function syncAllPendingItems(
  apiBase: string,
  authHeaders: (token?: any) => Record<string, string>,
  token?: string | null,
  onProgress?: (synced: number, total: number) => void
): Promise<{ synced: number; failed: number; total: number }> {
  const queue = await getOfflineQueue()
  const pending = queue.filter((i) => i.status === 'pending' || i.status === 'failed')

  if (pending.length === 0) {
    return { synced: 0, failed: 0, total: 0 }
  }

  let synced = 0
  let failed = 0

  for (let i = 0; i < pending.length; i++) {
    const item = pending[i]
    const res = await syncSingleItem(item, apiBase, authHeaders, token)
    if (res.success) {
      synced++
    } else {
      failed++
    }
    if (onProgress) {
      onProgress(synced + failed, pending.length)
    }
  }

  return { synced, failed, total: pending.length }
}

// ─── Directory & Master Cache ───────────────────────────────────────────────

/** Cache customer directory data for lookup while the device is offline. */
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
    localStorage.setItem(LEGACY_STORAGE_KEYS.DIRECTORY, JSON.stringify(payload))
  } catch (err) {
    console.warn('Failed to cache directory to localStorage:', err)
  }
}

/** Read the cached customer directory, or null when no browser cache exists. */
export function getOfflineDirectory(): CachedCustomerDirectory | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(LEGACY_STORAGE_KEYS.DIRECTORY)
    if (!raw) return null
    return JSON.parse(raw) as CachedCustomerDirectory
  } catch (err) {
    console.warn('Failed to read offline directory cache:', err)
    return null
  }
}

// ─── Backward Compatible Shims for Existing Check-In Code ───────────────────

/** Read legacy localStorage check-ins for older callers during migration. */
export function getPendingCheckIns(): OfflineCheckIn[] {
  // Synchronous fallback reads from localStorage cache if present,
  // but caller is encouraged to use getOfflineQueue
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(LEGACY_STORAGE_KEYS.PENDING_CHECKINS)
    if (!raw) return []
    return JSON.parse(raw) || []
  } catch {
    return []
  }
}

/** Queue a check-in using the unified IndexedDB transaction format. */
export async function queueOfflineCheckInAsync(
  item: Omit<OfflineCheckIn, 'id' | 'queued_at'>
): Promise<OfflineQueueItem> {
  return queueOfflineItem({
    type: 'check_in',
    shop_name: item.shop_name || item.custom_shop_name || 'Customer Shop',
    payload: {
      ledger_id: item.ledger_id || null,
      customer_profile_id: item.customer_profile_id || null,
      custom_shop_name: item.custom_shop_name || item.shop_name || null,
      latitude: item.latitude,
      longitude: item.longitude,
      comments: item.comments || null,
      photo_base64: item.photo_base64 || null,
    },
  })
}

/** Backward-compatible synchronous wrapper that also starts an IndexedDB queue write. */
export function queueOfflineCheckIn(item: Omit<OfflineCheckIn, 'id' | 'queued_at'>): OfflineCheckIn {
  // Fire async queue in background
  queueOfflineCheckInAsync(item).catch((err) => {
    console.error('Failed to queue offline check-in to IndexedDB:', err)
  })

  // Return synchronous structure for existing call signatures
  return {
    ...item,
    id: `offline_check_in_${Date.now()}`,
    queued_at: new Date().toISOString(),
  }
}

/** Remove a legacy check-in through the unified offline queue. */
export function removePendingCheckIn(id: string): void {
  removeOfflineItem(id).catch((err) => console.warn('Failed to remove item:', err))
}

/** Synchronize queued check-ins through the unified transaction engine. */
export async function syncPendingCheckIns(
  apiBase: string,
  authHeaders: (token?: any) => Record<string, string>,
  token?: string | null
): Promise<{ synced: number; failed: number }> {
  const result = await syncAllPendingItems(apiBase, authHeaders, token)
  return { synced: result.synced, failed: result.failed }
}
