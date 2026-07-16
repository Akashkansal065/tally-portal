'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase } from '@/lib/utils'
import { ShoppingCart, Plus, X, Trash2, ChevronRight, CheckCircle, Clock, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

type OrderItem = {
  stock_item_name: string
  qty: number
  price: number
  has_gst: boolean
}

type Order = {
  id: number
  customer_name: string
  status: string
  created_at: string
  total: number
  items: OrderItem[]
}

type Ledger = { ledger_id: number; name: string; is_customer?: boolean }
type StockItem = { item_id: number; name: string; closing_rate: number }

export default function OrdersPage() {
  const { user, token } = useAuth()
  const router = useRouter()
  const [orders, setOrders] = useState<Order[]>([])
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [stocks, setStocks] = useState<StockItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const [ledgerId, setLedgerId] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [customCustomerName, setCustomCustomerName] = useState('')
  const [items, setItems] = useState<{ item_id: string; qty: string; price: string; has_gst: boolean; searchQuery?: string; isOpen?: boolean }[]>([
    { item_id: '', qty: '1', price: '', has_gst: true, searchQuery: '', isOpen: false },
  ])

  useEffect(() => {
    if (ledgerId === '') {
      setSearchQuery('')
    }
  }, [ledgerId])

  const fetchData = async () => {
    const [os, ls, ss] = await Promise.all([
      fetch(`${API_BASE}/orders`, { headers: authHeaders(token) }).then(r => r.json()).catch(() => []),
      fetch(`${API_BASE}/ledgers`, { headers: authHeaders(token) }).then(r => r.json()).catch(() => []),
      fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) }).then(r => r.json()).catch(() => []),
    ])
    setOrders(Array.isArray(os) ? os : (os?.data ?? []))
    const customers = Array.isArray(ls) ? ls.filter((l: any) => l.is_customer) : []
    setLedgers(customers.slice(0, 200))
    setStocks(Array.isArray(ss) ? ss.slice(0, 300) : [])
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    fetchData().finally(() => setLoading(false))
  }, [user, token, router])

  const getFilteredStocks = (query: string) => {
    if (!query) return stocks.slice(0, 100)
    return stocks.filter(s => s.name.toLowerCase().includes(query.toLowerCase())).slice(0, 100)
  }

  const addItem = () => setItems(v => [...v, { item_id: '', qty: '1', price: '', has_gst: true, searchQuery: '', isOpen: false }])
  const removeItem = (i: number) => setItems(v => v.filter((_, idx) => idx !== i))
  const updateItem = (i: number, key: string, val: string | boolean) => setItems(v => v.map((it, idx) => idx === i ? { ...it, [key]: val } : it))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ledgerId && !customCustomerName) { setError('Select a customer or enter new customer name.'); return }
    const validItems = items.filter(i => i.item_id && parseFloat(i.qty) > 0 && parseFloat(i.price) >= 0)
    if (validItems.length === 0) { setError('Add at least one item.'); return }
    setSubmitting(true); setError(''); setSuccess('')
    try {
      const res = await fetch(`${API_BASE}/orders`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          ledger_id: ledgerId ? parseInt(ledgerId) : null,
          custom_customer_name: customCustomerName || null,
          items: validItems.map(i => ({ stock_item_id: parseInt(i.item_id), qty: parseFloat(i.qty), price: parseFloat(i.price), has_gst: i.has_gst }))
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      setSuccess('Order created!'); setShowForm(false); setLedgerId(''); setCustomCustomerName(''); setSearchQuery(''); setItems([{ item_id: '', qty: '1', price: '', has_gst: true }])
      await fetchData()
    } catch (err: any) { setError(err.message) } finally { setSubmitting(false) }
  }

  const statusIcon = (s: string) => s === 'done' ? <CheckCircle className="h-4 w-4 text-emerald-600" /> : s === 'cancelled' ? <XCircle className="h-4 w-4 text-destructive" /> : <Clock className="h-4 w-4 text-amber-500" />
  const statusColor = (s: string) => s === 'done' ? 'text-emerald-600' : s === 'cancelled' ? 'text-destructive' : 'text-amber-500'

  const filteredLedgers = ledgers.filter(l =>
    l.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-4 pb-3 border-b border-border flex items-center justify-between">
        <h1 className="text-xl font-extrabold flex items-center gap-2"><ShoppingCart className="h-5 w-5 text-amber-500" /> Orders</h1>
        <button onClick={() => setShowForm(v => !v)} className="flex items-center gap-1.5 px-3 py-2 bg-primary text-white rounded-xl text-xs font-bold">
          {showForm ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />} {showForm ? 'Close' : 'New Order'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pt-4 pb-2 space-y-3">
        {success && <div className="p-3 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 text-sm">{success}</div>}
        {error && <div className="p-3 rounded-xl bg-destructive/10 text-destructive text-sm">{error}</div>}

        {showForm && (
          <form onSubmit={handleSubmit} className="bg-card border border-border rounded-2xl p-4 space-y-3">
            <h2 className="font-bold text-sm">New Temporary Order</h2>
            <div className="relative">
              <label className="text-xs text-muted-foreground font-semibold uppercase">Customer (from Ledger)</label>
              <input
                type="text"
                className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm focus:outline-none focus:ring-2 focus:ring-primary font-medium text-foreground"
                placeholder="Search & select customer..."
                value={searchQuery}
                onChange={e => {
                  setSearchQuery(e.target.value)
                  if (e.target.value === '') {
                    setLedgerId('')
                  }
                  setIsOpen(true)
                }}
                onFocus={() => setIsOpen(true)}
              />
              {isOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
                  <div className="absolute left-0 right-0 mt-1 max-h-60 overflow-y-auto bg-card border border-border rounded-xl shadow-lg z-50 divide-y divide-border/50">
                    {filteredLedgers.length === 0 ? (
                      <div className="p-3 text-xs text-muted-foreground text-center">No customers found</div>
                    ) : (
                      filteredLedgers.map(l => (
                        <button
                          key={l.ledger_id}
                          type="button"
                          onClick={() => {
                            setLedgerId(String(l.ledger_id))
                            setSearchQuery(toTitleCase(l.name))
                            setIsOpen(false)
                          }}
                          className="w-full text-left px-4 py-3 text-sm hover:bg-muted font-medium transition-colors text-foreground"
                        >
                          {toTitleCase(l.name)}
                        </button>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>

            <div className="flex items-center gap-2"><div className="flex-1 h-px bg-border" /><span className="text-[10px] text-muted-foreground uppercase font-bold">or</span><div className="flex-1 h-px bg-border" /></div>

            <div>
              <label className="text-xs text-muted-foreground font-semibold uppercase">New / Custom Shop Name</label>
              <input
                type="text"
                className="mt-1 w-full px-3 py-2.5 rounded-xl border border-border bg-muted/40 text-sm focus:outline-none focus:ring-2 focus:ring-primary text-foreground font-medium"
                placeholder="Enter customer shop name..."
                value={customCustomerName}
                onChange={e => setCustomCustomerName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              {items.map((item, i) => (
                <div key={i} className="border border-border rounded-xl p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-muted-foreground">Item {i + 1}</span>
                    {items.length > 1 && <button type="button" onClick={() => removeItem(i)} className="text-destructive"><Trash2 className="h-3.5 w-3.5" /></button>}
                  </div>
                  <div className="relative">
                    <input
                      type="text"
                      className="w-full px-3 py-2 rounded-lg border border-border bg-muted/40 text-sm focus:outline-none focus:ring-2 focus:ring-primary font-medium text-foreground"
                      placeholder="Search & select item..."
                      value={item.searchQuery || ''}
                      onChange={e => {
                        updateItem(i, 'searchQuery', e.target.value)
                        if (e.target.value === '') {
                          updateItem(i, 'item_id', '')
                        }
                        updateItem(i, 'isOpen', true)
                      }}
                      onFocus={() => updateItem(i, 'isOpen', true)}
                    />
                    {item.isOpen && (
                      <>
                        <div className="fixed inset-0 z-40" onClick={() => updateItem(i, 'isOpen', false)} />
                        <div className="absolute left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-card border border-border rounded-lg shadow-lg z-50 divide-y divide-border/50">
                          {getFilteredStocks(item.searchQuery || '').length === 0 ? (
                            <div className="p-2 text-xs text-muted-foreground text-center">No items found</div>
                          ) : (
                            getFilteredStocks(item.searchQuery || '').map(s => (
                              <button
                                key={s.item_id}
                                type="button"
                                onClick={() => {
                                  updateItem(i, 'item_id', String(s.item_id))
                                  updateItem(i, 'searchQuery', toTitleCase(s.name))
                                  updateItem(i, 'isOpen', false)
                                  if (s.closing_rate && !item.price) {
                                    updateItem(i, 'price', String(s.closing_rate))
                                  }
                                }}
                                className="w-full text-left px-3 py-2 text-xs hover:bg-muted font-medium transition-colors text-foreground"
                              >
                                {toTitleCase(s.name)}
                              </button>
                            ))
                          )}
                        </div>
                      </>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input type="number" min="0" step="0.01" placeholder="Qty" className="px-3 py-2 rounded-lg border border-border bg-muted/40 text-sm" value={item.qty} onChange={e => updateItem(i, 'qty', e.target.value)} />
                    <input type="number" min="0" step="0.01" placeholder="Price ₹" className="px-3 py-2 rounded-lg border border-border bg-muted/40 text-sm" value={item.price} onChange={e => updateItem(i, 'price', e.target.value)} />
                  </div>
                </div>
              ))}
            </div>
            <button type="button" onClick={addItem} className="text-xs text-primary font-semibold flex items-center gap-1"><Plus className="h-3.5 w-3.5" /> Add Item</button>
            <button type="submit" disabled={submitting} className="w-full py-3 bg-primary text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 disabled:opacity-50">
              {submitting && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}Create Order
            </button>
          </form>
        )}

        {loading ? (
          <div className="flex justify-center py-8"><div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" /></div>
        ) : orders.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground"><ShoppingCart className="h-10 w-10 mx-auto mb-3 opacity-30" /><p className="text-sm">No orders yet</p></div>
        ) : (
          <div className="space-y-2">
            {orders.map(o => (
              <div key={o.id} className="bg-card border border-border rounded-2xl overflow-hidden">
                <button onClick={() => setExpandedId(expandedId === o.id ? null : o.id)} className="w-full text-left p-4 flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">{statusIcon(o.status)}</div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm">{o.customer_name}</p>
                    <p className="text-xs text-muted-foreground">{formatDate(o.created_at)}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="font-bold text-sm">{formatCurrency(o.total)}</p>
                    <p className={cn('text-[10px] font-bold capitalize', statusColor(o.status))}>{o.status}</p>
                  </div>
                  <ChevronRight className={cn('h-4 w-4 text-muted-foreground shrink-0 transition-transform', expandedId === o.id && 'rotate-90')} />
                </button>
                {expandedId === o.id && o.items && (
                  <div className="px-4 pb-4 border-t border-border pt-3 space-y-1.5">
                    {o.items.map((item, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">{item.stock_item_name}</span>
                        <span className="font-semibold">{item.qty} × {formatCurrency(item.price)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
