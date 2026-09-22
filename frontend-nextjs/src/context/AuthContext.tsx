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
  showLedger: true,
  showSalesLedgers: true,
  showPurchaseLedgers: false,
  showVouchers: true,
  showReceipts: true,
  showPayments: true,
  showExpenses: false,
  showAttendance: true,
  showStocks: true,
  showReports: false,
  showOrders: false,
  showCheckIn: true,
  showGst: false,
  showCustomers: true,
  ledgerScope: 'dr_only',
  stockScope: 'full',
  voucherActionScope: 'full',
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

      const isAdmin = data.role === 'admin' || data.role === 'Admin'
      setUser({
        ...data,
        allowedCompanies,
        capabilities: data.capabilities || {},
        username: data.email?.split('@')[0] ?? data.email ?? 'User',
        permissions: {
          showLedger: isAdmin ? true : (data.showLedger ?? true),
          showSalesLedgers: isAdmin ? true : (data.showSalesLedgers ?? true),
          showPurchaseLedgers: isAdmin ? true : (data.showPurchaseLedgers ?? false),
          showVouchers: isAdmin ? true : (data.showVouchers ?? data.showReceipts ?? true),
          showReceipts: isAdmin ? true : (data.showReceipts ?? true),
          showPayments: isAdmin ? true : (data.showPayments ?? true),
          showExpenses: isAdmin ? true : (data.showExpenses ?? false),
          showAttendance: isAdmin ? true : (data.showAttendance ?? true),
          showStocks: isAdmin ? true : (data.showStocks ?? true),
          showReports: isAdmin ? true : (data.showReports ?? false),
          showOrders: isAdmin ? true : (data.showOrders ?? false),
          showCheckIn: isAdmin ? true : (data.showCheckIn ?? true),
          showGst: isAdmin ? true : (data.showGst ?? false),
          showCustomers: isAdmin ? true : (data.showCustomers ?? true),
          ledgerScope: isAdmin ? 'all' : (data.ledgerScope ?? 'dr_only'),
          stockScope: isAdmin ? 'full' : (data.stockScope ?? 'full'),
          voucherActionScope: isAdmin ? 'full' : (data.voucherActionScope ?? 'full'),
          allowedVoucherTypeIds: isAdmin ? null : (data.allowedVoucherTypeIds ?? null),
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

  const can = useCallback((module: string, action: 'create' | 'read' | 'update' | 'delete'): boolean => {
    if (!user) return false
    if (user.permissions?.isAdmin) return true
    const cap = user.capabilities?.[module]
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
