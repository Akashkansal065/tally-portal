'use client'

import { useEffect, useState, useMemo, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase } from '@/lib/utils'
import { 
  ShoppingCart, 
  Plus, 
  X, 
  Edit, 
  Eye, 
  Check, 
  XCircle, 
  Clock, 
  CheckCircle2, 
  Calendar, 
  User as UserIcon, 
  ChevronLeft,
  Truck,
  RotateCcw,
  Loader2
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { LinkParams, idParam } from '@/components/LinkParams'
import { DailyDispatchSummary } from '@/components/orders/DailyDispatchSummary'

type OrderItem = {
  id?: number
  stock_item_id?: number | null
  custom_item_name?: string
  stock_item_name: string
  company_name?: string
  qty: number
  price: number
  is_bill_required?: boolean
  has_gst?: boolean
  is_custom?: boolean
  is_sent?: boolean
  sent_qty?: number
  sent_at?: string | null
  subtotal?: number
  sent_subtotal?: number
  remaining_subtotal?: number
}

type Order = {
  id: number
  user_id: number
  salesperson: string
  customer_name: string
  custom_customer_name?: string
  custom_customer_gstin?: string
  customer_gstin?: string
  status: 'pending' | 'partial' | 'done' | 'cancelled'
  acted_by_id?: number | null
  acted_by_name?: string | null
  acted_at?: string | null
  status_reason?: string | null
  created_at: string
  total: number
  sent_total?: number
  remaining_total?: number
  sent_items_count?: number
  total_items_count?: number
  items: OrderItem[]
}

type Salesperson = {
  user_id: number
  username: string
}

export default function TempOrdersPage() {
  const { user, token, permissions, can } = useAuth()
  const router = useRouter()
  const [orders, setOrders] = useState<Order[]>([])
  const [salespersons, setSalespersons] = useState<Salesperson[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedOrder, setExpandedOrder] = useState<Order | null>(null)
  const [updatingItemId, setUpdatingItemId] = useState<number | null>(null)
  const [updatingAllItems, setUpdatingAllItems] = useState(false)
  
  // Tab states: 'orders' | 'dispatch'
  const [activeTab, setActiveTab] = useState<'orders' | 'dispatch'>('orders')

  // Filter states
  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [salespersonFilter, setSalespersonFilter] = useState<string>('all')

  // Links from notifications: ?status=done&order=123 shows that status and opens the order
  const linkedOrderId = useRef<number | null>(null)
  const openLinkedOrder = (list: Order[]) => {
    const found = linkedOrderId.current ? list.find(o => o.id === linkedOrderId.current) : null
    if (found) {
      setExpandedOrder(found)
      linkedOrderId.current = null
    }
  }
  const applyLink = (params: URLSearchParams) => {
    const tab = params.get('tab')
    if (tab === 'dispatch' || tab === 'summary') setActiveTab('dispatch')
    else if (tab === 'orders') setActiveTab('orders')

    const status = params.get('status')
    if (status && ['pending', 'partial', 'done', 'cancelled', 'all'].includes(status)) setStatusFilter(status)
    linkedOrderId.current = idParam(params.get('order'))
    if (orders.length) openLinkedOrder(orders)
  }

  const fetchData = async () => {
    setLoading(true)
    try {
      const isAdmin = permissions.isAdmin
      const ordersUrl = isAdmin ? `${API_BASE}/temporders/all` : `${API_BASE}/temporders`
      const headers = authHeaders(token)

      if (isAdmin) {
        const [ordersRes, usersRes] = await Promise.all([
          fetch(ordersUrl, { headers }),
          fetch(`${API_BASE}/admin/users`, { headers }).catch(() => null)
        ])
        
        if (ordersRes.ok) {
          const ordersData = await ordersRes.json()
          const raw = Array.isArray(ordersData) ? ordersData : []
          const uniqueMap = new Map<number, Order>()
          raw.forEach((item: Order) => {
            if (item && item.id != null) uniqueMap.set(item.id, item)
          })
          const list = Array.from(uniqueMap.values())
          setOrders(list)
          openLinkedOrder(list)
        } else {
          setOrders([])
        }

        if (usersRes && usersRes.ok) {
          const usersData = await usersRes.json()
          setSalespersons(Array.isArray(usersData) ? usersData : [])
        }
      } else {
        const res = await fetch(ordersUrl, { headers })
        if (res.ok) {
          const data = await res.json()
          const raw = Array.isArray(data) ? data : []
          const uniqueMap = new Map<number, Order>()
          raw.forEach((item: Order) => {
            if (item && item.id != null) uniqueMap.set(item.id, item)
          })
          const list = Array.from(uniqueMap.values())
          setOrders(list)
          openLinkedOrder(list)
        } else {
          setOrders([])
        }
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!can('orders', 'read')) { router.replace('/'); return }
    fetchData()
  }, [user, token, router, can])

  const handleStatusChange = async (orderId: number, nextStatus: 'done' | 'cancelled') => {
    let reason: string | null = null
    if (nextStatus === 'cancelled') {
      const input = window.prompt('Enter reason for cancelling this order (optional):')
      if (input === null) return // User cancelled the prompt dialog
      reason = input.trim() || null
    }

    try {
      const res = await fetch(`${API_BASE}/temporders/${orderId}/status`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({ status: nextStatus, reason: reason || undefined })
      })
      if (!res.ok) throw new Error('Failed to update order status')
      const data = await res.json()
      const actedByName = data.acted_by_name || user?.username || 'You'
      const actedAt = data.acted_at || new Date().toISOString()
      const statusReason = data.status_reason !== undefined ? data.status_reason : (reason ? reason.trim() : null)

      if (data && Array.isArray(data.items)) {
        setOrders(prev => prev.map(o => o.id === orderId ? data : o))
        if (expandedOrder && expandedOrder.id === orderId) {
          setExpandedOrder(data)
        }
      } else {
        setOrders(prev => prev.map(o => {
          if (o.id !== orderId) return o
          const isDone = nextStatus === 'done'
          return {
            ...o,
            status: nextStatus,
            acted_by_name: actedByName,
            acted_at: actedAt,
            status_reason: statusReason,
            sent_total: isDone ? o.total : (nextStatus === 'cancelled' ? o.sent_total : 0),
            remaining_total: isDone ? 0 : o.total,
            sent_items_count: isDone ? o.items.length : 0,
            items: o.items.map(it => ({
              ...it,
              is_sent: isDone,
              sent_qty: isDone ? it.qty : 0
            }))
          }
        }))

        if (expandedOrder && expandedOrder.id === orderId) {
          const isDone = nextStatus === 'done'
          setExpandedOrder(prev => prev ? {
            ...prev,
            status: nextStatus,
            acted_by_name: actedByName,
            acted_at: actedAt,
            status_reason: statusReason,
            sent_total: isDone ? prev.total : (nextStatus === 'cancelled' ? prev.sent_total : 0),
            remaining_total: isDone ? 0 : prev.total,
            sent_items_count: isDone ? prev.items.length : 0,
            items: prev.items.map(it => ({
              ...it,
              is_sent: isDone,
              sent_qty: isDone ? it.qty : 0
            }))
          } : null)
        }
      }
      toast.success(nextStatus === 'done' ? 'Order marked as Completed / Done' : 'Order cancelled')
    } catch (err: any) {
      toast.error(err.message || 'Failed to update order status')
    }
  }

  const handleToggleItemDispatch = async (orderId: number, itemId: number, currentIsSent: boolean, customQty?: number) => {
    setUpdatingItemId(itemId)
    try {
      const nextIsSent = !currentIsSent
      const payload: { is_sent: boolean; sent_qty?: number } = { is_sent: nextIsSent }
      if (customQty !== undefined) {
        payload.sent_qty = customQty
      }
      const res = await fetch(`${API_BASE}/temporders/${orderId}/items/${itemId}/dispatch`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to update item dispatch status')
      }
      const updatedOrder: Order = await res.json()
      
      setOrders(prev => prev.map(o => o.id === orderId ? updatedOrder : o))
      if (expandedOrder && expandedOrder.id === orderId) {
        setExpandedOrder(updatedOrder)
      }
      toast.success(nextIsSent ? 'Item marked as Sent / Success' : 'Item marked as Pending')
    } catch (err: any) {
      toast.error(err.message || 'Error updating item')
    } finally {
      setUpdatingItemId(null)
    }
  }

  const handleMarkAllRemainingItems = async (order: Order) => {
    setUpdatingAllItems(true)
    try {
      const pendingItems = (order.items || []).filter(it => !it.is_sent)
      if (pendingItems.length === 0) return

      const payload = {
        items: pendingItems.map(it => ({
          item_id: it.id!,
          is_sent: true,
          sent_qty: it.qty
        }))
      }
      const res = await fetch(`${API_BASE}/temporders/${order.id}/items-dispatch`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to dispatch remaining items')
      }
      const updatedOrder: Order = await res.json()
      setOrders(prev => prev.map(o => o.id === order.id ? updatedOrder : o))
      if (expandedOrder && expandedOrder.id === order.id) {
        setExpandedOrder(updatedOrder)
      }
      toast.success('All remaining items marked as Sent / Success')
    } catch (err: any) {
      toast.error(err.message || 'Error updating items')
    } finally {
      setUpdatingAllItems(false)
    }
  }

  // Status counts (respecting the salesperson filter so the numbers reflect what's selected)
  const statusCounts = useMemo(() => {
    const list = salespersonFilter === 'all'
      ? orders
      : orders.filter(o => String(o.user_id) === salespersonFilter)

    const counts = {
      all: list.length,
      pending: 0,
      partial: 0,
      done: 0,
      cancelled: 0,
    }

    list.forEach(o => {
      if (o.status === 'pending') counts.pending++
      else if (o.status === 'partial') counts.partial++
      else if (o.status === 'done') counts.done++
      else if (o.status === 'cancelled') counts.cancelled++
    })

    return counts
  }, [orders, salespersonFilter])

  // Filter orders (sorted by date desc)
  const filteredOrders = useMemo(() => {
    return orders
      .filter(o => {
        if (statusFilter !== 'all' && o.status !== statusFilter) return false
        if (salespersonFilter !== 'all' && String(o.user_id) !== salespersonFilter) return false
        return true
      })
      .sort((a, b) => {
        const timeA = a.created_at ? new Date(a.created_at).getTime() : 0
        const timeB = b.created_at ? new Date(b.created_at).getTime() : 0
        return timeB - timeA
      })
  }, [orders, statusFilter, salespersonFilter])

  const checkIsEditable = (order: Order) => {
    if (!can('orders', 'update')) return false
    if (permissions?.isAdmin) return true
    const currentUserId = user?.user_id ?? user?.id
    if (currentUserId != null && order.user_id !== currentUserId) return false
    if (order.status !== 'pending') return false
    
    // time limit 30 minutes for non-admin
    if (!order.created_at) return true
    const dateStr = order.created_at.endsWith('Z') || order.created_at.includes('+') ? order.created_at : `${order.created_at}Z`
    const createdDate = new Date(dateStr)
    const elapsedMinutes = (Date.now() - createdDate.getTime()) / (60 * 1000)
    return elapsedMinutes <= 30
  }

  const canDispatchOrder = (order: Order | null) => {
    if (!order) return false
    if (order.status === 'cancelled') return false
    if (permissions?.isAdmin) return true
    const currentUserId = user?.user_id ?? user?.id
    return Boolean(can('orders', 'update') && currentUserId != null && order.user_id === currentUserId)
  }

  const statusBadge = (status: string, sentCount?: number, totalCount?: number) => {
    switch (status) {
      case 'done':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 whitespace-nowrap">
            <Check className="h-3 w-3" /> Done
          </span>
        )
      case 'partial':
        return (
          <span 
            className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-600 border border-sky-500/20 whitespace-nowrap" 
            title={sentCount != null && totalCount != null ? `${sentCount} of ${totalCount} items sent` : 'Partially sent'}
          >
            <Clock className="h-3 w-3" /> Partial {sentCount != null && totalCount != null ? `(${sentCount}/${totalCount})` : ''}
          </span>
        )
      case 'cancelled':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-destructive/10 text-destructive border border-destructive/20 whitespace-nowrap">
            <X className="h-3 w-3" /> Cancelled
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 border border-amber-500/20 whitespace-nowrap">
            <Clock className="h-3 w-3" /> Pending
          </span>
        )
    }
  }

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      <LinkParams onChange={applyLink} />
      {/* Main Container */}
      <div className={cn(
        "flex-1 overflow-y-auto px-4 py-5 mx-auto w-full space-y-4",
        activeTab === 'dispatch' ? "max-w-3xl" : "max-w-xl"
      )}>
        {/* Title and CTA */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-extrabold tracking-tight flex items-center gap-2 text-foreground">
              <ShoppingCart className="h-5.5 w-5.5 text-amber-500" /> Temporary Orders
            </h1>
            <p className="text-[11px] text-muted-foreground mt-0.5">Place & approve salesperson sales orders</p>
          </div>
          {can('orders', 'create') && (
            <button 
              onClick={() => router.push('/temporders/new')}
              className="flex items-center gap-1.5 px-3 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold transition-all active:scale-[0.98] shadow-md shadow-emerald-500/10 cursor-pointer"
            >
              <Plus className="h-3.5 w-3.5" /> Place Order
            </button>
          )}
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 bg-muted/60 border border-border p-1 rounded-2xl">
          <button
            onClick={() => setActiveTab('orders')}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-xs font-bold transition-all cursor-pointer',
              activeTab === 'orders'
                ? 'bg-background text-foreground shadow-xs'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <ShoppingCart className="h-3.5 w-3.5 text-amber-500" />
            <span>Orders List</span>
            {orders.length > 0 && (
              <span className="text-[10px] font-black px-1.5 py-0.2 rounded-full bg-amber-500/10 text-amber-600">
                {orders.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('dispatch')}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-xl text-xs font-bold transition-all cursor-pointer',
              activeTab === 'dispatch'
                ? 'bg-background text-foreground shadow-xs'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Truck className="h-3.5 w-3.5 text-emerald-500" />
            <span>Daily Dispatch Summary</span>
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 uppercase tracking-wider">
              Daily
            </span>
          </button>
        </div>

        {activeTab === 'dispatch' ? (
          <DailyDispatchSummary />
        ) : (
          <>
            {/* Filters Panel with Status Counts */}
            <div className="bg-card border border-border rounded-2xl p-4 space-y-3.5 shadow-sm text-sm">
              {/* Quick Status Pill Filter Tabs */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
                {[
                  { id: 'all', label: 'All', count: statusCounts.all, color: 'bg-muted text-foreground' },
                  { id: 'pending', label: 'Pending', count: statusCounts.pending, color: 'bg-amber-500/15 text-amber-700 dark:text-amber-300' },
                  { id: 'partial', label: 'Partial', count: statusCounts.partial, color: 'bg-sky-500/15 text-sky-700 dark:text-sky-300' },
                  { id: 'done', label: 'Completed', count: statusCounts.done, color: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' },
                  { id: 'cancelled', label: 'Cancelled', count: statusCounts.cancelled, color: 'bg-rose-500/15 text-rose-700 dark:text-rose-300' },
                ].map(pill => (
                  <button
                    key={pill.id}
                    type="button"
                    onClick={() => setStatusFilter(pill.id)}
                    className={cn(
                      "px-3 py-1.5 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 border cursor-pointer",
                      statusFilter === pill.id
                        ? "bg-foreground text-background border-foreground shadow-sm"
                        : "bg-card text-muted-foreground hover:text-foreground border-border hover:bg-muted/30"
                    )}
                  >
                    <span>{pill.label}</span>
                    <span className={cn(
                      "text-[10px] px-1.5 py-0.2 rounded-full font-black",
                      statusFilter === pill.id
                        ? "bg-background/25 text-background"
                        : pill.color
                    )}>
                      {pill.count}
                    </span>
                  </button>
                ))}
              </div>

              {/* Status Dropdown with counts */}
              <div className="flex items-center gap-2.5">
                <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider min-w-[70px]">Status:</span>
                <select
                  value={statusFilter}
                  onChange={e => setStatusFilter(e.target.value)}
                  className="flex-1 bg-muted/40 border border-border rounded-xl px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer"
                >
                  <option value="all">All Status ({statusCounts.all})</option>
                  <option value="pending">Pending ({statusCounts.pending})</option>
                  <option value="partial">Partially Success ({statusCounts.partial})</option>
                  <option value="done">Completed / Done ({statusCounts.done})</option>
                  <option value="cancelled">Cancelled ({statusCounts.cancelled})</option>
                </select>
              </div>

              {/* Salesperson Dropdown with counts */}
              {permissions.isAdmin && salespersons.length > 0 && (
                <div className="flex items-center gap-2.5">
                  <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider min-w-[70px]">Salesperson:</span>
                  <select
                    value={salespersonFilter}
                    onChange={e => setSalespersonFilter(e.target.value)}
                    className="flex-1 bg-muted/40 border border-border rounded-xl px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer"
                  >
                    <option value="all">All Salespersons ({orders.length})</option>
                    {salespersons.map(sp => {
                      const spCount = orders.filter(o => o.user_id === sp.user_id).length
                      return (
                        <option key={sp.user_id} value={String(sp.user_id)}>
                          {sp.username} ({spCount})
                        </option>
                      )
                    })}
                  </select>
                </div>
              )}
            </div>

        {/* Orders List */}
        {loading ? (
          <div className="flex justify-center py-10">
            <div className="w-6 h-6 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filteredOrders.length === 0 ? (
          <div className="text-center py-12 bg-card border border-border rounded-2xl border-dashed">
            <ShoppingCart className="h-10 w-10 mx-auto mb-3 opacity-25 text-muted-foreground" />
            <p className="text-sm font-bold text-muted-foreground">No orders found</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">Try changing your filters or place a new order</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredOrders.map(o => {
              const isEditable = checkIsEditable(o)
              return (
                <div key={o.id} className="bg-card border border-border rounded-2xl p-4 shadow-sm hover:border-emerald-500/30 transition-all flex flex-col gap-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-extrabold text-sm text-foreground break-words">{o.customer_name}</h3>
                        {o.customer_gstin ? (
                          <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 uppercase tracking-wider">
                            GST: {o.customer_gstin.toUpperCase()}
                          </span>
                        ) : o.custom_customer_name ? (
                          <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border">
                            No GST
                          </span>
                        ) : null}
                      </div>
                      <div className="flex gap-2 items-center mt-1 text-[10px] text-muted-foreground font-semibold flex-wrap">
                        <span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> {formatDate(o.created_at)}</span>
                        {permissions.isAdmin && (
                          <span className="flex items-center gap-1 uppercase bg-muted px-1.5 py-0.5 rounded tracking-wider text-[8px]">
                            {o.salesperson}
                          </span>
                        )}
                      </div>
                      {o.status === 'done' && (
                        <div className="mt-1 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1 flex-wrap">
                          <CheckCircle2 className="h-3 w-3 shrink-0" />
                          <span>Approved {o.acted_by_name ? `by ${o.acted_by_name}` : ''} {o.acted_at ? `on ${formatDate(o.acted_at)}` : ''}</span>
                          {o.status_reason && <span className="text-muted-foreground font-normal italic">• "{o.status_reason}"</span>}
                        </div>
                      )}
                      {o.status === 'partial' && (
                        <div className="mt-1 text-[10px] font-semibold text-sky-600 dark:text-sky-400 flex items-center gap-1 flex-wrap">
                          <Clock className="h-3 w-3 shrink-0" />
                          <span>Partially Dispatched ({o.sent_items_count ?? (o.items?.filter(it => it.is_sent).length ?? 0)} of {o.total_items_count ?? o.items?.length} items sent)</span>
                          {o.acted_by_name && <span className="text-muted-foreground font-normal">• by {o.acted_by_name}</span>}
                        </div>
                      )}
                      {o.status === 'cancelled' && (
                        <div className="mt-1 text-[10px] font-semibold text-rose-600 dark:text-rose-400 flex items-center gap-1 flex-wrap">
                          <XCircle className="h-3 w-3 shrink-0" />
                          <span>Cancelled {o.acted_by_name ? `by ${o.acted_by_name}` : ''} {o.acted_at ? `on ${formatDate(o.acted_at)}` : ''}</span>
                          {o.status_reason && <span className="text-muted-foreground font-normal italic">• "{o.status_reason}"</span>}
                        </div>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      {o.status === 'partial' ? (
                        <div className="flex flex-col items-end">
                          <div className="flex items-baseline gap-1">
                            <span className="text-[9px] font-bold text-muted-foreground uppercase">Bal:</span>
                            <p className="font-black text-sm text-sky-600 dark:text-sky-400 font-mono">
                              {formatCurrency(o.remaining_total ?? Math.max(0, o.total - (o.sent_total ?? 0)))}
                            </p>
                          </div>
                          <p className="text-[10px] text-muted-foreground line-through font-mono">
                            {formatCurrency(o.total)}
                          </p>
                          <span className="text-[9px] font-bold text-emerald-600 dark:text-emerald-400">
                            ✓ {formatCurrency(o.sent_total ?? 0)} sent
                          </span>
                        </div>
                      ) : (
                        <p className="font-black text-sm text-emerald-600 dark:text-emerald-400 font-mono">
                          {formatCurrency(o.total)}
                        </p>
                      )}
                      <div className="mt-1">
                        {statusBadge(o.status, o.sent_items_count, o.total_items_count ?? o.items?.length)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between border-t border-border/40 pt-3 mt-1 text-xs">
                    <button 
                      onClick={() => setExpandedOrder(o)}
                      className="px-3 py-1.5 border border-border hover:bg-muted text-muted-foreground hover:text-foreground font-bold rounded-lg transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      <Eye className="h-3.5 w-3.5" /> Details
                    </button>

                    <div className="flex items-center gap-2">
                      {isEditable && (
                        <button 
                          onClick={() => router.push(`/temporders/edit/${o.id}`)}
                          className="px-3 py-1.5 border border-border hover:bg-muted text-primary font-bold rounded-lg transition-colors flex items-center gap-1 cursor-pointer"
                        >
                          <Edit className="h-3.5 w-3.5" /> Edit
                        </button>
                      )}

                      {permissions.isAdmin && (o.status === 'pending' || o.status === 'partial') && (
                        <>
                          <button 
                            onClick={() => handleStatusChange(o.id, 'done')}
                            className="h-8 w-8 bg-green-500/10 hover:bg-green-500 text-green-600 hover:text-white rounded-lg transition-colors flex items-center justify-center cursor-pointer border border-green-500/20"
                            title="Mark Entire Order Complete"
                          >
                            <Check className="h-4 w-4" />
                          </button>
                          <button 
                            onClick={() => handleStatusChange(o.id, 'cancelled')}
                            className="h-8 w-8 bg-destructive/10 hover:bg-destructive text-destructive hover:text-white rounded-lg transition-colors flex items-center justify-center cursor-pointer border border-destructive/20"
                            title="Cancel Order"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
          </>
        )}

        {/* Scroll spacer */}
        <div className="h-16" />
      </div>

      {/* Expanded Order Details Modal */}
      {expandedOrder && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-card w-full max-w-lg rounded-3xl shadow-xl overflow-hidden animate-in slide-in-from-bottom-10 sm:zoom-in-95 duration-200 flex flex-col max-h-[85vh]">
            <div className="px-6 py-5 border-b border-border flex justify-between items-center shrink-0">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-black text-lg text-foreground">Order Details</h3>
                  {statusBadge(expandedOrder.status, expandedOrder.sent_items_count, expandedOrder.total_items_count ?? expandedOrder.items.length)}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">Placed by <span className="font-bold text-foreground">{expandedOrder.salesperson}</span></p>
              </div>
              <button 
                onClick={() => setExpandedOrder(null)}
                className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors cursor-pointer"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4 overflow-y-auto flex-1">
              <div>
                <span className="text-[9px] font-extrabold text-muted-foreground uppercase tracking-widest block">Customer</span>
                <span className="font-extrabold text-base text-foreground mt-0.5 block">{expandedOrder.customer_name}</span>
                {expandedOrder.customer_gstin ? (
                  <span className="inline-flex items-center gap-1 mt-1 text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 uppercase tracking-wider">
                    GSTIN: {expandedOrder.customer_gstin.toUpperCase()}
                  </span>
                ) : expandedOrder.custom_customer_name ? (
                  <span className="inline-flex items-center gap-1 mt-1 text-[10px] font-semibold px-2 py-0.5 rounded bg-muted text-muted-foreground border border-border">
                    GST: Unregistered Consumer
                  </span>
                ) : null}
                <span className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1"><Calendar className="h-3 w-3" /> Ordered at {formatDate(expandedOrder.created_at)}</span>
              </div>

              {expandedOrder.status !== 'pending' && (
                <div className={cn(
                  "p-3 rounded-2xl border text-xs flex items-start gap-2.5",
                  expandedOrder.status === 'done' 
                    ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-700 dark:text-emerald-300"
                    : expandedOrder.status === 'partial'
                      ? "bg-sky-500/10 border-sky-500/20 text-sky-700 dark:text-sky-300"
                      : "bg-rose-500/10 border-rose-500/20 text-rose-700 dark:text-rose-300"
                )}>
                  {expandedOrder.status === 'done' ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-emerald-600 dark:text-emerald-400" />
                  ) : expandedOrder.status === 'partial' ? (
                    <Clock className="h-4 w-4 shrink-0 mt-0.5 text-sky-600 dark:text-sky-400" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
                  )}
                  <div className="space-y-0.5 flex-1 min-w-0">
                    <p className="font-bold">
                      {expandedOrder.status === 'done' && 'Order Completed / All Items Dispatched'}
                      {expandedOrder.status === 'partial' && `Partially Dispatched (${expandedOrder.sent_items_count ?? expandedOrder.items.filter(i => i.is_sent).length} of ${expandedOrder.items.length} items sent)`}
                      {expandedOrder.status === 'cancelled' && 'Order Cancelled'}
                      {expandedOrder.acted_by_name ? ` by ${expandedOrder.acted_by_name}` : ''}
                      {expandedOrder.acted_at ? ` on ${formatDate(expandedOrder.acted_at)}` : ''}
                    </p>
                    {expandedOrder.status_reason && (
                      <p className="text-[11px] text-muted-foreground italic font-normal break-words">
                        "{expandedOrder.status_reason}"
                      </p>
                    )}
                  </div>
                </div>
              )}

              <div className="border-t border-border pt-4">
                <div className="flex items-center justify-between mb-2.5">
                  <div>
                    <span className="text-[9px] font-extrabold text-muted-foreground uppercase tracking-widest block">Order Items</span>
                    <span className="text-[11px] text-muted-foreground font-semibold">
                      {expandedOrder.items.filter(it => it.is_sent).length} of {expandedOrder.items.length} items dispatched
                    </span>
                  </div>

                  {canDispatchOrder(expandedOrder) && 
                    expandedOrder.items.some(it => !it.is_sent) && (
                    <button
                      type="button"
                      onClick={() => handleMarkAllRemainingItems(expandedOrder)}
                      disabled={updatingAllItems}
                      className="text-xs font-bold px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 flex items-center gap-1 transition-all cursor-pointer disabled:opacity-50"
                    >
                      {updatingAllItems ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                      Mark All Sent
                    </button>
                  )}
                </div>

                <div className="space-y-2.5">
                  {expandedOrder.items.map((item, idx) => {
                    const isItemSent = Boolean(item.is_sent)
                    const isItemUpdating = updatingItemId === item.id
                    const canItemDispatch = canDispatchOrder(expandedOrder) && item.id != null
                    
                    return (
                      <div
                        key={item.id ?? idx}
                        className={cn(
                          "flex flex-col gap-2 p-3 rounded-xl border transition-all text-sm",
                          isItemSent
                            ? "bg-emerald-500/5 border-emerald-500/25"
                            : "bg-muted/20 border-border/40"
                        )}
                      >
                        <div className="flex justify-between items-start gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-bold text-foreground text-xs leading-tight block truncate">
                                {toTitleCase(item.stock_item_name)}{item.company_name ? ` (${item.company_name})` : ''}
                              </span>
                              {(item.is_custom || !item.stock_item_id) && (
                                <span className="px-1.5 py-0.2 text-[8px] font-extrabold uppercase tracking-wider bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 rounded">
                                  Custom
                                </span>
                              )}
                              {isItemSent && (
                                <span className="px-1.5 py-0.2 text-[8px] font-extrabold uppercase tracking-wider bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 rounded inline-flex items-center gap-0.5">
                                  <Check className="w-2.5 h-2.5" /> Sent
                                </span>
                              )}
                            </div>
                            <span className="text-[10px] text-muted-foreground mt-1 block">
                              Rate: {formatCurrency(item.price)} • Qty: {item.qty} •{' '}
                              {(item.is_bill_required ?? item.has_gst) ? (
                                <span className="text-emerald-600 dark:text-emerald-400 font-bold">With Bill</span>
                              ) : (
                                <span className="text-muted-foreground font-medium">Without Bill</span>
                              )}
                            </span>
                          </div>

                          <div className="text-right shrink-0">
                            <span className={cn(
                              "font-black text-sm font-mono block",
                              isItemSent ? "text-emerald-600 dark:text-emerald-400" : "text-foreground"
                            )}>
                              {formatCurrency(item.qty * item.price)}
                            </span>
                            <span className={cn(
                              "text-[9px] font-bold block mt-0.5",
                              isItemSent ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"
                            )}>
                              {isItemSent ? "Dispatched" : "Pending"}
                            </span>
                          </div>
                        </div>

                        {/* Item-level action bar */}
                        {canItemDispatch && (
                          <div className="flex items-center justify-between border-t border-border/40 pt-2 mt-1">
                            <span className="text-[10px] text-muted-foreground font-medium">
                              {isItemSent ? (
                                <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                                  <CheckCircle2 className="w-3 h-3" /> Dispatched {item.sent_at ? `(${formatDate(item.sent_at)})` : ''}
                                </span>
                              ) : (
                                <span>Awaiting dispatch</span>
                              )}
                            </span>

                            {isItemSent ? (
                              <button
                                type="button"
                                onClick={() => handleToggleItemDispatch(expandedOrder.id, item.id!, true)}
                                disabled={isItemUpdating}
                                className="px-2 py-1 text-[11px] font-bold rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground flex items-center gap-1 transition-all cursor-pointer disabled:opacity-50"
                                title="Revert to pending"
                              >
                                {isItemUpdating ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                                <span>Undo</span>
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => handleToggleItemDispatch(expandedOrder.id, item.id!, false)}
                                disabled={isItemUpdating}
                                className="px-2.5 py-1 text-[11px] font-bold rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white flex items-center gap-1 shadow-xs transition-all cursor-pointer disabled:opacity-50"
                              >
                                {isItemUpdating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                                <span>Mark Sent ✓</span>
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Financial Summary */}
              <div className="border-t border-border pt-4 space-y-2 bg-muted/20 p-4 rounded-2xl border">
                <div className="flex justify-between items-center text-xs text-muted-foreground">
                  <span>Original Order Total ({expandedOrder.items.length} item{expandedOrder.items.length > 1 ? 's' : ''})</span>
                  <span className="font-mono font-bold text-foreground">{formatCurrency(expandedOrder.total)}</span>
                </div>

                {(expandedOrder.sent_total ?? 0) > 0 && (
                  <div className="flex justify-between items-center text-xs text-emerald-600 dark:text-emerald-400 font-semibold">
                    <span className="flex items-center gap-1">
                      <Check className="h-3.5 w-3.5" /> Already Sent / Dispatched ({expandedOrder.sent_items_count ?? expandedOrder.items.filter(i => i.is_sent).length} items)
                    </span>
                    <span className="font-mono font-bold">- {formatCurrency(expandedOrder.sent_total ?? 0)}</span>
                  </div>
                )}

                <div className="border-t border-border/60 pt-2 flex justify-between items-baseline">
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-wider block text-foreground">
                      {expandedOrder.status === 'done' ? 'Remaining Amount' : (expandedOrder.sent_total ?? 0) > 0 ? 'Remaining Order Amount' : 'Grand Total'}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {expandedOrder.status === 'done' 
                        ? 'All items sent / completed'
                        : (expandedOrder.sent_total ?? 0) > 0
                          ? `Decreased by sent items`
                          : `${expandedOrder.items.length} items`}
                    </span>
                  </div>
                  <span className={cn(
                    "text-xl font-black font-mono",
                    expandedOrder.status === 'done'
                      ? "text-emerald-600 dark:text-emerald-400"
                      : (expandedOrder.sent_total ?? 0) > 0
                        ? "text-sky-600 dark:text-sky-400"
                        : "text-foreground"
                  )}>
                    {formatCurrency(
                      expandedOrder.status === 'done'
                        ? 0
                        : (expandedOrder.remaining_total ?? Math.max(0, expandedOrder.total - (expandedOrder.sent_total ?? 0)))
                    )}
                  </span>
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-border bg-muted/20 flex gap-2 shrink-0">
              {checkIsEditable(expandedOrder) && (
                <button 
                  onClick={() => {
                    setExpandedOrder(null)
                    router.push(`/temporders/edit/${expandedOrder.id}`)
                  }}
                  className="flex-1 py-3 border border-border bg-card hover:bg-muted text-primary font-bold rounded-xl text-sm transition-all text-center flex items-center justify-center gap-1 cursor-pointer"
                >
                  <Edit className="h-4 w-4" /> Edit Order
                </button>
              )}
              {permissions.isAdmin && (expandedOrder.status === 'pending' || expandedOrder.status === 'partial') && (
                <button 
                  onClick={() => handleStatusChange(expandedOrder.id, 'done')}
                  className="flex-1 py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl text-sm transition-all shadow-md cursor-pointer"
                >
                  Mark Done / All Sent
                </button>
              )}
              <button 
                onClick={() => setExpandedOrder(null)}
                className={cn(
                  "py-3 font-bold rounded-xl text-sm transition-all px-6 text-center cursor-pointer",
                  permissions.isAdmin && (expandedOrder.status === 'pending' || expandedOrder.status === 'partial') ? "bg-muted hover:bg-muted/80 text-foreground" : "flex-1 bg-emerald-500 hover:bg-emerald-600 text-white"
                )}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
