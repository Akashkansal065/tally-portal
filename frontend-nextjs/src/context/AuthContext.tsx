'use client'

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { toast } from 'sonner'
import { API_BASE, authHeaders } from '@/lib/utils'
import { noteCompanySwitch, setCurrentCompany } from '@/lib/current-company'
import { signOutMessage } from '@/lib/device'
import { stopHeadlessNativeTracking } from '@/lib/capacitor-native-tracking'

// ─── Session-ended handling ──────────────────────────────────────────────────
// Most screens call fetch() directly, so one wrapper around window.fetch notices when the server
// rejects the current token (signed out by an admin, device blocked, password changed, ...) and
// signs the user out with an explanation. Only 401s for requests that carried the current token
// count; network errors and 403 permission errors never sign anyone out.
let activeToken = ''
// The company this device is working in. Sent on every API request so the server never has to assume one.
let activeCompanyId: number | null = null
// The company is chosen per device: picking one on a phone must not move a laptop, or the sync agent
const COMPANY_KEY = 'mytally_company_id'

function rememberedCompanyId(): number | null {
  try {
    const stored = Number(localStorage.getItem(COMPANY_KEY))
    return Number.isInteger(stored) && stored > 0 ? stored : null
  } catch {
    return null
  }
}

function rememberCompany(companyId: number) {
  activeCompanyId = companyId
  try { localStorage.setItem(COMPANY_KEY, String(companyId)) } catch { /* private mode: lasts for this page only */ }
}
let onSessionEnded: ((reason: string | null) => void) | null = null
let fetchPatched = false

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return input.url
}

function requestAuthorization(input: RequestInfo | URL, init?: RequestInit): string | null {
  const headers = init?.headers ?? (input instanceof Request ? input.headers : undefined)
  if (!headers) return null
  if (headers instanceof Headers) return headers.get('Authorization')
  if (Array.isArray(headers)) return headers.find(([k]) => k.toLowerCase() === 'authorization')?.[1] ?? null
  const record = headers as Record<string, string>
  return record.Authorization ?? record.authorization ?? null
}

// ─── Write-once requests ─────────────────────────────────────────────────────
// Every write to the API carries an Idempotency-Key, and the server carries out a key only once. The
// same write sent again within a few seconds (a double tap, a retry after a dropped connection) reuses
// the key, so it returns the first result instead of creating a second record.
const WRITE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])
const SAME_WRITE_WINDOW_MS = 3000
const recentWrites = new Map<string, { key: string; at: number }>()

function withIdempotencyKey(input: RequestInfo | URL, init?: RequestInit): RequestInit | undefined {
  const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
  if (!WRITE_METHODS.has(method) || !requestUrl(input).startsWith(API_BASE)) return init
  // Only plain (JSON or empty) bodies can be compared; uploads go through untouched
  const body = init?.body
  if (body != null && typeof body !== 'string') return init
  const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
  if (headers.has('Idempotency-Key')) return init

  const now = Date.now()
  for (const [signature, entry] of recentWrites) {
    if (now - entry.at > SAME_WRITE_WINDOW_MS) recentWrites.delete(signature)
  }
  const signature = `${method} ${requestUrl(input)} ${body ?? ''}`
  let entry = recentWrites.get(signature)
  if (!entry) {
    entry = { key: `${now.toString(36)}-${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`, at: now }
    recentWrites.set(signature, entry)
  }
  headers.set('Idempotency-Key', entry.key)
  return { ...init, headers }
}

function withCompanyHeader(input: RequestInfo | URL, init?: RequestInit): RequestInit | undefined {
  if (activeCompanyId == null) activeCompanyId = rememberedCompanyId()
  if (activeCompanyId == null || !activeToken) return init
  const url = requestUrl(input)
  if (!url.startsWith(API_BASE) || url.includes('/auth/login')) return init
  if (requestAuthorization(input, init) !== `Bearer ${activeToken}`) return init
  const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
  if (headers.has('X-Company-ID')) return init
  headers.set('X-Company-ID', String(activeCompanyId))
  return { ...init, headers }
}

