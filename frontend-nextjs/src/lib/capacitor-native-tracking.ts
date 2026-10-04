'use client'

import { registerPlugin } from '@capacitor/core'
import { isNativePlatform } from './capacitor'
import { API_BASE } from './utils'

export interface NativeTrackingPluginInterface {
  startTracking(options: { token: string; apiBase: string }): Promise<{ success: boolean; active: boolean }>
  stopTracking(): Promise<{ success: boolean; active: boolean }>
  isTrackingActive(): Promise<{ active: boolean }>
  requestBatteryExemption(): Promise<{ prompted: boolean; isIgnoring: boolean }>
}

let NativeTracking: NativeTrackingPluginInterface | null = null

function getNativeTrackingPlugin(): NativeTrackingPluginInterface | null {
  if (typeof window === 'undefined') return null
  if (!isNativePlatform()) return null

  if (!NativeTracking) {
    try {
      NativeTracking = registerPlugin<NativeTrackingPluginInterface>('NativeTracking')
    } catch (err) {
      console.warn('[NativeTracking] Failed to register plugin:', err)
    }
  }
  return NativeTracking
}

/**
 * Starts the Headless Native Android Foreground Service.
 * This service runs 100% in native Java and continues tracking
 * even if the user swipes away or force-closes the app!
 */
export async function startHeadlessNativeTracking(token: string, customApiBase?: string): Promise<boolean> {
  const plugin = getNativeTrackingPlugin()
  if (!plugin) {
    console.debug('[NativeTracking] Plugin not available on web platform.')
    return false
  }

  try {
    const base = customApiBase || API_BASE
    const res = await plugin.startTracking({ token, apiBase: base })
    console.log('[NativeTracking] Started native headless service:', res)
    return Boolean(res?.success)
  } catch (err) {
    console.warn('[NativeTracking] Failed to start native tracking:', err)
    return false
  }
}

/**
 * Stops the Headless Native Android Foreground Service.
 */
export async function stopHeadlessNativeTracking(): Promise<boolean> {
  const plugin = getNativeTrackingPlugin()
  if (!plugin) return false

  try {
    const res = await plugin.stopTracking()
    console.log('[NativeTracking] Stopped native headless service:', res)
    return Boolean(res?.success)
  } catch (err) {
    console.warn('[NativeTracking] Failed to stop native tracking:', err)
    return false
  }
}

/**
 * Checks if the native headless tracking service is active in Android preferences.
 */
export async function isHeadlessTrackingActive(): Promise<boolean> {
  const plugin = getNativeTrackingPlugin()
  if (!plugin) return false

  try {
    const res = await plugin.isTrackingActive()
    return Boolean(res?.active)
  } catch {
    return false
  }
}

/**
 * Prompts the user to exempt SnehDist from Android battery optimization
 * so the OS never freezes or kills the background GPS process during deep sleep.
 */
export async function requestNativeBatteryExemption(): Promise<boolean> {
  const plugin = getNativeTrackingPlugin()
  if (!plugin) return false

  try {
    const res = await plugin.requestBatteryExemption()
    return Boolean(res?.isIgnoring)
  } catch (err) {
    console.warn('[NativeTracking] Failed to request battery exemption:', err)
    return false
  }
}
