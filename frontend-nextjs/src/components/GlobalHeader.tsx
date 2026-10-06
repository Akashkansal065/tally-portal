'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { isAdminUser } from '@/lib/navigation'
import {
  MapPin,
  X,
  Building,
  ArrowLeft,
  Info,
  Phone,
  Mail,
  Globe,
  Hash,
  Edit3,
  Save,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  CreditCard,
  Bell,
  CheckCheck,
  Check,
  CloudOff,
} from 'lucide-react'
import { forgetBranding } from '@/lib/branding'
import { cn, API_BASE, authHeaders } from '@/lib/utils'
import { getOfflineQueue } from '@/lib/offline-storage'
import { useState, useEffect, useRef } from 'react'
import { NotificationList } from '@/components/notifications/NotificationList'
import { PushAlertsBanner } from '@/components/notifications/PushAlertsBanner'
import { useOpenNotification } from '@/hooks/useOpenNotification'
import {
  NOTIFICATIONS_CHANGED,
  deleteNotification as deleteNotificationRequest,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type AppNotification,
} from '@/lib/notifications'

// Newest notifications shown in the bell; the Notifications page has the rest
const BELL_LIMIT = 20

// 44pt touch target for every icon button in the header
const HEADER_ICON_BUTTON = 'inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-white hover:bg-emerald-600/60 transition-colors cursor-pointer'

