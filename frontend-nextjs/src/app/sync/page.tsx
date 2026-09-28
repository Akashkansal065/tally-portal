'use client'

import { useEffect, useState, useMemo, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate } from '@/lib/utils'
import { 
  getOfflineQueue, 
  removeOfflineItem, 
  syncSingleItem, 
  syncAllPendingItems, 
  clearSyncedItems,
  OfflineQueueItem 
} from '@/lib/offline-storage'
import {
  CloudOff,
  Cloud,
  RefreshCw,
  ShoppingCart,
  IndianRupee,
  Receipt,
  MapPin,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Trash2,
  ArrowRight,
  Filter,
  Check,
  ChevronRight,
  Eye,
  X
} from 'lucide-react'
import { cn } from '@/lib/utils'

export default function SyncCenterPage() {
  const { user, token } = useAuth()
  const router = useRouter()

  const [queue, setQueue] = useState<OfflineQueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [syncingAll, setSyncingAll] = useState(false)
  const [syncProgress, setSyncProgress] = useState<{ current: number; total: number } | null>(null)
  const [activeFilter, setActiveFilter] = useState<'all' | 'order' | 'payment' | 'expense' | 'check_in'>('all')
  const [isOnline, setIsOnline] = useState(true)
  const [previewPhoto, setPreviewPhoto] = useState<string | null>(null)
  const [syncResultBanner, setSyncResultBanner] = useState<string | null>(null)

  // Load offline queue from IndexedDB
  const loadQueue = useCallback(async () => {
    try {
      const items = await getOfflineQueue()
      setQueue(items)
    } catch (err) {
      console.error('Failed to load queue:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadQueue()

    // Listen for queue update events dispatched across the app
    const handleQueueChange = () => loadQueue()
    window.addEventListener('mytally:offline-queue-changed', handleQueueChange)

    // Online/offline status detection
    setIsOnline(navigator.onLine)
    const handleOnline = () => {
      setIsOnline(true)
      // Auto-sync when coming back online
      triggerAutoSync()
    }
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('mytally:offline-queue-changed', handleQueueChange)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [loadQueue])

  // Trigger automated background sync
  const triggerAutoSync = useCallback(async () => {
    const items = await getOfflineQueue()
    const pending = items.filter(i => i.status === 'pending' || i.status === 'failed')
    if (pending.length === 0) return

    setSyncingAll(true)
    try {
      const res = await syncAllPendingItems(API_BASE, authHeaders, token, (cur, tot) => {
        setSyncProgress({ current: cur, total: tot })
      })
      await loadQueue()
      if (res.synced > 0) {
        setSyncResultBanner(`✓ Reconnected! Automatically synced ${res.synced} offline item(s).`)
      }
    } finally {
      setSyncingAll(false)
      setSyncProgress(null)
    }
  }, [token, loadQueue])

  // Manual sync all
  const handleSyncAll = async () => {
    if (syncingAll) return
    setSyncingAll(true)
    setSyncResultBanner(null)
    try {
      const res = await syncAllPendingItems(API_BASE, authHeaders, token, (cur, tot) => {
        setSyncProgress({ current: cur, total: tot })
      })
      await loadQueue()
      if (res.failed === 0) {
        setSyncResultBanner(`✓ All ${res.synced} pending item(s) successfully synced to server!`)
      } else {
        setSyncResultBanner(`Synced ${res.synced} item(s). ${res.failed} item(s) failed with errors.`)
      }
    } catch (err: any) {
      setSyncResultBanner(`Sync error: ${err.message || 'Network unreachable'}`)
    } finally {
      setSyncingAll(false)
      setSyncProgress(null)
    }
  }

  // Sync a single item
  const handleSyncItem = async (item: OfflineQueueItem) => {
    try {
      const res = await syncSingleItem(item, API_BASE, authHeaders, token)
      await loadQueue()
      if (!res.success) {
        alert(`Failed to sync: ${res.error}`)
      }
    } catch (err: any) {
      alert(`Sync failed: ${err.message}`)
    }
  }

  // Discard an item
  const handleDiscard = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to discard offline item for "${name}"? This cannot be undone.`)) {
      return
    }
    await removeOfflineItem(id)
    await loadQueue()
  }

  // Clear completed/synced
  const handleClearCompleted = async () => {
    await clearSyncedItems()
    await loadQueue()
  }

  // Filtered items
  const filteredItems = useMemo(() => {
    if (activeFilter === 'all') return queue
    return queue.filter(i => i.type === activeFilter)
  }, [queue, activeFilter])

  // Statistics
  const stats = useMemo(() => {
    const pending = queue.filter(i => i.status === 'pending')
    const failed = queue.filter(i => i.status === 'failed')
    const synced = queue.filter(i => i.status === 'synced')
    return {
      pending: pending.length,
      failed: failed.length,
      synced: synced.length,
      total: queue.length
    }
  }, [queue])

  const getItemIcon = (type: OfflineQueueItem['type']) => {
    switch (type) {
      case 'order':
        return <ShoppingCart className="h-4 w-4 text-blue-500" />
      case 'payment':
        return <IndianRupee className="h-4 w-4 text-emerald-500" />
      case 'expense':
        return <Receipt className="h-4 w-4 text-purple-500" />
      case 'check_in':
        return <MapPin className="h-4 w-4 text-amber-500" />
    }
  }

  const getTypeLabel = (type: OfflineQueueItem['type']) => {
    switch (type) {
      case 'order': return 'Temp Order'
      case 'payment': return 'Payment Collection'
      case 'expense': return 'Expense Claim'
      case 'check_in': return 'Shop Check-In'
    }
  }

  return (
    <div className="flex flex-col min-h-screen bg-background font-sans pb-16">
      {/* Top Banner & Header */}
      <div className="border-b border-border bg-card/60 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-4xl mx-auto px-4 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn(
              "h-9 w-9 rounded-xl flex items-center justify-center border",
              isOnline 
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                : "bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-400"
            )}>
              {isOnline ? <Cloud className="h-5 w-5" /> : <CloudOff className="h-5 w-5" />}
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-foreground flex items-center gap-2">
                Offline Sync Center
                <span className={cn(
                  "text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border",
                  isOnline 
                    ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-600" 
                    : "bg-amber-500/10 border-amber-500/20 text-amber-600"
                )}>
                  {isOnline ? 'Online' : 'Offline'}
                </span>
              </h1>
              <p className="text-[12px] text-muted-foreground">
                Local queue for orders, payments, expenses, and check-ins
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadQueue}
              disabled={loading || syncingAll}
              className="p-2 text-muted-foreground hover:text-foreground hover:bg-muted/60 rounded-xl border border-border transition-colors"
              title="Refresh Queue"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </button>
            <button
              onClick={handleSyncAll}
              disabled={syncingAll || stats.pending + stats.failed === 0 || !isOnline}
              className={cn(
                "px-3.5 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all shadow-sm",
                stats.pending + stats.failed > 0 && isOnline
                  ? "bg-primary text-primary-foreground hover:opacity-90 active:scale-95"
                  : "bg-muted text-muted-foreground cursor-not-allowed border border-border"
              )}
            >
              <RefreshCw className={cn("h-3.5 w-3.5", syncingAll && "animate-spin")} />
              <span>{syncingAll ? 'Syncing...' : `Sync All (${stats.pending + stats.failed})`}</span>
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-6 w-full space-y-5">
        {/* Progress Bar during Sync */}
        {syncingAll && syncProgress && (
          <div className="bg-card border border-primary/20 rounded-2xl p-4 shadow-sm space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold">
              <span className="text-primary flex items-center gap-2">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                Synchronizing offline records...
              </span>
              <span className="text-muted-foreground">
                {syncProgress.current} of {syncProgress.total} completed
              </span>
            </div>
            <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
              <div 
                className="bg-primary h-full transition-all duration-300 rounded-full"
                style={{ width: `${Math.round((syncProgress.current / syncProgress.total) * 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* Sync Result Banner */}
        {syncResultBanner && (
          <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300 p-3.5 rounded-2xl text-xs font-medium flex items-center justify-between">
            <span>{syncResultBanner}</span>
            <button 
              onClick={() => setSyncResultBanner(null)}
              className="text-emerald-600 hover:text-emerald-800 dark:text-emerald-400 p-1"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* KPI Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-card border border-border rounded-2xl p-3.5 shadow-sm space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Pending Sync</span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-amber-500">{stats.pending}</span>
              <span className="text-[11px] text-muted-foreground">in queue</span>
            </div>
          </div>

          <div className="bg-card border border-border rounded-2xl p-3.5 shadow-sm space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Sync Errors</span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-rose-500">{stats.failed}</span>
              <span className="text-[11px] text-muted-foreground">require retry</span>
            </div>
          </div>

          <div className="bg-card border border-border rounded-2xl p-3.5 shadow-sm space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Synced</span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-emerald-500">{stats.synced}</span>
              <span className="text-[11px] text-muted-foreground">completed</span>
            </div>
          </div>

          <div className="bg-card border border-border rounded-2xl p-3.5 shadow-sm space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Storage</span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-black text-foreground">{stats.total}</span>
              <span className="text-[11px] text-muted-foreground">IndexedDB</span>
            </div>
          </div>
        </div>

        {/* Filter Tabs & Clean Actions */}
        <div className="flex items-center justify-between gap-2 overflow-x-auto pb-1">
          <div className="flex items-center gap-1.5 p-1 bg-muted/60 rounded-xl border border-border text-xs font-medium">
            <button
              onClick={() => setActiveFilter('all')}
              className={cn(
                "px-3 py-1.5 rounded-lg transition-colors",
                activeFilter === 'all' 
                  ? "bg-card text-foreground shadow-sm font-bold" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              All ({queue.length})
            </button>
            <button
              onClick={() => setActiveFilter('order')}
              className={cn(
                "px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5",
                activeFilter === 'order' 
                  ? "bg-card text-foreground shadow-sm font-bold" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <ShoppingCart className="h-3 w-3 text-blue-500" />
              Orders ({queue.filter(i => i.type === 'order').length})
            </button>
            <button
              onClick={() => setActiveFilter('payment')}
              className={cn(
                "px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5",
                activeFilter === 'payment' 
                  ? "bg-card text-foreground shadow-sm font-bold" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <IndianRupee className="h-3 w-3 text-emerald-500" />
              Payments ({queue.filter(i => i.type === 'payment').length})
            </button>
            <button
              onClick={() => setActiveFilter('expense')}
              className={cn(
                "px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5",
                activeFilter === 'expense' 
                  ? "bg-card text-foreground shadow-sm font-bold" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Receipt className="h-3 w-3 text-purple-500" />
              Expenses ({queue.filter(i => i.type === 'expense').length})
            </button>
            <button
              onClick={() => setActiveFilter('check_in')}
              className={cn(
                "px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5",
                activeFilter === 'check_in' 
                  ? "bg-card text-foreground shadow-sm font-bold" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <MapPin className="h-3 w-3 text-amber-500" />
              Check-ins ({queue.filter(i => i.type === 'check_in').length})
            </button>
          </div>

          {stats.synced > 0 && (
            <button
              onClick={handleClearCompleted}
              className="text-[11px] text-muted-foreground hover:text-rose-600 px-3 py-1.5 rounded-xl border border-border hover:bg-rose-500/10 hover:border-rose-500/20 transition-colors whitespace-nowrap"
            >
              Clear Synced ({stats.synced})
            </button>
          )}
        </div>

        {/* Queue Items List */}
        {loading ? (
          <div className="bg-card border border-border rounded-2xl p-12 text-center">
            <RefreshCw className="h-6 w-6 animate-spin mx-auto text-primary mb-3" />
            <p className="text-sm font-medium text-muted-foreground">Accessing offline storage...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="bg-card border border-border rounded-2xl p-12 text-center space-y-3 shadow-sm">
            <div className="h-12 w-12 rounded-2xl bg-muted/60 border border-border flex items-center justify-center mx-auto text-muted-foreground">
              <CheckCircle2 className="h-6 w-6 text-emerald-500" />
            </div>
            <h3 className="text-sm font-bold text-foreground">No Offline Items Pending</h3>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              All field orders, payments, expenses, and check-ins are in sync with the central server.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredItems.map(item => {
              const hasPhoto = Boolean(item.payload?.photo_base64)

              return (
                <div 
                  key={item.id}
                  className="bg-card border border-border rounded-2xl p-4 shadow-sm hover:border-primary/30 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="flex items-start gap-3.5 min-w-0">
                    <div className="h-10 w-10 rounded-xl bg-muted/80 border border-border flex items-center justify-center shrink-0 mt-0.5">
                      {getItemIcon(item.type)}
                    </div>

                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-foreground truncate">
                          {item.shop_name}
                        </span>
                        <span className="text-[10px] font-semibold text-muted-foreground bg-muted px-2 py-0.5 rounded-md border border-border/80">
                          {getTypeLabel(item.type)}
                        </span>
                        {item.amount !== undefined && item.amount !== null && (
                          <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                            {formatCurrency(item.amount)}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3 text-[11px] text-muted-foreground flex-wrap">
                        <span>Queued {formatDate(item.created_at)}</span>
                        {item.attempts > 0 && (
                          <span>Attempts: {item.attempts}</span>
                        )}
                        {hasPhoto && (
                          <button
                            onClick={() => setPreviewPhoto(item.payload.photo_base64)}
                            className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
                          >
                            <Eye className="h-3 w-3" /> View Photo
                          </button>
                        )}
                      </div>

                      {/* Error Banner if failed */}
                      {item.status === 'failed' && item.last_error && (
                        <div className="mt-1.5 text-[11px] text-rose-600 dark:text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2.5 py-1 rounded-lg flex items-center gap-1.5 max-w-lg">
                          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                          <span className="break-words font-medium">{item.last_error}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Actions & Status */}
                  <div className="flex items-center justify-between sm:justify-end gap-2.5 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-border">
                    {/* Status Badge */}
                    <div className="mr-1">
                      {item.status === 'pending' && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                          <Clock className="h-3 w-3" /> Pending
                        </span>
                      )}
                      {item.status === 'syncing' && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 animate-pulse">
                          <RefreshCw className="h-3 w-3 animate-spin" /> Syncing...
                        </span>
                      )}
                      {item.status === 'failed' && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
                          <AlertTriangle className="h-3 w-3" /> Failed
                        </span>
                      )}
                      {item.status === 'synced' && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="h-3 w-3" /> Synced
                        </span>
                      )}
                    </div>

                    {item.status !== 'synced' && (
                      <button
                        onClick={() => handleSyncItem(item)}
                        disabled={item.status === 'syncing' || !isOnline}
                        className="px-3 py-1.5 rounded-xl text-xs font-bold bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground transition-all disabled:opacity-50 border border-primary/20"
                      >
                        Sync Now
                      </button>
                    )}

                    <button
                      onClick={() => handleDiscard(item.id, item.shop_name)}
                      className="p-1.5 text-muted-foreground hover:text-rose-600 hover:bg-rose-500/10 rounded-lg transition-colors border border-transparent hover:border-rose-500/20"
                      title="Discard Item"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Photo Preview Modal */}
      {previewPhoto && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 backdrop-blur-sm animate-in fade-in">
          <div className="relative max-w-lg w-full bg-card border border-border rounded-3xl overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <span className="text-xs font-bold text-foreground">Attached Photo Proof</span>
              <button 
                onClick={() => setPreviewPhoto(null)}
                className="p-1 rounded-full hover:bg-muted text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-4 flex items-center justify-center bg-black/20">
              <img 
                src={previewPhoto} 
                alt="Proof" 
                className="max-h-[70vh] w-auto object-contain rounded-xl"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
