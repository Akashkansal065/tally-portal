'use client'

/**
 * app/(console)/console/layout.tsx – Dedicated Root Layout for the Platform Operator Console.
 *
 * Distinct styling, navigation, and security boundaries from the customer tenant portal.
 */

import React, { useState, Suspense } from 'react'
import Link from 'next/link'
import { usePathname, useSearchParams } from 'next/navigation'
import {
  Users,
  ShieldCheck,
  FileText,
  CreditCard,
  LogOut,
  LayoutDashboard,
  AlertTriangle,
  Menu,
  X,
  Lock,
  UserCheck,
} from 'lucide-react'
import { ConsoleAuthProvider, useConsoleAuth } from '@/console/context/ConsoleAuthContext'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { label: 'Overview', href: '/console', icon: LayoutDashboard },
  { label: 'Customer Users', href: '/console/users', icon: Users, badge: 'Phase 2' },
  { label: 'Platform Operators', href: '/console/roles?tab=admins', icon: UserCheck, badge: 'Staff' },
  { label: 'Roles & Access', href: '/console/roles', icon: ShieldCheck, badge: 'Phase 3' },
  { label: 'Audit Trail', href: '/console/audit', icon: FileText, badge: 'Phase 4' },
  { label: 'Platform Billing', href: '/console/billing', icon: CreditCard },
]

function ConsoleNavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const currentTab = searchParams?.get('tab')

  return (
    <>
      {NAV_ITEMS.map((item) => {
        const isOperatorsTab = item.href === '/console/roles?tab=admins'
        const isRolesTab = item.href === '/console/roles'
        let isActive = false

        if (isOperatorsTab) {
          isActive = pathname === '/console/roles' && currentTab === 'admins'
        } else if (isRolesTab) {
          isActive = pathname === '/console/roles' && currentTab !== 'admins'
        } else {
          isActive = pathname === item.href || (item.href !== '/console' && pathname.startsWith(item.href))
        }

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => onNavigate?.()}
            className={cn(
              'flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all group',
              isActive
                ? 'bg-[#ecfff7] text-[#0f172a] shadow-sm ring-1 ring-[#c8f6df]'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
            )}
          >
            <div className="flex items-center gap-3">
              <item.icon className={cn('w-4 h-4 transition-colors', isActive ? 'text-[#00a26d]' : 'text-slate-500 group-hover:text-slate-700')} />
              <span>{item.label}</span>
            </div>
            {item.badge && (
              <span className={cn(
                'text-[10px] px-1.5 py-0.2 rounded font-mono font-normal',
                isActive ? 'bg-[#dffdf0] text-[#00a26d]' : 'bg-slate-100 text-slate-500'
              )}>
                {item.badge}
              </span>
            )}
          </Link>
        )
      })}
    </>
  )
}

function ConsoleShell({ children }: { children: React.ReactNode }) {
  const { operator, isLoading, logout } = useConsoleAuth()
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  // Login page renders without the sidebar and top navigation
  const isLoginPage = pathname === '/console/login'
  if (isLoginPage) {
    return <div className="min-h-screen bg-[#f4fbf7] text-[#0f172a]">{children}</div>
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#f4fbf7] flex flex-col items-center justify-center text-slate-500">
        <div className="w-10 h-10 border-2 border-[#00d09c] border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium tracking-wide text-slate-600">Validating operator credentials...</p>
      </div>
    )
  }

  if (!operator) {
    return (
      <div className="min-h-screen bg-[#f4fbf7] flex flex-col items-center justify-center text-slate-500">
        <div className="w-10 h-10 border-2 border-[#00d09c] border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-sm font-medium tracking-wide text-slate-600">Redirecting to operator login...</p>
      </div>
    )
  }

  return (
    <div className="h-full min-h-0 flex bg-[#f3faf7] text-slate-900 antialiased selection:bg-[#00d09c]/20 selection:text-[#0f172a]">
      {/* ── Sidebar (Desktop) ── */}
      <aside className="hidden md:flex flex-col w-64 border-r border-[#dfeee8] bg-white/85 backdrop-blur-xl shrink-0 shadow-[0_10px_30px_rgba(15,23,42,0.04)]">
        <div className="h-16 flex items-center px-6 border-b border-[#e3f4ee] gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#00b37a] via-[#00d09c] to-[#6ee7b7] flex items-center justify-center shadow-lg shadow-[#00d09c]/20 text-white font-bold text-lg">
            G
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-slate-900 flex items-center gap-1.5">
              MyTally <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#ebfff7] text-[#00a26d] border border-[#b8f5dc] font-semibold uppercase tracking-wider">Console</span>
            </div>
            <div className="text-[11px] text-slate-500 font-mono">Platform Admin</div>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <Suspense fallback={<div className="space-y-1 px-3 py-2 text-xs text-slate-400">Loading navigation...</div>}>
            <ConsoleNavLinks />
          </Suspense>
        </nav>

        {/* Operator Badge & Session Info */}
        <div className="p-4 border-t border-[#e3f4ee] bg-[#f9fffc]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-[#ecfff7] border border-[#cfeee0] flex items-center justify-center font-bold text-xs text-[#00a26d]">
              {operator?.email?.slice(0, 2).toUpperCase() || 'OP'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-semibold text-slate-800 truncate">{operator?.full_name || 'Operator'}</div>
              <div className="text-[11px] text-slate-500 truncate font-mono">{operator?.email}</div>
            </div>
          </div>
          <button
            onClick={() => logout()}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-[#d92d20] hover:text-[#b42318] hover:bg-[#fff1f2] border border-[#fecaca] transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* ── Main Workspace ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header Bar */}
        <header className="h-16 border-b border-[#e3f4ee] bg-white/80 backdrop-blur-md flex items-center justify-between px-6 shrink-0 z-20 shadow-sm">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#00d09c] animate-pulse" />
              <span className="text-xs font-mono text-slate-500">FASTAPI HOST / PLATFORM API</span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-[#ebfff7] border border-[#cfeee0] text-[11px] text-slate-700 font-mono">
              <Lock className="w-3 h-3 text-[#00a26d]" />
              Rank: {operator?.max_rank || 0}
            </div>

            <button
              onClick={() => logout()}
              className="md:hidden p-2 text-[#d92d20] hover:bg-[#fff1f2] rounded-lg"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Warning Banner if Passkeys Disabled (Plan Section 5.2) */}
        {!operator?.passkey_required && (
          <div className="bg-[#fff7db] border-b border-[#f4d86a] px-6 py-2.5 flex items-center gap-2 text-[#9a5d00] text-xs">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>
              <strong>Security Warning:</strong> Hardware Passkeys are currently switched off (<code className="font-mono bg-[#fdf3c5] px-1 py-0.5 rounded text-[11px]">PLATFORM_PASSKEY_REQUIRED=false</code>). Operators are authenticated with password alone.
            </span>
          </div>
        )}

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-white/95 border-b border-[#e3f4ee] p-4 space-y-1 shadow-sm">
            <Suspense fallback={null}>
              <ConsoleNavLinks onNavigate={() => setMobileMenuOpen(false)} />
            </Suspense>
          </div>
        )}

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-[#f3faf7]">
          <div className="max-w-7xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  )
}

export default function PlatformConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <ConsoleAuthProvider>
      <ConsoleShell>{children}</ConsoleShell>
    </ConsoleAuthProvider>
  )
}
