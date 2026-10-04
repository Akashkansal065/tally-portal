'use client'

import { useEffect, useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronRight, Loader2, Share2 } from 'lucide-react'
import { toast } from 'sonner'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { Switch } from '@/components/ui/switch'
import { API_BASE, authHeaders, cn, formatCurrency } from '@/lib/utils'
import { shareText } from '@/lib/share'

/* Phone layouts for the stock screens: compact rows, a filter & sort sheet, and a product detail sheet. */

export function formatQty(qty: number): string {
  return qty.toLocaleString('en-IN', { maximumFractionDigits: 3 })
}

function GpLabel({ gpPercent, hasSales }: { gpPercent: number; hasSales: boolean }) {
  if (!hasSales) return <span className="text-muted-foreground">GP —</span>
  return (
    <span
      className={cn(
        'font-semibold tabular-nums',
        gpPercent > 0 ? 'text-emerald-700 dark:text-emerald-400' : gpPercent < 0 ? 'text-rose-700 dark:text-rose-400' : 'text-muted-foreground',
      )}
    >
      GP {gpPercent.toFixed(1)}%
    </span>
  )
}

/** One product: name and closing value, then quantity, unit rate and gross profit. The whole row opens details. */
export function StockRow({
  name,
  qty,
  uom,
  rate,
  value,
  gpPercent,
  hasSales,
  onOpen,
}: {
  name: string
  qty: number
  uom: string
  rate: number
  value: number
  gpPercent: number
  hasSales: boolean
  onOpen: () => void
}) {
  const negative = qty < 0
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="flex w-full min-h-16 items-center gap-2 px-4 py-2.5 text-left hover:bg-muted/40 active:bg-muted/60 cursor-pointer"
      >
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate text-[15px] font-semibold text-foreground">{name}</span>
            <span className={cn('shrink-0 text-[15px] font-bold tabular-nums', negative ? 'text-rose-700 dark:text-rose-400' : 'text-foreground')}>
              {formatCurrency(value)}
            </span>
          </span>
          <span className="mt-0.5 flex items-center justify-between gap-3 text-sm text-muted-foreground">
            <span className="flex min-w-0 items-center gap-1 truncate tabular-nums">
              {negative && <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-rose-600" aria-label="Negative stock" />}
              <span className={cn(negative && 'font-semibold text-rose-700 dark:text-rose-400')}>
                {formatQty(qty)} {uom}
              </span>
              {rate > 0 && <span className="truncate">· {formatCurrency(rate)}/{uom}</span>}
            </span>
            <GpLabel gpPercent={gpPercent} hasSales={hasSales} />
          </span>
        </span>
        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      </button>
    </li>
  )
}

/* ─── Filter & sort sheet ─── */

const STATUS_OPTIONS = [
  { value: 'All Items', label: 'All' },
  { value: 'In Stock', label: 'In stock' },
  { value: 'Out of Stock', label: 'Out of stock' },
  { value: 'Negative Stock', label: 'Negative' },
]
const MOVEMENT_OPTIONS = [
  { value: 'All Movement', label: 'All' },
  { value: 'With Movement', label: 'Moving' },
  { value: 'No Movement', label: 'No movement' },
]
const PROFIT_OPTIONS = [
  { value: 'All Profit', label: 'All' },
  { value: 'Profitable', label: 'Profitable' },
  { value: 'Non-Profitable', label: 'Not profitable' },
]
export const STOCK_SORT_FIELDS = [
  { key: 'name', label: 'Name' },
  { key: 'closing_balance', label: 'Closing quantity' },
  { key: 'closing_value', label: 'Closing value' },
  { key: 'gp_percent', label: 'Gross profit %' },
  { key: 'gp_value', label: 'Gross profit' },
  { key: 'closing_rate', label: 'Price per unit' },
  { key: 'inward_qty', label: 'Inward quantity' },
  { key: 'inward_value', label: 'Inward value' },
  { key: 'outward_qty', label: 'Outward quantity' },
  { key: 'outward_value', label: 'Outward value' },
  { key: 'cons_value', label: 'Consumption value' },
] as const
const COMMON_SORTS = 4

