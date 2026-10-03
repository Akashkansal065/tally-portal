/**
 * Native Background Geolocation Service
 *
 * Utilizes @capacitor-community/background-geolocation to maintain accurate
 * GPS tracking even when the app is minimized, screen is locked, or user is in transit.
 */

import { registerPlugin } from '@capacitor/core'
import type {
  BackgroundGeolocationPlugin,
  Location,
} from '@capacitor-community/background-geolocation'
import { isNativePlatform } from './capacitor'
import { API_BASE, authHeaders } from './utils'

// Lazy-register the plugin only on client-side
let BackgroundGeolocation: BackgroundGeolocationPlugin | null = null
function getBackgroundGeolocationPlugin(): BackgroundGeolocationPlugin | null {
  if (typeof window === 'undefined') return null
  if (!BackgroundGeolocation) {
    try {
      BackgroundGeolocation = registerPlugin<BackgroundGeolocationPlugin>(
        'BackgroundGeolocation'
      )
    } catch (err) {
      console.warn('[BG-Geo] Failed to register BackgroundGeolocation plugin:', err)
    }
  }
  return BackgroundGeolocation
}

let currentWatcherId: string | null = null
let lastPingTime = 0
let lastLatitude: number | null = null
let lastLongitude: number | null = null
let isSendingPing = false

const MIN_PING_INTERVAL_MS = 2 * 60 * 1000 // At least 2 minutes between pings
const MIN_DISTANCE_METERS = 50 // Or moved by 50 meters

function calculateDistance(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371e3 // Earth radius in meters
  const phi1 = (lat1 * Math.PI) / 180
  const phi2 = (lat2 * Math.PI) / 180
  const deltaPhi = ((lat2 - lat1) * Math.PI) / 180
  const deltaLambda = ((lon2 - lon1) * Math.PI) / 180

  const a =
    Math.sin(deltaPhi / 2) * Math.sin(deltaPhi / 2) +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2) * Math.sin(deltaLambda / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}

/**
 * Send location ping to backend
 */
