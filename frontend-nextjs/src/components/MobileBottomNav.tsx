'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutGrid, type LucideIcon } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { MoreSheet } from '@/components/MoreSheet'
import { cn } from '@/lib/utils'
import { HOME, isActivePath, isAdminUser, tabModules } from '@/lib/navigation'

/*
 * Five fixed slots: Home, three tabs picked for the person's role, and More (every other screen).
 * Fixed slots keep each tab in the same place every day; nothing scrolls off the edge.
 */
export function MobileBottomNav() {
  const pathname = usePathname()
  const { user, permissions, can } = useAuth()
  const [moreOpen, setMoreOpen] = useState(false)

  const tabs = useMemo(
    () => [HOME, ...tabModules({ permissions, can, isAdmin: isAdminUser(permissions, user?.role) })],
    [permissions, can, user?.role],
  )

  if (!user) return null

  const onTab = tabs.some(tab => isActivePath(pathname, tab.href))

  return (
    <>
      <nav
        aria-label="Main"
        className="fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-card shadow-lg"
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      >
        <ul className="mx-auto grid h-16 max-w-xl grid-cols-5">
          {tabs.map(tab => (
            <li key={tab.id}>
              <TabLink href={tab.href} label={tab.tabLabel ?? tab.label} icon={tab.icon} active={isActivePath(pathname, tab.href)} />
            </li>
          ))}
          {/* Keep five slots even when a user has access to fewer modules */}
          {Array.from({ length: Math.max(0, 4 - tabs.length) }, (_, i) => <li key={`empty-${i}`} aria-hidden="true" />)}
          <li>
            <button
              type="button"
              onClick={() => setMoreOpen(true)}
              aria-haspopup="dialog"
              aria-expanded={moreOpen}
              className="h-full w-full cursor-pointer"
            >
              <TabFace label="More" icon={LayoutGrid} active={moreOpen || !onTab} />
            </button>
          </li>
        </ul>
      </nav>
      <MoreSheet open={moreOpen} onOpenChange={setMoreOpen} />
    </>
  )
}

function TabLink({ href, label, icon, active }: { href: string; label: string; icon: LucideIcon; active: boolean }) {
  return (
    <Link href={href} aria-current={active ? 'page' : undefined} className="block h-full">
      <TabFace label={label} icon={icon} active={active} />
    </Link>
  )
}

function TabFace({ label, icon: Icon, active }: { label: string; icon: LucideIcon; active: boolean }) {
  return (
    <span className="flex h-full flex-col items-center justify-center gap-1 px-1">
      <span
        className={cn(
          'flex h-8 w-14 items-center justify-center rounded-full transition-colors',
          active ? 'bg-primary/15 text-primary' : 'text-muted-foreground',
        )}
      >
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <span
        className={cn(
          'w-full truncate text-center text-xs leading-none',
          active ? 'font-bold text-primary' : 'font-medium text-muted-foreground',
        )}
      >
        {label}
      </span>
    </span>
  )
}
