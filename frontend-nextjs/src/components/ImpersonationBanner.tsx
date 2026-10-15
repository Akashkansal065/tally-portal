'use client'

import React, { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { ShieldAlert, LogOut, Clock } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

interface ImpersonationClaims {
  sub: string
  is_impersonation?: boolean
  impersonated_by_admin_id?: number
  impersonator_email?: string
  impersonation_session_id?: number
  is_write?: boolean
  exp?: number
}

function parseJwt(token: string): ImpersonationClaims | null {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const base64Url = parts[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

export function ImpersonationBanner() {
  const pathname = usePathname()
  const router = useRouter()
  const { token, user, logout } = useAuth()
  const [claims, setClaims] = useState<ImpersonationClaims | null>(null)
  const [terminating, setTerminating] = useState(false)
  const [timeLeft, setTimeLeft] = useState<string>('')

  // Hide inside console pages
  const isConsole = pathname?.startsWith('/console')

  useEffect(() => {
    if (isConsole) {
      queueMicrotask(() => setClaims(null))
      return
    }

    const tok = token || (typeof window !== 'undefined' ? localStorage.getItem('mytally_token') : '')
    if (!tok) {
      queueMicrotask(() => setClaims(null))
      return
    }

    const decoded = parseJwt(tok)
    queueMicrotask(() => {
      if (decoded?.is_impersonation) {
        setClaims(decoded)
      } else {
        setClaims(null)
      }
    })
  }, [token, pathname, isConsole])

  // Live countdown timer
  useEffect(() => {
    if (!claims?.exp) return

    const updateRemaining = () => {
      const now = Math.floor(Date.now() / 1000)
      const diff = claims.exp! - now
      if (diff <= 0) {
        setTimeLeft('Expired')
        return
      }
      const mins = Math.floor(diff / 60)
      const secs = diff % 60
      setTimeLeft(`${mins}m ${secs < 10 ? '0' : ''}${secs}s`)
    }

    updateRemaining()
    const timer = setInterval(updateRemaining, 1000)
    return () => clearInterval(timer)
  }, [claims])

  if (!claims || isConsole) {
    return null
  }

  const handleEndSession = async () => {
    setTerminating(true)
    try {
      if (claims.impersonation_session_id) {
        // Attempt to terminate on platform backend proxy with CSRF token
        const match = typeof document !== 'undefined' ? document.cookie.match(/(?:^|;\s*)pa_csrf=([^;]+)/) : null
        const csrf = match ? decodeURIComponent(match[1]) : ''
        await fetch(`/console-api/users/impersonations/${claims.impersonation_session_id}`, {
          method: 'DELETE',
          credentials: 'same-origin',
          headers: csrf ? { 'X-CSRF-Token': csrf } : {},
        }).catch(() => {})
      }
    } finally {
      logout()
      if (typeof window !== 'undefined') {
        window.location.href = '/console/users'
      } else {
        router.push('/console/users')
      }
    }
  }

  return (
    <div className="sticky top-0 z-[100] w-full bg-gradient-to-r from-amber-950 via-amber-900 to-rose-950 border-b border-amber-500/40 px-4 py-2.5 shadow-xl text-amber-100 flex flex-wrap items-center justify-between gap-3 animate-in slide-in-from-top duration-200">
      <div className="flex items-center gap-3 text-xs sm:text-sm">
        <div className="p-1.5 rounded-lg bg-amber-500/20 border border-amber-500/30 text-amber-300 shrink-0">
          <ShieldAlert className="w-4 h-4 animate-pulse" />
        </div>
        <div className="leading-tight">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold tracking-wide uppercase text-amber-300 text-[11px] sm:text-xs">
              Operator Impersonation Active
            </span>
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                claims.is_write
                  ? 'bg-rose-500/30 text-rose-200 border border-rose-500/40'
                  : 'bg-amber-500/30 text-amber-200 border border-amber-500/40'
              }`}
            >
              {claims.is_write ? 'Read-Write Mode' : 'Strictly Read-Only'}
            </span>
          </div>
          <div className="text-[11px] sm:text-xs text-amber-200/80 mt-0.5">
            Acting as <strong className="text-white">{user?.username || claims.sub}</strong> ({user?.email || 'Customer'}
            ) • Impersonated by <span className="font-mono text-amber-300">{claims.impersonator_email}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {timeLeft && (
          <div className="flex items-center gap-1.5 text-xs font-mono bg-black/40 px-2.5 py-1 rounded-md border border-amber-500/20 text-amber-300">
            <Clock className="w-3.5 h-3.5" />
            <span>{timeLeft}</span>
          </div>
        )}

        <button
          onClick={() => void handleEndSession()}
          disabled={terminating}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 shadow-sm transition-all disabled:opacity-50"
        >
          <LogOut className="w-3.5 h-3.5" />
          {terminating ? 'Ending...' : 'End Impersonation Session'}
        </button>
      </div>
    </div>
  )
}
