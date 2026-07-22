'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/components/ThemeProvider'
import {
  Home,
  FileText,
  BookOpen,
  Layers,
  BarChart3,
  Wallet,
  ShoppingCart,
  IndianRupee,
  MapPin,
  LogOut,
  Sun,
  Moon,
  Menu,
  X,
  Shield,
  Building,
  ArrowLeft,
  FileSpreadsheet,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useState } from 'react'

export function GlobalHeader() {
  const { user, logout, permissions, switchCompany } = useAuth()
  const { dark, toggle } = useTheme()
  const pathname = usePathname()
  const router = useRouter()
  const [drawerOpen, setDrawerOpen] = useState(false)

  if (!user) return null

  const isAdmin = permissions.isAdmin

  return (
    <>
      <header className={cn("shrink-0 border-b border-emerald-600/30 bg-emerald-500 dark:bg-emerald-600 text-white z-20", drawerOpen && "z-50 relative")}>
        <div className="flex items-center justify-between px-4 h-14">
          {/* Left: back button, logo, and title */}
          <div className="flex items-center gap-2 min-w-0">
            {pathname !== '/' && pathname !== '/login' && pathname !== '/signup' && (
              <button
                onClick={() => router.back()}
                className="p-1.5 rounded-full hover:bg-emerald-600/60 text-white transition-colors shrink-0 cursor-pointer"
                aria-label="Go Back"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
            )}
            <img src="/logo.png" alt="Logo" className="h-8 w-8 object-contain shrink-0 rounded-md bg-white p-0.5" />
            <Link
              href="/"
              className="text-base sm:text-lg font-extrabold text-white hover:opacity-90 transition-all truncate"
            >
              Sneh Distributors
            </Link>
            
            {user.allowedCompanies && user.allowedCompanies.length > 0 && (
              <div className="ml-2 relative group hidden sm:block">
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-emerald-600/60 text-xs font-semibold text-white/90 transition-colors border border-transparent">
                  <Building className="w-3.5 h-3.5" />
                  <span className="max-w-[120px] truncate">
                    {user.allowedCompanies.find(c => c.company_id === user.company_id)?.name || "Select Company"}
                  </span>
                </button>
                <div className="absolute top-full left-0 mt-1 w-48 bg-card border border-border rounded-xl shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 overflow-hidden text-foreground">
                  {user.allowedCompanies.map(c => (
                    <button 
                      key={c.company_id}
                      onClick={() => switchCompany(c.company_id)}
                      className={`w-full text-left px-4 py-2.5 text-xs font-medium hover:bg-muted transition-colors ${c.company_id === user.company_id ? 'text-primary bg-primary/5' : 'text-foreground'}`}
                    >
                      {c.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right: theme + menu */}
          <div className="flex items-center gap-1">
            <button
              onClick={toggle}
              className="p-2 rounded-full hover:bg-emerald-600/60 text-white transition-colors cursor-pointer"
              aria-label="Toggle theme"
            >
              {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
            <button
              onClick={() => setDrawerOpen(true)}
              className="p-2 rounded-full hover:bg-emerald-600/60 text-white transition-colors cursor-pointer"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Drawer overlay */}
      {drawerOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-50"
          onClick={() => setDrawerOpen(false)}
        >
          <div
            className="absolute right-0 top-0 bottom-0 w-72 bg-card border-l border-border flex flex-col shadow-2xl z-50"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div>
                <p className="font-bold text-sm">{user.username}</p>
                <p className="text-xs text-muted-foreground capitalize">{user.role}</p>
              </div>
              <button onClick={() => setDrawerOpen(false)} className="p-1 rounded hover:bg-muted">
                <X className="h-5 w-5" />
              </button>
            </div>

            {user.allowedCompanies && user.allowedCompanies.length > 0 && (
              <div className="px-4 py-3 border-b border-border bg-muted/20">
                <label className="block text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-1.5">
                  Active Company
                </label>
                <select
                  value={user.company_id}
                  onChange={(e) => {
                    switchCompany(Number(e.target.value))
                    setDrawerOpen(false)
                  }}
                  className="w-full bg-background border border-border rounded-xl px-3 py-2 text-xs font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  {user.allowedCompanies.map((c) => (
                    <option key={c.company_id} value={c.company_id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <nav className="flex-1 overflow-y-auto p-3 space-y-1">
              {isAdmin && (
                <DrawerLink href="/admin" icon={Shield} label="Admin Panel" onClick={() => setDrawerOpen(false)} />
              )}
              {(permissions.showSalesLedgers || permissions.showPurchaseLedgers || permissions.showReceipts || permissions.showPayments) && (
                <DrawerLink href="/vouchers" icon={FileText} label="Vouchers" onClick={() => setDrawerOpen(false)} />
              )}
              {permissions.showLedger && (
                <DrawerLink href="/ledgers" icon={BookOpen} label="Ledgers" onClick={() => setDrawerOpen(false)} />
              )}
              {permissions.showStocks && (
                <DrawerLink href="/stocks" icon={Layers} label="Stocks" onClick={() => setDrawerOpen(false)} />
              )}
              {permissions.showOrders && (
                <DrawerLink href="/temporders" icon={ShoppingCart} label="Orders" onClick={() => setDrawerOpen(false)} />
              )}
              {permissions.showPayments && (
                <DrawerLink href="/payments" icon={IndianRupee} label="Payments" onClick={() => setDrawerOpen(false)} />
              )}
              {permissions.showCheckIn && (
                <DrawerLink href="/check-in" icon={MapPin} label="Check-In" onClick={() => setDrawerOpen(false)} />
              )}
              {permissions.showExpenses && (
                <DrawerLink href="/expenses" icon={Wallet} label="Expenses" onClick={() => setDrawerOpen(false)} />
              )}
              {permissions.showReports && (
                <DrawerLink href="/reports" icon={BarChart3} label="Reports" onClick={() => setDrawerOpen(false)} />
              )}
              {permissions.showGst && (
                <DrawerLink href="/gst" icon={FileSpreadsheet} label="GST Returns" onClick={() => setDrawerOpen(false)} />
              )}
            </nav>

            <div className="p-3 border-t border-border">
              <button
                onClick={logout}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-destructive hover:bg-destructive/10 text-sm font-medium transition-colors"
              >
                <LogOut className="h-4 w-4" />
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function DrawerLink({
  href,
  icon: Icon,
  label,
  onClick,
}: {
  href: string
  icon: LucideIcon
  label: string
  onClick: () => void
}) {
  const pathname = usePathname()
  const isActive = href === '/' ? pathname === '/' : pathname.startsWith(href)

  return (
    <Link
      href={href}
      onClick={onClick}
      className={cn(
        'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
        isActive
          ? 'bg-primary/10 text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {label}
    </Link>
  )
}