export function GlobalHeader() {
  const { user, token, permissions, switchCompany } = useAuth()
  const isAdmin = isAdminUser(permissions, user?.role)
  const pathname = usePathname()
  const router = useRouter()
  const [showCompanySheet, setShowCompanySheet] = useState(false)
  const [showCompanyModal, setShowCompanyModal] = useState(false)
  const [isEditingCompany, setIsEditingCompany] = useState(false)
  const [savingCompany, setSavingCompany] = useState(false)
  const [editError, setEditError] = useState('')
  const [editSuccess, setEditSuccess] = useState('')
  const [syncHealth, setSyncHealth] = useState<{
    status: string
    total_sync_issues: number
    unreconciled_deleted_count: number
    total_failed_traffic: number
    pending_queue_count: number
  } | null>(null)

  const isAdminRef = useRef(isAdmin)
  isAdminRef.current = isAdmin

  useEffect(() => {
    if (!token || !isAdminRef.current) return
    const fetchSyncHealth = async () => {
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') {
        return
      }
      if (!isAdminRef.current) return
      try {
        const res = await fetch(`${API_BASE}/sync/health`, {
          headers: authHeaders(token)
        })
        if (res.ok) {
          const data = await res.json()
          setSyncHealth(data)
        }
      } catch (e) {
        // silent fail
      }
    }
    fetchSyncHealth()
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return
      fetchSyncHealth()
    }, 60000)
    return () => clearInterval(interval)
  }, [token])

  // Notification States
  const [unreadNotifCount, setUnreadNotifCount] = useState<number>(0)
  const [showNotifications, setShowNotifications] = useState<boolean>(false)
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const [loadingNotifications, setLoadingNotifications] = useState<boolean>(false)
  const openNotification = useOpenNotification()

  // Offline Queue States
  const [offlinePendingCount, setOfflinePendingCount] = useState<number>(0)

  useEffect(() => {
    const updateOfflineCount = async () => {
      try {
        const q = await getOfflineQueue()
        const pending = q.filter((i) => i.status === 'pending' || i.status === 'failed')
        setOfflinePendingCount(pending.length)
      } catch {
        // silent
      }
    }
    updateOfflineCount()
    window.addEventListener('mytally:offline-queue-changed', updateOfflineCount)
    return () => window.removeEventListener('mytally:offline-queue-changed', updateOfflineCount)
  }, [])

  const lastUnreadFetchTime = useRef<number>(0)
  const fetchUnreadCount = async (force: boolean = false) => {
    if (!token) return
    const now = Date.now()
    if (!force && now - lastUnreadFetchTime.current < 20000) return
    lastUnreadFetchTime.current = now
    try {
      const res = await fetch(`${API_BASE}/notifications/unread-count`, {
        headers: authHeaders(token),
      })
      if (res.ok) {
        const data = await res.json()
        setUnreadNotifCount(data.count || 0)
      }
    } catch (e) {
      // silent fail
    }
  }

  const fetchNotifications = async () => {
    if (!token) return
    setLoadingNotifications(true)
    try {
      setNotifications(await listNotifications(token, 'all', BELL_LIMIT))
    } catch (e) {
      console.error('Failed to fetch notifications:', e)
    } finally {
      setLoadingNotifications(false)
    }
  }

  const markAllAsRead = async () => {
    if (!token) return
    try {
      await markAllNotificationsRead(token)
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
      setUnreadNotifCount(0)
    } catch (e) {
      console.error('Failed to mark all as read:', e)
    }
  }

  const markAsRead = async (notif: AppNotification) => {
    if (!token) return
    setNotifications(prev => prev.map(n => (n.id === notif.id ? { ...n, is_read: true } : n)))
    setUnreadNotifCount(prev => Math.max(0, prev - 1))
    markNotificationRead(token, notif.id).catch(e => console.error('Failed to mark notification as read:', e))
  }

  const dismissNotification = async (notif: AppNotification) => {
    if (!token) return
    setNotifications(prev => prev.filter(n => n.id !== notif.id))
    if (!notif.is_read) setUnreadNotifCount(prev => Math.max(0, prev - 1))
    deleteNotificationRequest(token, notif.id).catch(e => console.error('Failed to delete notification:', e))
  }

  const handleDecided = (notif: AppNotification, decision: 'approved' | 'rejected') => {
    setNotifications(prev => prev.map(n => (n.id === notif.id ? { ...n, decision, is_read: true } : n)))
    if (!notif.is_read) {
      setUnreadNotifCount(prev => Math.max(0, prev - 1))
      if (token) markNotificationRead(token, notif.id).catch(() => {})
    }
  }

  // Close first and navigate at once; marking it read happens in the background
  const handleNotificationClick = (notif: AppNotification) => {
    setShowNotifications(false)
    if (!notif.is_read) {
      setNotifications(prev => prev.map(n => (n.id === notif.id ? { ...n, is_read: true } : n)))
      setUnreadNotifCount(prev => Math.max(0, prev - 1))
    }
    openNotification(notif)
  }

  // Other screens (the Notifications page, approvals) changed something: refresh the badge
  useEffect(() => {
    const refresh = () => fetchUnreadCount(true)
    window.addEventListener(NOTIFICATIONS_CHANGED, refresh)
    return () => window.removeEventListener(NOTIFICATIONS_CHANGED, refresh)
  }, [token])

  useEffect(() => {
    if (!token) return
    fetchUnreadCount(true)
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return
      fetchUnreadCount(true)
    }, 120000)

    const handleVisibilityChange = () => {
      if (typeof document !== 'undefined' && !document.hidden) {
        fetchUnreadCount(false)
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      clearInterval(interval)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [token, user?.company_id])

  const [formData, setFormData] = useState({
    name: '',
    address_line1: '',
    address_line2: '',
    state: '',
    country: '',
    pincode: '',
    telephone: '',
    mobile: '',
    email: '',
    website: '',
    gstin: '',
    pan: '',
    books_begin_date: '',
    financial_year_start: '',
    upi_id: ''
  })

  if (!user) return null

  const isHome = pathname === '/'
  const activeCompany = user.allowedCompanies?.find(c => c.company_id === user.company_id)

  const handleOpenCompanyModal = () => {
    if (activeCompany) {
      setFormData({
        name: activeCompany.name || '',
        address_line1: activeCompany.address_line1 || '',
        address_line2: activeCompany.address_line2 || '',
        state: activeCompany.state || '',
        country: activeCompany.country || 'India',
        pincode: activeCompany.pincode || '',
        telephone: activeCompany.telephone || '',
        mobile: activeCompany.mobile || '',
        email: activeCompany.email || '',
        website: activeCompany.website || '',
        gstin: activeCompany.gstin || '',
        pan: activeCompany.pan || '',
        books_begin_date: activeCompany.books_begin_date || '',
        financial_year_start: activeCompany.financial_year_start || '',
        upi_id: (activeCompany as any).features?.upi_id || (activeCompany as any).features?.upi_vpa || ''
      })
    }
    setIsEditingCompany(false)
    setEditError('')
    setEditSuccess('')
    setShowCompanyModal(true)
  }

  const startEditingCompany = () => {
    if (activeCompany) {
      setFormData({
        name: activeCompany.name || '',
        address_line1: activeCompany.address_line1 || '',
        address_line2: activeCompany.address_line2 || '',
        state: activeCompany.state || '',
        country: activeCompany.country || 'India',
        pincode: activeCompany.pincode || '',
        telephone: activeCompany.telephone || '',
        mobile: activeCompany.mobile || '',
        email: activeCompany.email || '',
        website: activeCompany.website || '',
        gstin: activeCompany.gstin || '',
        pan: activeCompany.pan || '',
        books_begin_date: activeCompany.books_begin_date || '',
        financial_year_start: activeCompany.financial_year_start || '',
        upi_id: (activeCompany as any).features?.upi_id || (activeCompany as any).features?.upi_vpa || ''
      })
    }
    setEditError('')
    setEditSuccess('')
    setIsEditingCompany(true)
  }

  const handleSaveCompanyDetails = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeCompany) return
    setSavingCompany(true)
    setEditError('')
    setEditSuccess('')
    try {
      const token = localStorage.getItem('mytally_token') || localStorage.getItem('token')
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
      const res = await fetch(`${API_BASE}/companies/${activeCompany.company_id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-Company-ID': activeCompany.company_id.toString()
        },
        body: JSON.stringify(formData)
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to update company details')
      }
      setEditSuccess('Company details updated & queued for Tally sync!')
      forgetBranding()
      setIsEditingCompany(false)
      setTimeout(() => {
        window.location.reload()
      }, 1200)
    } catch (err: any) {
      setEditError(err.message || 'Error updating company profile')
    } finally {
      setSavingCompany(false)
    }
  }

  return (
    <>
      <header
        className={cn(
          "shrink-0 border-b border-emerald-600/30 bg-emerald-500 dark:bg-emerald-600 text-white relative z-40",
          (showNotifications || showCompanyModal) && "z-50"
        )}
        style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}
      >
        <div className="flex items-center justify-between gap-2 pl-2 pr-1 sm:px-3 h-14">
          {/* Left: back button, logo, and the active company (tap to switch or see its profile) */}
          <div className="flex items-center gap-1 min-w-0">
            {!isHome && pathname !== '/login' && pathname !== '/signup' && (
              <button
                onClick={() => router.back()}
                className={HEADER_ICON_BUTTON}
                aria-label="Go back"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
            )}
            <Link href="/" className="shrink-0 rounded-md" aria-label="Home">
              <img src="/logo.png" alt="" className="h-8 w-8 object-contain rounded-md bg-white p-0.5" />
            </Link>
            {user.allowedCompanies && user.allowedCompanies.length > 0 ? (
              <button
                type="button"
                onClick={() => setShowCompanySheet(true)}
                aria-haspopup="dialog"
                className="ml-1 flex min-h-11 min-w-0 items-center gap-1 rounded-lg px-1.5 text-left hover:bg-emerald-600/60 cursor-pointer"
              >
                <span className="truncate text-base sm:text-lg font-extrabold">{activeCompany?.name || 'Select company'}</span>
                <ChevronDown className="h-4 w-4 shrink-0 opacity-80" aria-hidden="true" />
              </button>
            ) : (
              <Link href="/" className="ml-1 truncate text-base sm:text-lg font-extrabold hover:opacity-90">
                Sneh Distributors
              </Link>
            )}
          </div>

          {/* Right: sync status, offline queue, notifications */}
          <div className="flex items-center gap-1.5">
            {syncHealth && isAdmin && (
              <Link
                href="/admin?tab=sync"
                className="group inline-flex min-h-11 shrink-0 items-center cursor-pointer"
                title={
                  syncHealth.total_sync_issues > 0
                    ? `${syncHealth.total_sync_issues} Tally sync discrepancies detected across Create, Alter, or Delete actions. Click to view Sync Console.`
                    : "Tally Prime Live & Synced"
                }
              >
                <span className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg transition-all border shadow-sm",
                  syncHealth.total_sync_issues > 0
                    ? "bg-rose-600 group-hover:bg-rose-700 text-white border-rose-400 animate-pulse"
                    : "bg-white/20 group-hover:bg-white/30 text-white border-white/20"
                )}>
                <span className={cn("w-2 h-2 rounded-full", syncHealth.total_sync_issues > 0 ? "bg-white" : "bg-emerald-300")}></span>
                <span className="hidden sm:inline">
                  {syncHealth.total_sync_issues > 0
                    ? `${syncHealth.total_sync_issues} Sync Issues`
                    : "Tally Synced"}
                </span>
                <span className="sm:hidden">
                  {syncHealth.total_sync_issues > 0 ? `${syncHealth.total_sync_issues} Issues` : "Synced"}
                </span>
                </span>
              </Link>
            )}

            {/* Offline Sync Indicator */}
            {offlinePendingCount > 0 && (
              <button
                onClick={() => router.push('/sync')}
                className={cn(HEADER_ICON_BUTTON, "relative text-amber-300")}
                aria-label="Offline Sync Center"
                title={`${offlinePendingCount} offline item(s) pending sync. Click to open Sync Center.`}
              >
                <CloudOff className="h-5 w-5 text-amber-300 animate-pulse" />
                <span className="absolute top-1 right-1 flex items-center justify-center min-w-[17px] h-[17px] px-1 bg-amber-400 text-black font-black text-[10px] leading-none rounded-full border-2 border-emerald-600 shadow-sm">
                  {offlinePendingCount > 9 ? '9+' : offlinePendingCount}
                </span>
              </button>
            )}

            {/* Notification Bell & Dropdown */}
            <div className="relative">
              <button
                onClick={() => {
                  const nextState = !showNotifications
                  setShowNotifications(nextState)
                  if (nextState) {
                    fetchNotifications()
                  }
                }}
                className={cn(
                  HEADER_ICON_BUTTON, "relative",
                  showNotifications && "bg-emerald-600/80 z-50 ring-2 ring-white/20"
                )}
                aria-label="Notifications"
                title="Notifications"
              >
                <Bell className="h-5 w-5" />
                {unreadNotifCount > 0 && (
                  <span className="absolute top-1 right-1 flex items-center justify-center min-w-[17px] h-[17px] px-1 bg-rose-500 text-white font-black text-[10px] leading-none rounded-full border-2 border-emerald-500 dark:border-emerald-600 shadow-sm animate-pulse">
                    {unreadNotifCount > 9 ? '9+' : unreadNotifCount}
                  </span>
                )}
              </button>

              {/* Notification Dropdown Panel */}
              {showNotifications && (
                <>
                  <div
                    className="fixed inset-0 z-40 bg-black/25 backdrop-blur-[1px] sm:bg-transparent sm:backdrop-blur-none"
                    onClick={() => setShowNotifications(false)}
                  />
                  <div className="fixed sm:absolute inset-x-3 sm:inset-x-auto sm:right-0 top-[calc(3.5rem+env(safe-area-inset-top,0px)+8px)] sm:top-full sm:mt-3 w-auto sm:w-[400px] max-w-[calc(100vw-24px)] bg-card border border-border rounded-2xl shadow-2xl z-50 overflow-hidden text-foreground animate-in fade-in slide-in-from-top-2 duration-150">
                    <div className="flex items-center justify-between gap-2 border-b border-border bg-muted/40 px-4 py-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="text-base font-extrabold text-foreground">Notifications</span>
                        {unreadNotifCount > 0 && (
                          <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-bold text-primary">
                            {unreadNotifCount} new
                          </span>
                        )}
                      </div>
                      {unreadNotifCount > 0 && (
                        <button
                          type="button"
                          onClick={markAllAsRead}
                          className="inline-flex min-h-10 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-semibold text-emerald-700 hover:underline dark:text-emerald-400 cursor-pointer"
                        >
                          <CheckCheck className="h-4 w-4" />
                          Read all
                        </button>
                      )}
                    </div>

                    <PushAlertsBanner className="border-b border-border" />

                    <div className="max-h-[min(440px,calc(100dvh-14rem))] overflow-y-auto overscroll-contain">
                      {loadingNotifications && notifications.length === 0 ? (
                        <div className="flex flex-col items-center justify-center gap-2 p-8 text-muted-foreground">
                          <Loader2 className="h-5 w-5 animate-spin text-primary" />
                          <span className="text-sm">Loading notifications…</span>
                        </div>
                      ) : notifications.length === 0 ? (
                        <div className="flex flex-col items-center justify-center gap-1.5 p-8 text-center">
                          <Bell className="h-6 w-6 text-muted-foreground/60" aria-hidden="true" />
                          <span className="text-sm font-semibold text-foreground">No notifications yet</span>
                          <span className="text-xs text-muted-foreground">You&apos;re all caught up.</span>
                        </div>
                      ) : (
                        <NotificationList
                          compact
                          items={notifications}
                          onOpen={handleNotificationClick}
                          onMarkRead={markAsRead}
                          onDelete={dismissNotification}
                          onDecided={handleDecided}
                        />
                      )}
                    </div>

                    <Link
                      href="/notifications"
                      onClick={() => setShowNotifications(false)}
                      className="flex min-h-11 items-center justify-center gap-1 border-t border-border bg-muted/25 text-sm font-semibold text-primary hover:bg-muted/50"
                    >
                      See all notifications and settings
                    </Link>
                  </div>
                </>
              )}
            </div>

          </div>
        </div>
      </header>

      <BottomSheet
        open={showCompanySheet}
        onOpenChange={setShowCompanySheet}
        title="Company"
        description={user.allowedCompanies && user.allowedCompanies.length > 1 ? 'Switch the company you are working in' : undefined}
      >
        <ul className="space-y-1.5" role="list">
          {(user.allowedCompanies ?? []).map(c => {
            const current = c.company_id === user.company_id
            return (
              <li key={c.company_id}>
                <button
                  type="button"
                  onClick={() => {
                    setShowCompanySheet(false)
                    if (!current) switchCompany(c.company_id)
                  }}
                  aria-current={current ? 'true' : undefined}
                  className={cn(
                    'flex min-h-12 w-full items-center gap-3 rounded-xl border px-4 py-2.5 text-left text-sm font-semibold transition-colors cursor-pointer',
                    current ? 'border-primary/40 bg-primary/10 text-primary' : 'border-border/70 hover:bg-muted',
                  )}
                >
                  <Building className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate">{c.name}</span>
                  {current && <Check className="h-4 w-4 shrink-0" aria-label="Current company" />}
                </button>
              </li>
            )
          })}
        </ul>
        <div className="mt-4 grid grid-cols-2 gap-2">
          {activeCompany && (
            <button
              type="button"
              onClick={() => { setShowCompanySheet(false); setShowCompanyModal(true) }}
              className="flex min-h-12 items-center justify-center gap-2 rounded-xl border border-border px-3 text-sm font-semibold hover:bg-muted cursor-pointer"
            >
              <Info className="h-4 w-4" aria-hidden="true" />
              Company profile
            </button>
          )}
          <Link
            href="/companies/new"
            onClick={() => setShowCompanySheet(false)}
            className="flex min-h-12 items-center justify-center gap-2 rounded-xl border border-border px-3 text-sm font-semibold text-emerald-700 dark:text-emerald-400 hover:bg-muted"
          >
            + New company
          </Link>
        </div>
      </BottomSheet>

      {/* Company Info / Edit Modal */}
      {showCompanyModal && activeCompany && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 text-foreground animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center font-bold">
                  <Building className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-foreground leading-snug">{activeCompany.name}</h3>
                  <span className="text-[11px] text-muted-foreground font-mono">Company ID #{activeCompany.company_id}</span>
                </div>
              </div>
              <button
                onClick={() => setShowCompanyModal(false)}
                className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {isEditingCompany ? (
              <form onSubmit={handleSaveCompanyDetails} className="space-y-3 text-xs max-h-[65vh] overflow-y-auto pr-1">
                {editError && (
                  <div className="p-2.5 rounded-xl bg-destructive/10 text-destructive text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{editError}</span>
                  </div>
                )}
                {editSuccess && (
                  <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-600 text-xs flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span>{editSuccess}</span>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-muted-foreground">Company Name</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-1.5 rounded-xl border border-input bg-background font-semibold text-xs"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">Address Line 1</label>
                    <input
                      type="text"
                      value={formData.address_line1}
                      onChange={e => setFormData({ ...formData, address_line1: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">Address Line 2</label>
                    <input
                      type="text"
                      value={formData.address_line2}
                      onChange={e => setFormData({ ...formData, address_line2: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">State</label>
                    <input
                      type="text"
                      value={formData.state}
                      onChange={e => setFormData({ ...formData, state: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">Pincode</label>
                    <input
                      type="text"
                      value={formData.pincode}
                      onChange={e => setFormData({ ...formData, pincode: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">Country</label>
                    <input
                      type="text"
                      value={formData.country}
                      onChange={e => setFormData({ ...formData, country: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">Mobile Number</label>
                    <input
                      type="text"
                      value={formData.mobile}
                      onChange={e => setFormData({ ...formData, mobile: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                      placeholder="Enter mobile number"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">Telephone</label>
                    <input
                      type="text"
                      value={formData.telephone}
                      onChange={e => setFormData({ ...formData, telephone: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">Email Address</label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={e => setFormData({ ...formData, email: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">Website</label>
                    <input
                      type="text"
                      value={formData.website}
                      onChange={e => setFormData({ ...formData, website: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">GSTIN</label>
                    <input
                      type="text"
                      value={formData.gstin}
                      onChange={e => setFormData({ ...formData, gstin: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background font-mono text-xs uppercase"
                      maxLength={15}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">PAN</label>
                    <input
                      type="text"
                      value={formData.pan}
                      onChange={e => setFormData({ ...formData, pan: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background font-mono text-xs uppercase"
                      maxLength={10}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">Books Begin Date</label>
                    <input
                      type="date"
                      value={formData.books_begin_date}
                      onChange={e => setFormData({ ...formData, books_begin_date: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-bold text-muted-foreground">Financial Year Start</label>
                    <input
                      type="date"
                      value={formData.financial_year_start}
                      onChange={e => setFormData({ ...formData, financial_year_start: e.target.value })}
                      className="w-full px-3 py-1.5 rounded-xl border border-input bg-background text-xs"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-muted-foreground flex items-center gap-1">
                    <CreditCard className="w-3 h-3 text-emerald-600" />
                    Direct Merchant UPI ID / VPA
                  </label>
                  <input
                    type="text"
                    value={formData.upi_id}
                    onChange={e => setFormData({ ...formData, upi_id: e.target.value })}
                    className="w-full px-3 py-1.5 rounded-xl border border-input bg-background font-mono text-xs"
                    placeholder="e.g. 8384854172@upi or business@okhdfcbank"
                  />
                  <span className="text-[10px] text-muted-foreground">Used for 1-click WhatsApp payment reminders and Instant QR codes.</span>
                </div>

                <div className="pt-3 flex items-center justify-end gap-2 border-t border-border">
                  <button
                    type="button"
                    onClick={() => setIsEditingCompany(false)}
                    className="px-3.5 py-1.5 rounded-xl border border-border text-xs font-semibold hover:bg-muted transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={savingCompany}
                    className="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
                  >
                    {savingCompany ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    Save & Sync to Tally
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-3.5 text-xs">
                {/* Address */}
                <div className="bg-muted/40 p-3 rounded-xl space-y-1">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-emerald-600" />
                    Address & Location
                  </div>
                  <p className="font-medium text-foreground leading-relaxed">
                    {[activeCompany.address_line1, activeCompany.address_line2, activeCompany.city, activeCompany.state, activeCompany.pincode, activeCompany.country]
                      .filter(Boolean)
                      .join(', ') || 'Address not registered in Tally'}
                  </p>
                </div>

                {/* Contact Info Grid */}
                <div className="grid grid-cols-2 gap-2.5">
                  <div className="bg-muted/40 p-2.5 rounded-xl space-y-0.5">
                    <div className="text-[10px] font-bold text-muted-foreground flex items-center gap-1">
                      <Phone className="w-3 h-3 text-emerald-600" /> Mobile Number
                    </div>
                    <div className="font-semibold text-foreground truncate">{activeCompany.mobile || 'Not set'}</div>
                  </div>

                  <div className="bg-muted/40 p-2.5 rounded-xl space-y-0.5">
                    <div className="text-[10px] font-bold text-muted-foreground flex items-center gap-1">
                      <Phone className="w-3 h-3 text-emerald-600" /> Telephone (Landline)
                    </div>
                    <div className="font-semibold text-foreground truncate">{activeCompany.telephone || 'Not set'}</div>
                  </div>

                  <div className="bg-muted/40 p-2.5 rounded-xl space-y-0.5">
                    <div className="text-[10px] font-bold text-muted-foreground flex items-center gap-1">
                      <Mail className="w-3 h-3 text-emerald-600" /> Email Address
                    </div>
                    <div className="font-semibold text-foreground truncate">{activeCompany.email || 'Not set'}</div>
                  </div>

                  <div className="bg-muted/40 p-2.5 rounded-xl space-y-0.5 col-span-2">
                    <div className="text-[10px] font-bold text-muted-foreground flex items-center gap-1">
                      <Globe className="w-3 h-3 text-emerald-600" /> Website
                    </div>
                    {activeCompany.website ? (
                      <a
                        href={activeCompany.website.startsWith('http') ? activeCompany.website : `https://${activeCompany.website}`}
                        target="_blank"
                        rel="noreferrer"
                        className="font-semibold text-emerald-600 dark:text-emerald-400 hover:underline break-all block text-xs"
                      >
                        {activeCompany.website}
                      </a>
                    ) : (
                      <div className="font-semibold text-foreground">Not set</div>
                    )}
                  </div>
                </div>

                {/* Tax & Financial Info */}
                <div className="bg-muted/40 p-3 rounded-xl space-y-2">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Hash className="w-3.5 h-3.5 text-emerald-600" /> Tax & Financial Details
                  </div>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                    <div>
                      <span className="text-muted-foreground text-[11px]">GSTIN: </span>
                      <span className="font-mono font-bold text-foreground">{activeCompany.gstin || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground text-[11px]">PAN: </span>
                      <span className="font-mono font-bold text-foreground">{activeCompany.pan || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground text-[11px]">Books Begin: </span>
                      <span className="font-medium text-foreground">{activeCompany.books_begin_date || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground text-[11px]">FY Start: </span>
                      <span className="font-medium text-foreground">{activeCompany.financial_year_start || 'N/A'}</span>
                    </div>
                  </div>
                </div>

                {/* Merchant UPI ID / VPA */}
                <div className="bg-emerald-500/10 border border-emerald-500/20 p-2.5 rounded-xl flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs text-foreground font-medium">
                    <CreditCard className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Direct Merchant UPI VPA:</span>
                    <strong className="font-mono text-emerald-600 font-bold">
                      {(activeCompany as any).features?.upi_id || (activeCompany as any).features?.upi_vpa || 'Not configured'}
                    </strong>
                  </div>
                </div>
              </div>
            )}

            {!isEditingCompany && (
              <div className="pt-2 flex items-center justify-between border-t border-border">
                {isAdmin ? (
                  <button
                    onClick={startEditingCompany}
                    className="px-3.5 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 font-bold text-xs rounded-xl flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    Edit Profile Details
                  </button>
                ) : (
                  <span className="text-[11px] text-muted-foreground italic">Read-only (Admin only)</span>
                )}
                <button
                  onClick={() => setShowCompanyModal(false)}
                  className="px-4 py-1.5 bg-primary text-primary-foreground font-semibold text-xs rounded-xl hover:bg-primary/90 transition-colors shadow-sm cursor-pointer"
                >
                  Close
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}


