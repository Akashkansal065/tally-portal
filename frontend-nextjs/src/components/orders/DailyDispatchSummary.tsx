'use client'

import { useEffect, useState, useMemo, useCallback } from 'react'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate } from '@/lib/utils'
import { toast } from 'sonner'
import {
  Truck,
  Package,
  Calendar,
  Share2,
  Printer,
  Download,
  Search,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Store,
  Layers,
  CheckSquare,
  Square,
  RefreshCw,
  SlidersHorizontal,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Sparkles,
  Info
} from 'lucide-react'
import { cn } from '@/lib/utils'

export type DispatchItemBreakdown = {
  order_id: number
  customer_name: string
  customer_gstin?: string | null
  salesperson: string
  qty: number
  unit: string
  price: number
  subtotal: number
  status: 'pending' | 'done' | 'cancelled'
  created_at?: string | null
}

export type DispatchItem = {
  key: string
  stock_item_id?: number | null
  item_name: string
  company_name?: string | null
  unit: string
  closing_stock?: number | null
  is_custom: boolean
  total_qty: number
  total_amount: number
  orders_count: number
  unique_customers_count: number
  order_breakdown: DispatchItemBreakdown[]
}

export type DispatchOrderSummary = {
  order_id: number
  user_id: number
  salesperson: string
  customer_name: string
  customer_gstin?: string | null
  items_count: number
  total_qty: number
  total_amount: number
  status: 'pending' | 'done' | 'cancelled'
  created_at?: string | null
  items: Array<{
    item_name: string
    company_name?: string | null
    qty: number
    unit: string
    price: number
    subtotal: number
    is_custom: boolean
  }>
}

export type DispatchSummaryData = {
  date: string
  start_date: string
  end_date: string
  status_filter: string
  is_manager: boolean
  total_orders: number
  total_distinct_items: number
  total_quantity: number
  total_amount: number
  items: DispatchItem[]
  orders: DispatchOrderSummary[]
}

type Salesperson = {
  user_id: number
  username: string
}

function getTodayString(): string {
  const d = new Date()
  const offset = d.getTimezoneOffset() * 60000
  const local = new Date(d.getTime() - offset)
  return local.toISOString().split('T')[0]
}

