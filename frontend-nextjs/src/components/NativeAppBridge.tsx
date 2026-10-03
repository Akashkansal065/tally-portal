'use client'

import { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { isNativePlatform } from '@/lib/capacitor'

/**
 * NativeAppBridge
 *
 * Runs exclusively inside native Capacitor environments (Android & iOS).
 * - Configures native Status Bar color and style to match the dark app theme.
 * - Handles the Android hardware back button (dismisses active modals, navigates back, or minimizes app).
 */
export function NativeAppBridge() {
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (!isNativePlatform()) return

    let cleanup: (() => void) | undefined

    const initBridge = async () => {
      try {
        const { App } = await import('@capacitor/app')
        const { StatusBar, Style } = await import('@capacitor/status-bar')

        // 1. Native Status Bar Styling
        try {
          await StatusBar.setStyle({ style: Style.Dark })
          await StatusBar.setBackgroundColor({ color: '#0f172a' })
        } catch (e) {
          console.debug('[NativeAppBridge] StatusBar styling error:', e)
        }

        // 2. Android Hardware Back Button Handling
        const backListener = await App.addListener('backButton', () => {
          // Check if any open modal / sheet / dialog exists in DOM
          const openDialogCloseBtn = document.querySelector(
            '[data-state="open"] button[aria-label="Close"], [role="dialog"] button[aria-label="Close"], [role="dialog"] button:has(svg.lucide-x)'
          ) as HTMLElement | null

          if (openDialogCloseBtn) {
            openDialogCloseBtn.click()
            return
          }

          // If on home dashboard or login, minimize app
          if (pathname === '/' || pathname === '/login') {
            App.minimizeApp()
          } else {
            router.back()
          }
        })

        cleanup = () => {
          backListener.remove()
        }
      } catch (err) {
        console.warn('[NativeAppBridge] Init failed:', err)
      }
    }

    initBridge()

    return () => {
      if (cleanup) cleanup()
    }
  }, [router, pathname])

  return null
}