function ChoiceChips({
  name,
  label,
  options,
  value,
  onChange,
}: {
  name: string
  label: string
  options: { value: string; label: string }[]
  value: string
  onChange: (value: string) => void
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map(o => (
          <label key={o.value} className="cursor-pointer">
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              className="peer sr-only"
            />
            <span className="inline-flex h-11 items-center rounded-full border border-border px-4 text-sm font-semibold text-foreground transition-colors peer-checked:border-primary peer-checked:bg-primary peer-checked:text-primary-foreground peer-focus-visible:ring-2 peer-focus-visible:ring-primary/50">
              {o.label}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

export function StockFilterSheet({
  open,
  onOpenChange,
  stockStatus,
  onStockStatus,
  movement,
  onMovement,
  profit,
  onProfit,
  sortField,
  sortDir,
  onSort,
  withGst,
  onWithGst,
  resultCount,
  hasActive,
  onReset,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  stockStatus: string
  onStockStatus: (v: string) => void
  movement: string
  onMovement: (v: string) => void
  profit: string
  onProfit: (v: string) => void
  sortField: string
  sortDir: 'asc' | 'desc'
  onSort: (field: string, dir: 'asc' | 'desc') => void
  withGst: boolean
  onWithGst: (v: boolean) => void
  resultCount: number
  hasActive: boolean
  onReset: () => void
}) {
  const sortIndex = STOCK_SORT_FIELDS.findIndex(f => f.key === sortField)
  const [showAllSorts, setShowAllSorts] = useState(false)
  const sortFields = showAllSorts || sortIndex >= COMMON_SORTS ? STOCK_SORT_FIELDS : STOCK_SORT_FIELDS.slice(0, COMMON_SORTS)
  const isName = sortField === 'name'

  return (
    <BottomSheet
      open={open}
      onOpenChange={onOpenChange}
      title="Filter & sort"
      headerAction={
        hasActive ? (
          <button type="button" onClick={onReset} className="h-11 px-2 text-sm font-semibold text-primary cursor-pointer">
            Reset
          </button>
        ) : null
      }
      footer={
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          className="h-12 w-full rounded-xl bg-primary text-base font-bold text-primary-foreground cursor-pointer"
        >
          {resultCount === 1 ? 'Show 1 product' : `Show ${resultCount} products`}
        </button>
      }
    >
      <div className="space-y-5">
        <ChoiceChips name="stock-status" label="Stock" options={STATUS_OPTIONS} value={stockStatus} onChange={onStockStatus} />
        <ChoiceChips name="stock-movement" label="Movement" options={MOVEMENT_OPTIONS} value={movement} onChange={onMovement} />
        <ChoiceChips name="stock-profit" label="Profit" options={PROFIT_OPTIONS} value={profit} onChange={onProfit} />

        <fieldset className="space-y-1">
          <legend className="mb-1 text-xs font-bold uppercase tracking-wider text-muted-foreground">Sort by</legend>
          {sortFields.map(f => (
            <label key={f.key} className="flex min-h-12 cursor-pointer items-center gap-3 rounded-xl px-2 hover:bg-muted/50">
              <input
                type="radio"
                name="stock-sort"
                checked={sortField === f.key}
                onChange={() => onSort(f.key, f.key === 'name' ? 'asc' : 'desc')}
                className="h-5 w-5 accent-primary"
              />
              <span className="text-base text-foreground">{f.label}</span>
            </label>
          ))}
          {sortFields.length < STOCK_SORT_FIELDS.length && (
            <button
              type="button"
              onClick={() => setShowAllSorts(true)}
              className="flex min-h-11 items-center gap-1 px-2 text-sm font-semibold text-primary cursor-pointer"
            >
              More sort options <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
          <div className="mt-2 grid grid-cols-2 gap-1 rounded-xl bg-muted p-1" role="radiogroup" aria-label="Sort direction">
            {(['desc', 'asc'] as const).map(dir => (
              <button
                key={dir}
                type="button"
                role="radio"
                aria-checked={sortDir === dir}
                onClick={() => onSort(sortField, dir)}
                className={cn(
                  'h-10 rounded-lg text-sm font-semibold cursor-pointer',
                  sortDir === dir ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground',
                )}
              >
                {isName ? (dir === 'asc' ? 'A → Z' : 'Z → A') : dir === 'desc' ? 'High → low' : 'Low → high'}
              </button>
            ))}
          </div>
        </fieldset>

        <label className="flex min-h-12 cursor-pointer items-center justify-between gap-3 rounded-xl border border-border px-4">
          <span>
            <span className="block text-base font-semibold text-foreground">Prices include GST</span>
            <span className="block text-sm text-muted-foreground">Values and rates shown {withGst ? 'with' : 'without'} GST</span>
          </span>
          <Switch checked={withGst} onCheckedChange={onWithGst} aria-label="Prices include GST" />
        </label>
      </div>
    </BottomSheet>
  )
}

/* ─── Product detail sheet ─── */

interface ItemVoucher {
  stock_entry_id: number
  voucher_id: number
  voucher_date: string
  voucher_type: string
  voucher_number: string
  party_name?: string
  quantity: number
  amount: number
  gst_rate?: number
  is_inward: boolean
}

export interface StockSheetItem {
  itemId: number
  name: string
  group: string
  uom: string
  gstRate: number
  brand?: string
  subtitle?: string
  closingQty: number
  closingValue: number
  rate: number
  inwardQty: number
  inwardValue: number
  outwardQty: number
  outwardValue: number
  consValue: number
  gpValue: number
  gpPercent: number
}

function Metric({ label, primary, secondary, tone }: { label: string; primary: string; secondary?: string; tone?: 'in' | 'out' | 'gp' }) {
  return (
    <div className="min-w-0 p-3">
      <div className="text-xs font-semibold text-muted-foreground">{label}</div>
      <div
        className={cn(
          'mt-0.5 truncate text-base font-bold tabular-nums',
          tone === 'in' && 'text-emerald-700 dark:text-emerald-400',
          tone === 'out' && 'text-rose-700 dark:text-rose-400',
          !tone && 'text-foreground',
          tone === 'gp' && 'text-foreground',
        )}
      >
        {primary}
      </div>
      {secondary && <div className="truncate text-sm text-muted-foreground tabular-nums">{secondary}</div>}
    </div>
  )
}

export function StockItemSheet({
  item,
  open,
  onOpenChange,
  token,
  withGst,
  companyName,
  onSeeAll,
  onOpenVoucher,
}: {
  item: StockSheetItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
  token: string | null
  withGst: boolean
  companyName: string
  onSeeAll: () => void
  onOpenVoucher: (voucherId: number) => void
}) {
  const itemId = item?.itemId
  const [vouchers, setVouchers] = useState<{ itemId: number; rows: ItemVoucher[] } | null>(null)

  useEffect(() => {
    if (!open || !itemId || !token) return
    let cancelled = false
    fetch(`${API_BASE}/inventory/items/${itemId}/vouchers`, { headers: authHeaders(token) })
      .then(r => (r.ok ? r.json() : []))
      .then((data: ItemVoucher[]) => {
        if (cancelled) return
        const rows = (Array.isArray(data) ? data : [])
          .slice()
          .sort((a, b) => new Date(b.voucher_date).getTime() - new Date(a.voucher_date).getTime())
        setVouchers({ itemId, rows })
      })
      .catch(() => !cancelled && setVouchers({ itemId, rows: [] }))
    return () => {
      cancelled = true
    }
  }, [open, itemId, token])

  if (!item) return null
  const recent = vouchers?.itemId === item.itemId ? vouchers.rows : null
  const gstNote = withGst ? `incl. ${item.gstRate}% GST` : 'excl. GST'

  const share = async () => {
    const lines = [
      item.name,
      `In stock: ${formatQty(item.closingQty)} ${item.uom}`,
      item.rate > 0 ? `Rate: ${formatCurrency(item.rate)} per ${item.uom} (${gstNote})` : null,
      companyName ? `— ${companyName}` : null,
    ].filter(Boolean)
    try {
      const result = await shareText(item.name, lines.join('\n'))
      if (result === 'copied') toast.success('Product details copied. Paste them into a message.')
    } catch {
      toast.error('Could not share. Try again.')
    }
  }

  return (
    <BottomSheet
      open={open}
      onOpenChange={onOpenChange}
      title={item.name}
      description={[item.group, item.subtitle && item.subtitle !== item.name ? item.subtitle : null, `${item.gstRate}% GST`].filter(Boolean).join(' · ')}
      footer={
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onSeeAll}
            className="h-12 rounded-xl bg-primary text-base font-bold text-primary-foreground cursor-pointer"
          >
            All movement
          </button>
          <button
            type="button"
            onClick={share}
            className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-border text-base font-semibold text-foreground hover:bg-muted cursor-pointer"
          >
            <Share2 className="h-4 w-4" aria-hidden="true" /> Share
          </button>
        </div>
      }
    >
      <div className="space-y-5">
        <div className="flex items-end justify-between gap-3 rounded-2xl bg-muted/50 p-4">
          <div>
            <div className="text-xs font-semibold text-muted-foreground">Closing stock</div>
            <div className={cn('text-2xl font-bold tabular-nums', item.closingQty < 0 ? 'text-rose-700 dark:text-rose-400' : 'text-foreground')}>
              {formatQty(item.closingQty)} <span className="text-base font-semibold">{item.uom}</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xl font-bold tabular-nums text-foreground">{formatCurrency(item.closingValue)}</div>
            <div className="text-sm text-muted-foreground tabular-nums">
              {item.rate > 0 ? `${formatCurrency(item.rate)} per ${item.uom} · ` : ''}{gstNote}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 divide-x divide-border overflow-hidden rounded-2xl border border-border [&>*:nth-child(n+3)]:border-t [&>*:nth-child(n+3)]:border-border">
          <Metric label="Inward" primary={`${formatQty(item.inwardQty)} ${item.uom}`} secondary={formatCurrency(item.inwardValue)} tone="in" />
          <Metric label="Outward" primary={`${formatQty(item.outwardQty)} ${item.uom}`} secondary={formatCurrency(item.outwardValue)} tone="out" />
          <Metric label="Consumed (cost)" primary={formatCurrency(item.consValue)} />
          <Metric label="Gross profit" primary={formatCurrency(item.gpValue)} secondary={`${item.gpPercent.toFixed(1)}% of sales`} tone="gp" />
        </div>

        <section aria-labelledby="stock-sheet-recent">
          <h3 id="stock-sheet-recent" className="mb-1 text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Recent movement
          </h3>
          {recent === null ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Loading vouchers…
            </div>
          ) : recent.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">No vouchers for this product yet.</p>
          ) : (
            <ul className="divide-y divide-border">
              {recent.slice(0, 5).map(v => {
                const rate = Number(v.gst_rate) > 0 ? Number(v.gst_rate) : item.gstRate
                const amount = withGst ? Number(v.amount) * (1 + rate / 100) : Number(v.amount)
                return (
                  <li key={v.stock_entry_id}>
                    <button
                      type="button"
                      onClick={() => onOpenVoucher(v.voucher_id)}
                      className="flex w-full min-h-14 items-center gap-3 py-2 text-left hover:bg-muted/40 cursor-pointer"
                    >
                      <span className="w-14 shrink-0 text-sm font-semibold text-muted-foreground tabular-nums">
                        {new Date(v.voucher_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-foreground">{v.party_name || v.voucher_type}</span>
                        <span className="block truncate text-xs text-muted-foreground">{v.voucher_type} #{v.voucher_number}</span>
                      </span>
                      <span className="shrink-0 text-right tabular-nums">
                        <span className={cn('block text-sm font-bold', v.is_inward ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400')}>
                          {v.is_inward ? '+' : '−'}{formatQty(Number(v.quantity))} {item.uom}
                        </span>
                        <span className="block text-xs text-muted-foreground">{formatCurrency(amount)}</span>
                      </span>
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </div>
    </BottomSheet>
  )
}