export function DailyDispatchSummary() {
  const { user, token, permissions } = useAuth()
  const [selectedDate, setSelectedDate] = useState<string>(getTodayString())
  const [statusFilter, setStatusFilter] = useState<'active' | 'pending' | 'done' | 'all'>('active')
  const [salespersonFilter, setSalespersonFilter] = useState<string>('all')
  const [salespersons, setSalespersons] = useState<Salesperson[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState<'items' | 'shops'>('items')

  const [data, setData] = useState<DispatchSummaryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())
  const [packedItems, setPackedItems] = useState<Set<string>>(new Set())

  // Fetch salespersons if admin
  useEffect(() => {
    if (!token || !permissions?.isAdmin) return
    fetch(`${API_BASE}/admin/users`, { headers: authHeaders(token) })
      .then(r => r.ok ? r.json() : [])
      .then(users => {
        if (Array.isArray(users)) setSalespersons(users)
      })
      .catch(() => {})
  }, [token, permissions?.isAdmin])

  // Fetch dispatch summary
  const fetchSummary = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const params = new URLSearchParams()
      params.set('date', selectedDate)
      params.set('status', statusFilter)
      if (salespersonFilter !== 'all') {
        params.set('salesperson_id', salespersonFilter)
      }

      const res = await fetch(`${API_BASE}/temporders/dispatch-summary?${params.toString()}`, {
        headers: authHeaders(token),
      })
      if (!res.ok) {
        throw new Error((await res.json()).detail || 'Failed to fetch dispatch summary')
      }
      const json: DispatchSummaryData = await res.json()
      setData(json)
    } catch (err: any) {
      console.error(err)
      toast.error(err.message || 'Could not load dispatch summary')
    } finally {
      setLoading(false)
    }
  }, [token, selectedDate, statusFilter, salespersonFilter])

  useEffect(() => {
    fetchSummary()
  }, [fetchSummary])

  // Reset packed items when date changes
  useEffect(() => {
    setPackedItems(new Set())
  }, [selectedDate])

  // Date Shift Helpers
  const shiftDate = (days: number) => {
    const current = new Date(selectedDate + 'T00:00:00')
    current.setDate(current.getDate() + days)
    const yyyy = current.getFullYear()
    const mm = String(current.getMonth() + 1).padStart(2, '0')
    const dd = String(current.getDate()).padStart(2, '0')
    setSelectedDate(`${yyyy}-${mm}-${dd}`)
  }

  const isToday = selectedDate === getTodayString()

  // Filtered items
  const filteredItems = useMemo(() => {
    if (!data?.items) return []
    const q = searchQuery.toLowerCase().trim()
    if (!q) return data.items
    return data.items.filter(item => {
      const matchName = item.item_name.toLowerCase().includes(q)
      const matchCompany = (item.company_name || '').toLowerCase().includes(q)
      const matchOrders = item.order_breakdown.some(b => 
        b.customer_name.toLowerCase().includes(q) || b.salesperson.toLowerCase().includes(q)
      )
      return matchName || matchCompany || matchOrders
    })
  }, [data?.items, searchQuery])

  // Filtered shop orders
  const filteredOrders = useMemo(() => {
    if (!data?.orders) return []
    const q = searchQuery.toLowerCase().trim()
    if (!q) return data.orders
    return data.orders.filter(ord => {
      const matchCust = ord.customer_name.toLowerCase().includes(q)
      const matchSp = ord.salesperson.toLowerCase().includes(q)
      const matchItem = ord.items.some(i => i.item_name.toLowerCase().includes(q))
      return matchCust || matchSp || matchItem
    })
  }, [data?.orders, searchQuery])

  // Toggle item expanded state
  const toggleExpandItem = (key: string) => {
    setExpandedItems(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const toggleAllExpanded = () => {
    if (!data?.items) return
    if (expandedItems.size === filteredItems.length) {
      setExpandedItems(new Set())
    } else {
      setExpandedItems(new Set(filteredItems.map(i => i.key)))
    }
  }

  // Toggle packed state
  const togglePacked = (key: string) => {
    setPackedItems(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // Copy WhatsApp Summary
  const handleCopyWhatsApp = () => {
    if (!data || data.items.length === 0) {
      toast.error('No items to copy')
      return
    }

    const dObj = new Date(selectedDate + 'T00:00:00')
    const dateFormatted = dObj.toLocaleDateString('en-IN', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })

    const statusTitle =
      statusFilter === 'pending' ? 'Pending Orders' :
      statusFilter === 'done' ? 'Approved Orders' :
      statusFilter === 'all' ? 'All Orders' : 'Active Orders'

    let text = `📦 *DAILY DISPATCH SUMMARY - ${dateFormatted}*\n`
    text += `🎯 *Status:* ${statusTitle} | *For Tomorrow Dispatch*\n`
    text += `━━━━━━━━━━━━━━━━━━━━━━━━━━\n`
    text += `📊 *Total Orders:* ${data.total_orders}\n`
    text += `🏷️ *Unique Items:* ${data.total_distinct_items}\n`
    text += `🔢 *Total Quantity:* ${data.total_quantity.toLocaleString('en-IN')} units\n`
    text += `💰 *Total Value:* ₹${Math.round(data.total_amount).toLocaleString('en-IN')}\n`
    text += `━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`
    text += `*📋 CONSOLIDATED ITEM QUANTITIES:*\n\n`

    filteredItems.forEach((item, idx) => {
      const brandStr = item.company_name ? ` _(${item.company_name})_` : ''
      text += `${idx + 1}. *${item.item_name}*${brandStr}\n`
      text += `   ↳ *Total: ${item.total_qty} ${item.unit}*  (in ${item.orders_count} ${item.orders_count === 1 ? 'shop' : 'shops'})\n`
      if (item.closing_stock != null) {
        text += `   ↳ Current Stock: ${item.closing_stock} ${item.unit}\n`
      }
    })

    text += `\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n`
    text += `_Generated via MyTally Field Portal_`

    navigator.clipboard.writeText(text)
    toast.success('WhatsApp dispatch summary copied to clipboard!')
  }

  // Export CSV
  const handleExportCsv = () => {
    if (!data || data.items.length === 0) {
      toast.error('No items to export')
      return
    }

    const headers = [
      'Sr',
      'Item Name',
      'Brand/Group',
      'Total Required Qty',
      'Unit',
      'Tally Closing Stock',
      'No. of Orders',
      'Unique Shops',
      'Estimated Value (Rs)',
      'Customer Breakdown'
    ]

    const rows = filteredItems.map((item, idx) => {
      const breakdownStr = item.order_breakdown
        .map(b => `${b.customer_name}: ${b.qty} ${b.unit}`)
        .join('; ')
      return [
        idx + 1,
        `"${item.item_name.replace(/"/g, '""')}"`,
        `"${(item.company_name || 'General').replace(/"/g, '""')}"`,
        item.total_qty,
        item.unit,
        item.closing_stock != null ? item.closing_stock : '',
        item.orders_count,
        item.unique_customers_count,
        item.total_amount,
        `"${breakdownStr.replace(/"/g, '""')}"`
      ]
    })

    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `dispatch_summary_${selectedDate}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    toast.success('CSV downloaded!')
  }

  const packedCount = packedItems.size
  const totalCount = filteredItems.length
  const packingProgressPercent = totalCount > 0 ? Math.round((packedCount / totalCount) * 100) : 0

  return (
    <div className="space-y-4">
      {/* Print-only CSS rules */}
      <style jsx global>{`
        @media print {
          body * {
            visibility: hidden;
          }
          #dispatch-print-section,
          #dispatch-print-section * {
            visibility: visible;
          }
          #dispatch-print-section {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            padding: 20px;
            background: white !important;
            color: black !important;
          }
          .no-print {
            display: none !important;
          }
        }
      `}</style>

      {/* Top Banner & Action Controls */}
      <div className="bg-card border border-border rounded-2xl p-4 shadow-sm space-y-3.5 no-print">
        {/* Date Selector Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
                <Truck className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-base font-extrabold text-foreground tracking-tight flex items-center gap-2">
                  Daily Dispatch Summary
                  <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                    Tomorrow Dispatch
                  </span>
                </h2>
                <p className="text-[11px] text-muted-foreground">
                  Consolidated item quantities for packing and loading
                </p>
              </div>
            </div>
          </div>

          {/* Quick Actions (WhatsApp, Print, CSV) */}
          <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
            <button
              onClick={handleCopyWhatsApp}
              disabled={loading || !data?.items?.length}
              className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition-all shadow-sm active:scale-95 cursor-pointer whitespace-nowrap"
              title="Copy WhatsApp text formatted list"
            >
              <Share2 className="h-3.5 w-3.5" />
              <span>Copy WhatsApp</span>
            </button>
            <button
              onClick={() => window.print()}
              disabled={loading || !data?.items?.length}
              className="flex items-center justify-center gap-1.5 px-3 py-1.5 bg-muted hover:bg-muted/80 text-foreground border border-border disabled:opacity-50 rounded-xl text-xs font-bold transition-all active:scale-95 cursor-pointer whitespace-nowrap"
              title="Print Packing Sheet"
            >
              <Printer className="h-3.5 w-3.5" />
              <span>Print</span>
            </button>
            <button
              onClick={handleExportCsv}
              disabled={loading || !data?.items?.length}
              className="flex items-center justify-center gap-1.5 px-3 py-1.5 bg-muted hover:bg-muted/80 text-foreground border border-border disabled:opacity-50 rounded-xl text-xs font-bold transition-all active:scale-95 cursor-pointer whitespace-nowrap"
              title="Download CSV"
            >
              <Download className="h-3.5 w-3.5" />
              <span>CSV</span>
            </button>
          </div>
        </div>

        {/* Date Controls */}
        <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-border/50">
          <div className="flex items-center bg-muted/40 border border-border rounded-xl p-0.5">
            <button
              onClick={() => shiftDate(-1)}
              className="p-1.5 hover:bg-muted text-muted-foreground hover:text-foreground rounded-lg transition-colors cursor-pointer"
              title="Previous day"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setSelectedDate(getTodayString())}
              className={cn(
                'px-2.5 py-1 text-xs font-bold rounded-lg transition-colors cursor-pointer',
                isToday ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              Today
            </button>
            <button
              onClick={() => shiftDate(1)}
              className="p-1.5 hover:bg-muted text-muted-foreground hover:text-foreground rounded-lg transition-colors cursor-pointer"
              title="Next day"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="flex items-center gap-1.5 bg-muted/40 border border-border rounded-xl px-2.5 py-1 text-xs">
            <Calendar className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <input
              type="date"
              value={selectedDate}
              onChange={e => e.target.value && setSelectedDate(e.target.value)}
              className="bg-transparent border-none text-xs font-bold focus:outline-none cursor-pointer text-foreground"
            />
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value as any)}
            className="bg-muted/40 border border-border rounded-xl px-2.5 py-1.5 text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
          >
            <option value="active">Active (Pending + Done)</option>
            <option value="pending">Pending Only</option>
            <option value="done">Approved (Done) Only</option>
            <option value="all">All (Incl. Cancelled)</option>
          </select>

          {/* Salesperson Filter (for admins) */}
          {permissions?.isAdmin && salespersons.length > 0 && (
            <select
              value={salespersonFilter}
              onChange={e => setSalespersonFilter(e.target.value)}
              className="bg-muted/40 border border-border rounded-xl px-2.5 py-1.5 text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
            >
              <option value="all">All Salespersons</option>
              {salespersons.map(sp => (
                <option key={sp.user_id} value={String(sp.user_id)}>
                  {sp.username}
                </option>
              ))}
            </select>
          )}

          <button
            onClick={fetchSummary}
            className="p-1.5 hover:bg-muted text-muted-foreground hover:text-foreground rounded-xl border border-border transition-colors cursor-pointer ml-auto"
            title="Refresh"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* KPI Overview Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 no-print">
        <div className="bg-card border border-border rounded-2xl p-3 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider">Orders</span>
            <Package className="h-4 w-4 text-amber-500" />
          </div>
          <p className="text-xl font-black text-foreground">{loading ? '...' : data?.total_orders ?? 0}</p>
          <p className="text-[10px] text-muted-foreground font-semibold">on {selectedDate}</p>
        </div>

        <div className="bg-card border border-border rounded-2xl p-3 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider">Distinct Items</span>
            <Layers className="h-4 w-4 text-blue-500" />
          </div>
          <p className="text-xl font-black text-foreground">{loading ? '...' : data?.total_distinct_items ?? 0}</p>
          <p className="text-[10px] text-muted-foreground font-semibold">SKUs to pick</p>
        </div>

        <div className="bg-card border border-border rounded-2xl p-3 shadow-xs bg-emerald-500/5 border-emerald-500/20">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">Total Quantity</span>
            <Truck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          </div>
          <p className="text-xl font-black text-emerald-700 dark:text-emerald-400">
            {loading ? '...' : data?.total_quantity.toLocaleString('en-IN') ?? 0}
          </p>
          <p className="text-[10px] text-emerald-600/70 dark:text-emerald-400/70 font-semibold">Units to dispatch</p>
        </div>

        <div className="bg-card border border-border rounded-2xl p-3 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider">Total Value</span>
            <span className="text-xs font-bold text-muted-foreground">₹</span>
          </div>
          <p className="text-xl font-black text-foreground">
            {loading ? '...' : formatCurrency(data?.total_amount ?? 0)}
          </p>
          <p className="text-[10px] text-muted-foreground font-semibold">Booking amount</p>
        </div>
      </div>

      {/* Packing Progress Bar (Interactive Checklist) */}
      {viewMode === 'items' && filteredItems.length > 0 && (
        <div className="bg-card border border-border rounded-xl p-3 shadow-2xs no-print flex items-center justify-between gap-3 text-xs">
          <div className="flex-1 space-y-1">
            <div className="flex items-center justify-between text-[11px] font-bold">
              <span className="flex items-center gap-1.5 text-foreground">
                <CheckSquare className="h-3.5 w-3.5 text-emerald-600" />
                Warehouse Packing Progress:
              </span>
              <span className="text-muted-foreground">
                {packedCount} / {totalCount} items ({packingProgressPercent}%)
              </span>
            </div>
            <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
              <div 
                className="h-full bg-emerald-500 transition-all duration-300 rounded-full"
                style={{ width: `${packingProgressPercent}%` }}
              />
            </div>
          </div>
          {packedCount > 0 && (
            <button
              onClick={() => setPackedItems(new Set())}
              className="text-[10px] font-bold text-muted-foreground hover:text-foreground px-2 py-1 bg-muted rounded-lg transition-colors cursor-pointer shrink-0"
            >
              Reset
            </button>
          )}
        </div>
      )}

      {/* View Switcher & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 no-print">
        {/* Toggle Mode: By Items (Packing) vs By Customer (Loading) */}
        <div className="flex items-center bg-muted/60 border border-border p-1 rounded-xl">
          <button
            onClick={() => setViewMode('items')}
            className={cn(
              'flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer',
              viewMode === 'items'
                ? 'bg-background text-foreground shadow-xs'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Package className="h-3.5 w-3.5 text-amber-500" />
            <span>By Item (Packing List)</span>
            <span className="text-[10px] font-black px-1.5 py-0.2 rounded-full bg-amber-500/10 text-amber-600">
              {filteredItems.length}
            </span>
          </button>
          <button
            onClick={() => setViewMode('shops')}
            className={cn(
              'flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer',
              viewMode === 'shops'
                ? 'bg-background text-foreground shadow-xs'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Store className="h-3.5 w-3.5 text-blue-500" />
            <span>By Shop (Vehicle Loading)</span>
            <span className="text-[10px] font-black px-1.5 py-0.2 rounded-full bg-blue-500/10 text-blue-600">
              {filteredOrders.length}
            </span>
          </button>
        </div>

        {/* Search & Accordion Controls */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1 sm:w-56">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder={viewMode === 'items' ? "Filter items or brands..." : "Filter shops or items..."}
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-card border border-border rounded-xl pl-8 pr-3 py-1.5 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>
          {viewMode === 'items' && filteredItems.length > 0 && (
            <button
              onClick={toggleAllExpanded}
              className="px-2.5 py-1.5 bg-card border border-border hover:bg-muted text-muted-foreground hover:text-foreground rounded-xl text-xs font-bold transition-colors cursor-pointer shrink-0"
              title={expandedItems.size === filteredItems.length ? "Collapse All" : "Expand All"}
            >
              {expandedItems.size === filteredItems.length ? 'Collapse All' : 'Expand All'}
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div id="dispatch-print-section">
        {/* Printable Header (Visible only when printed) */}
        <div className="hidden print:block mb-6 border-b pb-4">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-2xl font-black tracking-tight">DAILY DISPATCH & PACKING SHEET</h1>
              <p className="text-sm text-gray-600 font-semibold">
                Orders Date: {selectedDate} | For Tomorrow Dispatch
              </p>
            </div>
            <div className="text-right text-xs">
              <p className="font-bold">Total Orders: {data?.total_orders}</p>
              <p className="font-bold">Total SKUs: {data?.total_distinct_items}</p>
              <p className="font-bold">Total Qty: {data?.total_quantity} units</p>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-16 bg-card border border-border rounded-2xl">
            <div className="w-8 h-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin mb-3" />
            <p className="text-xs font-bold text-muted-foreground">Calculating daily dispatch summary...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="text-center py-14 bg-card border border-border border-dashed rounded-2xl p-6">
            <Package className="h-12 w-12 mx-auto mb-3 opacity-25 text-muted-foreground" />
            <h3 className="text-sm font-extrabold text-foreground">No dispatch orders found for {selectedDate}</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
              There are no orders placed on this date matching the status filter ({statusFilter}).
            </p>
            {!isToday && (
              <button
                onClick={() => setSelectedDate(getTodayString())}
                className="mt-4 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold transition-all cursor-pointer"
              >
                Switch to Today
              </button>
            )}
          </div>
        ) : viewMode === 'items' ? (
          /* ======================================================== */
          /* MODE 1: ITEM CONSOLIDATED PACKING LIST (Default / Core)  */
          /* ======================================================== */
          <div className="space-y-2.5">
            {filteredItems.map((item, index) => {
              const isExpanded = expandedItems.has(item.key)
              const isPacked = packedItems.has(item.key)
              const hasStockIssue =
                item.closing_stock != null && item.closing_stock < item.total_qty

              return (
                <div
                  key={item.key}
                  className={cn(
                    'bg-card border rounded-2xl p-3.5 transition-all shadow-xs',
                    isPacked
                      ? 'border-emerald-500/40 bg-emerald-500/[0.02]'
                      : 'border-border hover:border-emerald-500/30'
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    {/* Checkbox for warehouse picking */}
                    <button
                      onClick={() => togglePacked(item.key)}
                      className="mt-0.5 text-muted-foreground hover:text-emerald-600 transition-colors cursor-pointer shrink-0 no-print"
                      title={isPacked ? "Mark as unpacked" : "Mark as packed"}
                    >
                      {isPacked ? (
                        <CheckSquare className="h-5 w-5 text-emerald-600" />
                      ) : (
                        <Square className="h-5 w-5 text-muted-foreground/60" />
                      )}
                    </button>

                    {/* Print Checkbox */}
                    <span className="hidden print:inline-block w-4 h-4 border border-black mr-2 mt-0.5"></span>

                    {/* Item Information */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[11px] font-mono font-bold text-muted-foreground/80">
                          #{index + 1}
                        </span>
                        <h4 className={cn(
                          'text-sm font-extrabold text-foreground break-words',
                          isPacked && 'line-through text-muted-foreground'
                        )}>
                          {item.item_name}
                        </h4>
                        {item.company_name && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-muted text-muted-foreground border border-border">
                            {item.company_name}
                          </span>
                        )}
                        {item.is_custom && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md bg-amber-500/10 text-amber-600 border border-amber-500/20">
                            Custom Item
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3 mt-1.5 text-[11px] text-muted-foreground font-semibold flex-wrap">
                        <span className="flex items-center gap-1">
                          <Store className="h-3 w-3 text-muted-foreground" />
                          <span>
                            Ordered by <strong className="text-foreground">{item.orders_count}</strong> {item.orders_count === 1 ? 'shop' : 'shops'}
                          </span>
                        </span>
                        <span>•</span>
                        <span>
                          Value: <strong className="text-foreground">{formatCurrency(item.total_amount)}</strong>
                        </span>

                        {/* Stock status indicator */}
                        {item.closing_stock != null && (
                          <>
                            <span>•</span>
                            <span className={cn(
                              'flex items-center gap-1 font-bold',
                              hasStockIssue ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'
                            )}>
                              {hasStockIssue ? (
                                <>
                                  <AlertTriangle className="h-3 w-3 shrink-0" />
                                  <span>Tally Stock: {item.closing_stock} {item.unit} (Short by {item.total_qty - item.closing_stock})</span>
                                </>
                              ) : (
                                <>
                                  <CheckCircle2 className="h-3 w-3 shrink-0" />
                                  <span>Tally Stock: {item.closing_stock} {item.unit}</span>
                                </>
                              )}
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Total Quantity Pill */}
                    <div className="flex flex-col items-end shrink-0 gap-1">
                      <div className="bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-xl text-right">
                        <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 block leading-none">
                          Total Qty
                        </span>
                        <span className="text-base sm:text-lg font-black text-emerald-700 dark:text-emerald-300 font-mono">
                          {item.total_qty} <span className="text-xs font-bold">{item.unit}</span>
                        </span>
                      </div>

                      <button
                        onClick={() => toggleExpandItem(item.key)}
                        className="text-[10px] font-bold text-muted-foreground hover:text-foreground flex items-center gap-0.5 px-1 py-0.5 rounded transition-colors cursor-pointer no-print"
                      >
                        <span>{isExpanded ? 'Hide Shops' : `View ${item.orders_count} Shops`}</span>
                        {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                      </button>
                    </div>
                  </div>

                  {/* Expandable Customer / Shop Breakdown */}
                  {isExpanded && (
                    <div className="mt-3 pt-3 border-t border-border/60 space-y-2">
                      <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                        Customer & Order Breakdown:
                      </p>
                      <div className="space-y-1.5">
                        {item.order_breakdown.map((b, bIdx) => (
                          <div
                            key={`${b.order_id}-${bIdx}`}
                            className="flex items-center justify-between text-xs bg-muted/40 p-2 rounded-xl border border-border/40"
                          >
                            <div className="min-w-0 pr-2">
                              <p className="font-extrabold text-foreground truncate">{b.customer_name}</p>
                              <p className="text-[10px] text-muted-foreground">
                                Order #{b.order_id} • Salesperson: {b.salesperson}
                              </p>
                            </div>
                            <div className="text-right shrink-0">
                              <p className="font-mono font-black text-emerald-600 dark:text-emerald-400">
                                {b.qty} {b.unit}
                              </p>
                              <p className="text-[10px] text-muted-foreground font-mono">
                                @ ₹{b.price} = {formatCurrency(b.subtotal)}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          /* ======================================================== */
          /* MODE 2: CUSTOMER / SHOP-WISE LOADING LIST                */
          /* ======================================================== */
          <div className="space-y-3">
            {filteredOrders.map(ord => (
              <div
                key={ord.order_id}
                className="bg-card border border-border rounded-2xl p-4 shadow-xs space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-extrabold text-sm text-foreground">{ord.customer_name}</h4>
                      {ord.customer_gstin && (
                        <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 uppercase">
                          GST: {ord.customer_gstin}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground font-semibold">
                      <span>Order #{ord.order_id}</span>
                      <span>•</span>
                      <span>Salesperson: <strong className="text-foreground">{ord.salesperson}</strong></span>
                      <span>•</span>
                      <span className="capitalize">{ord.status}</span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-mono font-black text-sm text-emerald-600 dark:text-emerald-400">
                      {formatCurrency(ord.total_amount)}
                    </p>
                    <p className="text-[10px] text-muted-foreground font-bold">
                      {ord.total_qty} units • {ord.items_count} items
                    </p>
                  </div>
                </div>

                {/* Items in this shop order */}
                <div className="bg-muted/30 border border-border/50 rounded-xl p-2.5 space-y-1.5 text-xs">
                  {ord.items.map((it, idx) => (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="font-semibold text-foreground truncate pr-2">
                        {it.item_name} {it.company_name ? `(${it.company_name})` : ''}
                      </span>
                      <span className="font-mono font-bold text-foreground shrink-0">
                        {it.qty} {it.unit}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Printable Footer */}
        <div className="hidden print:block mt-12 pt-6 border-t text-xs">
          <div className="flex justify-between items-center text-gray-700">
            <div>
              <p>Picker Name: _______________________</p>
              <p className="mt-2">Sign: _______________________</p>
            </div>
            <div>
              <p>Verifier Name: _______________________</p>
              <p className="mt-2">Sign: _______________________</p>
            </div>
            <div>
              <p>Driver / Dispatch Sign: _______________________</p>
              <p className="mt-2">Vehicle No: _______________________</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
