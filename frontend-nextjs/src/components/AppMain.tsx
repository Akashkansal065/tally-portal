'use client'

import React from 'react'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

interface AppMainProps {
  children: React.ReactNode
}

/**
 * AppMain – Root main content shell.
 *
 * For standard tenant/customer pages, applies bottom padding to prevent content
 * from being obscured by the fixed MobileBottomNav and iOS safe area.
 *
 * For /console routes, omits the bottom padding and secondary overflow container
 * so the dedicated platform console shell can manage its own full-height layout
 * without leaving a blank white footer gap.
 */
export function AppMain({ children }: AppMainProps) {
  const pathname = usePathname()
  const isConsole = pathname?.startsWith('/console')

  return (
    <main
      className={cn(
        'flex-1 min-w-0',
        isConsole
          ? 'flex flex-col h-full min-h-0 overflow-hidden'
          : 'overflow-y-auto overflow-x-hidden pb-[calc(4.5rem+env(safe-area-inset-bottom,0px))] md:pb-[calc(3.5rem+env(safe-area-inset-bottom,0px))]'
      )}
    >
      {children}
    </main>
  )
}
