'use client'

import { useEffect, useState, useMemo } from 'react'
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
  ChevronLeft 
} from 'lucide-react'
import { cn } from '@/lib/utils'

type OrderItem = {
  stock_item_id: number
  stock_item_name: string
  qty: number
  price: number
  has_gst: boolean
}

type Order = {
  id: number
  user_id: number
  salesperson: string
  customer_name: string
  status: 'pending' | 'done' | 'cancelled'
  created_at: string
  total: number
  items: OrderItem[]
}

type Salesperson = {
  user_id: number
  username: string
}

export default function TempOrdersPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  const [orders, setOrders] = useState<Order[]>([])
  const [salespersons, setSalespersons] = useState<Salesperson[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedOrder, setExpandedOrder] = useState<Order | null>(null)
  
  // Filter states
  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [salespersonFilter, setSalespersonFilter] = useState<string>('all')

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
        
        const ordersData = await ordersRes.json()
        setOrders(Array.isArray(ordersData) ? ordersData : [])

        if (usersRes) {
          const usersData = await usersRes.json()
          setSalespersons(Array.isArray(usersData) ? usersData : [])
        }
      } else {
        const res = await fetch(ordersUrl, { headers })
        const data = await res.json()
        setOrders(Array.isArray(data) ? data : [])
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    fetchData()
  }, [user, token, router])

  const handleStatusChange = async (orderId: number, nextStatus: 'done' | 'cancelled') => {
    try {
      const res = await fetch(`${API_BASE}/temporders/${orderId}/status`, {
        method: 'PUT',
        headers: authHeaders(token),
        body: JSON.stringify({ status: nextStatus })
      })
      if (!res.ok) throw new Error('Failed to update order status')
      setOrders(prev => prev.map(o => o.id === orderId ? { ...o, status: nextStatus } : o))
      if (expandedOrder && expandedOrder.id === orderId) {
        setExpandedOrder(prev => prev ? { ...prev, status: nextStatus } : null)
      }
    } catch (err: any) {
      alert(err.message)
    }
  }

  // Filter orders
  const filteredOrders = useMemo(() => {
    return orders.filter(o => {
      if (statusFilter !== 'all' && o.status !== statusFilter) return false
      if (salespersonFilter !== 'all' && String(o.user_id) !== salespersonFilter) return false
      return true
    })
  }, [orders, statusFilter, salespersonFilter])

  const checkIsEditable = (order: Order) => {
    if (order.status !== 'pending') return false
    if (permissions.isAdmin) return true
    
    // time limit 30 minutes
    const createdDate = new Date(order.created_at)
    const elapsedMinutes = (Date.now() - createdDate.getTime()) / (60 * 1000)
    return elapsedMinutes <= 30
  }

  const statusBadge = (status: string) => {
    switch (status) {
      case 'done':
        return <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-500/10 text-green-600 border border-green-500/20"><Check className="h-3 w-3" /> Done</span>
      case 'cancelled':
        return <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-destructive/10 text-destructive border border-destructive/20"><X className="h-3 w-3" /> Cancelled</span>
      default:
        return <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 border border-amber-500/20"><Clock className="h-3 w-3" /> Pending</span>
    }
  }

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      {/* Main Container */}
      <div className="flex-1 overflow-y-auto px-4 py-5 max-w-xl mx-auto w-full space-y-4">
        {/* Title and CTA */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-extrabold tracking-tight flex items-center gap-2 text-foreground">
              <ShoppingCart className="h-5.5 w-5.5 text-amber-500" /> Temporary Orders
            </h1>
            <p className="text-[11px] text-muted-foreground mt-0.5">Place & approve salesperson sales orders</p>
          </div>
          <button 
            onClick={() => router.push('/temporders/new')}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold transition-all active:scale-[0.98] shadow-md shadow-emerald-500/10 cursor-pointer"
          >
            <Plus className="h-3.5 w-3.5" /> Place Order
          </button>
        </div>

        {/* Filters Panel */}
        <div className="bg-card border border-border rounded-2xl p-4 space-y-3.5 shadow-sm text-sm">
          <div className="flex items-center gap-2.5">
            <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider min-w-[70px]">Status:</span>
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="flex-1 bg-muted/40 border border-border rounded-xl px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="all">All Status</option>
              <option value="pending">Pending</option>
              <option value="done">Completed (Done)</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          {permissions.isAdmin && salespersons.length > 0 && (
            <div className="flex items-center gap-2.5">
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider min-w-[70px]">Salesperson:</span>
              <select
                value={salespersonFilter}
                onChange={e => setSalespersonFilter(e.target.value)}
                className="flex-1 bg-muted/40 border border-border rounded-xl px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="all">All Salespersons</option>
                {salespersons.map(sp => (
                  <option key={sp.user_id} value={String(sp.user_id)}>{sp.username}</option>
                ))}
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
                      <h3 className="font-extrabold text-sm text-foreground break-words">{o.customer_name}</h3>
                      <div className="flex gap-2 items-center mt-1 text-[10px] text-muted-foreground font-semibold">
                        <span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> {formatDate(o.created_at)}</span>
                        {permissions.isAdmin && (
                          <span className="flex items-center gap-1 uppercase bg-muted px-1.5 py-0.5 rounded tracking-wider text-[8px]">
                            {o.salesperson}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-black text-sm text-emerald-600 dark:text-emerald-400 font-mono">{formatCurrency(o.total)}</p>
                      <div className="mt-1">{statusBadge(o.status)}</div>
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

                      {permissions.isAdmin && o.status === 'pending' && (
                        <>
                          <button 
                            onClick={() => handleStatusChange(o.id, 'done')}
                            className="h-8 w-8 bg-green-500/10 hover:bg-green-500 text-green-600 hover:text-white rounded-lg transition-colors flex items-center justify-center cursor-pointer border border-green-500/20"
                            title="Approve Order"
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

        {/* Scroll spacer */}
        <div className="h-16" />
      </div>

      {/* Expanded Order Details Modal */}
      {expandedOrder && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-card w-full max-w-md rounded-3xl shadow-xl overflow-hidden animate-in slide-in-from-bottom-10 sm:zoom-in-95 duration-200 flex flex-col max-h-[85vh]">
            <div className="px-6 py-5 border-b border-border flex justify-between items-center shrink-0">
              <div>
                <h3 className="font-black text-lg text-foreground">Order Details</h3>
                <p className="text-xs text-muted-foreground mt-0.5">Placed by <span className="font-bold text-foreground">{expandedOrder.salesperson}</span></p>
              </div>
              <button 
                onClick={() => setExpandedOrder(null)}
                className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4 overflow-y-auto flex-1">
              <div>
                <span className="text-[9px] font-extrabold text-muted-foreground uppercase tracking-widest block">Customer</span>
                <span className="font-extrabold text-base text-foreground mt-0.5 block">{expandedOrder.customer_name}</span>
                <span className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1"><Calendar className="h-3 w-3" /> Ordered at {formatDate(expandedOrder.created_at)}</span>
              </div>

              <div className="border-t border-border pt-4">
                <span className="text-[9px] font-extrabold text-muted-foreground uppercase tracking-widest block mb-2">Order Items</span>
                <div className="space-y-2.5">
                  {expandedOrder.items.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-start gap-4 text-sm bg-muted/20 border border-border/40 p-3 rounded-xl">
                      <div className="min-w-0">
                        <span className="font-bold text-foreground text-xs leading-tight block truncate">{item.stock_item_name}</span>
                        <span className="text-[10px] text-muted-foreground mt-1 block">
                          Rate: {formatCurrency(item.price)} {item.has_gst && <span className="text-emerald-600 font-bold ml-1">+18% GST</span>}
                        </span>
                      </div>
                      <div className="text-right shrink-0">
                        <span className="font-extrabold text-xs text-foreground block">Qty: {item.qty}</span>
                        <span className="font-black text-sm text-emerald-600 dark:text-emerald-400 mt-1 block font-mono">
                          {formatCurrency(item.qty * item.price * (item.has_gst ? 1.18 : 1.0))}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="border-t border-border pt-4 flex justify-between items-center bg-muted/10 p-4 rounded-2xl border">
                <div>
                  <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider block">Grand Total</span>
                  <span className="text-[11px] text-muted-foreground">(Incl. of GST taxes)</span>
                </div>
                <span className="text-xl font-black text-emerald-600 dark:text-emerald-400 font-mono">{formatCurrency(expandedOrder.total)}</span>
              </div>
            </div>

            <div className="p-4 border-t border-border bg-muted/20 flex gap-2 shrink-0">
              {checkIsEditable(expandedOrder) && (
                <button 
                  onClick={() => {
                    setExpandedOrder(null)
                    router.push(`/temporders/edit/${expandedOrder.id}`)
                  }}
                  className="flex-1 py-3 border border-border bg-card hover:bg-muted text-primary font-bold rounded-xl text-sm transition-all text-center flex items-center justify-center gap-1"
                >
                  <Edit className="h-4 w-4" /> Edit Order
                </button>
              )}
              {permissions.isAdmin && expandedOrder.status === 'pending' && (
                <button 
                  onClick={() => handleStatusChange(expandedOrder.id, 'done')}
                  className="flex-1 py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl text-sm transition-all shadow-md"
                >
                  Approve Order
                </button>
              )}
              <button 
                onClick={() => setExpandedOrder(null)}
                className={cn(
                  "py-3 font-bold rounded-xl text-sm transition-all px-6 text-center",
                  permissions.isAdmin && expandedOrder.status === 'pending' ? "bg-muted hover:bg-muted/80 text-foreground" : "flex-1 bg-emerald-500 hover:bg-emerald-600 text-white"
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
