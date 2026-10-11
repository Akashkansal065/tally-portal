'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutGrid, type LucideIcon } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { MoreSheet } from '@/components/MoreSheet'
import { cn } from '@/lib/utils'
import { HOME, MAX_TABS, PHONE_TAB_COUNT, isActivePath, isAdminUser, tabModules } from '@/lib/navigation'

/*
 * Phones: five fixed slots (Home, three tabs picked for the person's role, More), so each tab stays in
 * the same place every day and nothing scrolls off the edge.
 * Wider screens: a slimmer bar with icon and label side by side, showing more of the same role list as
 * the window widens (4 tabs from md, 6 from lg, 7 from xl). More always holds every other screen.
 */

// Which breakpoint reveals the tab at each position after Home (index 0-2 show everywhere)
const REVEAL_AT = ['', '', '', 'hidden md:block', 'hidden lg:block', 'hidden lg:block', 'hidden xl:block']

/** Whether a tab is highlighted, per breakpoint: More's state depends on which tabs are visible. */
interface ActiveState {
  base: boolean
  md: boolean
  lg: boolean
  xl: boolean
}

const always = (on: boolean): ActiveState => ({ base: on, md: on, lg: on, xl: on })

export function MobileBottomNav() {
  const pathname = usePathname()
  const { user, permissions, can } = useAuth()
  const [moreOpen, setMoreOpen] = useState(false)

  const tabs = useMemo(
    () => tabModules({ permissions, can, isAdmin: isAdminUser(permissions, user?.role) }, MAX_TABS),
    [permissions, can, user?.role],
  )

  // No way around Connect Tally: the app's navigation appears once a Tally PC is connected
  if (!user || user.needs_tally_setup) return null

  // More lights up when the current screen has no visible tab at this width
  const shownUpTo = (count: number) =>
    isActivePath(pathname, HOME.href) || tabs.slice(0, count).some(tab => isActivePath(pathname, tab.href))
  const moreActive: ActiveState = {
    base: moreOpen || !shownUpTo(PHONE_TAB_COUNT),
    md: moreOpen || !shownUpTo(4),
    lg: moreOpen || !shownUpTo(6),
    xl: moreOpen || !shownUpTo(MAX_TABS),
  }

  return (
    <>
      <nav
        aria-label="Main"
        className="fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-card shadow-lg"
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      >
        <ul className="mx-auto grid h-16 max-w-xl grid-cols-5 md:flex md:h-12 md:max-w-none md:items-center md:justify-center md:gap-1 md:px-4">
          <li>
            <TabLink href={HOME.href} label={HOME.label} icon={HOME.icon} active={always(isActivePath(pathname, HOME.href))} />
          </li>
          {tabs.map((tab, i) => (
            <li key={tab.id} className={REVEAL_AT[i]}>
              <TabLink href={tab.href} label={tab.tabLabel ?? tab.label} icon={tab.icon} active={always(isActivePath(pathname, tab.href))} />
            </li>
          ))}
          {/* Keep five slots on phones even when a user has access to fewer modules */}
          {Array.from({ length: Math.max(0, PHONE_TAB_COUNT - tabs.length) }, (_, i) => (
            <li key={`empty-${i}`} aria-hidden="true" className="md:hidden" />
          ))}
          <li>
            <button
              type="button"
              onClick={() => setMoreOpen(true)}
              aria-haspopup="dialog"
              aria-expanded={moreOpen}
              className="h-full w-full cursor-pointer"
            >
              <TabFace label="More" icon={LayoutGrid} active={moreActive} />
            </button>
          </li>
        </ul>
      </nav>
      <MoreSheet open={moreOpen} onOpenChange={setMoreOpen} />
    </>
  )
}

function TabLink({ href, label, icon, active }: { href: string; label: string; icon: LucideIcon; active: ActiveState }) {
  return (
    <Link href={href} aria-current={active.base ? 'page' : undefined} className="block h-full">
      <TabFace label={label} icon={icon} active={active} />
    </Link>
  )
}

function TabFace({ label, icon: Icon, active }: { label: string; icon: LucideIcon; active: ActiveState }) {
  return (
    <span
      className={cn(
        // Phones: icon over label, the icon carries the highlight
        'flex h-full flex-col items-center justify-center gap-1 px-1',
        // Wider screens: one pill with icon and label side by side, the whole pill carries the highlight
        'md:h-9 md:flex-row md:gap-2 md:rounded-full md:px-3.5 md:transition-colors md:hover:bg-muted',
        active.md ? 'md:bg-primary/12' : 'md:bg-transparent',
        active.lg ? 'lg:bg-primary/12' : 'lg:bg-transparent',
        active.xl ? 'xl:bg-primary/12' : 'xl:bg-transparent',
      )}
    >
      <span
        className={cn(
          'flex h-8 w-14 items-center justify-center rounded-full transition-colors md:h-auto md:w-auto md:bg-transparent',
          active.base ? 'bg-primary/15 text-primary' : 'text-muted-foreground',
          active.md ? 'md:text-primary' : 'md:text-muted-foreground',
          active.lg ? 'lg:text-primary' : 'lg:text-muted-foreground',
          active.xl ? 'xl:text-primary' : 'xl:text-muted-foreground',
        )}
      >
        <Icon className="h-5 w-5 md:h-4.5 md:w-4.5" aria-hidden="true" />
      </span>
      <span
        className={cn(
          'w-full truncate text-center text-xs leading-none md:w-auto md:text-sm',
          active.base ? 'font-bold text-primary' : 'font-medium text-muted-foreground',
          active.md ? 'md:font-semibold md:text-primary' : 'md:font-medium md:text-muted-foreground',
          active.lg ? 'lg:font-semibold lg:text-primary' : 'lg:font-medium lg:text-muted-foreground',
          active.xl ? 'xl:font-semibold xl:text-primary' : 'xl:font-medium xl:text-muted-foreground',
        )}
      >
        {label}
      </span>
    </span>
  )
}
