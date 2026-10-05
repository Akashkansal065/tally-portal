'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Capacitor, registerPlugin } from '@capacitor/core'
import { toast } from 'sonner'
import { useAuth } from '@/context/AuthContext'
import { isNativePlatform, getPlatform } from '@/lib/capacitor'
import { getDeviceHeaders } from '@/lib/device'
import { announceNotificationsChanged } from '@/lib/notifications'
import { syncExistingSubscription } from '@/lib/pushNotifications'
import { API_BASE, authHeaders } from '@/lib/utils'

/** Native check (PushSetupPlugin.java): whether this app build includes Firebase. */
const PushSetup = registerPlugin<{ status(): Promise<{ firebase: boolean }> }>('PushSetup')

/** Must match ANDROID_CHANNEL_ID in backend/app/services/fcm.py */
const CHANNEL_ID = 'mytally_alerts'

/**
 * Registers this device for lock-screen alerts once someone is signed in.
 * Browser: re-saves an existing push subscription (signing out removes it on the server).
 * Android app: asks for notification permission, registers with Firebase and sends the token to the server;
 * tapping an alert opens its notification. Builds without Firebase are skipped, since registering would crash.
 */
export function PushRegistration() {
  const router = useRouter()
  const { token } = useAuth()

  useEffect(() => {
    if (!token) return
    if (!isNativePlatform()) {
      syncExistingSubscription(token).catch(() => {})
      return
    }

    let cancelled = false
    const removers: Array<() => Promise<void>> = []

    const setUp = async () => {
      if (!Capacitor.isPluginAvailable('PushNotifications') || !Capacitor.isPluginAvailable('PushSetup')) return
      const { firebase } = await PushSetup.status()
      if (!firebase || cancelled) return

      const { PushNotifications } = await import('@capacitor/push-notifications')
      let permission = await PushNotifications.checkPermissions()
      if (permission.receive === 'prompt' || permission.receive === 'prompt-with-rationale') {
        permission = await PushNotifications.requestPermissions()
      }
      if (permission.receive !== 'granted' || cancelled) return

      if (getPlatform() === 'android') {
        await PushNotifications.createChannel({
          id: CHANNEL_ID, name: 'Alerts', description: 'Approvals, orders, attendance and other alerts',
          importance: 4, visibility: 1, sound: 'default',
        })
      }

      const handles = await Promise.all([
        PushNotifications.addListener('registration', async ({ value }) => {
          await fetch(`${API_BASE}/notifications/native-token`, {
            method: 'POST',
            headers: { ...authHeaders(token), ...(await getDeviceHeaders()) },
            body: JSON.stringify({ token: value, platform: getPlatform() === 'ios' ? 'ios' : 'android' }),
          }).catch(() => {})
        }),
        PushNotifications.addListener('registrationError', err => {
          console.warn('[push] Registration failed:', err.error)
        }),
        // Tapped an alert (also delivered after a cold start)
        PushNotifications.addListener('pushNotificationActionPerformed', ({ notification }) => {
          const url = notification.data?.url
          if (typeof url === 'string' && url.startsWith('/')) router.push(url)
        }),
        // Arrived while the app is open: Android shows nothing, so show it in the app
        PushNotifications.addListener('pushNotificationReceived', notification => {
          announceNotificationsChanged()
          const url = notification.data?.url
          toast(notification.title || 'New notification', {
            description: notification.body,
            action: typeof url === 'string' && url.startsWith('/')
              ? { label: 'Open', onClick: () => router.push(url) }
              : undefined,
          })
        }),
      ])
      removers.push(...handles.map(h => () => h.remove()))
      if (!cancelled) await PushNotifications.register()
    }

    setUp().catch(err => console.warn('[push] Setup failed:', err))
    return () => {
      cancelled = true
      removers.forEach(remove => remove().catch(() => {}))
    }
  }, [token, router])

  return null
}
