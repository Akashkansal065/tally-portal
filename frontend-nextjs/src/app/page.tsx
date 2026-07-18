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
  
  useEffect(() => {
    if (!isLoading && !user) {
      router.replace('/login')
    } else if (user && permissions.showReports) {
      fetch(`${API_BASE}/reports/dashboard-summary`, { headers: authHeaders(token) })
        .then(res => res.json())
        .then(data => setDashboardData(data))
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
      {dashboardData && (
        <div className="grid grid-cols-2 gap-3 mb-6">
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-4 flex flex-col gap-1">
            <span className="text-[10px] uppercase font-bold text-emerald-600 tracking-wider">Total Sales</span>
            <span className="text-xl font-black text-emerald-700">₹{dashboardData.total_sales.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
          <div className="bg-blue-500/10 border border-blue-500/20 rounded-2xl p-4 flex flex-col gap-1">
            <span className="text-[10px] uppercase font-bold text-blue-600 tracking-wider">Total Receipts</span>
            <span className="text-xl font-black text-blue-700">₹{dashboardData.total_receipts.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-2xl p-4 flex flex-col gap-1">
            <span className="text-[10px] uppercase font-bold text-amber-600 tracking-wider">To Receive</span>
            <span className="text-xl font-black text-amber-700">₹{dashboardData.outstanding_receivables.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
          </div>
          <div className="bg-rose-500/10 border border-rose-500/20 rounded-2xl p-4 flex flex-col gap-1">
            <span className="text-[10px] uppercase font-bold text-rose-600 tracking-wider">To Pay</span>
            <span className="text-xl font-black text-rose-700">₹{dashboardData.outstanding_payables.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
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
    </div>
  )
}
