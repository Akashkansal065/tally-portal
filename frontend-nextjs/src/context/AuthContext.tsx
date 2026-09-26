'use client'

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { API_BASE, authHeaders } from '@/lib/utils'

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
  email: string
  username: string
  role: string
  company_id: number
  company_name?: string
  company?: CompanyInfo
  allowedCompanies: CompanyInfo[]
  permissions: UserPermissions
  capabilities?: Record<string, ModuleCapability>
}

interface AuthContextValue {
  user: AuthUser | null
  token: string
  isLoading: boolean
  login: (token: string, email: string) => Promise<void>
  logout: () => void
  switchCompany: (company_id: number) => Promise<void>
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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)

  const fetchMe = useCallback(async (tok: string) => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: authHeaders(tok),
      })
      if (!res.ok) throw new Error('Unauthorized')
      const data = await res.json()

      let allowedCompanies = []
      try {
        const compRes = await fetch(`${API_BASE}/auth/me/companies`, {
          headers: authHeaders(tok),
        })
        if (compRes.ok) allowedCompanies = await compRes.json()
      } catch (e) { }

      const isAdmin = data.isAdmin ?? (
        typeof data.role === 'string' && ['admin', 'superadmin', 'owner'].includes(data.role.toLowerCase())
      )
      setUser({
        ...data,
        allowedCompanies,
        capabilities: data.capabilities || {},
        username: data.email?.split('@')[0] ?? data.email ?? 'User',
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
    } catch {
      setUser(null)
      setToken('')
      localStorage.removeItem('mytally_token')
      localStorage.removeItem('mytally_email')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const saved = localStorage.getItem('mytally_token')
    if (saved) {
      setToken(saved)
      fetchMe(saved)
    } else {
      setIsLoading(false)
    }
  }, [fetchMe])

  const login = async (tok: string, email: string) => {
    setToken(tok)
    localStorage.setItem('mytally_token', tok)
    localStorage.setItem('mytally_email', email)
    await fetchMe(tok)
  }

  const logout = () => {
    setUser(null)
    setToken('')
    localStorage.removeItem('mytally_token')
    localStorage.removeItem('mytally_email')
  }

  const switchCompany = async (company_id: number) => {
    if (!token) return
    const res = await fetch(`${API_BASE}/auth/me/active-company`, {
      method: 'PUT',
      headers: authHeaders(token),
      body: JSON.stringify({ company_id })
    })
    if (res.ok) {
      await fetchMe(token)
    } else {
      let msg = "Failed to switch company"
      try {
        const err = await res.json()
        if (typeof err.detail === 'string') msg = err.detail
        else if (Array.isArray(err.detail)) msg = err.detail.map((e: any) => e.msg).join(', ')
      } catch (e) {}
      alert(msg)
    }
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

export function useAuth() {
  return useContext(AuthContext)
}
