/**
 * Geolocation & Permission Management Utilities
 * Handles browser permission queries, device detection for unblocking instructions,
 * high-accuracy GPS capture, and admin alert reporting.
 */

import { authHeaders } from './utils'

export type LocationPermissionState = 'granted' | 'prompt' | 'denied' | 'unsupported'

export interface Coordinates {
  lat: number
  lng: number
  accuracy: number
  timestamp?: number
}

export interface GeolocationErrorDetails {
  code: 'PERMISSION_DENIED' | 'POSITION_UNAVAILABLE' | 'TIMEOUT' | 'UNSUPPORTED' | 'UNKNOWN'
  message: string
}

export interface DevicePlatformInfo {
  isIOS: boolean
  isAndroid: boolean
  isSafari: boolean
  isChrome: boolean
  isFirefox: boolean
  isMobile: boolean
  browserName: string
}

/**
 * Detect client platform and browser for tailored unblocking instructions
 */
export function detectDevicePlatform(): DevicePlatformInfo {
  if (typeof window === 'undefined') {
    return {
      isIOS: false,
      isAndroid: false,
      isSafari: false,
      isChrome: false,
      isFirefox: false,
      isMobile: false,
      browserName: 'Browser',
    }
  }

  const ua = navigator.userAgent || ''
  const isIOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  const isAndroid = /Android/i.test(ua)
  const isMobile = isIOS || isAndroid || /Mobi|Tablet/i.test(ua)

  const isFirefox = /Firefox/i.test(ua)
  const isChrome = /Chrome|CriOS/i.test(ua) && !/Edg/i.test(ua) && !isFirefox
  const isSafari = /Safari/i.test(ua) && !isChrome && !/CriOS/i.test(ua) && !/Edg/i.test(ua)

  let browserName = 'Browser'
  if (isChrome) browserName = 'Google Chrome'
  else if (isSafari) browserName = 'Apple Safari'
  else if (isFirefox) browserName = 'Mozilla Firefox'
  else if (/Edg/i.test(ua)) browserName = 'Microsoft Edge'

  return {
    isIOS,
    isAndroid,
    isSafari,
    isChrome,
    isFirefox,
    isMobile,
    browserName,
  }
}

/**
 * Query current browser geolocation permission state
 */
export async function queryLocationPermissionState(): Promise<{
  state: LocationPermissionState
  permissionStatus: PermissionStatus | null
}> {
  if (typeof window === 'undefined' || !navigator || !navigator.geolocation) {
    return { state: 'unsupported', permissionStatus: null }
  }

  if (navigator.permissions && navigator.permissions.query) {
    try {
      const pStatus = await navigator.permissions.query({ name: 'geolocation' as PermissionName })
      return {
        state: pStatus.state as LocationPermissionState,
        permissionStatus: pStatus,
      }
    } catch {
      // Some browsers (e.g. Safari iOS) do not support querying 'geolocation' via Permissions API
      return { state: 'prompt', permissionStatus: null }
    }
  }

  return { state: 'prompt', permissionStatus: null }
}

/**
 * Actively request coordinates from the browser geolocation API
 */
export function requestCoordinates(
  options: {
    enableHighAccuracy?: boolean
    timeout?: number
    maximumAge?: number
  } = {}
): Promise<Coordinates> {
  return new Promise<Coordinates>((resolve, reject) => {
    if (typeof window === 'undefined' || !navigator || !navigator.geolocation) {
      reject({
        code: 'UNSUPPORTED',
        message: 'Geolocation is not supported by your device or browser.',
      } as GeolocationErrorDetails)
      return
    }

    const {
      enableHighAccuracy = true,
      timeout = 10000,
      maximumAge = 15000,
    } = options

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: Math.round(pos.coords.accuracy),
          timestamp: pos.timestamp,
        })
      },
      (err) => {
        let code: GeolocationErrorDetails['code'] = 'UNKNOWN'
        let message = err.message || 'Failed to acquire location coordinates.'

        if (err.code === 1) {
          code = 'PERMISSION_DENIED'
          message = 'Location permission was denied. Please allow location access in your browser settings.'
        } else if (err.code === 2) {
          code = 'POSITION_UNAVAILABLE'
          message = 'Location unavailable. Ensure your device GPS/Location Services are switched on.'
        } else if (err.code === 3) {
          code = 'TIMEOUT'
          message = 'GPS request timed out. Please check signal and retry.'
        }

        reject({ code, message } as GeolocationErrorDetails)
      },
      {
        enableHighAccuracy,
        timeout,
        maximumAge,
      }
    )
  })
}

/**
 * Report a Location Denied incident to company admins via backend endpoint
 */
export async function reportLocationDeniedAlert(
  apiBase: string,
  token: string | null,
  data: {
    activity: string
    shop_name?: string
    details?: string
    reference_id?: string
    reference_type?: string
    browser_name?: string
    is_mobile?: boolean
  }
): Promise<boolean> {
  if (!token) return false
  try {
    const res = await fetch(`${apiBase}/notifications/location-denied-alert`, {
      method: 'POST',
      headers: {
        ...authHeaders(token),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        activity: data.activity,
        shop_name: data.shop_name || null,
        details: data.details || null,
        reference_id: data.reference_id || null,
        reference_type: data.reference_type || 'visit',
        browser_name: data.browser_name || null,
        is_mobile: typeof data.is_mobile === 'boolean' ? data.is_mobile : null,
      }),
    })
    return res.ok
  } catch (err) {
    console.warn('[LocationAlert] Failed to notify admins of location denial:', err)
    return false
  }
}
