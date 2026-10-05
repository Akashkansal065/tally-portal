'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

/**
 * Lets a tapped push notification move the already-open app to the notification's page. The service worker
 * asks via postMessage and waits for the reply; without one it falls back to a full page load.
 */
export function NotificationNavigator() {
  const router = useRouter()

  useEffect(() => {
    if (!('serviceWorker' in navigator)) return
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type !== 'mytally:navigate' || typeof event.data.url !== 'string') return
      const url = new URL(event.data.url, window.location.origin)
      if (url.origin !== window.location.origin) return
      event.ports[0]?.postMessage('ok')
      router.push(`${url.pathname}${url.search}`)
    }
    navigator.serviceWorker.addEventListener('message', onMessage)
    return () => navigator.serviceWorker.removeEventListener('message', onMessage)
  }, [router])

  return null
}
