'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useAuth } from '@/context/AuthContext'
import { API_BASE } from '@/lib/utils'
import {
  LocationPermissionState,
  Coordinates,
  DevicePlatformInfo,
  detectDevicePlatform,
  queryLocationPermissionState,
  requestCoordinates,
  reportLocationDeniedAlert,
} from '@/lib/location'

export interface UseLocationPermissionOptions {
  activityName?: string
  shopName?: string
  autoRequestOnMount?: boolean
  referenceType?: string
  referenceId?: string
}

export function useLocationPermission(options: UseLocationPermissionOptions = {}) {
  const {
    activityName = 'Shop Check-In',
    shopName,
    autoRequestOnMount = true,
    referenceType = 'visit',
    referenceId,
  } = options

  const { token } = useAuth()
  const [permissionState, setPermissionState] = useState<LocationPermissionState>('prompt')
  const [coords, setCoords] = useState<Coordinates | null>(null)
  const [isAcquiring, setIsAcquiring] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState<boolean>(false)
  const [platform, setPlatform] = useState<DevicePlatformInfo>(() => detectDevicePlatform())

  // Ref to track last alert timestamp to avoid spamming alerts in the same session
  const lastAlertTimeRef = useRef<number>(0)

  // Report denial to admins
  const sendAdminAlert = useCallback(
    async (customDetails?: string) => {
      const now = Date.now()
      // Minimum 60s client throttle between reports
      if (now - lastAlertTimeRef.current < 60000) return
      lastAlertTimeRef.current = now

      await reportLocationDeniedAlert(API_BASE, token, {
        activity: activityName,
        shop_name: shopName,
        details: customDetails || 'User denied location permission in browser.',
        reference_type: referenceType,
        reference_id: referenceId,
      })
    },
    [activityName, shopName, referenceType, referenceId, token]
  )

  // Check permission state and subscribe to changes
  useEffect(() => {
    let pStatus: PermissionStatus | null = null
    setPlatform(detectDevicePlatform())

    queryLocationPermissionState().then((res) => {
      setPermissionState(res.state)
      if (res.state === 'denied' && autoRequestOnMount) {
        setShowModal(true)
        sendAdminAlert('Location permission was found denied upon loading activity.')
      }

      if (res.permissionStatus) {
        pStatus = res.permissionStatus
        pStatus.onchange = () => {
          const nextState = pStatus?.state as LocationPermissionState
          setPermissionState(nextState)
          if (nextState === 'granted') {
            setShowModal(false)
            setError(null)
            // Auto acquire coords when permission changes to granted
            requestCoordinates({ enableHighAccuracy: true })
              .then((c) => setCoords(c))
              .catch(() => {})
          } else if (nextState === 'denied') {
            setShowModal(true)
            sendAdminAlert('User switched location permission to denied.')
          }
        }
      }
    })

    return () => {
      if (pStatus) {
        pStatus.onchange = null
      }
    }
  }, [autoRequestOnMount, sendAdminAlert])

  // Initial GPS warm-up on mount if permission is granted
  useEffect(() => {
    if (autoRequestOnMount) {
      queryLocationPermissionState().then((res) => {
        if (res.state === 'granted') {
          setIsAcquiring(true)
          requestCoordinates({ enableHighAccuracy: true })
            .then((c) => {
              setCoords(c)
              setError(null)
            })
            .catch((err) => {
              setError(err.message || 'Failed to acquire location.')
            })
            .finally(() => setIsAcquiring(false))
        }
      })
    }
  }, [autoRequestOnMount])

  // Explicitly request location (triggers browser prompt if promptable, or opens modal if denied)
  const requestLocation = useCallback(
    async (forceModalOnDenied: boolean = true): Promise<Coordinates | null> => {
      setIsAcquiring(true)
      setError(null)

      try {
        const c = await requestCoordinates({ enableHighAccuracy: true })
        setCoords(c)
        setPermissionState('granted')
        setShowModal(false)
        setIsAcquiring(false)
        return c
      } catch (err: any) {
        setIsAcquiring(false)
        if (err.code === 'PERMISSION_DENIED') {
          setPermissionState('denied')
          setError('Location permission was denied.')
          if (forceModalOnDenied) {
            setShowModal(true)
          }
          sendAdminAlert('User explicitly denied location access when prompted.')
        } else {
          setError(err.message || 'Failed to acquire GPS location.')
        }
        return null
      }
    },
    [sendAdminAlert]
  )

  // Guardrail function to ensure location is present before an action proceeds
  const ensureLocation = useCallback(
    async (actionDescription?: string): Promise<Coordinates | null> => {
      // 1. If we already have fresh coords, return them
      if (coords && coords.lat !== 0 && coords.lng !== 0) {
        return coords
      }

      // 2. If state is explicitly denied, open modal, alert admins, and block action
      if (permissionState === 'denied') {
        setShowModal(true)
        sendAdminAlert(
          `User attempted ${actionDescription || activityName} while location was denied.`
        )
        return null
      }

      // 3. Otherwise, try to request coordinates
      return await requestLocation(true)
    },
    [coords, permissionState, activityName, sendAdminAlert, requestLocation]
  )

  // Retry from inside the modal
  const retryLocation = useCallback(async (): Promise<boolean> => {
    setIsAcquiring(true)
    setError(null)
    try {
      const c = await requestCoordinates({ enableHighAccuracy: true, timeout: 8000 })
      setCoords(c)
      setPermissionState('granted')
      setShowModal(false)
      setError(null)
      setIsAcquiring(false)
      return true
    } catch (err: any) {
      setIsAcquiring(false)
      if (err.code === 'PERMISSION_DENIED') {
        setPermissionState('denied')
        setError(
          'Location is still blocked in your browser. Please follow the instructions above to allow location, then tap retry.'
        )
        sendAdminAlert('User tapped retry in modal but location is still blocked in browser.')
      } else {
        setError(err.message || 'Unable to retrieve GPS. Make sure your device location is enabled.')
      }
      return false
    }
  }, [sendAdminAlert])

  const closeModal = useCallback(() => {
    setShowModal(false)
  }, [])

  return {
    permissionState,
    coords,
    setCoords,
    isAcquiring,
    error,
    showModal,
    setShowModal,
    platform,
    requestLocation,
    ensureLocation,
    retryLocation,
    closeModal,
    sendAdminAlert,
  }
}