async function handleLocationUpdate(loc: Location, token: string) {
  if (!token) return
  if (isSendingPing) return

  const now = Date.now()
  const timeSinceLastPing = now - lastPingTime

  let movedMeters = 0
  if (lastLatitude !== null && lastLongitude !== null) {
    movedMeters = calculateDistance(
      lastLatitude,
      lastLongitude,
      loc.latitude,
      loc.longitude
    )
  }

  // Throttle: only ping if enough time elapsed or moved enough distance
  if (lastPingTime > 0 && timeSinceLastPing < MIN_PING_INTERVAL_MS && movedMeters < MIN_DISTANCE_METERS) {
    return
  }

  isSendingPing = true

  try {
    const payload = {
      latitude: loc.latitude,
      longitude: loc.longitude,
      accuracyMeters: loc.accuracy ?? null,
    }

    const res = await fetch(`${API_BASE}/attendance/ping-location`, {
      method: 'POST',
      headers: {
        ...authHeaders(token),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })

    if (res.ok) {
      lastPingTime = now
      lastLatitude = loc.latitude
      lastLongitude = loc.longitude

      const data = await res.json()
      if (data && data.active === false) {
        // Server says shift is already checked out, stop background tracking
        console.log('[BG-Geo] Server marked shift inactive, stopping watcher.')
        localStorage.removeItem('mytally_shift_active')
        await stopNativeBackgroundTracking()
      }
    }
  } catch (err) {
    console.debug('[BG-Geo] Failed to ping server location:', err)
  } finally {
    isSendingPing = false
  }
}

/**
 * Start native background location tracking
 */
export async function startNativeBackgroundTracking(token: string): Promise<boolean> {
  if (!isNativePlatform()) return false

  const plugin = getBackgroundGeolocationPlugin()
  if (!plugin) return false

  // If already watching, don't start duplicate
  if (currentWatcherId) {
    return true
  }

  try {
    const watcherId = await plugin.addWatcher(
      {
        backgroundMessage: 'MyTally is recording your field location during active shift.',
        backgroundTitle: 'MyTally Shift Active',
        requestPermissions: true,
        stale: false,
        distanceFilter: 25, // Update every 25 meters of movement
      },
      (loc, error) => {
        if (error) {
          console.warn('[BG-Geo] Watcher error:', error.message)
          if (error.code === 'NOT_AUTHORIZED') {
            plugin.openSettings().catch(() => {})
          }
          return
        }

        if (loc) {
          handleLocationUpdate(loc, token)
        }
      }
    )

    currentWatcherId = watcherId
    console.log('[BG-Geo] Started background location watcher:', watcherId)
    return true
  } catch (err) {
    console.error('[BG-Geo] Error starting background watcher:', err)
    return false
  }
}

/**
 * Stop native background location tracking
 */
export async function stopNativeBackgroundTracking(): Promise<void> {
  if (!currentWatcherId) return

  const plugin = getBackgroundGeolocationPlugin()
  if (plugin) {
    try {
      await plugin.removeWatcher({ id: currentWatcherId })
      console.log('[BG-Geo] Stopped background location watcher:', currentWatcherId)
    } catch (err) {
      console.warn('[BG-Geo] Error stopping background watcher:', err)
    }
  }

  currentWatcherId = null
  lastPingTime = 0
}

/**
 * Check if native tracking is currently active
 */
export function isNativeTrackingActive(): boolean {
  return currentWatcherId !== null
}

/**
 * Detect OEM manufacturer and return battery optimization bypass guidance
 */
export async function getOEMBatteryGuidance(): Promise<{
  manufacturer: string
  instructions: string[]
  settingsActionText: string
}> {
  let manufacturer = 'Generic'
  try {
    const { Device } = await import('@capacitor/device')
    const info = await Device.getInfo()
    manufacturer = info.manufacturer || 'Generic'
  } catch {}

  const m = manufacturer.toLowerCase()
  if (m.includes('xiaomi') || m.includes('redmi') || m.includes('poco')) {
    return {
      manufacturer: 'Xiaomi / Redmi / POCO',
      instructions: [
        'Open Settings -> Apps -> Manage Apps -> MyTally',
        'Enable "Autostart"',
        'Tap "Battery saver" and choose "No restrictions"',
      ],
      settingsActionText: 'Open App Settings',
    }
  }
  if (m.includes('samsung')) {
    return {
      manufacturer: 'Samsung',
      instructions: [
        'Open Settings -> Battery and device care -> Battery',
        'Tap "Background usage limits" -> "Never sleeping apps"',
        'Add MyTally to the list',
      ],
      settingsActionText: 'Open Battery Settings',
    }
  }
  if (m.includes('vivo') || m.includes('iqoo')) {
    return {
      manufacturer: 'Vivo / iQOO',
      instructions: [
        'Open Settings -> Battery -> High background power consumption',
        'Turn ON MyTally to allow background running',
      ],
      settingsActionText: 'Open App Settings',
    }
  }
  if (m.includes('oppo') || m.includes('realme') || m.includes('oneplus')) {
    return {
      manufacturer: 'Oppo / Realme / OnePlus',
      instructions: [
        'Open Settings -> Battery -> App Battery Management -> MyTally',
        'Enable "Allow background activity" & "Allow auto-launch"',
      ],
      settingsActionText: 'Open App Settings',
    }
  }

  return {
    manufacturer: 'Android Device',
    instructions: [
      'Open Settings -> Apps -> MyTally -> Battery',
      'Select "Unrestricted" to keep attendance tracking alive',
    ],
    settingsActionText: 'Open App Settings',
  }
}

/**
 * Open native application settings
 */
export async function openNativeAppSettings(): Promise<void> {
  const plugin = getBackgroundGeolocationPlugin()
  if (plugin) {
    try {
      await plugin.openSettings()
    } catch (err) {
      console.warn('[BG-Geo] Failed to open settings:', err)
    }
  }
}
