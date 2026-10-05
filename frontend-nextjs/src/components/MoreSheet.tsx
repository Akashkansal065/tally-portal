'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LogOut, Moon, MonitorSmartphone, Search, Sun, X } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useTheme } from '@/components/ThemeProvider'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { cn } from '@/lib/utils'
import {
  NAV_GROUP_LABELS,
  isActivePath,
  isAdminUser,
  visibleModules,
  type NavGroup,
  type NavModule,
} from '@/lib/navigation'

const GROUP_ORDER: NavGroup[] = ['field', 'accounts', 'inventory', 'reports', 'masters', 'admin']

/** Icon-over-label tile used by the More sheet and Home's quick access, so both read the same way. */
export function moduleTileClass(active = false) {
  return cn(
    'flex h-full min-h-[76px] w-full flex-col items-center justify-center gap-1.5 rounded-2xl border px-1 py-2.5 text-center transition-colors cursor-pointer',
    active
      ? 'border-primary/40 bg-primary/10 text-primary'
      : 'border-border/70 bg-background text-foreground hover:bg-muted',
  )
}

/** Every screen the person can open, grouped and searchable, plus account settings. Replaces the side drawer. */
export function MoreSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { user, permissions, can, logout } = useAuth()
  const { dark, toggle } = useTheme()
  const pathname = usePathname()
  const [query, setQuery] = useState('')

  const modules = useMemo(
    () => visibleModules({ permissions, can, isAdmin: isAdminUser(permissions, user?.role) }),
    [permissions, can, user?.role],
  )

  const q = query.trim().toLowerCase()
  const matches = (m: NavModule) =>
    !q || m.label.toLowerCase().includes(q) || (m.keywords ?? '').includes(q) || NAV_GROUP_LABELS[m.group].toLowerCase().includes(q)
  const groups = GROUP_ORDER
    .map(group => ({ group, items: modules.filter(m => m.group === group && matches(m)) }))
    .filter(g => g.items.length > 0)

  const close = () => {
    onOpenChange(false)
    setQuery('')
  }

  return (
    <BottomSheet
      open={open}
      onOpenChange={(next) => (next ? onOpenChange(true) : close())}
      title="All screens"
      description={user ? `${user.username} · ${user.role}` : undefined}
      footer={
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={toggle}
            className="flex min-h-11 flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-xs font-semibold text-foreground hover:bg-muted cursor-pointer"
          >
            {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            {dark ? 'Light mode' : 'Dark mode'}
          </button>
          <Link
            href="/account/devices"
            onClick={close}
            className="flex min-h-11 flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-xs font-semibold text-foreground hover:bg-muted"
          >
            <MonitorSmartphone className="h-5 w-5" />
            My devices
          </Link>
          <button
            type="button"
            onClick={() => { close(); logout() }}
            className="flex min-h-11 flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-xs font-semibold text-destructive hover:bg-destructive/10 cursor-pointer"
          >
            <LogOut className="h-5 w-5" />
            Sign out
          </button>
        </div>
      }
    >
      <div className="relative mb-4">
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <input
          id="more-sheet-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Find a screen…"
          aria-label="Find a screen"
          className="h-12 w-full rounded-xl border border-border bg-muted/40 pl-10 pr-11 text-base [&::-webkit-search-cancel-button]:appearance-none text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        {query && (
          <button
            type="button"
            onClick={() => setQuery('')}
            className="absolute right-0.5 top-1/2 inline-flex h-11 w-11 -translate-y-1/2 items-center justify-center text-muted-foreground cursor-pointer"
            aria-label="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {groups.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">No screen matches “{query}”.</p>
      ) : (
        <div className="space-y-5">
          {groups.map(({ group, items }) => (
            <section key={group} aria-labelledby={`more-group-${group}`}>
              <h3 id={`more-group-${group}`} className="mb-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                {NAV_GROUP_LABELS[group]}
              </h3>
              <ul className="grid grid-cols-4 gap-2 sm:grid-cols-5">
                {items.map(m => {
                  const Icon = m.icon
                  const active = isActivePath(pathname, m.href)
                  return (
                    <li key={m.id}>
                      <Link
                        href={m.href}
                        onClick={close}
                        aria-current={active ? 'page' : undefined}
                        className={moduleTileClass(active)}
                      >
                        <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                        <span className="text-xs font-semibold leading-tight">{m.label}</span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </section>
          ))}
        </div>
      )}
    </BottomSheet>
  )
}