function installSessionEndedInterceptor() {
  if (fetchPatched || typeof window === 'undefined') return
  fetchPatched = true
  const originalFetch = window.fetch.bind(window)
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    init = withIdempotencyKey(input, init)
    init = withCompanyHeader(input, init)
    const response = await originalFetch(input, init)
    if (response.status === 401 && activeToken && onSessionEnded) {
      const url = requestUrl(input)
      if (url.startsWith(API_BASE) && !url.includes('/auth/login') && requestAuthorization(input, init) === `Bearer ${activeToken}`) {
        onSessionEnded(response.headers.get('X-Auth-Reason'))
      }
    }
    return response
  }
}

/** Remove everything that belongs to the signed-in session on this device. */
function clearLocalSession() {
  activeToken = ''
  activeCompanyId = null
  localStorage.removeItem(COMPANY_KEY)
  localStorage.removeItem('mytally_token')
  localStorage.removeItem('mytally_email')
  // Don't let the next person on a shared phone inherit an "active shift"
  localStorage.removeItem('mytally_shift_active')
  stopHeadlessNativeTracking().catch(() => {})
}

export interface UserPermissions {
  showLedger: boolean
  showSalesLedgers: boolean
  showPurchaseLedgers: boolean
  showVouchers: boolean
  showReceipts: boolean
  showPayments: boolean
  showExpenses: boolean
  showAttendance: boolean
  showStocks: boolean
  showReports: boolean
  showOrders: boolean
  showCheckIn: boolean
  showGst: boolean
  showCustomers: boolean
  ledgerScope: 'all' | 'dr_only' | 'restricted'
  stockScope: 'full' | 'restricted' | 'catalog_only'
  voucherActionScope: 'view_only' | 'can_create' | 'full'
  allowedVoucherTypeIds: number[] | null
  isAdmin: boolean
}

export interface ModuleCapability {
  can_create: boolean
  can_read: boolean
  can_update: boolean
  can_delete: boolean
}

export interface CompanyInfo {
  company_id: number
  name: string
  gstin?: string | null
  pan?: string | null
  address_line1?: string | null
  address_line2?: string | null
  city?: string | null
  state?: string | null
  pincode?: string | null
  country?: string | null
  telephone?: string | null
  mobile?: string | null
  email?: string | null
  website?: string | null
  financial_year_start?: string | null
  books_begin_date?: string | null
}

export interface AuthUser {
  id: number
  user_id?: number
  email: string
  username: string
  role: string
  company_id: number
  company_name?: string
  company?: CompanyInfo
  allowedCompanies: CompanyInfo[]
  permissions: UserPermissions
  capabilities?: Record<string, ModuleCapability>
  /** The business has no Tally PC yet and this person can connect one: they are held at Connect Tally. */
  needs_tally_setup?: boolean
}

interface AuthContextValue {
  user: AuthUser | null
  token: string
  isLoading: boolean
  login: (token: string, email: string) => Promise<void>
  logout: () => void
  /** Switch this device to another company. With `to`, open that path there instead of the home screen. */
  switchCompany: (company_id: number, to?: string) => Promise<void>
  permissions: UserPermissions
  can: (module: string, action: 'create' | 'read' | 'update' | 'delete') => boolean
}

const DEFAULT_PERMISSIONS: UserPermissions = {
  showLedger: false,
  showSalesLedgers: false,
  showPurchaseLedgers: false,
  showVouchers: false,
  showReceipts: false,
  showPayments: false,
  showExpenses: false,
  showAttendance: false,
  showStocks: false,
  showReports: false,
  showOrders: false,
  showCheckIn: false,
  showGst: false,
  showCustomers: false,
  ledgerScope: 'dr_only',
  stockScope: 'catalog_only',
  voucherActionScope: 'view_only',
  allowedVoucherTypeIds: null,
  isAdmin: false,
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: '',
  isLoading: true,
  login: async () => { },
  logout: () => { },
  switchCompany: async () => { },
  permissions: DEFAULT_PERMISSIONS,
  can: () => false,
})

