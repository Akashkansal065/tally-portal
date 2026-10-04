'use client'

import { useEffect, useState, useMemo, useRef, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, toTitleCase, cn } from '@/lib/utils'
import Link from 'next/link'
import { X, Package, ArrowUpDown, ArrowUp, ArrowDown, PackageCheck, SlidersHorizontal } from 'lucide-react'

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
  | 'closing_rate'

type SortDirection = 'asc' | 'desc'

const SORT_OPTIONS: { value: `${SortKey}-${SortDirection}`; label: string }[] = [
  { value: 'closing_balance-desc', label: 'Closing Qty (High to Low)' },
  { value: 'closing_balance-asc', label: 'Closing Qty (Low to High)' },
  { value: 'closing_value-desc', label: 'Closing Value (High to Low)' },
  { value: 'closing_value-asc', label: 'Closing Value (Low to High)' },
  { value: 'closing_rate-desc', label: 'Price / Qty (High to Low)' },
  { value: 'closing_rate-asc', label: 'Price / Qty (Low to High)' },
  { value: 'name-asc', label: 'Name (A to Z)' },
  { value: 'name-desc', label: 'Name (Z to A)' },
  { value: 'inward_qty-desc', label: 'Inward Qty (High to Low)' },
  { value: 'inward_qty-asc', label: 'Inward Qty (Low to High)' },
  { value: 'inward_value-desc', label: 'Inward Value (High to Low)' },
  { value: 'inward_value-asc', label: 'Inward Value (Low to High)' },
  { value: 'outward_qty-desc', label: 'Outward Qty (High to Low)' },
  { value: 'outward_qty-asc', label: 'Outward Qty (Low to High)' },
  { value: 'outward_value-desc', label: 'Outward Value (High to Low)' },
  { value: 'outward_value-asc', label: 'Outward Value (Low to High)' },
  { value: 'cons_value-desc', label: 'Cons. Value (High to Low)' },
  { value: 'cons_value-asc', label: 'Cons. Value (Low to High)' },
  { value: 'gp_value-desc', label: 'Gross Profit (High to Low)' },
  { value: 'gp_value-asc', label: 'Gross Profit (Low to High)' },
  { value: 'gp_percent-desc', label: 'Gross Profit % (High to Low)' },
  { value: 'gp_percent-asc', label: 'Gross Profit % (Low to High)' },
]
const DEFAULT_SORT = 'closing_balance-desc'

type StockItem = {
  item_id: number
  name: string
  group_name: string
  uom: string
  gst_rate_percent: number
  closing_balance: number
  closing_rate: number
  closing_value: number
  opening_balance: number
  opening_qty?: number
  opening_rate: number
  inward_qty: number
  inward_value: number
  outward_qty: number
  outward_value: number
  cons_value: number
  gp_value: number
  gp_percent: number
  hsn_code?: string
  part_number?: string
}

import { getProductDetails } from '@/lib/kgoc-mapping'
import { filterAndSortBySearch } from '@/lib/search'
import { ActiveFiltersSummary, FilterChips, FiltersToggle, useCollapsibleFilters } from '@/components/CollapsibleFilters'
import { Switch } from '@/components/ui/switch'
import { StockFilterSheet, StockItemSheet, StockRow, type StockSheetItem } from '@/components/stocks/StockMobile'

