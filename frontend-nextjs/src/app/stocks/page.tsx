'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, toTitleCase } from '@/lib/utils'
import Link from 'next/link'
import { Search, X, Package, ArrowLeft, ArrowUpDown, ArrowUp, ArrowDown, PackageCheck } from 'lucide-react'

type SortKey =
  | 'name'
  | 'inward_qty'
  | 'inward_value'
  | 'outward_qty'
  | 'outward_value'
  | 'cons_value'
  | 'gp_value'
  | 'gp_percent'
  | 'closing_balance'
  | 'closing_value'

type SortDirection = 'asc' | 'desc'

type StockItem = {
  item_id: number
  name: string
  group_name: string
  uom: string
  closing_balance: number
  closing_rate: number
  closing_value: number
  opening_balance: number
  opening_rate: number
  inward_qty: number
  inward_value: number
  outward_qty: number
  outward_value: number
  cons_value: number
  gp_value: number
  gp_percent: number
}

import { getProductDetails } from '@/lib/kgoc-mapping'

export default function StocksPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  const [items, setItems] = useState<StockItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showStocks && !permissions.isAdmin) { router.replace('/'); return }
  }, [user, permissions, router])

  const [search, setSearch] = useState('')
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)

  // 3rd level — selected stock item voucher detail
  const [selectedItem, setSelectedItem] = useState<StockItem | null>(null)
  const [itemVouchers, setItemVouchers] = useState<any[]>([])
  const [vouchersLoading, setVouchersLoading] = useState(false)
  const [voucherSearch, setVoucherSearch] = useState('')
  const [voucherTypeFilter, setVoucherTypeFilter] = useState('All Vouchers')
  const [voucherFlowFilter, setVoucherFlowFilter] = useState('All Flows')

  // Filters State
  const [stockStatus, setStockStatus] = useState('All Items')
  const [movement, setMovement] = useState('All Movement')
  const [profitFilter, setProfitFilter] = useState('All Profit')
  const [sortField, setSortField] = useState<SortKey>('closing_balance')
  const [sortDir, setSortDir] = useState<SortDirection>('desc')

  const handleSort = (field: SortKey) => {
    if (sortField === field) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir(field === 'name' ? 'asc' : 'desc')
    }
  }

  const getSortIcon = (field: SortKey) => {
    if (sortField === field) {
      return (
        <span className="text-primary font-black text-[10px] inline-flex items-center ml-1">
          {sortDir === 'asc' ? <ArrowUp className="h-3 w-3 stroke-[2.5]" /> : <ArrowDown className="h-3 w-3 stroke-[2.5]" />}
        </span>
      )
    }
    return <ArrowUpDown className="h-2.5 w-2.5 opacity-0 group-hover:opacity-40 transition-opacity text-muted-foreground ml-1" />
  }

  useEffect(() => {
    if (!user) {
      router.replace('/login')
      return
    }
    fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) })
      .then(r => r.json())
      .then((data: StockItem[]) => {
        const list = (Array.isArray(data) ? data : []).map(i => ({
          ...i,
          closing_balance: Number(i.closing_balance) || 0,
          closing_rate: Number(i.closing_rate) || 0,
          closing_value: Number(i.closing_value) || 0,
          opening_balance: Number(i.opening_balance) || 0,
          opening_rate: Number(i.opening_rate) || 0,
          inward_qty: Number(i.inward_qty) || 0,
          inward_value: Number(i.inward_value) || 0,
          outward_qty: Number(i.outward_qty) || 0,
          outward_value: Number(i.outward_value) || 0,
          cons_value: Number(i.cons_value) || 0,
          gp_value: Number(i.gp_value) || 0,
          gp_percent: Number(i.gp_percent) || 0,
        }))
        setItems(list)
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [user, token, router])

  // Fetch vouchers when an item is selected
  useEffect(() => {
    if (!selectedItem || !token) return
    setVouchersLoading(true)
    setItemVouchers([])
    fetch(`${API_BASE}/inventory/items/${selectedItem.item_id}/vouchers`, { headers: authHeaders(token) })
      .then(r => r.json())
      .then(data => setItemVouchers(Array.isArray(data) ? data : []))
      .catch(() => setItemVouchers([]))
      .finally(() => setVouchersLoading(false))
  }, [selectedItem, token])

  // Get active company name from allowedCompanies
  const activeCompanyName = useMemo(() => {
    if (!user) return 'Sneh Distributors'
    const active = user.allowedCompanies?.find(c => c.company_id === user.company_id)
    return active ? active.name : 'Sneh Distributors'
  }, [user])

  // Compute aggregated list of stock groups for the summary view
  const summaryData = useMemo(() => {
    const summary: Record<string, number> = {}
    items.forEach(item => {
      const g = item.group_name || 'Others'
      const val = Number(item.closing_value) || 0
      summary[g] = (summary[g] || 0) + val
    })
    return Object.entries(summary)
      .map(([group_name, value]) => ({
        group_name,
        value,
      }))
      .sort((a, b) => b.value - a.value)
  }, [items])

  const grandTotal = useMemo(() => {
    return summaryData.reduce((acc, row) => acc + row.value, 0)
  }, [summaryData])

  // Filter items in the detail view based on selected group & search keyword
  const filtered = useMemo(() => {
    if (!selectedGroup) return []
    let result = items.filter(item => item.group_name === selectedGroup)

    // Search filter
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(item =>
        item.name.toLowerCase().includes(q) ||
        getProductDetails(item.name, item.group_name).subtitle.toLowerCase().includes(q)
      )
    }

    // Stock Status filter
    if (stockStatus === 'In Stock') {
      result = result.filter(item => (item.closing_balance || 0) > 0)
    } else if (stockStatus === 'Out of Stock') {
      result = result.filter(item => (item.closing_balance || 0) <= 0)
    }

    // Movement filter
    if (movement === 'With Movement') {
      result = result.filter(item => (item.inward_qty || 0) > 0 || (item.outward_qty || 0) > 0)
    } else if (movement === 'No Movement') {
      result = result.filter(item => (item.inward_qty || 0) === 0 && (item.outward_qty || 0) === 0)
    }

    // Profit filter
    if (profitFilter === 'Profitable') {
      result = result.filter(item => (item.gp_value || 0) > 0)
    } else if (profitFilter === 'Non-Profitable') {
      result = result.filter(item => (item.gp_value || 0) <= 0)
    }

    // Sorting
    result = [...result].sort((a, b) => {
      let comparison = 0
      if (sortField === 'name') {
        comparison = a.name.localeCompare(b.name)
      } else {
        const valA = Number(a[sortField]) || 0
        const valB = Number(b[sortField]) || 0
        comparison = valA - valB
      }
      return sortDir === 'asc' ? comparison : -comparison
    })

    return result
  }, [items, selectedGroup, search, stockStatus, movement, profitFilter, sortField, sortDir])

  // Compute aggregated totals for the selected stock group
  const groupTotals = useMemo(() => {
    const totalInwardQty = filtered.reduce((sum, item) => sum + (Number(item.inward_qty) || 0), 0)
    const totalInwardValue = filtered.reduce((sum, item) => sum + (Number(item.inward_value) || 0), 0)
    const totalOutwardQty = filtered.reduce((sum, item) => sum + (Number(item.outward_qty) || 0), 0)
    const totalOutwardValue = filtered.reduce((sum, item) => sum + (Number(item.outward_value) || 0), 0)
    const totalConsValue = filtered.reduce((sum, item) => sum + (Number(item.cons_value) || 0), 0)
    const totalGpValue = filtered.reduce((sum, item) => sum + (Number(item.gp_value) || 0), 0)
    
    // In Tally, Gross Profit % is calculated as: (Total Gross Profit / Total Outward Value) * 100
    const totalGpPercent = totalOutwardValue > 0
      ? (totalGpValue / totalOutwardValue) * 100
      : (totalConsValue > 0 ? (totalGpValue / totalConsValue) * 100 : 0)
      
    const totalClosingQty = filtered.reduce((sum, item) => sum + (Number(item.closing_balance) || 0), 0)
    const totalClosingValue = filtered.reduce((sum, item) => sum + (Number(item.closing_value) || 0), 0)

    return {
      totalInwardQty,
      totalInwardValue,
      totalOutwardQty,
      totalOutwardValue,
      totalConsValue,
      totalGpValue,
      totalGpPercent,
      totalClosingQty,
      totalClosingValue,
    }
  }, [filtered])

  // Filtered vouchers for 3rd level
  const filteredVouchers = itemVouchers.filter(v => {
    if (voucherTypeFilter !== 'All Vouchers' && v.voucher_type !== voucherTypeFilter) return false
    if (voucherFlowFilter === 'Inward' && !v.is_inward) return false
    if (voucherFlowFilter === 'Outward' && v.is_inward) return false
    if (voucherSearch.trim()) {
      const q = voucherSearch.toLowerCase()
      if (!v.party_name.toLowerCase().includes(q) && !v.voucher_number.toLowerCase().includes(q)) return false
    }
    return true
  })

  const voucherTypes = Array.from(new Set(itemVouchers.map(v => v.voucher_type)))

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header — changes based on current drill-down level */}
      {selectedItem !== null ? (
        <div className="relative px-4 py-3 bg-[#1b4332] text-white border-b border-green-900 flex items-center justify-between">
          <div>
            <span className="font-black text-sm tracking-wider uppercase">Stock Item Vouchers</span>
            <div className="text-green-300 text-[10px] mt-0.5">{selectedItem.group_name}</div>
          </div>
          <span className="font-extrabold text-sm tracking-wider text-green-300 absolute left-1/2 -translate-x-1/2 hidden xs:block">
            {activeCompanyName}
          </span>
          <button
            onClick={() => { setSelectedItem(null); setVoucherSearch(''); setVoucherTypeFilter('All Vouchers'); setVoucherFlowFilter('All Flows') }}
            className="text-green-300 hover:text-white font-bold text-lg leading-none focus:outline-none"
          >
            ✕
          </button>
        </div>
      ) : selectedGroup === null ? (
        <div className="relative px-4 py-3 bg-[#e2f5ec] dark:bg-[#1b3d2f] border-b border-emerald-200 dark:border-emerald-900 flex items-center justify-between">
          <span className="font-extrabold text-sm tracking-wider text-emerald-900 dark:text-emerald-50">Stock Summary</span>
          <span className="font-extrabold text-sm tracking-wider text-emerald-900 dark:text-emerald-50 absolute left-1/2 -translate-x-1/2 hidden xs:block">
            {activeCompanyName}
          </span>
        </div>
      ) : (
        <div className="relative px-4 py-3 bg-[#4a90e2] text-white border-b border-blue-400 flex items-center justify-between">
          <span className="font-black text-sm tracking-wider uppercase">Stock Group Summary</span>
          <span className="font-extrabold text-sm tracking-wider text-blue-100 absolute left-1/2 -translate-x-1/2 hidden xs:block">
            {activeCompanyName}
          </span>
          <button
            onClick={() => setSelectedGroup(null)}
            className="text-blue-100 hover:text-white font-bold text-lg leading-none focus:outline-none"
          >
            ✕
          </button>
        </div>
      )}

      {selectedGroup === null ? (
        // SUMMARY VIEW
        <div className="flex-1 flex flex-col min-h-0">
          <div className="shrink-0 px-4 py-4 flex items-start justify-between">
            <div className="space-y-1">
              <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">Inventory Statement</p>
              <h2 className="text-xl font-black tracking-tight text-foreground">{activeCompanyName}</h2>
              <p className="text-xs text-muted-foreground font-medium">Period: 1-Apr-2026 to 31-Mar-2027</p>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/reports?tab=company_stock"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100 dark:hover:bg-indigo-900 transition-colors shadow-2xs"
              >
                <PackageCheck className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                <span>Stock & Profit Report</span>
              </Link>
              <div className="bg-[#e2f5ec] text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 px-2.5 py-1 rounded text-[10px] font-extrabold uppercase self-start">
                Closing Balance
              </div>
            </div>
          </div>

          <div className="flex-1 min-h-0 px-4 pb-4 flex flex-col">
            <div className="border border-border rounded-lg overflow-hidden bg-card flex flex-col min-h-0 flex-initial shadow-sm">
              {/* Table Column Headers */}
              <div className="shrink-0 grid grid-cols-2 bg-muted/40 text-[10px] font-bold text-muted-foreground uppercase tracking-wider border-b border-border">
                <span className="px-4 py-3 border-r border-border">Particulars</span>
                <span className="px-4 py-3 text-right">Value</span>
              </div>

              {/* Table List Items */}
              <div className="overflow-y-auto divide-y divide-border/50 flex-initial min-h-0">
                {loading ? (
                  <div className="flex justify-center py-12">
                    <div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : summaryData.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <p className="text-sm font-medium">No items found</p>
                  </div>
                ) : (
                  summaryData.map(row => (
                    <button
                      key={row.group_name}
                      type="button"
                      onClick={() => {
                        setSelectedGroup(row.group_name)
                        setSearch('')
                      }}
                      className="w-full grid grid-cols-2 text-left font-medium text-sm transition-colors text-foreground focus:outline-none hover:bg-muted/30"
                    >
                      <span className="px-4 py-3.5 font-extrabold text-foreground uppercase tracking-wide border-r border-border">
                        {row.group_name}
                      </span>
                      <span className="px-4 py-3.5 font-black text-right text-foreground">
                        {formatCurrency(row.value)}
                      </span>
                    </button>
                  ))
                )}
              </div>

              {/* Table Grand Total Footer */}
              {!loading && summaryData.length > 0 && (
                <div className="shrink-0 grid grid-cols-2 bg-muted/40 border-t border-border font-black text-sm uppercase text-foreground">
                  <span className="px-4 py-3.5 border-r border-border">Grand Total</span>
                  <span className="text-right px-4 py-3.5">{formatCurrency(grandTotal)}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : selectedItem !== null ? null : (
        // DETAIL ITEMS VIEW FOR SELECTED GROUP MATCHING MOCKUP PRECISELY
        <div className="flex-1 flex flex-col min-h-0 bg-muted/10">
          {/* Combined Search and Filters Container */}
          <div className="px-4 py-3 bg-background border-b border-border flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            {/* Search Block */}
            <div className="flex items-center gap-4 flex-1 min-w-0 max-w-md">
              <button
                onClick={() => setSelectedGroup(null)}
                className="text-sm font-extrabold text-blue-600 dark:text-blue-400 hover:text-blue-800 flex items-center gap-1.5 focus:outline-none shrink-0"
              >
                <ArrowLeft className="h-4 w-4 stroke-[3]" />
                <span>Back</span>
              </button>
              <div className="flex-1 relative">
                <input
                  type="text"
                  placeholder="Search products..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="w-full px-4 py-2 border border-border rounded-lg text-sm bg-muted/20 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-background"
                />
                {search && (
                  <button
                    onClick={() => setSearch('')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 focus:outline-none text-muted-foreground"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>

            {/* Filters Block */}
            <div className="grid grid-cols-2 md:flex md:flex-row md:items-center md:gap-6 gap-2 text-xs font-semibold text-muted-foreground">
              <div className="flex items-center justify-between md:justify-start gap-1 md:gap-2">
                <span>STOCK STATUS:</span>
                <select
                  value={stockStatus}
                  onChange={e => setStockStatus(e.target.value)}
                  className="bg-card text-foreground border border-border rounded px-2 py-1 focus:outline-none"
                >
                  <option value="All Items">All Items</option>
                  <option value="In Stock">In Stock</option>
                  <option value="Out of Stock">Out of Stock</option>
                </select>
              </div>

              <div className="flex items-center justify-between md:justify-start gap-1 md:gap-2">
                <span>MOVEMENT:</span>
                <select
                  value={movement}
                  onChange={e => setMovement(e.target.value)}
                  className="bg-card text-foreground border border-border rounded px-2 py-1 focus:outline-none"
                >
                  <option value="All Movement">All Movement</option>
                  <option value="With Movement">With Movement</option>
                  <option value="No Movement">No Movement</option>
                </select>
              </div>

              <div className="flex items-center justify-between md:justify-start gap-1 md:gap-2">
                <span>PROFIT:</span>
                <select
                  value={profitFilter}
                  onChange={e => setProfitFilter(e.target.value)}
                  className="bg-card text-foreground border border-border rounded px-2 py-1 focus:outline-none"
                >
                  <option value="All Profit">All Profit</option>
                  <option value="Profitable">Profitable</option>
                  <option value="Non-Profitable">Non-Profitable</option>
                </select>
              </div>

              <div className="flex items-center justify-between md:justify-start gap-1 md:gap-2">
                <span>SORT BY:</span>
                <select
                  value={`${sortField}-${sortDir}`}
                  onChange={e => {
                    const [f, d] = e.target.value.split('-') as [SortKey, SortDirection]
                    setSortField(f)
                    setSortDir(d)
                  }}
                  className="bg-card text-foreground border border-border rounded px-2 py-1 focus:outline-none text-xs font-semibold"
                >
                  <option value="closing_balance-desc">Closing Qty (High to Low)</option>
                  <option value="closing_balance-asc">Closing Qty (Low to High)</option>
                  <option value="closing_value-desc">Closing Value (High to Low)</option>
                  <option value="closing_value-asc">Closing Value (Low to High)</option>
                  <option value="name-asc">Name (A to Z)</option>
                  <option value="name-desc">Name (Z to A)</option>
                  <option value="inward_qty-desc">Inward Qty (High to Low)</option>
                  <option value="inward_qty-asc">Inward Qty (Low to High)</option>
                  <option value="inward_value-desc">Inward Value (High to Low)</option>
                  <option value="inward_value-asc">Inward Value (Low to High)</option>
                  <option value="outward_qty-desc">Outward Qty (High to Low)</option>
                  <option value="outward_qty-asc">Outward Qty (Low to High)</option>
                  <option value="outward_value-desc">Outward Value (High to Low)</option>
                  <option value="outward_value-asc">Outward Value (Low to High)</option>
                  <option value="cons_value-desc">Cons. Value (High to Low)</option>
                  <option value="cons_value-asc">Cons. Value (Low to High)</option>
                  <option value="gp_value-desc">Gross Profit (High to Low)</option>
                  <option value="gp_value-asc">Gross Profit (Low to High)</option>
                  <option value="gp_percent-desc">Gross Profit % (High to Low)</option>
                  <option value="gp_percent-asc">Gross Profit % (Low to High)</option>
                </select>
              </div>
            </div>
          </div>

          <div className="md:hidden px-4 py-3 bg-muted/40 border-b border-border/80">
            <h3 className="font-extrabold text-sm uppercase tracking-wide text-foreground">Particulars</h3>
          </div>

          {/* MOBILE VIEW (CARD LAYOUT) */}
          <div className="md:hidden flex-1 overflow-y-auto min-h-0 px-4 py-3 space-y-4 pb-24">
            {filtered.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Package className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">No items found matching filters</p>
              </div>
            ) : (
              filtered.map(item => {
                const details = getProductDetails(item.name, item.group_name)
                return (
                  <div
                    key={item.item_id}
                    onClick={() => { setSelectedItem(item); setVoucherSearch('') }}
                    style={{ background: '#ffffff', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '16px', marginBottom: '0', boxShadow: '0 1px 3px rgba(0,0,0,0.06)', cursor: 'pointer' }}
                  >
                    {/* Title & Brand */}
                    <div style={{ marginBottom: '12px' }}>
                      <h3 style={{ fontWeight: 800, fontSize: '15px', color: '#111827', lineHeight: 1.3, marginBottom: '4px' }}>
                        {item.name}
                      </h3>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ background: '#2563eb', color: '#fff', padding: '1px 6px', borderRadius: '4px', fontSize: '10px', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          {details.brand}
                        </span>
                        <span style={{ fontSize: '11px', color: '#6b7280', fontWeight: 500 }}>
                          {details.subtitle}
                        </span>
                      </div>
                    </div>

                    {/* Metrics Grid — 2 columns */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>

                      {/* INWARD */}
                      <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '8px', padding: '10px' }}>
                        <div style={{ fontSize: '9px', fontWeight: 700, color: '#059669', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '6px' }}>Inward</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 800, fontSize: '13px', color: '#065f46' }}>
                            {item.inward_qty.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                          <span style={{ fontWeight: 700, fontSize: '12px', color: '#065f46' }}>
                            {formatCurrency(item.inward_value)}
                          </span>
                        </div>
                      </div>

                      {/* OUTWARD */}
                      <div style={{ background: '#fff5f5', border: '1px solid #fca5a5', borderRadius: '8px', padding: '10px' }}>
                        <div style={{ fontSize: '9px', fontWeight: 700, color: '#dc2626', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '6px' }}>Outward</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 800, fontSize: '13px', color: '#991b1b' }}>
                            {item.outward_qty.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                          <span style={{ fontWeight: 700, fontSize: '12px', color: '#991b1b' }}>
                            {formatCurrency(item.outward_value)}
                          </span>
                        </div>
                      </div>

                      {/* CONS */}
                      <div style={{ background: '#f9fafb', border: '1px solid #d1d5db', borderRadius: '8px', padding: '10px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '6px' }}>
                          <span style={{ fontSize: '9px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Cons</span>
                          <span style={{ fontSize: '10px', color: '#9ca3af' }}>ⓘ</span>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{ fontWeight: 800, fontSize: '13px', color: '#374151' }}>
                            {formatCurrency(item.cons_value)}
                          </span>
                        </div>
                      </div>

                      {/* GP */}
                      <div style={{ background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '8px', padding: '10px' }}>
                        <div style={{ fontSize: '9px', fontWeight: 700, color: '#2563eb', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '6px' }}>GP</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 800, fontSize: '13px', color: '#1d4ed8' }}>
                            {formatCurrency(item.gp_value)}
                          </span>
                          <span style={{ fontWeight: 700, fontSize: '11px', color: '#1d4ed8' }}>
                            ({item.gp_percent.toFixed(1)}%)
                          </span>
                        </div>
                      </div>

                      {/* CLOSING QTY */}
                      <div style={{ background: '#eef2ff', border: '1px solid #c7d2fe', borderRadius: '8px', padding: '10px' }}>
                        <div style={{ fontSize: '9px', fontWeight: 700, color: '#4338ca', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '6px' }}>Closing Qty</div>
                        <div style={{ fontWeight: 800, fontSize: '13px', color: '#312e81' }}>
                          {item.closing_balance.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {item.uom}
                        </div>
                      </div>

                      {/* CLOSING VALUE */}
                      <div style={{ background: '#eef2ff', border: '1px solid #c7d2fe', borderRadius: '8px', padding: '10px' }}>
                        <div style={{ fontSize: '9px', fontWeight: 700, color: '#4338ca', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '6px' }}>Closing Value</div>
                        <div style={{ fontWeight: 800, fontSize: '13px', color: '#312e81' }}>
                          {formatCurrency(item.closing_value)}
                        </div>
                      </div>

                    </div>
                  </div>
                )
              })
            )}

            {/* Mobile Summary Footer Card (Non-sticky, end of list) */}
            {filtered.length > 0 && (
              <div className="bg-card border border-primary/20 rounded-2xl p-4 shadow-sm mt-6 mb-4 space-y-3 font-sans">
                <div className="flex justify-between items-center pb-2 border-b border-border">
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-wider text-muted-foreground block">Stock Group Total</span>
                    <span className="text-xs font-bold text-muted-foreground">{filtered.length} Product{filtered.length === 1 ? '' : 's'}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] font-black uppercase tracking-wider text-muted-foreground block">Final Closing Value</span>
                    <span className="text-base font-black text-foreground">{formatCurrency(groupTotals.totalClosingValue)}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-emerald-500/10 border border-emerald-500/20 p-2.5 rounded-lg flex flex-col justify-between">
                    <span className="text-[10px] font-extrabold uppercase text-emerald-700 dark:text-emerald-400">Total Gross Profit</span>
                    <span className="text-sm font-black text-emerald-700 dark:text-emerald-300 mt-1">
                      {formatCurrency(groupTotals.totalGpValue)} <span className="text-xs font-bold">({groupTotals.totalGpPercent.toFixed(1)}%)</span>
                    </span>
                  </div>
                  <div className="bg-indigo-500/10 border border-indigo-500/20 p-2.5 rounded-lg flex flex-col justify-between">
                    <span className="text-[10px] font-extrabold uppercase text-indigo-700 dark:text-indigo-400">Total Closing Qty</span>
                    <span className="text-sm font-black text-indigo-700 dark:text-indigo-300 mt-1">
                      {groupTotals.totalClosingQty.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="bg-muted/40 p-2 rounded flex justify-between items-center col-span-2 text-[11px]">
                    <span className="text-muted-foreground font-medium">Inward: <strong>{formatCurrency(groupTotals.totalInwardValue)}</strong></span>
                    <span className="text-muted-foreground font-medium">Outward: <strong>{formatCurrency(groupTotals.totalOutwardValue)}</strong></span>
                    <span className="text-muted-foreground font-medium">Cons: <strong>{formatCurrency(groupTotals.totalConsValue)}</strong></span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* DESKTOP VIEW (TABULAR LAYOUT) */}
          <div className="hidden md:flex flex-1 flex-col min-h-0 px-4 py-4 overflow-auto">
            {filtered.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Package className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">No items found matching filters</p>
              </div>
            ) : (
              <div className="border border-border rounded-lg overflow-x-auto bg-card shadow-sm flex flex-col min-h-0 flex-initial">
                <table className="w-full border-collapse text-left text-xs min-w-[1000px]">
                  <thead>
                    <tr className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider select-none">
                      <th
                        onClick={() => handleSort('name')}
                        className="sticky top-0 z-10 bg-muted px-4 py-3 border-r border-b border-border cursor-pointer hover:bg-muted/80 transition-colors"
                        title="Click to sort by Product Name"
                      >
                        <div className="flex items-center justify-between">
                          <span>Product Particulars</span>
                          {sortField === 'name' && (
                            <span className="text-primary font-black ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('inward_value')}
                        className="sticky top-0 z-10 bg-muted px-4 py-3 text-right border-r border-b border-border cursor-pointer hover:bg-muted/80 transition-colors"
                        colSpan={2}
                        title="Click to sort by Inward Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Inward</span>
                          {(sortField === 'inward_qty' || sortField === 'inward_value') && (
                            <span className="text-primary font-black ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('outward_value')}
                        className="sticky top-0 z-10 bg-muted px-4 py-3 text-right border-r border-b border-border cursor-pointer hover:bg-muted/80 transition-colors"
                        colSpan={2}
                        title="Click to sort by Outward Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Outward</span>
                          {(sortField === 'outward_qty' || sortField === 'outward_value') && (
                            <span className="text-primary font-black ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('cons_value')}
                        className="sticky top-0 z-10 bg-muted px-4 py-3 text-right border-r border-b border-border cursor-pointer hover:bg-muted/80 transition-colors"
                        title="Click to sort by Consumption Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Cons. Value</span>
                          {sortField === 'cons_value' && (
                            <span className="text-primary font-black ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('gp_value')}
                        className="sticky top-0 z-10 bg-muted px-4 py-3 text-right border-r border-b border-border cursor-pointer hover:bg-muted/80 transition-colors"
                        colSpan={2}
                        title="Click to sort by Gross Profit Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Gross Profit</span>
                          {(sortField === 'gp_value' || sortField === 'gp_percent') && (
                            <span className="text-primary font-black ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('closing_balance')}
                        className="sticky top-0 z-10 bg-muted px-4 py-3 text-right border-r border-b border-border cursor-pointer hover:bg-muted/80 transition-colors"
                        title="Click to sort by Closing Quantity"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Closing Qty</span>
                          {sortField === 'closing_balance' && (
                            <span className="text-primary font-black ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('closing_value')}
                        className="sticky top-0 z-10 bg-muted px-4 py-3 text-right border-b border-border cursor-pointer hover:bg-muted/80 transition-colors"
                        title="Click to sort by Closing Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Closing Value</span>
                          {sortField === 'closing_value' && (
                            <span className="text-primary font-black ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>
                          )}
                        </div>
                      </th>
                    </tr>
                    <tr className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider select-none">
                      <th
                        onClick={() => handleSort('name')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-4 py-2 border-r border-border cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Name"
                      >
                        <div className="flex items-center justify-between">
                          <span>Name / Brand / Subtitle</span>
                          {getSortIcon('name')}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('inward_qty')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-3 py-2 text-right border-r border-border/50 cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Inward Quantity"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Qty</span>
                          {getSortIcon('inward_qty')}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('inward_value')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-3 py-2 text-right border-r border-border cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Inward Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Value</span>
                          {getSortIcon('inward_value')}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('outward_qty')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-3 py-2 text-right border-r border-border/50 cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Outward Quantity"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Qty</span>
                          {getSortIcon('outward_qty')}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('outward_value')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-3 py-2 text-right border-r border-border cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Outward Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Value</span>
                          {getSortIcon('outward_value')}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('cons_value')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-4 py-2 text-right border-r border-border cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Consumption Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>-</span>
                          {getSortIcon('cons_value')}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('gp_value')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-3 py-2 text-right border-r border-border/50 cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Gross Profit Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Value</span>
                          {getSortIcon('gp_value')}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('gp_percent')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-3 py-2 text-right border-r border-border cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Gross Profit %"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>%</span>
                          {getSortIcon('gp_percent')}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('closing_balance')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-4 py-2 text-right border-r border-border cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Closing Quantity"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Qty (UOM)</span>
                          {getSortIcon('closing_balance')}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('closing_value')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-4 py-2 text-right cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Closing Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Value</span>
                          {getSortIcon('closing_value')}
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {filtered.map(item => {
                      const details = getProductDetails(item.name, item.group_name)

                      const inwardQtyStr = item.inward_qty.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                      const outwardQtyStr = item.outward_qty.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                      const closingQtyStr = item.closing_balance.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

                      const isInwardZero = item.inward_qty === 0
                      const isOutwardZero = item.outward_qty === 0
                      const isConsZero = item.cons_value === 0
                      const isGpZero = item.gp_value === 0
                      const isClosingZero = item.closing_balance === 0

                      return (
                        <tr
                          key={item.item_id}
                          onClick={() => { setSelectedItem(item); setVoucherSearch('') }}
                          className="hover:bg-muted/30 cursor-pointer transition-colors text-foreground bg-card"
                        >
                          {/* Particulars */}
                          <td className="px-4 py-3 border-r border-border">
                            <div className="font-extrabold text-foreground uppercase text-[12px] mb-1">{item.name}</div>
                            <div className="flex items-center gap-2">
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-secondary text-secondary-foreground border border-border">
                                {details.brand}
                              </span>
                              <span className="text-muted-foreground font-medium text-[11px]">{details.subtitle}</span>
                            </div>
                          </td>
                          {/* Inward Qty */}
                          <td className={`px-3 py-3.5 text-right border-r border-border/50 font-medium ${isInwardZero ? 'text-muted-foreground/30' : 'text-foreground font-semibold'}`}>
                            {inwardQtyStr}
                          </td>
                          {/* Inward Value */}
                          <td className={`px-3 py-3.5 text-right border-r border-border ${isInwardZero ? 'text-muted-foreground/30' : 'text-foreground font-bold'}`}>
                            {formatCurrency(item.inward_value)}
                          </td>
                          {/* Outward Qty */}
                          <td className={`px-3 py-3.5 text-right border-r border-border/50 font-medium ${isOutwardZero ? 'text-muted-foreground/30' : 'text-foreground font-semibold'}`}>
                            {outwardQtyStr}
                          </td>
                          {/* Outward Value */}
                          <td className={`px-3 py-3.5 text-right border-r border-border ${isOutwardZero ? 'text-muted-foreground/30' : 'text-foreground font-bold'}`}>
                            {formatCurrency(item.outward_value)}
                          </td>
                          {/* Cons */}
                          <td className={`px-4 py-3.5 text-right border-r border-border font-medium ${isConsZero ? 'text-muted-foreground/30' : 'text-foreground'}`}>
                            {formatCurrency(item.cons_value)}
                          </td>
                          {/* GP Value */}
                          <td className={`px-3 py-3.5 text-right border-r border-border/50 font-bold ${isGpZero ? 'text-muted-foreground/30' : item.gp_value > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                            }`}>
                            {formatCurrency(item.gp_value)}
                          </td>
                          {/* GP % */}
                          <td className={`px-3 py-3.5 text-right border-r border-border font-semibold ${isGpZero ? 'text-muted-foreground/30' : item.gp_value > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                            }`}>
                            {item.gp_percent.toFixed(1)}%
                          </td>
                          {/* Closing Qty */}
                          <td className={`px-4 py-3.5 text-right border-r border-border font-bold ${isClosingZero ? 'text-muted-foreground/30' : 'text-foreground'}`}>
                            {closingQtyStr} <span className="text-[10px] text-muted-foreground font-medium">{item.uom}</span>
                          </td>
                          {/* Closing Value */}
                          <td className={`px-4 py-3.5 text-right font-black ${isClosingZero ? 'text-muted-foreground/30' : 'text-foreground'}`}>
                            {formatCurrency(item.closing_value)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                  {/* Table Grand Total Footer */}
                  <tfoot className="sticky bottom-0 z-10 bg-muted/95 backdrop-blur border-t-2 border-primary/40 shadow-md select-none">
                    <tr className="text-xs font-black text-foreground">
                      {/* Particulars / Total Label */}
                      <td className="px-4 py-3 border-r border-border bg-muted">
                        <div className="font-extrabold uppercase text-[12px] text-foreground">Grand Total</div>
                        <div className="text-[10px] text-muted-foreground font-semibold">
                          {filtered.length} Product{filtered.length === 1 ? '' : 's'}
                        </div>
                      </td>
                      {/* Inward Qty */}
                      <td className="px-3 py-3 text-right border-r border-border/50 font-bold bg-muted/90 text-foreground">
                        {groupTotals.totalInwardQty.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      {/* Inward Value */}
                      <td className="px-3 py-3 text-right border-r border-border font-bold bg-muted/90 text-foreground">
                        {formatCurrency(groupTotals.totalInwardValue)}
                      </td>
                      {/* Outward Qty */}
                      <td className="px-3 py-3 text-right border-r border-border/50 font-bold bg-muted/90 text-foreground">
                        {groupTotals.totalOutwardQty.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      {/* Outward Value */}
                      <td className="px-3 py-3 text-right border-r border-border font-bold bg-muted/90 text-foreground">
                        {formatCurrency(groupTotals.totalOutwardValue)}
                      </td>
                      {/* Cons. Value */}
                      <td className="px-4 py-3 text-right border-r border-border font-bold bg-muted/90 text-foreground">
                        {formatCurrency(groupTotals.totalConsValue)}
                      </td>
                      {/* Total Gross Profit Value */}
                      <td className={`px-3 py-3 text-right border-r border-border/50 font-extrabold bg-muted/90 ${
                        groupTotals.totalGpValue >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                      }`}>
                        {formatCurrency(groupTotals.totalGpValue)}
                      </td>
                      {/* Total Gross Profit % */}
                      <td className={`px-3 py-3 text-right border-r border-border font-extrabold bg-muted/90 ${
                        groupTotals.totalGpValue >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                      }`}>
                        {groupTotals.totalGpPercent.toFixed(1)}%
                      </td>
                      {/* Closing Qty */}
                      <td className="px-4 py-3 text-right border-r border-border font-bold bg-muted/90 text-foreground">
                        {groupTotals.totalClosingQty.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      {/* Final Closing Value */}
                      <td className="px-4 py-3 text-right font-black text-sm text-foreground bg-primary/10 border-l border-primary/20">
                        {formatCurrency(groupTotals.totalClosingValue)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3RD LEVEL — Stock Item Voucher Transaction List */}
      {selectedItem !== null ? (
        <div className="flex-1 flex flex-col min-h-0">
          {/* Item header card */}
          <div style={{ background: '#fff', borderBottom: '1px solid #e5e7eb', padding: '12px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <button
                onClick={() => { setSelectedItem(null); setVoucherSearch(''); setVoucherTypeFilter('All Vouchers'); setVoucherFlowFilter('All Flows') }}
                style={{ color: '#059669', fontWeight: 700, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '4px', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              >
                <ArrowLeft style={{ width: 14, height: 14, strokeWidth: 3 }} />
              </button>
              <span style={{ fontWeight: 900, fontSize: '22px', color: '#059669', letterSpacing: '-0.5px' }}>
                {selectedItem.name}
              </span>
            </div>
            <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: 600 }}>{selectedItem.group_name}</div>
            <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
              PART NO / UOM &nbsp;•&nbsp; <strong style={{ color: '#374151' }}>N/A / {selectedItem.uom || 'PCS'}</strong>
            </div>
          </div>

          {/* Search + filters */}
          <div style={{ background: '#fff', borderBottom: '1px solid #e5e7eb', padding: '10px 12px' }}>
            <input
              type="text"
              placeholder="Search party, voucher or invoice..."
              value={voucherSearch}
              onChange={e => setVoucherSearch(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '13px', outline: 'none', marginBottom: '8px', boxSizing: 'border-box' }}
            />
            <div style={{ display: 'flex', gap: '8px', fontSize: '12px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ color: '#6b7280', fontWeight: 600 }}>TYPE:</span>
                <select
                  value={voucherTypeFilter}
                  onChange={e => setVoucherTypeFilter(e.target.value)}
                  style={{ border: '1px solid #d1d5db', borderRadius: '6px', padding: '3px 6px', fontSize: '12px', background: '#fff' }}
                >
                  <option value="All Vouchers">All Vouchers</option>
                  {voucherTypes.map(vt => <option key={vt} value={vt}>{vt}</option>)}
                </select>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ color: '#6b7280', fontWeight: 600 }}>FLOW:</span>
                <select
                  value={voucherFlowFilter}
                  onChange={e => setVoucherFlowFilter(e.target.value)}
                  style={{ border: '1px solid #d1d5db', borderRadius: '6px', padding: '3px 6px', fontSize: '12px', background: '#fff' }}
                >
                  <option value="All Flows">All Flows</option>
                  <option value="Inward">Inward</option>
                  <option value="Outward">Outward</option>
                </select>
              </div>
            </div>
          </div>

          {/* Voucher list */}
          <div className="flex-1 overflow-y-auto min-h-0" style={{ background: '#f9fafb' }}>
            {vouchersLoading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
                <div style={{ width: 28, height: 28, border: '3px solid #059669', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} />
              </div>
            ) : filteredVouchers.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '48px 16px', color: '#9ca3af' }}>
                <Package style={{ width: 36, height: 36, margin: '0 auto 12px', opacity: 0.3 }} />
                <p style={{ fontSize: '13px' }}>No transactions found</p>
              </div>
            ) : (
              filteredVouchers.map((v, idx) => {
                const isInward = v.is_inward
                const date = new Date(v.voucher_date)
                const dateStr = date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' })
                const vType = v.voucher_type.toUpperCase()
                const vTypeBg = isInward ? '#059669' : '#e53e3e'
                return (
                  <div
                    key={v.stock_entry_id}
                    onClick={() => router.push(`/vouchers/${v.voucher_id}`)}
                    className="hover:bg-muted/40 transition-colors cursor-pointer"
                    style={{ background: '#fff', borderBottom: '1px solid #f3f4f6', padding: '12px 16px' }}
                    title="Click to view voucher details"
                  >
                    {/* Row 1: date + type badge + voucher link */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                      <span style={{ fontSize: '12px', color: '#374151', fontWeight: 700, minWidth: '64px' }}>{dateStr}</span>
                      <span style={{ background: vTypeBg, color: '#fff', fontSize: '9px', fontWeight: 800, padding: '2px 6px', borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {vType}
                      </span>
                      {v.reference_number && (
                        <span style={{ fontSize: '11px', color: '#6b7280' }}>#{v.reference_number}</span>
                      )}
                      <span style={{ marginLeft: 'auto', fontSize: '11px', fontWeight: 700, color: '#2563eb' }}>
                        Vch: {v.voucher_number}
                      </span>
                    </div>
                    {/* Row 2: party name */}
                    <div style={{ fontSize: '14px', fontWeight: 700, color: '#111827', marginBottom: '8px' }}>
                      {v.party_name}
                    </div>
                    {/* Row 3: flow badge + qty + value */}
                    <div style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      background: isInward ? '#f0fdf4' : '#fff5f5',
                      border: `1px solid ${isInward ? '#bbf7d0' : '#fecaca'}`,
                      borderRadius: '8px', padding: '8px 12px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{
                          fontSize: '10px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em',
                          color: isInward ? '#059669' : '#dc2626',
                          border: `1px solid ${isInward ? '#059669' : '#dc2626'}`,
                          borderRadius: '4px', padding: '1px 5px'
                        }}>
                          {isInward ? 'INWARD' : 'OUTWARD'}
                        </span>
                        <span style={{ fontSize: '10px', color: '#9ca3af' }}>ⓘ</span>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <span style={{ fontSize: '13px', fontWeight: 700, color: isInward ? '#065f46' : '#991b1b' }}>
                          {v.quantity.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {selectedItem.uom || 'PCS'}
                        </span>
                        <span style={{ fontSize: '12px', color: isInward ? '#059669' : '#dc2626', fontWeight: 700, marginLeft: '10px' }}>
                          | {formatCurrency(v.amount)}
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
