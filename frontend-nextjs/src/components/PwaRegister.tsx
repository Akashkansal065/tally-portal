'use client'

import { useEffect } from 'react'

export function PwaRegister() {
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return

    // In development, skip registering service worker to avoid caching/HMR issues
    // and clean up any stale registrations on localhost.
    if (process.env.NODE_ENV === 'development') {
      navigator.serviceWorker.getRegistrations().then((registrations) => {
        for (const reg of registrations) {
          reg.unregister().catch(() => {})
        }
      }).catch(() => {})
      return
    }

    const registerSW = async () => {
      try {
        const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
        console.log('[PWA] ServiceWorker registered with scope:', reg.scope)
      } catch (err) {
        console.warn('[PWA] ServiceWorker registration skipped/failed:', err)
      }
    }

    if (document.readyState === 'complete' || document.readyState === 'interactive') {
      registerSW()
    } else {
      window.addEventListener('load', registerSW)
      return () => window.removeEventListener('load', registerSW)
    }
  }, [])

  return null
}