function StocksContent() {
  const { user, token, permissions, can } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const groupParam = searchParams.get('group')
  const itemParam = searchParams.get('item')

  const [items, setItems] = useState<StockItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if ((!can('stock_items', 'read') || permissions.stockScope === 'catalog_only')) { router.replace('/'); return }
  }, [user, permissions, can, router])

  const [search, setSearch] = useState('')
  const [selectedGroup, setSelectedGroup] = useState<string | null>(groupParam || null)

  // GST Display Mode Toggle (Default: With GST / Gross)
  const [isGrossGst, setIsGrossGst] = useState(true)

  // Helper to calculate valuation with or without GST
  const getItemVal = (
    item: StockItem,
    field: 'closing_value' | 'inward_value' | 'outward_value' | 'cons_value' | 'gp_value'
  ): number => {
    let base = Number(item[field]) || 0
    if (field === 'closing_value') {
      const clBal = Number(item.closing_balance) || 0
      if (clBal <= 0) {
        base = 0
      } else {
        const inwardVal = Number(item.inward_value) || 0
        const consVal = Number(item.cons_value) || 0
        const opBal = Number(item.opening_balance) || Number(item.opening_qty) || 0
        const opRate = Number(item.opening_rate) || 0
        const totalInVal = (opBal * opRate) + inwardVal
        if (totalInVal > 0) {
          const expectedClosingVal = Math.max(0, totalInVal - consVal)
          // If backend provided 0 or significantly stale closing value, self-heal using cost invariant
          if (base === 0 || Math.abs(base - expectedClosingVal) > 0.05 * (expectedClosingVal || 1)) {
            base = expectedClosingVal
          }
        }
      }
    }
    if (isGrossGst) {
      const gstRate = Number(item.gst_rate_percent) > 0 ? Number(item.gst_rate_percent) : 18
      return base * (1 + gstRate / 100)
    }
    return base
  }

  // Helper to calculate unit price / rate per quantity
  const getItemRate = (item: StockItem): number => {
    const clBal = Math.abs(Number(item.closing_balance) || 0)
    const closingVal = getItemVal(item, 'closing_value')

    if (clBal > 0 && closingVal > 0) {
      return closingVal / clBal
    }

    // When closing stock is 0 or closingVal is 0, fall back to weighted average unit purchase rate
    const inwardVal = Number(item.inward_value) || 0
    const inwardQty = Number(item.inward_qty) || 0
    const opBal = Number(item.opening_balance) || Number(item.opening_qty) || 0
    const opRate = Number(item.opening_rate) || 0
    const totalInQty = opBal + inwardQty
    const totalInVal = (opBal * opRate) + inwardVal

    let unitRate = 0
    if (totalInQty > 0) {
      unitRate = totalInVal / totalInQty
    } else if (opRate > 0) {
      unitRate = opRate
    } else if (Number(item.closing_rate) > 0) {
      unitRate = Number(item.closing_rate)
    }

    if (unitRate > 0) {
      if (isGrossGst) {
        const gstRate = Number(item.gst_rate_percent) > 0 ? Number(item.gst_rate_percent) : 18
        return unitRate * (1 + gstRate / 100)
      }
      return unitRate
    }

    return 0
  }

  // 3rd level — selected stock item voucher detail
  const [selectedItem, setSelectedItem] = useState<StockItem | null>(null)
  const [itemVouchers, setItemVouchers] = useState<any[]>([])
  const [vouchersLoading, setVouchersLoading] = useState(false)
  const [voucherSearch, setVoucherSearch] = useState('')
  const [voucherTypeFilter, setVoucherTypeFilter] = useState('All Vouchers')
  const [voucherFlowFilter, setVoucherFlowFilter] = useState('All Flows')

  // Synchronize selectedGroup from URL parameter (supports browser back/forward)
  useEffect(() => {
    setSelectedGroup(groupParam || null)
  }, [groupParam])

  // Synchronize selectedItem from URL parameter once items catalog is loaded
  useEffect(() => {
    if (!itemParam) {
      setSelectedItem(null)
      return
    }
    if (items.length > 0) {
      const found = items.find(
        i => String(i.item_id) === itemParam || i.name.toLowerCase() === itemParam.toLowerCase()
      )
      if (found) {
        setSelectedItem(found)
        if (!groupParam && found.group_name) {
          setSelectedGroup(found.group_name)
        }
      }
    }
  }, [itemParam, items, groupParam])

  // Navigation handlers that update URL to maintain browser history hierarchy
  const handleSelectGroup = (groupName: string) => {
    setSelectedGroup(groupName)
    setSelectedItem(null)
    setSearch('')
    router.push(`/stocks?group=${encodeURIComponent(groupName)}`)
  }

  const handleSelectItem = (item: StockItem) => {
    setSelectedItem(item)
    setVoucherSearch('')
    const grp = selectedGroup || item.group_name || ''
    router.push(`/stocks?group=${encodeURIComponent(grp)}&item=${encodeURIComponent(item.item_id)}`)
  }

  // Phones: tapping a product opens a sheet over the list. The sheet lives in the URL (?peek=<item id>), so the
  // phone's Back button closes it instead of leaving the group, and the list keeps its scroll position.
  const peekParam = searchParams.get('peek')
  const peekPushed = useRef(false)
  const groupUrl = (extra?: Record<string, string>) => {
    const params = new URLSearchParams(selectedGroup ? { group: selectedGroup, ...extra } : extra)
    const query = params.toString()
    return query ? `/stocks?${query}` : '/stocks'
  }
  const openPeek = (item: StockItem) => {
    peekPushed.current = true
    router.push(groupUrl({ peek: String(item.item_id) }), { scroll: false })
  }
  const closePeek = () => {
    if (peekPushed.current) {
      peekPushed.current = false
      router.back()
    } else {
      // Opened from a shared link: there is no list entry to go back to
      router.replace(groupUrl(), { scroll: false })
    }
  }

  // Filters State
  const [stockStatus, setStockStatus] = useState('All Items')
  const [movement, setMovement] = useState('All Movement')
  const [profitFilter, setProfitFilter] = useState('All Profit')
  const [sortField, setSortField] = useState<SortKey>('closing_balance')
  const [sortDir, setSortDir] = useState<SortDirection>('desc')
  const groupFilters = useCollapsibleFilters('stocks-group')
  const sortValue = `${sortField}-${sortDir}`
  const activeGroupFilters = [
    stockStatus !== 'All Items' && stockStatus,
    movement !== 'All Movement' && movement,
    profitFilter !== 'All Profit' && profitFilter,
    sortValue !== DEFAULT_SORT && `Sorted by ${SORT_OPTIONS.find(o => o.value === sortValue)?.label ?? sortValue}`,
  ].filter((label): label is string => Boolean(label))
  const groupFilterChips = [
    stockStatus !== 'All Items' && { key: 'status', label: stockStatus, onRemove: () => setStockStatus('All Items') },
    movement !== 'All Movement' && { key: 'movement', label: movement, onRemove: () => setMovement('All Movement') },
    profitFilter !== 'All Profit' && { key: 'profit', label: profitFilter, onRemove: () => setProfitFilter('All Profit') },
    sortValue !== DEFAULT_SORT && {
      key: 'sort',
      label: `Sorted by ${SORT_OPTIONS.find(o => o.value === sortValue)?.label ?? sortValue}`,
      onRemove: () => { setSortField('closing_balance'); setSortDir('desc') },
    },
  ].filter((chip): chip is { key: string; label: string; onRemove: () => void } => Boolean(chip))
  const [filterSheetOpen, setFilterSheetOpen] = useState(false)
  const resetGroupFilters = () => {
    setStockStatus('All Items')
    setMovement('All Movement')
    setProfitFilter('All Profit')
    setSortField('closing_balance')
    setSortDir('desc')
  }

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
          gst_rate_percent: Number(i.gst_rate_percent) > 0 ? Number(i.gst_rate_percent) : 18,
          closing_balance: Number(i.closing_balance) || 0,
          closing_rate: Number(i.closing_rate) || 0,
          closing_value: Number(i.closing_value) || 0,
          opening_balance: Number(i.opening_balance) || Number((i as any).opening_qty) || 0,
          opening_qty: Number((i as any).opening_qty) || Number(i.opening_balance) || 0,
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
    const summary: Record<string, { value: number; gstRates: Set<number> }> = {}
    items.forEach(item => {
      const g = item.group_name || 'Others'
      const val = getItemVal(item, 'closing_value')
      const gstRate = Number(item.gst_rate_percent) > 0 ? Number(item.gst_rate_percent) : 18
      if (!summary[g]) {
        summary[g] = { value: 0, gstRates: new Set<number>() }
      }
      summary[g].value += val
      summary[g].gstRates.add(gstRate)
    })
    return Object.entries(summary)
      .map(([group_name, data]) => {
        const sortedRates = Array.from(data.gstRates).sort((a, b) => a - b)
        const gstLabel = sortedRates.length === 1
          ? `${sortedRates[0]}% GST`
          : `${sortedRates.join(', ')}% GST`
        return {
          group_name,
          value: data.value,
          gstLabel,
        }
      })
      .sort((a, b) => b.value - a.value)
  }, [items, isGrossGst])

  const grandTotal = useMemo(() => {
    return summaryData.reduce((acc, row) => acc + row.value, 0)
  }, [summaryData])

  const groupItemCount = useMemo(
    () => (selectedGroup ? items.filter(item => item.group_name === selectedGroup).length : 0),
    [items, selectedGroup],
  )

  // Filter items in the detail view based on selected group & search keyword
  const filtered = useMemo(() => {
    if (!selectedGroup) return []
    let result = items.filter(item => item.group_name === selectedGroup)

    // Search filter
    if (search.trim()) {
      result = filterAndSortBySearch(result, search, item => [
        item.name,
        item.group_name,
        getProductDetails(item.name, item.group_name).subtitle,
        item.hsn_code,
        item.part_number
      ])
    }

    // Stock Status filter
    if (stockStatus === 'In Stock') {
      result = result.filter(item => (item.closing_balance || 0) > 0)
    } else if (stockStatus === 'Out of Stock') {
      result = result.filter(item => (item.closing_balance || 0) <= 0)
    } else if (stockStatus === 'Negative Stock') {
      result = result.filter(item => (item.closing_balance || 0) < 0)
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
      } else if (
        sortField === 'closing_value' ||
        sortField === 'inward_value' ||
        sortField === 'outward_value' ||
        sortField === 'cons_value' ||
        sortField === 'gp_value'
      ) {
        const valA = getItemVal(a, sortField)
        const valB = getItemVal(b, sortField)
        comparison = valA - valB
      } else if (sortField === 'closing_rate') {
        const rateA = getItemRate(a)
        const rateB = getItemRate(b)
        comparison = rateA - rateB
      } else {
        const valA = Number(a[sortField]) || 0
        const valB = Number(b[sortField]) || 0
        comparison = valA - valB
      }
      return sortDir === 'asc' ? comparison : -comparison
    })

    return result
  }, [items, selectedGroup, search, stockStatus, movement, profitFilter, sortField, sortDir, isGrossGst])

  // Compute aggregated totals for the selected stock group
  const groupTotals = useMemo(() => {
    const totalInwardQty = filtered.reduce((sum, item) => sum + (Number(item.inward_qty) || 0), 0)
    const totalInwardValue = filtered.reduce((sum, item) => sum + getItemVal(item, 'inward_value'), 0)
    const totalOutwardQty = filtered.reduce((sum, item) => sum + (Number(item.outward_qty) || 0), 0)
    const totalOutwardValue = filtered.reduce((sum, item) => sum + getItemVal(item, 'outward_value'), 0)
    const totalConsValue = filtered.reduce((sum, item) => sum + getItemVal(item, 'cons_value'), 0)
    const totalGpValue = filtered.reduce((sum, item) => sum + getItemVal(item, 'gp_value'), 0)
    
    // In Tally, Gross Profit % is calculated as: (Total Gross Profit / Total Outward Value) * 100
    const totalGpPercent = totalOutwardValue > 0
      ? (totalGpValue / totalOutwardValue) * 100
      : (totalConsValue > 0 ? (totalGpValue / totalConsValue) * 100 : 0)
      
    const totalClosingQty = filtered.reduce((sum, item) => sum + (Number(item.closing_balance) || 0), 0)
    const totalClosingValue = filtered.reduce((sum, item) => sum + getItemVal(item, 'closing_value'), 0)

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
  }, [filtered, isGrossGst])

  const peekItem = peekParam ? items.find(i => String(i.item_id) === peekParam) ?? null : null
  const peekSheetItem: StockSheetItem | null = peekItem
    ? {
        itemId: peekItem.item_id,
        name: peekItem.name,
        group: toTitleCase(peekItem.group_name || ''),
        uom: peekItem.uom || 'PCS',
        gstRate: Number(peekItem.gst_rate_percent) || 18,
        subtitle: getProductDetails(peekItem.name, peekItem.group_name).subtitle,
        closingQty: Number(peekItem.closing_balance) || 0,
        closingValue: getItemVal(peekItem, 'closing_value'),
        rate: getItemRate(peekItem),
        inwardQty: Number(peekItem.inward_qty) || 0,
        inwardValue: getItemVal(peekItem, 'inward_value'),
        outwardQty: Number(peekItem.outward_qty) || 0,
        outwardValue: getItemVal(peekItem, 'outward_value'),
        consValue: getItemVal(peekItem, 'cons_value'),
        gpValue: getItemVal(peekItem, 'gp_value'),
        gpPercent: Number(peekItem.gp_percent) || 0,
      }
    : null

  // Filtered vouchers for 3rd level
  const filteredVouchers = useMemo(() => {
    let result = itemVouchers.filter(v => {
      if (voucherTypeFilter !== 'All Vouchers' && v.voucher_type !== voucherTypeFilter) return false
      if (voucherFlowFilter === 'Inward' && !v.is_inward) return false
      if (voucherFlowFilter === 'Outward' && v.is_inward) return false
      return true
    })
    if (voucherSearch.trim()) {
      result = filterAndSortBySearch(result, voucherSearch, v => [
        v.party_name,
        v.voucher_number,
        v.voucher_type,
        v.narration
      ])
    }
    return result
  }, [itemVouchers, voucherTypeFilter, voucherFlowFilter, voucherSearch])

  const voucherTypes = Array.from(new Set(itemVouchers.map(v => v.voucher_type)))

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Title for the current level. Going back is the header's Back button (or the Stock tab for the summary). */}
      <div className="shrink-0 border-b border-border bg-card px-4 py-2.5">
        <h1 className="truncate text-lg font-bold leading-tight text-foreground">
          {selectedItem !== null ? selectedItem.name : selectedGroup !== null ? toTitleCase(selectedGroup) : 'Stock summary'}
        </h1>
        <p className="truncate text-sm text-muted-foreground">
          {selectedItem !== null
            ? `${toTitleCase(selectedItem.group_name || '')} · Stock movement`
            : selectedGroup !== null
              ? `Stock group · ${groupItemCount} item${groupItemCount === 1 ? '' : 's'}`
              : `${activeCompanyName} · Closing balance ${isGrossGst ? 'incl.' : 'excl.'} GST`}
        </p>
      </div>

      {/* If an item is requested via URL and items are still loading, show smooth loader */}
      {itemParam && loading ? (
        <div className="flex-1 flex items-center justify-center py-20 bg-background">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs font-bold text-muted-foreground">Loading product details...</span>
          </div>
        </div>
      ) : selectedGroup === null ? (
        // SUMMARY VIEW
        <div className="flex-1 flex flex-col min-h-0">
          <div className="shrink-0 px-4 py-3 flex flex-wrap items-center gap-x-3 gap-y-2">
            <p className="mr-auto text-sm text-muted-foreground">Period: 1-Apr-2026 to 31-Mar-2027</p>
            <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-border bg-card px-3 text-sm font-semibold text-foreground">
              <Switch checked={isGrossGst} onCheckedChange={setIsGrossGst} aria-label="Values include GST" />
              With GST
            </label>
            <Link
              href="/reports?tab=company_stock"
              className="inline-flex min-h-11 items-center gap-1.5 px-3 rounded-xl text-sm font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100 dark:hover:bg-indigo-900 transition-colors"
            >
              <PackageCheck className="w-4 h-4" aria-hidden="true" />
              <span>Stock & profit report</span>
            </Link>
          </div>

          <div className="flex-1 min-h-0 px-4 pb-4 flex flex-col">
            <div className="border border-border rounded-lg overflow-hidden bg-card flex flex-col min-h-0 flex-initial shadow-sm">
              {/* Table Column Headers */}
              <div className="shrink-0 grid grid-cols-2 bg-muted/40 text-[10px] font-bold text-muted-foreground uppercase tracking-wider border-b border-border">
                <span className="px-4 py-3 border-r border-border">Particulars</span>
                <span className="px-4 py-3 text-right">Value {isGrossGst ? '(Incl. GST)' : '(Excl. GST)'}</span>
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
                      onClick={() => handleSelectGroup(row.group_name)}
                      className="w-full grid grid-cols-2 text-left font-medium text-sm transition-colors text-foreground focus:outline-none hover:bg-muted/30"
                    >
                      <span className="px-4 py-3.5 font-extrabold text-foreground uppercase tracking-wide border-r border-border flex items-center justify-between">
                        <span>{row.group_name}</span>
                        {isGrossGst && (
                          <span className="text-[11px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 px-2 py-0.5 rounded normal-case tracking-normal">
                            ({row.gstLabel})
                          </span>
                        )}
                      </span>
                      <span className="px-4 py-3.5 font-black text-right text-foreground flex flex-col items-end justify-center">
                        <span>{formatCurrency(row.value)}</span>
                        {isGrossGst && (
                          <span className="text-[11px] font-semibold text-muted-foreground">
                            ({row.gstLabel})
                          </span>
                        )}
                      </span>
                    </button>
                  ))
                )}
              </div>

              {/* Table Grand Total Footer */}
              {!loading && summaryData.length > 0 && (
                <div className="shrink-0 grid grid-cols-2 bg-muted/40 border-t border-border font-black text-sm uppercase text-foreground">
                  <span className="px-4 py-3.5 border-r border-border">Grand Total</span>
                  <span className="text-right px-4 py-3.5 flex flex-col items-end justify-center">
                    <span>{formatCurrency(grandTotal)}</span>
                    {isGrossGst && (
                      <span className="text-[11px] font-semibold text-muted-foreground normal-case tracking-normal">
                        (incl. applicable GST)
                      </span>
                    )}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : selectedItem !== null ? null : (
        // DETAIL ITEMS VIEW FOR SELECTED GROUP MATCHING MOCKUP PRECISELY
        <div className="flex-1 flex flex-col min-h-0 bg-muted/10">
          {/* Combined Search and Filters Container */}
          <div className="px-4 py-3 bg-background border-b border-border flex flex-wrap items-center md:items-start gap-x-4 gap-y-3">
            {/* Search Block, with the button that minimises the filters so the list gets the screen */}
            <div className="flex items-center gap-3 basis-full md:basis-96 md:flex-none min-w-0">
              <div className="flex-1 relative">
                <input
                  type="text"
                  placeholder="Search products..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  aria-label="Search products"
                  className="w-full h-11 px-4 pr-10 border border-border rounded-xl text-sm bg-muted/20 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:bg-background"
                />
                {search && (
                  <button
                    onClick={() => setSearch('')}
                    aria-label="Clear search"
                    className="absolute right-0 top-1/2 -translate-y-1/2 inline-flex h-11 w-11 items-center justify-center text-muted-foreground"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
              <FiltersToggle state={groupFilters} active={activeGroupFilters} className="hidden md:inline-flex" />
              {/* Phones: filters and sort open in a sheet */}
              <button
                type="button"
                onClick={() => setFilterSheetOpen(true)}
                aria-haspopup="dialog"
                className={cn(
                  'md:hidden shrink-0 inline-flex h-11 items-center gap-1.5 rounded-xl border px-3 text-sm font-bold cursor-pointer',
                  activeGroupFilters.length > 0 ? 'border-primary/40 bg-primary/10 text-primary' : 'border-border bg-card text-foreground',
                )}
              >
                <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                Filter
                {activeGroupFilters.length > 0 && (
                  <span className="min-w-5 h-5 px-1 rounded-full bg-primary text-primary-foreground text-xs leading-5 text-center tabular-nums">
                    {activeGroupFilters.length}
                  </span>
                )}
              </button>
            </div>

            <FilterChips
              className="basis-full md:hidden"
              items={groupFilterChips}
              onClearAll={resetGroupFilters}
            />

            <ActiveFiltersSummary
              state={groupFilters}
              active={activeGroupFilters}
              onReset={resetGroupFilters}
              className="basis-full hidden md:flex"
            />

            {/* Filters Block */}
            <div
              id={groupFilters.panelId}
              hidden={groupFilters.collapsed}
              className="max-md:hidden flex flex-wrap items-center gap-3 md:gap-4 md:basis-0 md:flex-1 md:min-w-0 md:justify-end text-xs font-semibold text-muted-foreground"
            >
              {/* GST Display Mode Toggle */}
              <button
                onClick={() => setIsGrossGst(!isGrossGst)}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-bold transition-all cursor-pointer shadow-2xs select-none',
                  isGrossGst
                    ? 'bg-emerald-600 text-white border-emerald-700 ring-2 ring-emerald-500/20'
                    : 'bg-card border-border text-foreground hover:bg-muted/50'
                )}
                title="Toggle between Valuation With GST (Gross) and Without GST (Net)"
              >
                <div className={cn(
                  'w-6 h-3.5 rounded-full p-0.5 transition-colors flex items-center',
                  isGrossGst ? 'bg-white/30 justify-end' : 'bg-muted-foreground/30 justify-start'
                )}>
                  <div className="w-2.5 h-2.5 rounded-full bg-white shadow-xs" />
                </div>
                <span>{isGrossGst ? 'With GST' : 'Without GST'}</span>
              </button>

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
                  <option value="Negative Stock">Negative Stock (Anomalies)</option>
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
                  value={sortValue}
                  onChange={e => {
                    const [f, d] = e.target.value.split('-') as [SortKey, SortDirection]
                    setSortField(f)
                    setSortDir(d)
                  }}
                  className="bg-card text-foreground border border-border rounded px-2 py-1 focus:outline-none text-xs font-semibold"
                >
                  {SORT_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* PHONES: compact rows; tapping one opens the product sheet and keeps the list where it is */}
          <ul className="md:hidden flex-1 overflow-y-auto min-h-0 divide-y divide-border bg-card" aria-label="Products">
            {filtered.length === 0 ? (
              <li className="text-center py-12 px-4 text-muted-foreground">
                <Package className="h-10 w-10 mx-auto mb-3 opacity-30" aria-hidden="true" />
                <p className="text-sm">No products match these filters.</p>
                {activeGroupFilters.length > 0 && (
                  <button type="button" onClick={resetGroupFilters} className="mt-2 min-h-11 px-3 text-sm font-semibold text-primary cursor-pointer">
                    Clear filters
                  </button>
                )}
              </li>
            ) : (
              filtered.map(item => (
                <StockRow
                  key={item.item_id}
                  name={item.name}
                  qty={Number(item.closing_balance) || 0}
                  uom={item.uom || 'PCS'}
                  rate={getItemRate(item)}
                  value={getItemVal(item, 'closing_value')}
                  gpPercent={Number(item.gp_percent) || 0}
                  hasSales={(Number(item.outward_qty) || 0) !== 0 || (Number(item.gp_value) || 0) !== 0}
                  onOpen={() => openPeek(item)}
                />
              ))
            )}
          </ul>
          {filtered.length > 0 && (
            <div className="md:hidden shrink-0 flex items-center justify-between gap-3 border-t border-border bg-muted/60 px-4 py-2.5">
              <span className="text-sm text-muted-foreground">
                {filtered.length} item{filtered.length === 1 ? '' : 's'} · {isGrossGst ? 'incl.' : 'excl.'} GST
              </span>
              <span className="text-base font-bold tabular-nums text-foreground">{formatCurrency(groupTotals.totalClosingValue)}</span>
            </div>
          )}

          {/* DESKTOP VIEW (TABULAR LAYOUT) */}
          <div className="hidden md:flex flex-1 flex-col min-h-0 px-4 py-4 overflow-auto">
            {filtered.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Package className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">No items found matching filters</p>
              </div>
            ) : (
              <div className="border border-border rounded-lg overflow-x-auto bg-card shadow-sm flex flex-col min-h-0 flex-initial">
                <table className="w-full border-collapse text-left text-xs min-w-[1100px]">
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
                          <span>Inward {isGrossGst ? '(Gross)' : ''}</span>
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
                          <span>Outward {isGrossGst ? '(Gross)' : ''}</span>
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
                          <span>Cons. Value {isGrossGst ? '(Gross)' : ''}</span>
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
                          <span>Gross Profit {isGrossGst ? '(Gross)' : ''}</span>
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
                        className="sticky top-0 z-10 bg-muted px-4 py-3 text-right border-r border-b border-border cursor-pointer hover:bg-muted/80 transition-colors"
                        title="Click to sort by Closing Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Closing Value {isGrossGst ? '(Gross)' : ''}</span>
                          {sortField === 'closing_value' && (
                            <span className="text-primary font-black ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>
                          )}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('closing_rate')}
                        className="sticky top-0 z-10 bg-muted px-4 py-3 text-right border-b border-border cursor-pointer hover:bg-muted/80 transition-colors"
                        title="Click to sort by Price per Qty"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Price / Qty {isGrossGst ? '(Gross)' : ''}</span>
                          {sortField === 'closing_rate' && (
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
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-4 py-2 text-right border-r border-border cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Closing Value"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Value</span>
                          {getSortIcon('closing_value')}
                        </div>
                      </th>
                      <th
                        onClick={() => handleSort('closing_rate')}
                        className="sticky top-[37px] z-10 bg-muted/95 border-b border-border px-4 py-2 text-right cursor-pointer hover:bg-muted transition-colors group"
                        title="Sort by Price per Qty"
                      >
                        <div className="flex items-center justify-end gap-1">
                          <span>Price / Qty</span>
                          {getSortIcon('closing_rate')}
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
                          onClick={() => handleSelectItem(item)}
                          className="hover:bg-muted/30 cursor-pointer transition-colors text-foreground bg-card"
                        >
                          {/* Particulars */}
                          <td className="px-4 py-3 border-r border-border">
                            <div className="font-extrabold text-foreground uppercase text-[12px] mb-1 flex items-center flex-wrap gap-1">
                              <span>{item.name}</span>
                              <span className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 normal-case tracking-normal">
                                ({item.gst_rate_percent}% GST)
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-secondary text-secondary-foreground border border-border">
                                {details.brand}
                              </span>
                              <span className="text-muted-foreground font-medium text-[11px]">{details.subtitle}</span>
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold text-muted-foreground bg-muted border border-border">
                                ({item.gst_rate_percent}% GST)
                              </span>
                            </div>
                          </td>
                          {/* Inward Qty */}
                          <td className={`px-3 py-3.5 text-right border-r border-border/50 font-medium ${isInwardZero ? 'text-muted-foreground/30' : 'text-foreground font-semibold'}`}>
                            {inwardQtyStr}
                          </td>
                          {/* Inward Value */}
                          <td className={`px-3 py-3.5 text-right border-r border-border ${isInwardZero ? 'text-muted-foreground/30' : 'text-foreground font-bold'}`}>
                            <div>{formatCurrency(getItemVal(item, 'inward_value'))}</div>
                            {!isInwardZero && isGrossGst && (
                              <div className="text-[10px] font-medium text-muted-foreground">
                                ({item.gst_rate_percent}% GST)
                              </div>
                            )}
                          </td>
                          {/* Outward Qty */}
                          <td className={`px-3 py-3.5 text-right border-r border-border/50 font-medium ${isOutwardZero ? 'text-muted-foreground/30' : 'text-foreground font-semibold'}`}>
                            {outwardQtyStr}
                          </td>
                          {/* Outward Value */}
                          <td className={`px-3 py-3.5 text-right border-r border-border ${isOutwardZero ? 'text-muted-foreground/30' : 'text-foreground font-bold'}`}>
                            <div>{formatCurrency(getItemVal(item, 'outward_value'))}</div>
                            {!isOutwardZero && isGrossGst && (
                              <div className="text-[10px] font-medium text-muted-foreground">
                                ({item.gst_rate_percent}% GST)
                              </div>
                            )}
                          </td>
                          {/* Cons */}
                          <td className={`px-4 py-3.5 text-right border-r border-border font-medium ${isConsZero ? 'text-muted-foreground/30' : 'text-foreground'}`}>
                            <div>{formatCurrency(getItemVal(item, 'cons_value'))}</div>
                            {!isConsZero && isGrossGst && (
                              <div className="text-[10px] font-medium text-muted-foreground">
                                ({item.gst_rate_percent}% GST)
                              </div>
                            )}
                          </td>
                          {/* GP Value */}
                          <td className={`px-3 py-3.5 text-right border-r border-border/50 font-bold ${isGpZero ? 'text-muted-foreground/30' : item.gp_value > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                            }`}>
                            <div>{formatCurrency(getItemVal(item, 'gp_value'))}</div>
                            {!isGpZero && isGrossGst && (
                              <div className="text-[10px] font-medium opacity-80">
                                ({item.gst_rate_percent}% GST)
                              </div>
                            )}
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
                          <td className={`px-4 py-3.5 text-right font-black border-r border-border ${isClosingZero ? 'text-muted-foreground/30' : 'text-foreground'}`}>
                            <div>{formatCurrency(getItemVal(item, 'closing_value'))}</div>
                            {!isClosingZero && isGrossGst && (
                              <div className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
                                ({item.gst_rate_percent}% GST)
                              </div>
                            )}
                          </td>
                          {/* Price per Qty */}
                          <td className={`px-4 py-3.5 text-right font-bold ${getItemRate(item) === 0 ? 'text-muted-foreground/30' : 'text-foreground'}`}>
                            <div>
                              {getItemRate(item) > 0 ? formatCurrency(getItemRate(item)) : '-'}
                            </div>
                            {item.uom && getItemRate(item) > 0 && (
                              <div className="text-[10px] font-medium text-muted-foreground">
                                per {item.uom}
                              </div>
                            )}
                            {isGrossGst && getItemRate(item) > 0 && (
                              <div className="text-[9px] font-semibold text-emerald-600 dark:text-emerald-400">
                                ({item.gst_rate_percent}% GST)
                              </div>
                            )}
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
                      <td className="px-4 py-3 text-right font-black text-sm text-foreground bg-primary/10 border-l border-r border-primary/20">
                        <div>{formatCurrency(groupTotals.totalClosingValue)}</div>
                        {isGrossGst && (
                          <div className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 normal-case tracking-normal">
                            (incl. GST)
                          </div>
                        )}
                      </td>
                      {/* Average Price per Qty */}
                      <td className="px-4 py-3 text-right font-black text-xs text-foreground bg-muted/90">
                        <div>
                          {groupTotals.totalClosingQty > 0
                            ? formatCurrency(groupTotals.totalClosingValue / groupTotals.totalClosingQty)
                            : '-'}
                        </div>
                        {groupTotals.totalClosingQty > 0 && (
                          <div className="text-[9px] font-semibold text-muted-foreground">
                            avg / unit
                          </div>
                        )}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3RD LEVEL — every voucher that moved this product */}
      {selectedItem !== null ? (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="shrink-0 border-b border-border bg-card px-4 py-3 space-y-2.5">
            <p className="text-sm text-muted-foreground">
              Unit: <span className="font-semibold text-foreground">{selectedItem.uom || 'PCS'}</span>
              {' · '}GST: <span className="font-semibold text-foreground">{selectedItem.gst_rate_percent}%</span>
            </p>
            <div className="relative">
              <input
                type="text"
                placeholder="Search party, voucher or invoice…"
                aria-label="Search vouchers"
                value={voucherSearch}
                onChange={e => setVoucherSearch(e.target.value)}
                className="w-full h-11 px-4 pr-10 rounded-xl border border-border bg-muted/20 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:bg-background"
              />
              {voucherSearch && (
                <button
                  type="button"
                  onClick={() => setVoucherSearch('')}
                  aria-label="Clear search"
                  className="absolute right-0 top-1/2 -translate-y-1/2 inline-flex h-11 w-11 items-center justify-center text-muted-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-xl border border-border bg-card px-3 font-semibold text-foreground">
                <Switch checked={isGrossGst} onCheckedChange={setIsGrossGst} aria-label="Amounts include GST" />
                With GST
              </label>
              <select
                value={voucherTypeFilter}
                onChange={e => setVoucherTypeFilter(e.target.value)}
                aria-label="Voucher type"
                className="h-11 rounded-xl border border-border bg-card px-3 text-sm font-semibold text-foreground"
              >
                <option value="All Vouchers">All voucher types</option>
                {voucherTypes.map(vt => <option key={vt} value={vt}>{vt}</option>)}
              </select>
              <select
                value={voucherFlowFilter}
                onChange={e => setVoucherFlowFilter(e.target.value)}
                aria-label="Direction"
                className="h-11 rounded-xl border border-border bg-card px-3 text-sm font-semibold text-foreground"
              >
                <option value="All Flows">In and out</option>
                <option value="Inward">Inward only</option>
                <option value="Outward">Outward only</option>
              </select>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto min-h-0 bg-muted/20">
            {vouchersLoading ? (
              <div className="flex justify-center py-10">
                <div className="h-7 w-7 rounded-full border-[3px] border-emerald-600 border-t-transparent animate-spin" aria-label="Loading vouchers" />
              </div>
            ) : filteredVouchers.length === 0 ? (
              <div className="py-12 px-4 text-center text-muted-foreground">
                <Package className="mx-auto mb-3 h-9 w-9 opacity-30" aria-hidden="true" />
                <p className="text-sm">No vouchers found.</p>
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {filteredVouchers.map(v => {
                  const isInward = v.is_inward
                  const dateStr = new Date(v.voucher_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' })
                  const effectiveGstRate = Number(v.gst_rate) > 0 ? Number(v.gst_rate) : (selectedItem.gst_rate_percent || 18)
                  const voucherDisplayAmount = isGrossGst
                    ? Number(v.amount) * (1 + effectiveGstRate / 100)
                    : Number(v.amount)
                  return (
                    <li key={v.stock_entry_id}>
                      <button
                        type="button"
                        onClick={() => router.push(`/vouchers/${v.voucher_id}`)}
                        className="w-full bg-card px-4 py-3 text-left hover:bg-muted/40 cursor-pointer"
                      >
                        <span className="flex items-center gap-2 text-sm">
                          <span className="font-semibold text-foreground tabular-nums">{dateStr}</span>
                          <span
                            className={cn(
                              'rounded px-1.5 py-0.5 text-xs font-bold uppercase tracking-wide text-white',
                              isInward ? 'bg-emerald-600' : 'bg-rose-600',
                            )}
                          >
                            {v.voucher_type}
                          </span>
                          {v.reference_number && <span className="truncate text-muted-foreground">#{v.reference_number}</span>}
                          <span className="ml-auto shrink-0 font-semibold text-blue-700 dark:text-blue-400">Vch {v.voucher_number}</span>
                        </span>
                        <span className="mt-1 block truncate text-[15px] font-semibold text-foreground">{v.party_name}</span>
                        <span
                          className={cn(
                            'mt-2 flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm',
                            isInward
                              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300'
                              : 'border-rose-500/30 bg-rose-500/10 text-rose-800 dark:text-rose-300',
                          )}
                        >
                          <span className="text-xs font-bold uppercase tracking-wide">{isInward ? 'Inward' : 'Outward'}</span>
                          <span className="font-bold tabular-nums">
                            {Number(v.quantity).toLocaleString('en-IN', { maximumFractionDigits: 3 })} {selectedItem.uom || 'PCS'}
                            {' · '}
                            {formatCurrency(voucherDisplayAmount)}
                            {isGrossGst && <span className="font-medium"> ({effectiveGstRate}% GST)</span>}
                          </span>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>
      ) : null}

      <StockFilterSheet
        open={filterSheetOpen}
        onOpenChange={setFilterSheetOpen}
        stockStatus={stockStatus}
        onStockStatus={setStockStatus}
        movement={movement}
        onMovement={setMovement}
        profit={profitFilter}
        onProfit={setProfitFilter}
        sortField={sortField}
        sortDir={sortDir}
        onSort={(field, dir) => { setSortField(field as SortKey); setSortDir(dir) }}
        withGst={isGrossGst}
        onWithGst={setIsGrossGst}
        resultCount={filtered.length}
        hasActive={activeGroupFilters.length > 0}
        onReset={resetGroupFilters}
      />
      <StockItemSheet
        item={peekSheetItem}
        open={peekSheetItem !== null && selectedItem === null}
        onOpenChange={(open) => { if (!open) closePeek() }}
        token={token}
        withGst={isGrossGst}
        companyName={activeCompanyName}
        onSeeAll={() => { if (peekItem) { peekPushed.current = false; handleSelectItem(peekItem) } }}
        onOpenVoucher={(voucherId) => { peekPushed.current = false; router.push(`/vouchers/${voucherId}`) }}
      />
    </div>
  )
}

export default function StocksPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full py-20 bg-background">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs font-bold text-muted-foreground">Loading Stock Summary...</span>
          </div>
        </div>
      }
    >
      <StocksContent />
    </Suspense>
  )
}
