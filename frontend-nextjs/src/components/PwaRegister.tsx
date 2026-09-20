'use client'

import { useEffect } from 'react'

export function PwaRegister() {
  useEffect(() => {
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      const registerSW = async () => {
        try {
          const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' })
          console.log('[PWA] ServiceWorker registered with scope:', reg.scope)
        } catch (err) {
          console.error('[PWA] ServiceWorker registration failed:', err)
        }
      }

      if (document.readyState === 'complete' || document.readyState === 'interactive') {
        registerSW()
      } else {
        window.addEventListener('load', registerSW)
        return () => window.removeEventListener('load', registerSW)
      }
    }
  }, [])

  return null
}
