'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/components/ThemeProvider'
import {
  Home,
  FileText,
  BookOpen,
  Layers,
  BarChart3,
  Wallet,
  ShoppingCart,
  IndianRupee,
  MapPin,
  LogOut,
  Sun,
  Moon,
  Menu,
  X,
  Shield,
  Building,
  ArrowLeft,
  FileSpreadsheet,
  Info,
  Phone,
  Mail,
  Globe,
  Calendar,
  Hash,
  Edit3,
  Save,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  FolderTree,
  type LucideIcon,
  RefreshCw,
  AlertTriangle,
  Clock,
  CreditCard,
  Package,
  Warehouse,
  Scale,
  Tag,
  Users,
  History,
  Bell,
  CheckCheck,
  Check,
  Trash2,
} from 'lucide-react'
import { cn, API_BASE, authHeaders } from '@/lib/utils'
import { useState, useEffect } from 'react'

export function GlobalHeader() {
  const { user, token, logout, permissions, switchCompany } = useAuth()
  const { dark, toggle } = useTheme()
  const pathname = usePathname()
  const router = useRouter()
  const [drawerOpen, setDrawerOpen] = useState(false)
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

  useEffect(() => {
    if (!token) return
    const fetchSyncHealth = async () => {
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
    const interval = setInterval(fetchSyncHealth, 15000)
    return () => clearInterval(interval)
  }, [token])

  // Notification States
  const [unreadNotifCount, setUnreadNotifCount] = useState<number>(0)
  const [showNotifications, setShowNotifications] = useState<boolean>(false)
  const [notifications, setNotifications] = useState<any[]>([])
  const [loadingNotifications, setLoadingNotifications] = useState<boolean>(false)
  const [clearingNotifications, setClearingNotifications] = useState<boolean>(false)

  const fetchUnreadCount = async () => {
    if (!token) return
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
      const res = await fetch(`${API_BASE}/notifications?limit=50`, {
        headers: authHeaders(token),
      })
      if (res.ok) {
        const data = await res.json()
        setNotifications(data)
      }
    } catch (e) {
      console.error('Failed to fetch notifications:', e)
    } finally {
      setLoadingNotifications(false)
    }
  }

  const markAllAsRead = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    if (!token) return
    try {
      const res = await fetch(`${API_BASE}/notifications/read-all`, {
        method: 'PATCH',
        headers: authHeaders(token),
      })
      if (res.ok) {
        setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
        setUnreadNotifCount(0)
      }
    } catch (e) {
      console.error('Failed to mark all as read:', e)
    }
  }

  const markAsRead = async (notifId: number, e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    if (!token) return
    try {
      const res = await fetch(`${API_BASE}/notifications/${notifId}/read`, {
        method: 'PATCH',
        headers: authHeaders(token),
      })
      if (res.ok) {
        setNotifications((prev) =>
          prev.map((n) => (n.id === notifId ? { ...n, is_read: true } : n))
        )
        setUnreadNotifCount((prev) => Math.max(0, prev - 1))
      }
    } catch (e) {
      console.error('Failed to mark notification as read:', e)
    }
  }

  const clearAllNotifications = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    if (!token) return
    if (!confirm('Are you sure you want to clear all notifications?')) return
    setClearingNotifications(true)
    try {
      const res = await fetch(`${API_BASE}/notifications/clear-all`, {
        method: 'DELETE',
        headers: authHeaders(token),
      })
      if (res.ok) {
        setNotifications([])
        setUnreadNotifCount(0)
      }
    } catch (e) {
      console.error('Failed to clear all notifications:', e)
    } finally {
      setClearingNotifications(false)
    }
  }

  const deleteNotification = async (notifId: number, isRead: boolean, e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    if (!token) return
    try {
      const res = await fetch(`${API_BASE}/notifications/${notifId}`, {
        method: 'DELETE',
        headers: authHeaders(token),
      })
      if (res.ok) {
        setNotifications((prev) => prev.filter((n) => n.id !== notifId))
        if (!isRead) {
          setUnreadNotifCount((prev) => Math.max(0, prev - 1))
        }
      }
    } catch (e) {
      console.error('Failed to delete notification:', e)
    }
  }

  const handleNotificationClick = async (notif: any) => {
    if (!notif.is_read) {
      try {
        await fetch(`${API_BASE}/notifications/${notif.id}/read`, {
          method: 'PATCH',
          headers: authHeaders(token),
        })
        setNotifications((prev) =>
          prev.map((n) => (n.id === notif.id ? { ...n, is_read: true } : n))
        )
        setUnreadNotifCount((prev) => Math.max(0, prev - 1))
      } catch (e) {
        console.error('Failed to mark notification as read:', e)
      }
    }
    setShowNotifications(false)

    // Contextual redirection to destination screen
    if (notif.type === 'check_in' || notif.reference_type === 'visit') {
      if (isAdmin) {
        router.push('/admin?tab=visits')
      } else {
        router.push('/check-in/history')
      }
    } else if (notif.type?.startsWith('order') || notif.reference_type === 'order') {
      router.push('/temporders')
    } else if (notif.type?.startsWith('expense') || notif.reference_type === 'expense') {
      router.push('/expenses')
    } else if (notif.type === 'attendance' || notif.reference_type === 'attendance') {
      router.push('/attendance')
    } else if (notif.type?.startsWith('payment') || notif.reference_type === 'payment') {
      router.push('/payments')
    } else if (
      notif.type === 'customer' ||
      notif.reference_type === 'customer' ||
      notif.reference_type === 'customer_profile'
    ) {
      if (notif.reference_id) {
        router.push(`/customers/${notif.reference_id}`)
      } else {
        router.push('/customers')
      }
    } else {
      router.push('/')
    }
  }

  useEffect(() => {
    if (!token) return
    fetchUnreadCount()
    const interval = setInterval(fetchUnreadCount, 30000)
    return () => clearInterval(interval)
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
  const isAdmin = permissions.isAdmin || user.role?.toLowerCase() === 'admin' || user.role?.toLowerCase() === 'owner' || user.role?.toLowerCase() === 'superadmin'
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
        className={cn("shrink-0 border-b border-emerald-600/30 bg-emerald-500 dark:bg-emerald-600 text-white z-20", drawerOpen && "z-50 relative")}
        style={{ paddingTop: 'env(safe-area-inset-top, 0px)' }}
      >
        <div className="flex items-center justify-between px-4 h-14">
          {/* Left: back button, logo, and title */}
          <div className="flex items-center gap-2 min-w-0">
            {!isHome && pathname !== '/login' && pathname !== '/signup' && (
              <button
                onClick={() => router.back()}
                className="p-1.5 rounded-full hover:bg-emerald-600/60 text-white transition-colors shrink-0 cursor-pointer"
                aria-label="Go Back"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
            )}
            <img src="/logo.png" alt="Logo" className="h-8 w-8 object-contain shrink-0 rounded-md bg-white p-0.5" />
            <Link
              href="/"
              className="text-base sm:text-lg font-extrabold text-white hover:opacity-90 transition-all truncate"
            >
              Sneh Distributors
            </Link>
            
            {user.allowedCompanies && user.allowedCompanies.length > 0 && (
              <div className="ml-2 relative group hidden sm:block">
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-emerald-600/60 text-xs font-semibold text-white/90 transition-colors border border-transparent">
                  <Building className="w-3.5 h-3.5" />
                  <span className="max-w-[120px] truncate">
                    {activeCompany?.name || "Select Company"}
                  </span>
                </button>
                <div className="absolute top-full left-0 mt-1 w-56 bg-card border border-border rounded-xl shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 overflow-hidden text-foreground">
                  <div className="px-3 py-2 text-[10px] font-bold tracking-wider text-muted-foreground uppercase bg-muted/30 border-b border-border">
                    Switch Active Company
                  </div>
                  {user.allowedCompanies.map(c => (
                    <button 
                      key={c.company_id}
                      onClick={() => switchCompany(c.company_id)}
                      className={`w-full text-left px-4 py-2.5 text-xs font-medium hover:bg-muted transition-colors flex items-center justify-between ${c.company_id === user.company_id ? 'text-primary bg-primary/5 font-bold' : 'text-foreground'}`}
                    >
                      <span className="truncate">{c.name}</span>
                      {c.company_id === user.company_id && <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0"></span>}
                    </button>
                  ))}
                  <div className="border-t border-border my-1"></div>
                  <button
                    onClick={() => setShowCompanyModal(true)}
                    className="w-full text-left px-4 py-2 text-xs font-semibold text-primary hover:bg-primary/10 transition-colors flex items-center gap-2"
                  >
                    <Info className="w-3.5 h-3.5" />
                    Company Profile Details
                  </button>
                  <Link 
                    href="/companies/new"
                    className="block w-full text-left px-4 py-2 text-xs font-medium text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950 transition-colors"
                  >
                    + Create New Company
                  </Link>
                </div>
              </div>
            )}
          </div>

          {/* Right: theme + menu */}
          <div className="flex items-center gap-1.5">
            {syncHealth && (
              <Link
                href="/admin?tab=sync"
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg transition-all border cursor-pointer shrink-0 shadow-sm mr-1",
                  syncHealth.total_sync_issues > 0
                    ? "bg-rose-600 hover:bg-rose-700 text-white border-rose-400 animate-pulse"
                    : "bg-white/20 hover:bg-white/30 text-white border-white/20"
                )}
                title={
                  syncHealth.total_sync_issues > 0
                    ? `${syncHealth.total_sync_issues} Tally sync discrepancies detected across Create, Alter, or Delete actions. Click to view Sync Console.`
                    : "Tally Prime Live & Synced"
                }
              >
                <span className={cn("w-2 h-2 rounded-full", syncHealth.total_sync_issues > 0 ? "bg-white" : "bg-emerald-300")}></span>
                <span className="hidden sm:inline">
                  {syncHealth.total_sync_issues > 0
                    ? `${syncHealth.total_sync_issues} Sync Issues`
                    : "Tally Synced"}
                </span>
                <span className="sm:hidden">
                  {syncHealth.total_sync_issues > 0 ? `${syncHealth.total_sync_issues} Issues` : "Synced"}
                </span>
              </Link>
            )}

            {activeCompany && (
              <button
                onClick={() => setShowCompanyModal(true)}
                className="hidden md:flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-white/20 hover:bg-white/30 text-white rounded-lg border border-white/20 transition-colors cursor-pointer mr-1"
                title="View Active Company Profile"
              >
                <Info className="w-3.5 h-3.5" />
                <span>Info</span>
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
                className="p-2 rounded-full hover:bg-emerald-600/60 text-white transition-colors cursor-pointer relative"
                aria-label="Notifications"
                title="Notifications"
              >
                <Bell className="h-5 w-5" />
                {unreadNotifCount > 0 && (
                  <span className="absolute top-1 right-1 flex items-center justify-center min-w-[17px] h-[17px] px-1 bg-rose-500 text-white font-black text-[10px] rounded-full border-2 border-emerald-500 dark:border-emerald-600 shadow-sm animate-pulse">
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
                  <div className="fixed sm:absolute inset-x-3 sm:inset-x-auto sm:right-0 top-[calc(3.5rem+env(safe-area-inset-top,0px)+8px)] sm:top-full sm:mt-2 w-auto sm:w-96 max-w-[calc(100vw-24px)] bg-card border border-border rounded-2xl shadow-2xl z-50 overflow-hidden text-foreground animate-in fade-in slide-in-from-top-2 duration-150">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/40">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="font-extrabold text-sm text-foreground">Notifications</span>
                        {unreadNotifCount > 0 ? (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-primary/10 text-primary shrink-0">
                            {unreadNotifCount} new
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-muted text-muted-foreground shrink-0">
                            {notifications.length}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2.5 shrink-0">
                        {unreadNotifCount > 0 && (
                          <button
                            onClick={markAllAsRead}
                            className="flex items-center gap-1 text-[11px] font-semibold text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 hover:underline cursor-pointer"
                            title="Mark all notifications as read"
                          >
                            <CheckCheck className="w-3.5 h-3.5" />
                            <span>Read all</span>
                          </button>
                        )}
                        {notifications.length > 0 && (
                          <button
                            onClick={clearAllNotifications}
                            disabled={clearingNotifications}
                            className="flex items-center gap-1 text-[11px] font-semibold text-rose-500 hover:text-rose-600 dark:text-rose-400 hover:underline cursor-pointer disabled:opacity-50"
                            title="Clear all notifications"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            <span>Clear all</span>
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="max-h-[min(380px,calc(100dvh-10rem))] sm:max-h-[380px] overflow-y-auto divide-y divide-border/40">
                      {loadingNotifications ? (
                        <div className="p-8 flex flex-col items-center justify-center gap-2 text-muted-foreground">
                          <Loader2 className="w-5 h-5 animate-spin text-primary" />
                          <span className="text-xs">Loading notifications...</span>
                        </div>
                      ) : notifications.length === 0 ? (
                        <div className="p-8 text-center flex flex-col items-center justify-center gap-2 text-muted-foreground">
                          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                            <Bell className="w-5 h-5 text-muted-foreground/60" />
                          </div>
                          <span className="text-xs font-semibold text-foreground">No notifications yet</span>
                          <span className="text-[11px] text-muted-foreground">You're all caught up!</span>
                        </div>
                      ) : (
                        notifications.map((notif) => (
                          <div
                            key={notif.id}
                            onClick={() => handleNotificationClick(notif)}
                            className={cn(
                              "group p-3 flex items-start gap-3 hover:bg-muted/60 transition-colors cursor-pointer text-left relative",
                              !notif.is_read ? "bg-primary/5 font-medium" : "opacity-85 hover:opacity-100"
                            )}
                          >
                            <div className={cn(
                              "w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-0.5 transition-transform group-hover:scale-105",
                              getNotifIconBg(notif.type, notif.title)
                            )}>
                              {getNotifIcon(notif.type, notif.title)}
                            </div>
                            <div className="flex-1 min-w-0 pr-1">
                              <div className="flex items-center justify-between gap-1">
                                <h4 className={cn("text-xs truncate", !notif.is_read ? "font-bold text-foreground" : "font-semibold text-foreground/80")}>
                                  {notif.title}
                                </h4>
                                <span className="text-[10px] text-muted-foreground whitespace-nowrap shrink-0">
                                  {formatTimeAgo(notif.created_at)}
                                </span>
                              </div>
                              <p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5 leading-snug break-words">
                                {notif.message}
                              </p>
                            </div>
                            <div className="flex items-center gap-1 shrink-0 self-center">
                              {!notif.is_read && (
                                <button
                                  onClick={(e) => markAsRead(notif.id, e)}
                                  className="p-1 rounded-md text-emerald-600 hover:bg-emerald-500/10 transition-colors"
                                  title="Mark as read"
                                >
                                  <Check className="w-3.5 h-3.5" />
                                </button>
                              )}
                              <button
                                onClick={(e) => deleteNotification(notif.id, notif.is_read, e)}
                                className="p-1 rounded-md text-muted-foreground hover:text-rose-500 hover:bg-rose-500/10 transition-colors opacity-70 sm:opacity-0 sm:group-hover:opacity-100 focus:opacity-100"
                                title="Dismiss notification"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                              {!notif.is_read && (
                                <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>

            <button
              onClick={toggle}

              className="p-2 rounded-full hover:bg-emerald-600/60 text-white transition-colors cursor-pointer"
              aria-label="Toggle theme"
            >
              {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
            <button
              onClick={() => setDrawerOpen(true)}
              className="p-2 rounded-full hover:bg-emerald-600/60 text-white transition-colors cursor-pointer"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Drawer overlay */}
      {drawerOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-50"
          onClick={() => setDrawerOpen(false)}
        >
          <div
            className="absolute right-0 top-0 bottom-0 w-72 bg-card border-l border-border flex flex-col shadow-2xl z-50"
            style={{
              paddingTop: 'env(safe-area-inset-top, 0px)',
              paddingBottom: 'env(safe-area-inset-bottom, 0px)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div>
                <p className="font-bold text-sm">{user.username}</p>
                <p className="text-xs text-muted-foreground capitalize">{user.role}</p>
              </div>
              <button onClick={() => setDrawerOpen(false)} className="p-1 rounded hover:bg-muted">
                <X className="h-5 w-5" />
              </button>
            </div>

            {user.allowedCompanies && user.allowedCompanies.length > 0 && (
              <div className="px-4 py-3 border-b border-border bg-muted/20">
                <label className="block text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-1.5">
                  Active Company
                </label>
                <select
                  value={user.company_id}
                  onChange={(e) => {
                    switchCompany(Number(e.target.value))
                    setDrawerOpen(false)
                  }}
                  className="w-full bg-background border border-border rounded-xl px-3 py-2 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  {user.allowedCompanies.map((c) => (
                    <option key={c.company_id} value={c.company_id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <nav className="flex-1 overflow-y-auto p-3 space-y-1">
              {isAdmin && (
                <DrawerLink href="/admin" icon={Shield} label="Admin Panel" onClick={() => setDrawerOpen(false)} />
              )}
              
              {permissions.showLedger && (
                <CollapsibleMenu label="Accounting Masters" icon={BookOpen} defaultOpen={true}>
                  {permissions.showLedger && (
                    <DrawerLink href="/ledgers/groups" icon={Layers} label="Group" onClick={() => setDrawerOpen(false)} />
                  )}
                  <DrawerLink href="/ledgers" icon={BookOpen} label="Ledger" onClick={() => setDrawerOpen(false)} />
                  {isAdmin && (
                    <>
                      <DrawerLink href="/masters/cost-categories" icon={Layers} label="Cost Category" onClick={() => setDrawerOpen(false)} />
                      <DrawerLink href="/masters/cost-centres" icon={FolderTree} label="Cost Centre" onClick={() => setDrawerOpen(false)} />
                      <DrawerLink href="/masters/cost-centre-classes" icon={BookOpen} label="Cost Centre Class" onClick={() => setDrawerOpen(false)} />
                      <DrawerLink href="/masters/currencies" icon={BookOpen} label="Currencies" onClick={() => setDrawerOpen(false)} />
                      <DrawerLink href="/masters/voucher-types" icon={BookOpen} label="Voucher Types" onClick={() => setDrawerOpen(false)} />
                    </>
                  )}
                </CollapsibleMenu>
              )}

              {permissions.showStocks && (
                <CollapsibleMenu label="Inventory Masters" icon={Package} defaultOpen={true}>
                  <DrawerLink href="/masters/stock-groups" icon={FolderTree} label="Stock Group" onClick={() => setDrawerOpen(false)} />
                  <DrawerLink href="/masters/stock-categories" icon={Tag} label="Stock Category" onClick={() => setDrawerOpen(false)} />
                  <DrawerLink href="/stocks" icon={Package} label="Stock Item" onClick={() => setDrawerOpen(false)} />
                  <DrawerLink href="/masters/units" icon={Scale} label="Unit" onClick={() => setDrawerOpen(false)} />
                  <DrawerLink href="/masters/godowns" icon={Warehouse} label="Godown" onClick={() => setDrawerOpen(false)} />
                  <DrawerLink href="/masters/price-lists" icon={Layers} label="Price Lists" onClick={() => setDrawerOpen(false)} />
                  <DrawerLink href="/inventory/bom" icon={Layers} label="BOM & Manufacturing" onClick={() => setDrawerOpen(false)} />
                </CollapsibleMenu>
              )}

              {(permissions.showSalesLedgers || permissions.showPurchaseLedgers || permissions.showReceipts || permissions.showPayments || permissions.showOrders || permissions.showExpenses) && (
                <CollapsibleMenu label="Transactions" icon={FileText} defaultOpen={true}>
                  {(permissions.showSalesLedgers || permissions.showPurchaseLedgers || permissions.showReceipts || permissions.showPayments) && (
                    <DrawerLink href="/vouchers" icon={FileText} label="Vouchers" onClick={() => setDrawerOpen(false)} />
                  )}
                  {permissions.showOrders && (
                    <DrawerLink href="/temporders" icon={ShoppingCart} label="Orders" onClick={() => setDrawerOpen(false)} />
                  )}
                  {permissions.showPayments && (
                    <DrawerLink href="/payments" icon={IndianRupee} label="Payments" onClick={() => setDrawerOpen(false)} />
                  )}
                  {permissions.showPayments && (
                    <DrawerLink href="/outstanding" icon={Clock} label="Debtors Aging & Reminders" onClick={() => setDrawerOpen(false)} />
                  )}
                  {permissions.showExpenses && (
                    <DrawerLink href="/expenses" icon={Wallet} label="Expenses" onClick={() => setDrawerOpen(false)} />
                  )}
                </CollapsibleMenu>
              )}

              {(permissions.showCheckIn || permissions.showLedger || permissions.showSalesLedgers) && (
                <CollapsibleMenu label="Field Operations" icon={MapPin} defaultOpen={true}>
                  <DrawerLink href="/customers" icon={Users} label="Customer Directory" onClick={() => setDrawerOpen(false)} />
                  {permissions.showCheckIn && (
                    <>
                      <DrawerLink href="/planner" icon={Calendar} label="Daily Beat Planner" onClick={() => setDrawerOpen(false)} />
                      <DrawerLink href="/check-in" icon={MapPin} label="Shop Check-In" onClick={() => setDrawerOpen(false)} />
                      <DrawerLink href="/check-in/history" icon={History} label="Visit Log & Audits" onClick={() => setDrawerOpen(false)} />
                    </>
                  )}
                </CollapsibleMenu>
              )}

              {(permissions.showReports || permissions.showGst) && (
                <CollapsibleMenu label="Reports" icon={BarChart3} defaultOpen={true}>
                  {permissions.showReports && (
                    <DrawerLink href="/reports" icon={BarChart3} label="Reports" onClick={() => setDrawerOpen(false)} />
                  )}
                  {permissions.showGst && (
                    <DrawerLink href="/gst" icon={FileSpreadsheet} label="GST Returns" onClick={() => setDrawerOpen(false)} />
                  )}
                </CollapsibleMenu>
              )}
            </nav>

            <div className="p-3 border-t border-border">
              <button
                onClick={logout}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-destructive hover:bg-destructive/10 text-sm font-medium transition-colors"
              >
                <LogOut className="h-4 w-4" />
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}

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

function CollapsibleMenu({ 
  label, 
  icon: Icon, 
  children,
  defaultOpen = false
}: { 
  label: string, 
  icon: LucideIcon, 
  children: React.ReactNode,
  defaultOpen?: boolean
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  
  return (
    <div className="mb-1">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <div className="flex items-center gap-3">
          <Icon className="h-4 w-4 shrink-0" />
          {label}
        </div>
        {isOpen ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
      </button>
      {isOpen && (
        <div className="pl-6 space-y-1 mt-1 border-l-2 border-border ml-5 py-1">
          {children}
        </div>
      )}
    </div>
  )
}

function DrawerLink({
  href,
  icon: Icon,
  label,
  onClick,
}: {
  href: string
  icon: LucideIcon
  label: string
  onClick: () => void
}) {
  const pathname = usePathname()
  const isActive = href === '/' ? pathname === '/' : pathname.startsWith(href)

  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
        isActive
          ? 'bg-primary/10 text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {label}
    </Link>
  )
}

function formatTimeAgo(dateStr?: string) {
  if (!dateStr) return ''
  try {
    const now = new Date().getTime()
    const d = new Date(dateStr.endsWith('Z') || dateStr.includes('+') ? dateStr : dateStr + 'Z').getTime()
    const diffSec = Math.max(0, Math.floor((now - d) / 1000))
    if (diffSec < 60) return 'just now'
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHours = Math.floor(diffMin / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    if (diffDays < 7) return `${diffDays}d ago`
    return new Date(dateStr).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })
  } catch (e) {
    return ''
  }
}

function getNotifIcon(type: string, title?: string) {
  if (title?.toLowerCase().includes('discrepancy')) {
    return <AlertTriangle className="w-4 h-4 text-rose-600 dark:text-rose-400" />
  }
  switch (type) {
    case 'check_in':
      return <MapPin className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
    case 'order_created':
    case 'order_status':
      return <ShoppingCart className="w-4 h-4 text-sky-600 dark:text-sky-400" />
    case 'expense_created':
    case 'expense_status':
      return <Wallet className="w-4 h-4 text-amber-600 dark:text-amber-400" />
    case 'attendance':
      return <Clock className="w-4 h-4 text-purple-600 dark:text-purple-400" />
    case 'payment_created':
    case 'payment_status':
      return <IndianRupee className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
    default:
      return <Bell className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
  }
}

function getNotifIconBg(type: string, title?: string) {
  if (title?.toLowerCase().includes('discrepancy')) {
    return 'bg-rose-500/15'
  }
  switch (type) {
    case 'check_in':
      return 'bg-emerald-500/15'
    case 'order_created':
    case 'order_status':
      return 'bg-sky-500/15'
    case 'expense_created':
    case 'expense_status':
      return 'bg-amber-500/15'
    case 'attendance':
      return 'bg-purple-500/15'
    case 'payment_created':
    case 'payment_status':
      return 'bg-emerald-500/15'
    default:
      return 'bg-muted'
  }
}

