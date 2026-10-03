/**
 * Capacitor Native Platform & Bridge Utilities
 *
 * Provides safe detection and helper methods for Capacitor native environments (Android/iOS)
 * with graceful fallbacks for web browsers (PWA/desktop).
 */

import { Capacitor } from '@capacitor/core'

/**
 * Returns true if running inside a native Capacitor shell (Android / iOS).
 * Safe to call during Next.js SSR (returns false on server).
 */
export function isNativePlatform(): boolean {
  if (typeof window === 'undefined') return false
  try {
    return Capacitor.isNativePlatform()
  } catch {
    return false
  }
}

/**
 * Returns the current platform name ('android' | 'ios' | 'web').
 */
export function getPlatform(): 'android' | 'ios' | 'web' {
  if (typeof window === 'undefined') return 'web'
  try {
    return Capacitor.getPlatform() as 'android' | 'ios' | 'web'
  } catch {
    return 'web'
  }
}

/**
 * Execute native logic if inside Capacitor, otherwise run optional web fallback.
 */
export async function onNative<T>(
  nativeAction: () => Promise<T>,
  webFallback?: () => Promise<T>
): Promise<T | undefined> {
  if (isNativePlatform()) {
    return nativeAction()
  }
  if (webFallback) {
    return webFallback()
  }
  return undefined
}
