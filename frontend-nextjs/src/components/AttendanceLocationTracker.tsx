'use client'

import { useEffect, useRef } from 'react'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'

const PING_INTERVAL_MS = 10 * 60 * 1000 // Ping every 10 minutes while active
const MIN_THROTTLE_MS = 3 * 60 * 1000  // At least 3 minutes between pings

export function AttendanceLocationTracker() {
  const { token, user } = useAuth()
  const isAuthenticated = Boolean(token && user)
  const lastPingRef = useRef<number>(0)
  const isPingingRef = useRef<boolean>(false)
  const shiftCheckedRef = useRef<boolean>(false)

  const sendPing = async () => {
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
  }

  useEffect(() => {
    if (!isAuthenticated || !token) return

    // Trigger initial check/ping shortly after mount
    const initialTimer = setTimeout(() => {
      sendPing()
    }, 4000)

    // Periodic ping timer
    const intervalId = setInterval(() => {
      sendPing()
    }, PING_INTERVAL_MS)

    // Ping on tab visibility restore
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
  }, [isAuthenticated, token])

  return null
}
