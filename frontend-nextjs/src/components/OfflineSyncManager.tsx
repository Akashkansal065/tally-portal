'use client'

import { useEffect, useRef } from 'react'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'
import { getPendingCheckIns, syncPendingCheckIns } from '@/lib/offline-storage'
import { syncAllPermittedDomains } from '@/lib/data-sync-service'
import { toast } from 'sonner'

/**
 * Headless Global Offline & Multi-Domain Sync Manager.
 * Mounts in RootLayout.
 * 
 * Capabilities:
 * 1. Automatically uploads queued offline shop check-ins as soon as internet reconnects.
 * 2. Role & Permission-Aware: Only syncs data domains the logged-in user has permission to access
 *    (e.g., field sales reps only sync Customers + Stocks + Visits; reports and ledgers are omitted).
 * 3. Delta Sync & SWR revalidation on mount, reconnection, and gentle background heartbeat.
 */
export function OfflineSyncManager() {
  const { token, user, permissions } = useAuth()
  const isSyncingRef = useRef(false)

  useEffect(() => {
    if (!token || !user) return

    const handleSync = async () => {
      if (isSyncingRef.current) return
      isSyncingRef.current = true

      try {
        // 1. Sync pending offline check-in queue first (highest priority)
        const pending = await getPendingCheckIns()
        if (pending.length > 0) {
          const res = await syncPendingCheckIns(API_BASE, authHeaders, token)
          if (res.synced > 0) {
            toast.success(`✓ Synced ${res.synced} offline shop check-in(s) successfully!`, {
              duration: 4000,
            })
            window.dispatchEvent(new CustomEvent('mytally:checkins-synced', { detail: res }))
          }
        }

        // 2. Permission-gated multi-domain background sync
        if (permissions) {
          const report = await syncAllPermittedDomains(token, permissions)
          if (report.syncedDomains.length > 0) {
            console.debug(
              `[OfflineSyncManager] Synced permitted domains: [${report.syncedDomains.join(', ')}]. Skipped: [${report.skippedDomains.join(', ')}]`
            )
          }
        }
      } catch (err) {
        console.warn('[OfflineSyncManager] Background sync error:', err)
      } finally {
        isSyncingRef.current = false
      }
    }

    // Run on initial mount if online
    if (typeof navigator !== 'undefined' && navigator.onLine) {
      handleSync()
    }

    // Reconnection listener
    const onOnline = () => {
      toast.info('Network restored. Synchronizing data...', { duration: 2500 })
      handleSync()
    }

    window.addEventListener('online', onOnline)

    // Gentle heartbeat sync every 5 minutes (only when window is visible)
    const interval = setInterval(() => {
      if (
        typeof document !== 'undefined' &&
        document.visibilityState === 'visible' &&
        typeof navigator !== 'undefined' &&
        navigator.onLine
      ) {
        handleSync()
      }
    }, 5 * 60 * 1000)

    return () => {
      window.removeEventListener('online', onOnline)
      clearInterval(interval)
    }
  }, [token, user, permissions])

  return null
}
