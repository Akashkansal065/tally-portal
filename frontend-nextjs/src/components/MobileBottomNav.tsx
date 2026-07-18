'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import {
  Home,
  FileText,
  BookOpen,
  Layers,
  ShoppingCart,
  IndianRupee,
  MapPin,
  Wallet,
  BarChart3,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavTab {
  href: string
  label: string
  icon: LucideIcon
}

export function MobileBottomNav() {
  const pathname = usePathname()
  const { user, permissions } = useAuth()

  if (!user) return null

  const tabs: NavTab[] = [
    { href: '/', label: 'Home', icon: Home },
    { href: '/vouchers', label: 'Vouchers', icon: FileText },
    { href: '/ledgers', label: 'Ledgers', icon: BookOpen },
    { href: '/stocks', label: 'Items', icon: Layers },
    { href: '/temporders', label: 'Orders', icon: ShoppingCart },
    { href: '/payments', label: 'Payments', icon: IndianRupee },
    { href: '/check-in', label: 'Check-In', icon: MapPin },
    ...(permissions.showExpenses
      ? [{ href: '/expenses', label: 'Expenses', icon: Wallet }]
      : []),
    ...(permissions.showReports
      ? [{ href: '/reports', label: 'Reports', icon: BarChart3 }]
      : []),
  ]

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-30 bg-card border-t border-border shadow-lg"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      <div className="flex items-stretch overflow-x-auto scrollbar-none px-1 h-16">
        {tabs.map(tab => {
          const isActive = tab.href === '/' ? pathname === '/' : pathname.startsWith(tab.href)
          const Icon = tab.icon
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className="flex flex-col items-center justify-center flex-shrink-0 w-[68px] gap-0.5 py-1 cursor-pointer group"
            >
              <div
                className={cn(
                  'flex items-center justify-center w-12 h-7 rounded-full transition-all duration-200',
                  isActive
                    ? 'bg-primary/15 text-primary'
                    : 'text-muted-foreground group-hover:text-foreground'
                )}
              >
                <Icon className="h-5 w-5 shrink-0" />
              </div>
              <span
                className={cn(
                  'text-[10px] font-medium truncate w-full text-center px-1 leading-none transition-colors',
                  isActive
                    ? 'text-primary font-semibold'
                    : 'text-muted-foreground group-hover:text-foreground'
                )}
              >
                {tab.label}
              </span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
