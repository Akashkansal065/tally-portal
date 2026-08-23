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
    financial_year_start: ''
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
        financial_year_start: activeCompany.financial_year_start || ''
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
        financial_year_start: activeCompany.financial_year_start || ''
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
      <header className={cn("shrink-0 border-b border-emerald-600/30 bg-emerald-500 dark:bg-emerald-600 text-white z-20", drawerOpen && "z-50 relative")}>
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
                <CollapsibleMenu label="Inventory Masters" icon={Layers} defaultOpen={true}>
                  <DrawerLink href="/stocks" icon={Layers} label="Stocks" onClick={() => setDrawerOpen(false)} />
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
                  {permissions.showExpenses && (
                    <DrawerLink href="/expenses" icon={Wallet} label="Expenses" onClick={() => setDrawerOpen(false)} />
                  )}
                </CollapsibleMenu>
              )}

              {permissions.showCheckIn && (
                <CollapsibleMenu label="Utilities" icon={MapPin}>
                  <DrawerLink href="/check-in" icon={MapPin} label="Check-In" onClick={() => setDrawerOpen(false)} />
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
