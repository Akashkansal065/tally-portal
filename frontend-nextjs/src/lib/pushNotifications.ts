import { API_BASE, authHeaders } from '@/lib/utils'

/**
 * Convert a URL-safe Base64 string to a Uint8Array for PushManager subscription.
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/')

  const rawData = window.atob(base64)
  const outputArray = new Uint8Array(rawData.length)

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}

export function isPushNotificationSupported(): boolean {
  if (typeof window === 'undefined') return false
  return (
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

export function isIOS(): boolean {
  if (typeof window === 'undefined') return false
  return (
    /iPad|iPhone|iPod/.test(navigator.userAgent) || 
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  )
}

export function isStandalone(): boolean {
  if (typeof window === 'undefined') return false
  return (
    (window.navigator as unknown as { standalone?: boolean }).standalone === true ||
    window.matchMedia('(display-mode: standalone)').matches
  )
}

export function getNotificationPermission(): NotificationPermission {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return 'default'
  }
  return Notification.permission
}

/**
 * Check if the current device/browser is already subscribed to push notifications.
 */
export async function isCurrentDeviceSubscribed(): Promise<boolean> {
  if (!isPushNotificationSupported()) return false
  try {
    const reg = await Promise.race([
      navigator.serviceWorker.ready,
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 2500))
    ])
    if (!reg) return false
    const sub = await reg.pushManager.getSubscription()
    return !!sub
  } catch {
    return false
  }
}

/**
 * Request notification permission, register with Apple/Google push servers,
 * and sync subscription with the MyTally backend.
 */
export async function subscribeToPushNotifications(
  token: string
): Promise<{ success: boolean; message: string }> {
  if (typeof window === 'undefined') {
    return { success: false, message: 'Browser window is undefined.' }
  }

  // Handle iOS specific requirement: Apple requires web app to be saved to Home Screen
  if (isIOS() && !isStandalone()) {
    return {
      success: false,
      message: 'On iPhone/iPad, Apple requires saving to Home Screen first. Tap Safari’s Share button -> "Add to Home Screen", then open from your Home Screen to enable alerts.'
    }
  }

  if (!isPushNotificationSupported()) {
    return {
      success: false,
      message: 'Push notifications are not supported by this browser.'
    }
  }

  try {
    // 1. Request permission synchronously on user gesture
    let permission: NotificationPermission = Notification.permission
    if (permission !== 'granted') {
      try {
        const permResult = Notification.requestPermission()
        if (permResult && typeof permResult.then === 'function') {
          permission = await Promise.race([
            permResult,
            new Promise<NotificationPermission>((_, reject) => 
              setTimeout(() => reject(new Error('Permission prompt timed out')), 20000)
            )
          ])
        } else {
          permission = await new Promise<NotificationPermission>((resolve) => {
            Notification.requestPermission((p) => resolve(p))
          })
        }
      } catch (err) {
        console.warn('Notification permission request error:', err)
        permission = Notification.permission
      }
    }

    if (permission !== 'granted') {
      return {
        success: false,
        message: permission === 'denied' 
          ? 'Notification permission was denied. Please allow notifications in device settings.'
          : 'Notification permission was not granted.'
      }
    }

    // 2. Ensure Service Worker is registered & ready
    try {
      await navigator.serviceWorker.register('/sw.js', { scope: '/' })
    } catch (e) {
      console.warn('Direct SW register error:', e)
    }

    // Wait for SW ready with a 6-second timeout so it NEVER hangs indefinitely
    const readyPromise = navigator.serviceWorker.ready
    const timeoutPromise = new Promise<ServiceWorkerRegistration>((_, reject) =>
      setTimeout(() => reject(new Error('Service Worker took too long to activate. Please refresh and try again.')), 6000)
    )
    const reg = await Promise.race([readyPromise, timeoutPromise])

    if (!reg) {
      throw new Error('Could not obtain an active Service Worker.')
    }

    // 3. Fetch VAPID public key with 8-second timeout
    const controller = new AbortController()
    const fetchTimer = setTimeout(() => controller.abort(), 8000)
    const vapidRes = await fetch(`${API_BASE}/notifications/vapid-public-key`, {
      headers: authHeaders(token),
      signal: controller.signal
    }).finally(() => clearTimeout(fetchTimer))

    if (!vapidRes.ok) {
      throw new Error('Failed to retrieve push encryption key from server.')
    }
    const { public_key } = await vapidRes.json()
    if (!public_key) {
      throw new Error('VAPID public key missing from server response.')
    }

    // 4. Subscribe to PushManager
    const applicationServerKey = urlBase64ToUint8Array(public_key)
    let subscription = await reg.pushManager.getSubscription()
    
    if (!subscription) {
      try {
        subscription = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: applicationServerKey as unknown as BufferSource
        })
      } catch (subErr) {
        console.warn('Subscribe with Uint8Array failed, retrying with ArrayBuffer:', subErr)
        subscription = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: applicationServerKey.buffer as unknown as BufferSource
        })
      }
    }

    const subJson = subscription.toJSON()
    if (!subJson.endpoint || !subJson.keys?.p256dh || !subJson.keys?.auth) {
      throw new Error('Browser returned an incomplete push subscription.')
    }

    // 5. Send subscription to MyTally backend with 10-second timeout
    const saveController = new AbortController()
    const saveTimer = setTimeout(() => saveController.abort(), 10000)
    const saveRes = await fetch(`${API_BASE}/notifications/subscribe`, {
      method: 'POST',
      headers: {
        ...authHeaders(token),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        endpoint: subJson.endpoint,
        keys: {
          p256dh: subJson.keys.p256dh,
          auth: subJson.keys.auth
        },
        user_agent: typeof navigator !== 'undefined' ? navigator.userAgent.slice(0, 255) : null
      }),
      signal: saveController.signal
    }).finally(() => clearTimeout(saveTimer))

    if (!saveRes.ok) {
      const err = await saveRes.json().catch(() => ({}))
      throw new Error(err.detail || 'Failed to save push subscription on server.')
    }

    return {
      success: true,
      message: 'Mobile alerts enabled! You will now receive notifications anytime.'
    }
  } catch (err: unknown) {
    console.error('[PushNotifications] Subscription error:', err)
    return {
      success: false,
      message: err instanceof Error ? err.message : 'An error occurred while enabling push notifications.'
    }
  }
}

/**
 * Unsubscribe current device from push notifications.
 */
export async function unsubscribeFromPushNotifications(
  token: string
): Promise<{ success: boolean; message: string }> {
  try {
    if (!isPushNotificationSupported()) return { success: true, message: 'Not supported' }
    const reg = await navigator.serviceWorker.ready
    const sub = await reg.pushManager.getSubscription()
    if (sub) {
      const endpoint = sub.endpoint
      await sub.unsubscribe()
      await fetch(`${API_BASE}/notifications/unsubscribe`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ endpoint })
      }).catch(() => null)
    }
    return { success: true, message: 'Push notifications disabled on this device.' }
  } catch (err) {
    console.error('[PushNotifications] Unsubscribe error:', err)
    return { success: false, message: 'Failed to disable push notifications.' }
  }
}

/**
 * Send an immediate test notification to verify device alerts.
 */
export async function sendTestPushNotification(
  token: string
): Promise<{ success: boolean; message: string; devices_notified?: number }> {
  try {
    const res = await fetch(`${API_BASE}/notifications/test-push`, {
      method: 'POST',
      headers: authHeaders(token)
    })
    const data = await res.json()
    return data
  } catch {
    return { success: false, message: 'Network error sending test push notification.' }
  }
}
