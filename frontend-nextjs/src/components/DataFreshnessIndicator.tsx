'use client'

import React, { useEffect, useState, useCallback } from 'react'
import { CheckCircle2, Clock, WifiOff, RefreshCw } from 'lucide-react'
import { getDomainFreshness, DomainFreshness } from '@/lib/data-sync-service'

interface DataFreshnessIndicatorProps {
  domain: string
  onRefresh?: () => void | Promise<void>
  className?: string
  isRefreshing?: boolean
  showRefreshButton?: boolean
}

export default function DataFreshnessIndicator({
  domain,
  onRefresh,
  className = '',
  isRefreshing = false,
  showRefreshButton = true,
}: DataFreshnessIndicatorProps) {
  const [freshness, setFreshness] = useState<DomainFreshness>({
    domain,
    lastSyncedAt: null,
    isStale: true,
    label: 'Checking...',
  })
  const [isOnline, setIsOnline] = useState<boolean>(true)
  const [localRefreshing, setLocalRefreshing] = useState<boolean>(false)

  const checkFreshness = useCallback(async () => {
    try {
      const info = await getDomainFreshness(domain)
      setFreshness(info)
    } catch {
      // Ignore
    }
  }, [domain])

  useEffect(() => {
    setIsOnline(typeof navigator !== 'undefined' ? navigator.onLine : true)

    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    checkFreshness()

    // Poll every 30s to update timestamp label
    const interval = setInterval(checkFreshness, 30000)

    // Listen for sync updates
    const handleUpdate = (e: Event) => {
      const customEvent = e as CustomEvent
      if (!customEvent.detail?.domain || customEvent.detail.domain === domain) {
        checkFreshness()
      }
    }
    window.addEventListener('mytally:data-updated', handleUpdate)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('mytally:data-updated', handleUpdate)
      clearInterval(interval)
    }
  }, [domain, checkFreshness])

  const handleManualRefresh = async () => {
    if (!onRefresh || isRefreshing || localRefreshing) return
    setLocalRefreshing(true)
    try {
      await onRefresh()
      await checkFreshness()
    } finally {
      setLocalRefreshing(false)
    }
  }

  const refreshing = isRefreshing || localRefreshing

  if (!isOnline) {
    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 ${className}`}
        title="Operating in offline mode with locally cached data"
      >
        <WifiOff className="w-3.5 h-3.5" />
        <span>Offline ({freshness.label})</span>
      </div>
    )
  }

  if (!freshness.lastSyncedAt) {
    return (
      <div
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-muted text-muted-foreground border ${className}`}
      >
        <Clock className="w-3.5 h-3.5 animate-pulse" />
        <span>Syncing...</span>
      </div>
    )
  }

  return (
    <div
      className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
        freshness.isStale
          ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20'
          : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20'
      } ${className}`}
      title={`Data domain: ${domain}. Last updated: ${new Date(freshness.lastSyncedAt).toLocaleTimeString()}`}
    >
      <div className="flex items-center gap-1.5">
        <span
          className={`w-2 h-2 rounded-full ${
            freshness.isStale ? 'bg-amber-500' : 'bg-emerald-500'
          } ${refreshing ? 'animate-ping' : ''}`}
        />
        {freshness.isStale ? (
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-amber-500" />
            <span>Cached {freshness.label}</span>
          </span>
        ) : (
          <span className="flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-500" />
            <span>Live ({freshness.label})</span>
          </span>
        )}
      </div>

      {showRefreshButton && onRefresh && (
        <button
          type="button"
          onClick={handleManualRefresh}
          disabled={refreshing}
          className="hover:opacity-80 active:scale-95 transition-all p-0.5 rounded focus:outline-none"
          title="Force refresh from server"
        >
          <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin text-primary' : 'opacity-70'}`} />
        </button>
      )}
    </div>
  )
}
