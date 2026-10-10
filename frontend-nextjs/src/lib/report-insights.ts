import { API_BASE, authHeaders } from '@/lib/utils'

/* Goal-tracking reports: monthly sales target, customers buying less, items about to run out. */

export interface SalesTarget {
  month: string
  as_of: string
  target: number
  sales: number
  achieved_pct: number | null
  remaining: number
  days_in_month: number
  days_elapsed: number
  days_left: number
  needed_per_day: number
  projected: number
  on_track: boolean | null
  daily: { date: string; sales: number; cumulative: number; target_cumulative: number }[]
}

export interface ReportSettings {
  monthly_sales_target: number
  default_credit_days: number
}

export interface WatchlistCustomer {
  ledger_id: number
  name: string
  phone: string | null
  city: string | null
  pincode: string | null
  recent_sales: number
  previous_sales: number
  change_pct: number | null
  last_invoice: string
  days_since_last: number
  usual_gap_days: number | null
  invoices: number
  reasons: ('dropped' | 'late')[]
  lost: number
  outstanding: number
  overdue: number
}

export interface WatchlistCriteria {
  drop_pct: number
  gap_multiplier: number
  window_days: number
  min_gap_days: number
}

export interface ReorderItem {
  stock_item_id: number
  name: string
  group: string | null
  unit: string
  stock: number
  sold_recently: number
  per_day: number
  days_left: number
  out_of_stock: boolean
  suggested_order: number
}

async function get<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers: authHeaders(token) })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {}
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const query = (params: object) =>
  new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()

export const getSalesTarget = (token: string) => get<SalesTarget>(token, '/reports/sales-target')
export const getReportSettings = (token: string) => get<ReportSettings>(token, '/reports/settings')
export const updateReportSettings = (token: string, changes: Partial<ReportSettings>) =>
  get<ReportSettings>(token, '/reports/settings', { method: 'PUT', body: JSON.stringify(changes) })
export const getWatchlist = (token: string, criteria: WatchlistCriteria) =>
  get<{ as_of: string; checked: number; customers: WatchlistCustomer[] }>(token, `/reports/customer-watchlist?${query(criteria)}`)
export const getReorderAlerts = (token: string, coverDays: number, lookbackDays = 30) =>
  get<{ as_of: string; items: ReorderItem[] }>(token, `/reports/reorder-alerts?${query({ cover_days: coverDays, lookback_days: lookbackDays })}`)

/** ₹6,42,300 */
export const rupees = (n: number) => `₹${Math.round(n).toLocaleString('en-IN')}`

/** ₹17.8 L / ₹1.2 Cr / ₹65.5k, for tight spaces */
export function rupeesShort(n: number): string {
  const abs = Math.abs(n)
  const sign = n < 0 ? '−' : ''
  if (abs >= 1e7) return `${sign}₹${(abs / 1e7).toFixed(abs >= 1e8 ? 0 : 1)} Cr`
  if (abs >= 1e5) return `${sign}₹${(abs / 1e5).toFixed(abs >= 1e6 ? 1 : 2).replace(/\.?0+$/, '')} L`
  if (abs >= 1e3) return `${sign}₹${(abs / 1e3).toFixed(1).replace(/\.0$/, '')}k`
  return `${sign}₹${Math.round(abs)}`
}

/** Remembered per viewer (thresholds, chosen views). Never throws: private mode or blocked storage just forgets. */
export function remembered<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`mytally_${key}`)
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback
  } catch {
    return fallback
  }
}

export function remember(key: string, value: unknown) {
  try {
    localStorage.setItem(`mytally_${key}`, JSON.stringify(value))
  } catch {}
}

// ─── Release 2: cities, collections, dead stock ──────────────────────────────

export interface CityRow {
  city: string
  customers: number
  leads: number
  buying: number
  not_buying: number
  buying_pct: number
  sales: number
  sales_previous: number
  change_pct: number | null
  share_pct: number
  invoices: number
  average_invoice: number | null
  sales_per_buying_customer: number | null
  outstanding: number
  overdue: number
}

export interface CityReport {
  month: string
  period: { from: string; to: string }
  compared_with: { from: string; to: string }
  total_sales: number
  cash_sales: number
  cities: CityRow[]
}

export interface CityMapping {
  pincodes: { pincode: string; customers: number; city: string | null; source: 'set' | 'proposed' | null }[]
  customers_without_city: { ledger_id: number; company: string; name: string; pincode: string | null; address: string | null }[]
}

export interface ChaseCustomer {
  ledger_id: number
  name: string
  phone: string | null
  overdue: number
  outstanding: number
  average_days_late: number
  oldest_days_late: number
  overdue_bills: number
  credit_days: number
  priority: number
}

export interface Collections {
  as_of: string
  receivables: number
  overdue: number
  overdue_customers: number
  dso: number | null
  dso_last_month_end: number | null
  dso_trend: { day: string; dso: number | null }[]
  overdue_trend: { day: string; overdue: number | null; receivables: number | null }[]
  chase: ChaseCustomer[]
}

export interface DeadStockItem {
  stock_item_id: number
  name: string
  group: string | null
  unit: string
  stock: number
  value: number
  band: string
  last_sold: string | null
  days_since_sale: number | null
  in_stock_since: string | null
  buyers: { ledger_id: number; name: string; phone: string | null; quantity: number; last_bought: string | null }[]
}

export interface DeadStock {
  as_of: string
  days: number
  total_value: number
  count: number
  bands: { band: string; value: number; count: number }[]
  items: DeadStockItem[]
  trend: { day: string; value: number | null; count: number | null }[]
  trend_days: number
}

export const getCityReport = (token: string) => get<CityReport>(token, '/reports/cities')
export const getCityMapping = (token: string) => get<CityMapping>(token, '/reports/city-mapping')
export const setPincodeCity = (token: string, pincode: string, city: string | null) =>
  get<{ pincode: string; city: string | null }>(token, `/reports/city-mapping/${pincode}`, { method: 'PUT', body: JSON.stringify({ city }) })
export const setCustomerCity = (token: string, ledgerId: number, city: string | null) =>
  get<{ ledger_id: number; city: string | null }>(token, `/reports/customer-city/${ledgerId}`, { method: 'PUT', body: JSON.stringify({ city }) })
export const getCollections = (token: string) => get<Collections>(token, '/reports/collections')
export const getDeadStock = (token: string, days: number) => get<DeadStock>(token, `/reports/dead-stock?days=${days}`)

/** wa.me needs the country code; Indian mobiles are often stored as 10 digits. */
export function whatsappLink(phone: string, text?: string) {
  const digits = phone.replace(/\D/g, '')
  const number = digits.length === 10 ? `91${digits}` : digits
  return `https://wa.me/${number}${text ? `?text=${encodeURIComponent(text)}` : ''}`
}
