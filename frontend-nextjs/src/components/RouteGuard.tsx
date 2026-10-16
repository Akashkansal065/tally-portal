'use client'

import { useAuth } from '@/context/AuthContext'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { afterLoginPath } from '@/lib/utils'

// Public pages that someone already signed in may still open: an invitation link is often opened on a device
// where somebody else (the admin who sent it) is signed in, or pricing / plans comparison.
const OPEN_WHEN_SIGNED_IN = ['/accept-invite', '/pricing']
// Pages anyone may open without signing in
export const PUBLIC_PATHS = ['/login', '/signup', '/accept-invite', '/pricing']
// Where someone whose business has no Tally PC yet is kept until they have connected one
const CONNECT_TALLY = '/connect'

export function RouteGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  // The operator console has its own sign-in; customer sessions do not guard it. Checked after every hook has
  // run, so moving between the console and the app keeps the same hooks.
  const isConsole = pathname?.startsWith('/console') ?? false
  const isPublicPath = PUBLIC_PATHS.includes(pathname)

  useEffect(() => {
    if (isConsole || isLoading) return

    if (!user && !isPublicPath) {
      // Come back here after signing in (e.g. a notification opened while signed out)
      const here = `${pathname}${window.location.search}`
      router.replace(here === '/' ? '/login' : `/login?next=${encodeURIComponent(here)}`)
    } else if (user?.needs_tally_setup && pathname !== CONNECT_TALLY && !OPEN_WHEN_SIGNED_IN.includes(pathname)) {
      router.replace(CONNECT_TALLY)
    } else if (user && isPublicPath && !OPEN_WHEN_SIGNED_IN.includes(pathname)) {
      router.replace(afterLoginPath())
    }
  }, [user, isLoading, pathname, router, isConsole, isPublicPath])

  if (isConsole) {
    return <>{children}</>
  }

  if (isLoading) {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center bg-background min-h-[50vh]">
        <Loader2 className="animate-spin h-8 w-8 text-primary" />
        <p className="text-xs text-muted-foreground mt-2 font-medium">Verifying session...</p>
      </div>
    )
  }

  // Prevent rendering protected content before redirect completes
  if (!user && !isPublicPath) {
    return null
  }
  if (user && isPublicPath && !OPEN_WHEN_SIGNED_IN.includes(pathname)) {
    return null
  }
  if (user?.needs_tally_setup && pathname !== CONNECT_TALLY && !OPEN_WHEN_SIGNED_IN.includes(pathname)) {
    return null
  }

  return <>{children}</>
}
