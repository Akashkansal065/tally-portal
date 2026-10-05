'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Bell, CheckCheck, Loader2, Settings2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { NotificationList } from '@/components/notifications/NotificationList'
import { PushAlertsBanner } from '@/components/notifications/PushAlertsBanner'
import { useOpenNotification } from '@/hooks/useOpenNotification'
import { cn } from '@/lib/utils'
import {
  NOTIFICATION_FILTERS,
  announceNotificationsChanged,
  clearAllNotifications,
  deleteNotification,
  getNotificationPreferences,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  updateNotificationPreference,
  type AppNotification,
  type Delivery,
  type NotificationFilter,
  type NotificationPreference,
} from '@/lib/notifications'

const PAGE_SIZE = 30

const DELIVERY_OPTIONS: { id: Delivery; label: string }[] = [
  { id: 'all', label: 'Alerts' },
  { id: 'in_app', label: 'In-app' },
  { id: 'off', label: 'Off' },
]

export default function NotificationsPage() {
  const router = useRouter()
  const { user, token, isLoading } = useAuth()
  const openNotification = useOpenNotification()

  const [filter, setFilter] = useState<NotificationFilter>('all')
  const [items, setItems] = useState<AppNotification[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)

  const [settingsOpen, setSettingsOpen] = useState(false)
  const [prefs, setPrefs] = useState<NotificationPreference[] | null>(null)
  const [savingCategory, setSavingCategory] = useState<string | null>(null)

  useEffect(() => {
    if (!isLoading && !user) router.replace('/login')
  }, [isLoading, user, router])

  // First page for the current filter (switching filters clears the list first, in chooseFilter)
  useEffect(() => {
    if (!token) return
    let current = true
    listNotifications(token, filter, PAGE_SIZE, 0)
      .then(page => {
        if (!current) return
        setItems(page)
        setHasMore(page.length === PAGE_SIZE)
      })
      .catch(() => toast.error('Could not load notifications'))
      .finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [token, filter])

  const chooseFilter = (next: NotificationFilter) => {
    if (next === filter) return
    setItems([])
    setLoading(true)
    setFilter(next)
  }

  const loadMore = async () => {
    if (!token) return
    setLoadingMore(true)
    try {
      const page = await listNotifications(token, filter, PAGE_SIZE, items.length)
      setItems(prev => [...prev, ...page])
      setHasMore(page.length === PAGE_SIZE)
    } catch {
      toast.error('Could not load more')
    } finally {
      setLoadingMore(false)
    }
  }

  const markRead = (n: AppNotification) => {
    if (!token) return
    setItems(prev => prev.map(x => (x.id === n.id ? { ...x, is_read: true } : x)))
    markNotificationRead(token, n.id).then(announceNotificationsChanged).catch(() => {})
  }

  const remove = (n: AppNotification) => {
    if (!token) return
    setItems(prev => prev.filter(x => x.id !== n.id))
    deleteNotification(token, n.id).then(announceNotificationsChanged).catch(() => toast.error('Could not dismiss'))
  }

  const decided = (n: AppNotification, decision: 'approved' | 'rejected') => {
    setItems(prev => prev.map(x => (x.id === n.id ? { ...x, decision, is_read: true } : x)))
    if (token && !n.is_read) markNotificationRead(token, n.id).then(announceNotificationsChanged).catch(() => {})
  }

  const readAll = async () => {
    if (!token) return
    try {
      await markAllNotificationsRead(token)
      setItems(prev => prev.map(x => ({ ...x, is_read: true })))
      announceNotificationsChanged()
    } catch {
      toast.error('Could not mark all as read')
    }
  }

  const clearAll = async () => {
    if (!token || !confirm('Delete all notifications? This can’t be undone.')) return
    try {
      await clearAllNotifications(token)
      setItems([])
      setHasMore(false)
      announceNotificationsChanged()
    } catch {
      toast.error('Could not clear notifications')
    }
  }

  const openSettings = () => {
    setSettingsOpen(true)
    if (token && !prefs) getNotificationPreferences(token).then(setPrefs).catch(() => toast.error('Could not load settings'))
  }

  const changeDelivery = async (category: string, delivery: Delivery) => {
    if (!token) return
    setSavingCategory(category)
    try {
      setPrefs(await updateNotificationPreference(token, category, delivery))
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setSavingCategory(null)
    }
  }

  if (!user) return null

  const unread = items.filter(n => !n.is_read).length
  const emptyText = filter === 'unread' ? 'Nothing unread.' : filter === 'all' ? 'No notifications yet.' : 'Nothing here yet.'

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <div className="flex items-start justify-between gap-3 pt-1">
        <div className="min-w-0">
          <h1 className="text-xl font-extrabold tracking-tight md:text-2xl">Notifications</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {unread > 0 ? `${unread} unread on this page` : 'You’re all caught up'}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={readAll}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-emerald-700 hover:bg-emerald-500/10 dark:text-emerald-400 cursor-pointer"
          >
            <CheckCheck className="h-4 w-4" />
            <span className="max-sm:sr-only">Read all</span>
          </button>
          <button
            type="button"
            onClick={openSettings}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-xl border border-border px-3 text-sm font-semibold text-foreground hover:bg-muted cursor-pointer"
          >
            <Settings2 className="h-4 w-4" />
            Settings
          </button>
        </div>
      </div>

      <PushAlertsBanner className="overflow-hidden rounded-2xl border border-border" />

      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none]" role="tablist" aria-label="Filter notifications">
        {NOTIFICATION_FILTERS.map(f => (
          <button
            key={f.id}
            type="button"
            role="tab"
            aria-selected={filter === f.id}
            onClick={() => chooseFilter(f.id)}
            className={cn(
              'min-h-10 shrink-0 rounded-full border px-4 text-sm font-semibold transition-colors cursor-pointer',
              filter === f.id
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border bg-card text-foreground hover:bg-muted',
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <section className="overflow-hidden rounded-2xl border border-border bg-card" aria-live="polite">
        {loading ? (
          <div className="flex items-center justify-center gap-2 p-10 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin text-primary" /> Loading…
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 p-10 text-center">
            <Bell className="h-7 w-7 text-muted-foreground/60" aria-hidden="true" />
            <p className="text-sm font-semibold text-foreground">{emptyText}</p>
          </div>
        ) : (
          <NotificationList
            items={items}
            onOpen={n => {
              if (!n.is_read) setItems(prev => prev.map(x => (x.id === n.id ? { ...x, is_read: true } : x)))
              openNotification(n)
            }}
            onMarkRead={markRead}
            onDelete={remove}
            onDecided={decided}
          />
        )}
      </section>

      {hasMore && (
        <button
          type="button"
          onClick={loadMore}
          disabled={loadingMore}
          className="flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl border border-border bg-card text-sm font-semibold text-foreground hover:bg-muted disabled:opacity-60 cursor-pointer"
        >
          {loadingMore && <Loader2 className="h-4 w-4 animate-spin" />}
          Load older notifications
        </button>
      )}

      {items.length > 0 && (
        <div className="flex justify-center pb-2">
          <button
            type="button"
            onClick={clearAll}
            className="inline-flex min-h-11 items-center gap-1.5 rounded-xl px-3 text-sm font-semibold text-rose-600 hover:bg-rose-500/10 dark:text-rose-400 cursor-pointer"
          >
            <Trash2 className="h-4 w-4" />
            Delete all notifications
          </button>
        </div>
      )}

      <BottomSheet
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        title="Notification settings"
        description="Alerts = in the app and on your device. In-app = only in this list."
      >
        {!prefs ? (
          <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin text-primary" /> Loading…
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {prefs.map(p => (
              <li key={p.category} className="py-3.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-bold text-foreground">{p.label}</p>
                  {savingCategory === p.category && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">{p.description}</p>
                <div className="mt-2.5 grid grid-cols-3 gap-1 rounded-xl bg-muted p-1" role="radiogroup" aria-label={`${p.label} delivery`}>
                  {DELIVERY_OPTIONS.map(opt => {
                    const locked = opt.id === 'off' && !p.can_turn_off
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        role="radio"
                        aria-checked={p.delivery === opt.id}
                        disabled={locked || savingCategory === p.category}
                        onClick={() => changeDelivery(p.category, opt.id)}
                        title={locked ? 'This category can’t be turned off' : undefined}
                        className={cn(
                          'min-h-10 rounded-lg text-sm font-semibold transition-colors cursor-pointer disabled:cursor-not-allowed',
                          p.delivery === opt.id ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
                          locked && 'opacity-40',
                        )}
                      >
                        {opt.label}
                      </button>
                    )
                  })}
                </div>
              </li>
            ))}
          </ul>
        )}
      </BottomSheet>
    </div>
  )
}