/** Provide authenticated user state, company switching, and permission checks. */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)

  const fetchMe = useCallback(async (tok: string) => {
    try {
      // Name this device's company here rather than rely on the request interceptor: this is the first request
      // of a page load, and the answer decides which company the device stays in.
      const deviceCompanyId = activeCompanyId ?? rememberedCompanyId()
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { ...authHeaders(tok), ...(deviceCompanyId ? { 'X-Company-ID': String(deviceCompanyId) } : {}) },
        cache: 'no-store',
      })
      const contentType = res.headers.get('content-type') || ''
      if (!res.ok) {
        let errorDetail = `HTTP ${res.status} (${res.statusText || 'Error'})`
        try {
          if (contentType.includes('application/json')) {
            const errJson = await res.json()
            errorDetail = errJson.detail || errJson.message || errorDetail
          } else {
            const errText = await res.text()
            if (errText) errorDetail = errText.slice(0, 200)
          }
        } catch {}
        if (res.status === 401 || res.status === 403) {
          console.warn(`[AuthContext] Session invalid or expired (${res.status}):`, errorDetail)
        } else {
          console.error(`[AuthContext] /auth/me failed with status ${res.status}:`, errorDetail)
        }
        const errorObj = new Error(errorDetail) as Error & { status?: number }
        errorObj.status = res.status
        throw errorObj
      }
      if (!contentType.includes('application/json')) {
        throw new Error(`Invalid response format from server (${contentType || 'empty'})`)
      }
      const data = await res.json()
      // The server answers with the company this device asked for when it may open it, else the person's own
      if (typeof data.company_id === 'number') rememberCompany(data.company_id)

      let allowedCompanies = []
      try {
        const compRes = await fetch(`${API_BASE}/auth/me/companies`, {
          headers: authHeaders(tok),
          cache: 'no-store',
        })
        const compContentType = compRes.headers.get('content-type') || ''
        if (compRes.ok && compContentType.includes('application/json')) {
          allowedCompanies = await compRes.json()
        }
      } catch (e) { }

      const isAdmin = data.isAdmin ?? (
        typeof data.role === 'string' && ['admin', 'superadmin', 'owner'].includes(data.role.toLowerCase())
      )
      const here = (allowedCompanies as { company_id: number; name: string }[]).find(c => c.company_id === data.company_id)
      setCurrentCompany(here?.name ?? '', allowedCompanies.length, data.company_id)
      setUser({
        ...data,
        id: data.user_id ?? data.id,
        user_id: data.user_id ?? data.id,
        allowedCompanies,
        capabilities: data.capabilities || {},
        // Someone who signed up with a mobile number may have no email: show the name they gave
        username: data.email ? data.email.split('@')[0] : (data.username || 'User'),
        permissions: {
          showLedger: data.showLedger ?? Boolean(data.capabilities?.ledgers?.can_read),
          showSalesLedgers: data.showSalesLedgers ?? Boolean(data.capabilities?.ledger_customer?.can_read),
          showPurchaseLedgers: data.showPurchaseLedgers ?? Boolean(data.capabilities?.ledger_supplier?.can_read),
          showVouchers: data.showVouchers ?? Boolean(data.capabilities?.vouchers?.can_read),
          showReceipts: data.showReceipts ?? Boolean(data.capabilities?.vouchers?.can_read),
          showPayments: data.showPayments ?? Boolean(data.capabilities?.payments?.can_read),
          showExpenses: data.showExpenses ?? Boolean(data.capabilities?.expenses?.can_read),
          showAttendance: data.showAttendance ?? Boolean(data.capabilities?.attendance?.can_read),
          showStocks: data.showStocks ?? Boolean(data.capabilities?.inventory?.can_read),
          showReports: data.showReports ?? Boolean(data.capabilities?.reports?.can_read),
          showOrders: data.showOrders ?? Boolean(data.capabilities?.orders?.can_read),
          showCheckIn: data.showCheckIn ?? Boolean(data.capabilities?.visits?.can_read),
          showGst: data.showGst ?? Boolean(data.capabilities?.gst?.can_read),
          showCustomers: data.showCustomers ?? Boolean(data.capabilities?.customers?.can_read),
          ledgerScope: data.ledgerScope ?? 'all',
          stockScope: data.stockScope ?? 'full',
          voucherActionScope: data.voucherActionScope ?? 'view_only',
          allowedVoucherTypeIds: data.allowedVoucherTypeIds ?? null,
          isAdmin,
        },
      })
    } catch (err: any) {
      // Only clear storage and state if it is an actual authentication error (HTTP 401 / 403 or invalid credentials),
      // NEVER clear the token on transient network errors (like TypeError: Failed to fetch)
      const isAuthError =
        err?.status === 401 ||
        err?.status === 403 ||
        err?.message?.toLowerCase().includes('unauthorized') ||
        err?.message?.toLowerCase().includes('session expired') ||
        err?.message?.toLowerCase().includes('could not validate credentials')

      if (isAuthError) {
        // Graceful session expiry: clear stale token without triggering dev error overlay
        if (typeof window !== 'undefined' && localStorage.getItem('mytally_token') === tok) {
          setUser(null)
          setToken('')
          clearLocalSession()
        }
        return
      }

      console.error('[AuthContext] Failed to load session user profile:', err)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    // Before the first request: every call after this one carries the device's company
    installSessionEndedInterceptor()
    const saved = localStorage.getItem('mytally_token')
    if (saved) {
      activeToken = saved
      setToken(saved)
      fetchMe(saved).catch(() => {})
    } else {
      setIsLoading(false)
    }
  }, [fetchMe])

  // Keep the interceptor pointed at the current token and handler
  useEffect(() => {
    // Signing out clears activeToken itself; an empty token here is only the first render, before the saved
    // one is read, and must not blank the token the effect above has just set
    if (token) activeToken = token
  }, [token])

  useEffect(() => {
    installSessionEndedInterceptor()
    onSessionEnded = (reason) => {
      if (!activeToken) return
      clearLocalSession()
      setUser(null)
      setToken('')
      toast.error(signOutMessage(reason), { id: 'session-ended', duration: 8000 })
    }
    return () => {
      onSessionEnded = null
    }
  }, [])

  const login = async (tok: string, email: string) => {
    setIsLoading(true)
    setToken(tok)
    activeToken = tok
    localStorage.setItem('mytally_token', tok)
    localStorage.setItem('mytally_email', email)
    await fetchMe(tok)
  }

  const logout = () => {
    const tok = token
    // Stop the interceptor reacting to this request, then end the session on the server too
    // (keepalive lets it finish while the page navigates away). Without this the token stayed
    // valid on the server for 30 days after "logging out".
    clearLocalSession()
    if (tok) {
      fetch(`${API_BASE}/auth/logout`, { method: 'POST', headers: authHeaders(tok), keepalive: true }).catch(() => {})
    }
    setUser(null)
    setToken('')
  }

  const switchCompany = async (company_id: number, to?: string) => {
    if (!token || !user || company_id === user.company_id) return
    if (!user.allowedCompanies?.some(c => c.company_id === company_id)) return
    // A form open in a dialog belongs to the company being left: never carry it across
    if (document.querySelector('[role="dialog"] form, [data-unsaved="true"]')
      && !window.confirm('You have a form open. Switch company and discard what you entered?')) return
    rememberCompany(company_id)
    noteCompanySwitch(user.allowedCompanies.find(c => c.company_id === company_id)?.name ?? '', Boolean(to))
    // Start again with nothing of the previous company left in memory: at the home screen, or at the page a
    // link or notification was for. The server checks the company against what this person may open on every request.
    window.location.assign(to && to.startsWith('/') ? to : '/')
  }

  const SUB_MODULE_PARENT_MAP: Record<string, string> = {
    ledger_groups: 'ledgers',
    cost_categories: 'ledgers',
    cost_centres: 'ledgers',
    cost_centre_classes: 'ledgers',
    currencies: 'settings',
    voucher_types: 'settings',
    stock_groups: 'inventory',
    stock_categories: 'inventory',
    stock_items: 'inventory',
    units: 'inventory',
    godowns: 'inventory',
    price_lists: 'inventory',
    bom: 'inventory',
  }

  const can = useCallback((module: string, action: 'create' | 'read' | 'update' | 'delete'): boolean => {
    if (!user) return false
    // Zero admin bypass: evaluate capabilities directly with hierarchical parent fallback
    let cap = user.capabilities?.[module]
    if (!cap && SUB_MODULE_PARENT_MAP[module]) {
      cap = user.capabilities?.[SUB_MODULE_PARENT_MAP[module]]
    }
    if (!cap) return false
    const field = `can_${action}` as keyof typeof cap
    return Boolean(cap[field])
  }, [user])

  const permissions = user?.permissions ?? DEFAULT_PERMISSIONS

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout, permissions, switchCompany, can }}>
      {children}
    </AuthContext.Provider>
  )
}

/** Read the current authentication state from the nearest AuthProvider. */
export function useAuth() {
  return useContext(AuthContext)
}
