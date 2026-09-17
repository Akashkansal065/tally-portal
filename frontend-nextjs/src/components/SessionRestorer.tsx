'use client'

import { useEffect, Suspense } from 'react'
import { usePathname, useSearchParams, useRouter } from 'next/navigation'

function SessionRestorerInner() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const router = useRouter()

  // On mount and route change, record the path (except if it's login or the redirector itself)
  useEffect(() => {
    if (pathname && pathname !== '/login') {
      const qs = searchParams.toString()
      const currentUrl = pathname + (qs ? `?${qs}` : '')
      
      // Save last visited path for restoration later
      if (currentUrl !== '/?source=pwa' && currentUrl !== '/') {
        localStorage.setItem('mytally_last_path', currentUrl)
        localStorage.setItem('mytally_last_path_time', Date.now().toString())
      }
    }
  }, [pathname, searchParams])

  // On mount (app startup), check if we have a recent saved path to restore
  useEffect(() => {
    if (pathname === '/') {
      const hasBooted = sessionStorage.getItem('mytally_has_booted')
      
      if (!hasBooted) {
        // Mark this tab/session as booted so we don't restore again on normal navigation to home
        sessionStorage.setItem('mytally_has_booted', 'true')
        
        const lastPath = localStorage.getItem('mytally_last_path')
        const lastPathTimeStr = localStorage.getItem('mytally_last_path_time')
        
        if (lastPath && lastPath !== '/' && lastPathTimeStr) {
          const lastPathTime = parseInt(lastPathTimeStr, 10)
          const now = Date.now()
          // If the path was saved within the last 12 hours, restore it
          if (now - lastPathTime < 12 * 60 * 60 * 1000) {
            router.replace(lastPath)
            return
          }
        }
      }
      
      // Clean up PWA source parameter if present
      if (searchParams.get('source') === 'pwa') {
        router.replace('/')
      }
    } else {
      // If they booted directly into a deep link, mark as booted
      sessionStorage.setItem('mytally_has_booted', 'true')
    }
  }, [pathname, searchParams, router])

  return null
}

export function SessionRestorer() {
  return (
    <Suspense fallback={null}>
      <SessionRestorerInner />
    </Suspense>
  )
}
