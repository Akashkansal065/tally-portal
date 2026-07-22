'use client'

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { API_BASE, authHeaders } from '@/lib/utils'

export interface UserPermissions {
  showLedger: boolean
  showSalesLedgers: boolean
  showPurchaseLedgers: boolean
  showReceipts: boolean
  showPayments: boolean
  showExpenses: boolean
  showAttendance: boolean
  showStocks: boolean
  showReports: boolean
  showOrders: boolean
  showCheckIn: boolean
  showGst: boolean
  ledgerScope: 'all' | 'dr_only' | 'restricted'
  stockScope: 'full' | 'restricted'
  isAdmin: boolean
}

export interface AuthUser {
  id: number
  email: string
  username: string
  role: string
  company_id: number
  allowedCompanies: { company_id: number, name: string }[]
  permissions: UserPermissions
}

interface AuthContextValue {
  user: AuthUser | null
  token: string
  isLoading: boolean
  login: (token: string, email: string) => Promise<void>
  logout: () => void
  switchCompany: (company_id: number) => Promise<void>
  permissions: UserPermissions
}

const DEFAULT_PERMISSIONS: UserPermissions = {
  showLedger: true,
  showSalesLedgers: true,
  showPurchaseLedgers: false,
  showReceipts: true,
  showPayments: true,
  showExpenses: false,
  showAttendance: true,
  showStocks: true,
  showReports: false,
  showOrders: false,
  showCheckIn: true,
  showGst: false,
  ledgerScope: 'dr_only',
  stockScope: 'full',
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
        username: data.email?.split('@')[0] ?? data.email ?? 'User',
        permissions: {
          showLedger: isAdmin ? true : (data.showLedger ?? true),
          showSalesLedgers: isAdmin ? true : (data.showSalesLedgers ?? true),
          showPurchaseLedgers: isAdmin ? true : (data.showPurchaseLedgers ?? false),
          showReceipts: isAdmin ? true : (data.showReceipts ?? true),
          showPayments: isAdmin ? true : (data.showPayments ?? true),
          showExpenses: isAdmin ? true : (data.showExpenses ?? false),
          showAttendance: isAdmin ? true : (data.showAttendance ?? true),
          showStocks: isAdmin ? true : (data.showStocks ?? true),
          showReports: isAdmin ? true : (data.showReports ?? false),
          showOrders: isAdmin ? true : (data.showOrders ?? false),
          showCheckIn: isAdmin ? true : (data.showCheckIn ?? true),
          showGst: isAdmin ? true : (data.showGst ?? false),
          ledgerScope: isAdmin ? 'all' : (data.ledgerScope ?? 'dr_only'),
          stockScope: isAdmin ? 'full' : (data.stockScope ?? 'full'),
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
      const err = await res.json()
      alert(err.detail || "Failed to switch company")
    }
  }

  const permissions = user?.permissions ?? DEFAULT_PERMISSIONS

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout, permissions, switchCompany }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
