'use client'

import { useEffect, useState, useSyncExternalStore } from 'react'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { isNativePlatform } from '@/lib/capacitor'
import {
  getNotificationPermission,
  isCurrentDeviceSubscribed,
  isIOS,
  isPushNotificationSupported,
  isStandalone,
  prefetchVapidKey,
  sendTestPushNotification,
  subscribeToPushNotifications,
} from '@/lib/pushNotifications'

const noSubscribe = () => () => {}

/** Browser support never changes during a visit; read it on the client, assume "no" while server-rendering. */
function useBrowserFlag(read: () => boolean) {
  return useSyncExternalStore(noSubscribe, read, () => false)
}

/**
 * Device (push) alerts for this browser: whether they're possible, on, or blocked, plus enabling them and
 * sending a test. The Android app gets alerts through native push instead (see NativePushRegistrar).
 */
export function usePushAlerts() {
  const { token } = useAuth()
  const native = useBrowserFlag(isNativePlatform)
  const supported = useBrowserFlag(isPushNotificationSupported) && !native
  const iosBrowser = useBrowserFlag(() => isIOS() && !isStandalone()) && !native
  const browserPermission = useSyncExternalStore(noSubscribe, getNotificationPermission, () => 'default' as NotificationPermission)
  const [permission, setPermission] = useState<NotificationPermission | null>(null)
  const [subscribed, setSubscribed] = useState(false)
  const [enabling, setEnabling] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!supported) return
    isCurrentDeviceSubscribed().then(setSubscribed).catch(() => {})
    if (token) prefetchVapidKey(token).catch(() => null)
  }, [supported, token])

  const enable = async () => {
    if (!token) return
    setEnabling(true)
    setError(null)
    const safetyTimer = setTimeout(() => {
      setEnabling(false)
      setError('Alert setup timed out. Please check phone notification settings.')
    }, 15000)
    try {
      const result = await subscribeToPushNotifications(token)
      if (result.success) {
        setSubscribed(true)
        setPermission('granted')
        toast.success(result.message || 'Device alerts are on.')
      } else {
        setPermission(getNotificationPermission())
        setError(result.message)
        toast.error(result.message)
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to enable notifications'
      setError(msg)
      toast.error(msg)
    } finally {
      clearTimeout(safetyTimer)
      setEnabling(false)
    }
  }

  const sendTest = async () => {
    if (!token) return
    setTesting(true)
    try {
      const result = await sendTestPushNotification(token)
      if (result.success) toast.success(result.message || 'Test alert sent. Check your lock screen.')
      else toast.error(result.message)
    } catch {
      toast.error('Failed to send test alert')
    } finally {
      setTesting(false)
    }
  }

  return {
    native,
    supported,
    iosBrowser,
    permission: permission ?? browserPermission,
    subscribed,
    enabling,
    testing,
    error,
    enable,
    sendTest,
  }
}
