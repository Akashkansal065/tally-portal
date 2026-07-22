'use client'

import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { API_BASE, authHeaders } from '@/lib/utils'
import {
  FileText,
  BookOpen,
  Layers,
  BarChart3,
  ShoppingCart,
  IndianRupee,
  MapPin,
  Wallet,
  ArrowRight,
  Shield,
  Clock,
  FileSpreadsheet,
  X,
  Search,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface DashboardCard {
  href: string
  label: string
  description: string
  icon: React.ElementType
  color: string
  bgColor: string
  show?: boolean
}

export default function DashboardPage() {
  const { user, token, permissions, isLoading } = useAuth()
  const router = useRouter()

  const [dashboardData, setDashboardData] = useState<any>(null)
  const [detailModal, setDetailModal] = useState<string | null>(null)
  const [detailData, setDetailData] = useState<any[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  const openDetail = async (category: string) => {
    setDetailModal(category)
    setDetailLoading(true)
    setDetailData([])
    setSearchTerm('')
    try {
      const res = await fetch(`${API_BASE}/reports/dashboard-details?category=${category}`, {
        headers: authHeaders(token)
      })
      if (res.ok) {
        const data = await res.json()
        setDetailData(data)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setDetailLoading(false)
    }
  }
  
  useEffect(() => {
    if (!isLoading && !user) {
      router.replace('/login')
    } else if (user && permissions.showReports) {
      fetch(`${API_BASE}/reports/dashboard-summary`, { headers: authHeaders(token) })
        .then(res => {
          if (!res.ok) throw new Error('Failed to fetch dashboard data')
          return res.json()
        })
        .then(data => {
          if (data && typeof data.total_sales === 'number') {
            setDashboardData(data)
          }
        })
        .catch(() => {})
    }
  }, [user, isLoading, router, token, permissions.showReports])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!user) return null

  const cards: DashboardCard[] = [
    {
      href: '/vouchers',
      label: 'Vouchers',
      description: 'View and post sales, payment, and journal entries',
      icon: FileText,
      color: 'text-blue-600',
      bgColor: 'bg-blue-500/10 border-blue-500/20',
      show: true,
    },
    {
      href: '/ledgers',
      label: 'Ledgers',
      description: 'Check account balances and party statements',
      icon: BookOpen,
      color: 'text-primary',
      bgColor: 'bg-primary/10 border-primary/20',
      show: permissions.showLedger,
    },
    {
      href: '/stocks',
      label: 'Stocks & Inventory',
      description: 'Browse warehouse items, closing rates, and batch values',
      icon: Layers,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-500/10 border-emerald-500/20',
      show: permissions.showStocks,
    },
    {
      href: '/temporders',
      label: 'Temporary Orders',
      description: 'Create and manage pre-Tally customer orders',
      icon: ShoppingCart,
      color: 'text-amber-600',
      bgColor: 'bg-amber-500/10 border-amber-500/20',
      show: permissions.showOrders,
    },
    {
      href: '/payments',
      label: 'Payments',
      description: 'Collect cash, cheque, or online payments from shops',
      icon: IndianRupee,
      color: 'text-teal-600',
      bgColor: 'bg-teal-500/10 border-teal-500/20',
      show: permissions.showPayments,
    },
    {
      href: '/check-in',
      label: 'Shop Check-In',
      description: 'GPS verify shop visits with photo proof',
      icon: MapPin,
      color: 'text-rose-600',
      bgColor: 'bg-rose-500/10 border-rose-500/20',
      show: permissions.showCheckIn,
    },
    {
      href: '/expenses',
      label: 'Expenses',
      description: 'Submit business expense claims with receipt uploads',
      icon: Wallet,
      color: 'text-purple-600',
      bgColor: 'bg-purple-500/10 border-purple-500/20',
      show: permissions.showExpenses,
    },
    {
      href: '/attendance',
      label: 'Attendance Log',
      description: 'Daily punch-in, punch-out, and shift logs',
      icon: Clock,
      color: 'text-sky-600',
      bgColor: 'bg-sky-500/10 border-sky-500/20',
      show: permissions.showAttendance,
    },
    {
      href: '/reports',
      label: 'Reports',
      description: 'Day book, outstanding, stock reports and PDF exports',
      icon: BarChart3,
      color: 'text-indigo-600',
      bgColor: 'bg-indigo-500/10 border-indigo-500/20',
      show: permissions.showReports,
    },
    {
      href: '/gst',
      label: 'GST Returns',
      description: 'Manage GSTR-1, GSTR-3B filings, track eligible ITC, and export GST JSONs',
      icon: FileSpreadsheet,
      color: 'text-emerald-600',
      bgColor: 'bg-emerald-500/10 border-emerald-500/20',
      show: permissions.showGst,
    },
    {
      href: '/admin',
      label: 'Admin Panel',
      description: 'Manage users, devices, and system settings',
      icon: Shield,
      color: 'text-slate-600',
      bgColor: 'bg-slate-500/10 border-slate-500/20',
      show: permissions.isAdmin,
    },
  ].filter(c => c.show)

  return (
    <div className="p-4 space-y-6 max-w-2xl mx-auto">
      {/* Welcome block */}
      <div className="pt-2">
        <h1 className="text-2xl font-extrabold tracking-tight">
          Welcome, <span className="text-primary">{user.username}</span>
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Access your inventory management and ledger reports below.
        </p>
      </div>

{/* Metrics Row */}
      {dashboardData && typeof dashboardData.total_sales === 'number' && (
        <div className="grid grid-cols-2 gap-3 mb-6">
          <div 
            onClick={() => openDetail('sales')}
            className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-4 flex flex-col gap-1 cursor-pointer hover:scale-[1.02] active:scale-[0.98] transition-transform duration-100 hover:shadow-sm"
          >
            <span className="text-[10px] uppercase font-bold text-emerald-600 tracking-wider">Total Sales</span>
            <span className="text-xl font-black text-emerald-700">₹{dashboardData.total_sales?.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
          <div 
            onClick={() => openDetail('receipts')}
            className="bg-blue-500/10 border border-blue-500/20 rounded-2xl p-4 flex flex-col gap-1 cursor-pointer hover:scale-[1.02] active:scale-[0.98] transition-transform duration-100 hover:shadow-sm"
          >
            <span className="text-[10px] uppercase font-bold text-blue-600 tracking-wider">Total Receipts</span>
            <span className="text-xl font-black text-blue-700">₹{dashboardData.total_receipts?.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
          <div 
            onClick={() => openDetail('receivables')}
            className="bg-amber-500/10 border border-amber-500/20 rounded-2xl p-4 flex flex-col gap-1 cursor-pointer hover:scale-[1.02] active:scale-[0.98] transition-transform duration-100 hover:shadow-sm"
          >
            <span className="text-[10px] uppercase font-bold text-amber-600 tracking-wider">To Receive</span>
            <span className="text-xl font-black text-amber-700">₹{dashboardData.outstanding_receivables?.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
          <div 
            onClick={() => openDetail('payables')}
            className="bg-rose-500/10 border border-rose-500/20 rounded-2xl p-4 flex flex-col gap-1 cursor-pointer hover:scale-[1.02] active:scale-[0.98] transition-transform duration-100 hover:shadow-sm"
          >
            <span className="text-[10px] uppercase font-bold text-rose-600 tracking-wider">To Pay</span>
            <span className="text-xl font-black text-rose-700">₹{dashboardData.outstanding_payables?.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
        </div>
      )}

      {/* Dashboard grid */}
      <div className="grid grid-cols-2 gap-3">
        {cards.map(card => {
          const Icon = card.icon
          return (
            <Link key={card.href} href={card.href} className="group">
              <div
                className={cn(
                  'relative rounded-2xl border p-4 h-full flex flex-col gap-3 transition-all duration-200',
                  'hover:-translate-y-0.5 hover:shadow-lg active:scale-[0.97]',
                  card.bgColor
                )}
              >
                <div className={cn('w-9 h-9 rounded-xl flex items-center justify-center', card.bgColor)}>
                  <Icon className={cn('h-5 w-5', card.color)} />
                </div>
                <div className="flex-1">
                  <h2 className={cn('text-sm font-bold flex items-center gap-1 group-hover:underline', card.color)}>
                    {card.label}
                    <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </h2>
                  <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                    {card.description}
                  </p>
                </div>
              </div>
            </Link>
          )
        })}
      </div>

      {/* Detail Drill-down Modal */}
      {detailModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setDetailModal(null)}
        >
          <div 
            className="bg-card border border-border w-full max-w-md rounded-2xl p-6 shadow-2xl relative flex flex-col max-h-[80vh] animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <div>
                <h3 className="text-base font-black text-foreground capitalize">
                  {detailModal === 'sales' && 'Total Sales Breakdown'}
                  {detailModal === 'receipts' && 'Total Receipts Breakdown'}
                  {detailModal === 'receivables' && 'Receivables Breakdown'}
                  {detailModal === 'payables' && 'Payables Breakdown'}
                </h3>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  Detailed ledger balances contributing to summary
                </p>
              </div>
              <button 
                onClick={() => setDetailModal(null)}
                className="w-8 h-8 rounded-full border border-border flex items-center justify-center hover:bg-muted text-muted-foreground transition-colors"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>

            {/* Search filter */}
            <div className="mt-4 relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search ledgers or groups..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-4 py-2 border border-border rounded-xl text-xs bg-background text-foreground focus:outline-none focus:border-primary/50"
              />
            </div>

            {/* Ledger list container */}
            <div className="flex-1 overflow-y-auto mt-4 pr-1 space-y-2.5 divide-y divide-border/30">
              {detailLoading ? (
                <div className="flex flex-col items-center justify-center py-12 gap-2">
                  <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  <p className="text-[10px] text-muted-foreground">Fetching ledger accounts...</p>
                </div>
              ) : (
                (() => {
                  const filtered = detailData.filter(item => 
                    item.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                    item.group_name.toLowerCase().includes(searchTerm.toLowerCase())
                  )
                  
                  if (filtered.length === 0) {
                    return (
                      <p className="text-center text-xs text-muted-foreground py-8">
                        No ledger accounts found.
                      </p>
                    )
                  }
                  
                  const isCreditHeavy = detailModal === 'sales' || detailModal === 'payables'
                  
                  return filtered.map((item, idx) => {
                    const balanceSign = isCreditHeavy 
                      ? (item.balance >= 0 ? 'Cr' : 'Dr') 
                      : (item.balance >= 0 ? 'Dr' : 'Cr')
                      
                    return (
                      <div key={item.ledger_id} className={cn("flex items-center justify-between gap-3 text-xs", idx > 0 ? "pt-2.5" : "")}>
                        <div className="min-w-0 flex-1">
                          <p className="font-bold text-foreground truncate">{item.name}</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{item.group_name}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className={cn(
                            "font-black text-sm",
                            detailModal === 'sales' || detailModal === 'receipts' ? "text-emerald-600" :
                            detailModal === 'receivables' ? "text-amber-600" : "text-rose-600"
                          )}>
                            ₹{Math.abs(item.balance).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                          </span>
                          <p className="text-[9px] text-muted-foreground/80 mt-0.5 uppercase tracking-wider">
                            {balanceSign}
                          </p>
                        </div>
                      </div>
                    )
                  })
                })()
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
