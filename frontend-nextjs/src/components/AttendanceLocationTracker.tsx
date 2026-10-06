'use client'

import { useEffect, useRef, useCallback } from 'react'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'

import { isNativePlatform } from '@/lib/capacitor'
import {
  startNativeBackgroundTracking,
  stopNativeBackgroundTracking,
} from '@/lib/capacitor-bg-geo'
import {
  startHeadlessNativeTracking,
  stopHeadlessNativeTracking,
  requestNativeBatteryExemption,
} from '@/lib/capacitor-native-tracking'

const PING_INTERVAL_MS = 2 * 60 * 1000 // Ping every 2 minutes while the tab is open during an active shift
const MIN_THROTTLE_MS = 30 * 1000  // At least 30 seconds between web pings (tab switches also ping)

/** Whether today's shift is punched in and not out. Asks the server; offline, trusts what this device last saw. */
async function shiftIsOpen(token: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/attendance/today`, { headers: authHeaders(token) })
    if (!res.ok) return localStorage.getItem('mytally_shift_active') === '1'
    const data = await res.json()
    const open = Boolean(data?.attendance && !data.attendance.checkOutTime)
    if (open) localStorage.setItem('mytally_shift_active', '1')
    else localStorage.removeItem('mytally_shift_active')
    return open
  } catch {
    return localStorage.getItem('mytally_shift_active') === '1'
  }
}

export function AttendanceLocationTracker() {
  const { token, user } = useAuth()
  const isAuthenticated = Boolean(token && user)
  const lastPingRef = useRef<number>(0)
  const isPingingRef = useRef<boolean>(false)
  const shiftCheckedRef = useRef<boolean>(false)

  const sendPing = useCallback(async () => {
    if (!isAuthenticated || !token) return
    if (typeof window === 'undefined' || !navigator.geolocation) return

    // Throttle check
    const now = Date.now()
    if (now - lastPingRef.current < MIN_THROTTLE_MS) return
    if (isPingingRef.current) return

    // Check if active shift is marked; if not checked yet, verify with server
    let isActiveShift = localStorage.getItem('mytally_shift_active') === '1'
    if (!isActiveShift && !shiftCheckedRef.current) {
      shiftCheckedRef.current = true
      try {
        const checkRes = await fetch(`${API_BASE}/attendance/today`, {
          headers: authHeaders(token),
        })
        if (checkRes.ok) {
          const data = await checkRes.json()
          if (data?.attendance && !data.attendance.checkOutTime) {
            isActiveShift = true
            localStorage.setItem('mytally_shift_active', '1')
          } else {
            localStorage.removeItem('mytally_shift_active')
            return
          }
        }
      } catch {
        return
      }
    }

    if (!isActiveShift) return

    isPingingRef.current = true

    try {
      // If browser supports permissions query, verify we won't show an intrusive prompt
      if (typeof navigator !== 'undefined' && 'permissions' in navigator && navigator.permissions?.query) {
        try {
          const perm = await navigator.permissions.query({ name: 'geolocation' as PermissionName })
          if (perm.state !== 'granted') {
            isPingingRef.current = false
            return
          }
        } catch {
          // Permissions query failed (e.g. Safari), proceed with fallback
        }
      }

      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            lastPingRef.current = Date.now()
            const payload = {
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
              accuracyMeters: pos.coords.accuracy ?? null,
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
              const data = await res.json()
              if (data && data.active === false) {
                // Server indicated shift is closed
                localStorage.removeItem('mytally_shift_active')
              }
            }
          } catch (err) {
            console.debug('[AttendanceLocationTracker] Ping failed:', err)
          } finally {
            isPingingRef.current = false
          }
        },
        (err) => {
          console.debug('[AttendanceLocationTracker] Geolocation error:', err.message)
          isPingingRef.current = false
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000,
        }
      )
    } catch {
      isPingingRef.current = false
    }
  }, [isAuthenticated, token])

  useEffect(() => {
    if (!isAuthenticated || !token) return

    // 🟢 NATIVE PLATFORM: Start background geolocation service
    if (isNativePlatform()) {
      // Track only during an open shift. Without this every signed-in user was tracked from app launch, and a
      // shift left marked open on the phone kept restarting the service.
      shiftIsOpen(token).then((open) => {
        if (!open) {
          stopHeadlessNativeTracking().catch(() => {})
          return
        }

        // 1. Request battery optimization exemption (so Android never kills process in deep sleep)
        requestNativeBatteryExemption().catch(() => {})

        // 2. Track with the pure native Java service, which survives app force-close/swiping. The Capacitor
        //    watcher is only a fallback (iOS, no location permission yet, or the service failed to start): running
        //    both doubled every ping. The watcher asks for location permission; the next launch uses the service.
        return startHeadlessNativeTracking(token)
          .catch(() => false)
          .then((nativeStarted) => {
            if (nativeStarted) return
            return startNativeBackgroundTracking(token).catch((err) => {
              console.warn('[AttendanceLocationTracker] Native tracking init failed, falling back to web ping:', err)
              sendPing()
            })
          })
      })

      return () => {
        // Do not stop service on unmount while shift is active
      }
    }

    // 🟡 WEB / PWA PLATFORM: Periodic ping while tab is open/active
    const initialTimer = setTimeout(() => {
      sendPing()
    }, 4000)

    const intervalId = setInterval(() => {
      sendPing()
    }, PING_INTERVAL_MS)

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        sendPing()
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      clearTimeout(initialTimer)
      clearInterval(intervalId)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [isAuthenticated, token, sendPing])

  return null
}
