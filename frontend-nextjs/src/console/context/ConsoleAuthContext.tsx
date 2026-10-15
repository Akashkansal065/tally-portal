'use client'

/**
 * console/context/ConsoleAuthContext.tsx – Dedicated session provider for Platform Operators.
 *
 * Isolation guarantees:
 *   • Never reads customer token, localStorage, or customer company ID
 *   • Completely isolated from customer AuthContext
 *   • Uses HttpOnly cookies and Next.js /console-api rewrite
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { consoleApi, ConsoleApiError, OperatorProfile, LoginResult } from '../api'

interface ConsoleAuthContextType {
  operator: OperatorProfile | null
  isLoading: boolean
  isAuthenticated: boolean
  permissions: Set<string>
  hasPermission: (code: string) => boolean
  login: (email: string, password: string) => Promise<LoginResult>
  completePasskeyLogin: (mfaToken: string, assertion: Record<string, unknown>, challengeToken: string) => Promise<void>
  logout: () => Promise<void>
  logoutAll: () => Promise<void>
  refreshProfile: () => Promise<void>
}

const ConsoleAuthContext = createContext<ConsoleAuthContextType | undefined>(undefined)

export function ConsoleAuthProvider({ children }: { children: React.ReactNode }) {
  const [operator, setOperator] = useState<OperatorProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  const refreshProfile = useCallback(async () => {
    try {
      const profile = await consoleApi.me()
      setOperator(profile)
    } catch (err: unknown) {
      if (err instanceof ConsoleApiError && err.status === 401) {
        // Attempt token rotation / refresh
        try {
          await consoleApi.refresh()
          const retryProfile = await consoleApi.me()
          setOperator(retryProfile)
          return
        } catch {
          setOperator(null)
        }
      } else {
        setOperator(null)
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    const checkSession = async () => {
      try {
        const profile = await consoleApi.me()
        if (active) setOperator(profile)
      } catch (err: unknown) {
        if (err instanceof ConsoleApiError && err.status === 401) {
          try {
            await consoleApi.refresh()
            const retryProfile = await consoleApi.me()
            if (active) setOperator(retryProfile)
            return
          } catch {
            if (active) setOperator(null)
          }
        } else {
          if (active) setOperator(null)
        }
      } finally {
        if (active) setIsLoading(false)
      }
    }
    checkSession()
    return () => {
      active = false
    }
  }, [])

  // Route protection
  useEffect(() => {
    if (isLoading) return

    const isLoginPage = pathname === '/console/login'
    if (!operator && !isLoginPage) {
      router.replace('/console/login')
    } else if (operator && isLoginPage) {
      router.replace('/console')
    }
  }, [operator, isLoading, pathname, router])

  const login = async (email: string, password: string): Promise<LoginResult> => {
    const res = await consoleApi.login(email, password)
    if (!res.passkey_required) {
      await refreshProfile()
    }
    return res
  }

  const completePasskeyLogin = async (
    mfaToken: string,
    assertion: Record<string, unknown>,
    challengeToken: string
  ): Promise<void> => {
    await consoleApi.passkeyLoginVerify(mfaToken, assertion, challengeToken)
    await refreshProfile()
  }

  const logout = async (): Promise<void> => {
    try {
      await consoleApi.logout()
    } catch {
      // Ignore network errors on logout
    }
    setOperator(null)
    router.replace('/console/login')
  }

  const logoutAll = async (): Promise<void> => {
    try {
      await consoleApi.logoutAll()
    } catch {
      // Ignore
    }
    setOperator(null)
    router.replace('/console/login')
  }

  const permissions = React.useMemo(() => {
    return new Set(operator?.permissions || [])
  }, [operator])

  const hasPermission = useCallback(
    (code: string): boolean => {
      return permissions.has(code)
    },
    [permissions]
  )

  return (
    <ConsoleAuthContext.Provider
      value={{
        operator,
        isLoading,
        isAuthenticated: !!operator,
        permissions,
        hasPermission,
        login,
        completePasskeyLogin,
        logout,
        logoutAll,
        refreshProfile,
      }}
    >
      {children}
    </ConsoleAuthContext.Provider>
  )
}

export function useConsoleAuth() {
  const context = useContext(ConsoleAuthContext)
  if (!context) {
    throw new Error('useConsoleAuth must be used within a ConsoleAuthProvider')
  }
  return context
}
