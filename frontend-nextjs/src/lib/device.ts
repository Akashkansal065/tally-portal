import { getPlatform, isNativePlatform } from '@/lib/capacitor'

/**
 * Identifies this device to the backend at login (see backend app/core/sessions.py).
 * The server records it so admins and the user can see, sign out and block devices.
 */

const WEB_DEVICE_ID_KEY = 'mytally_device_id'
const DEVICE_ID_PATTERN = /^[A-Za-z0-9._:-]{8,64}$/

let headersPromise: Promise<Record<string, string>> | null = null

/** Device headers for /auth/login. Never rejects: login works without them. */
export function getDeviceHeaders(): Promise<Record<string, string>> {
  if (!headersPromise) {
    headersPromise = buildDeviceHeaders().catch((err) => {
      console.warn('[device] Could not read device details:', err)
      headersPromise = null
      return {}
    })
  }
  return headersPromise
}

async function buildDeviceHeaders(): Promise<Record<string, string>> {
  if (typeof window === 'undefined') return {}

  if (isNativePlatform()) {
    const platform = getPlatform() // 'android' | 'ios'
    const { Device } = await import('@capacitor/device')
    const [{ identifier }, info] = await Promise.all([Device.getId(), Device.getInfo()])
    const headers: Record<string, string> = {
      'X-Client-Type': platform,
      // Phones under 600dp on their short side; larger screens are tablets
      'X-Device-Type': Math.min(window.screen.width, window.screen.height) >= 600 ? 'tablet' : 'mobile',
    }
    const nativeId = `${platform}-${identifier}`.replace(/[^A-Za-z0-9._:-]/g, '').slice(0, 64)
    if (DEVICE_ID_PATTERN.test(nativeId)) headers['X-Device-Id'] = nativeId
    const manufacturer = info.manufacturer ? info.manufacturer.charAt(0).toUpperCase() + info.manufacturer.slice(1) : ''
    const name = [manufacturer, info.model].filter(Boolean).join(' ').trim()
    if (name) headers['X-Device-Name'] = name.slice(0, 120)
    try {
      const { App } = await import('@capacitor/app')
      headers['X-App-Version'] = (await App.getInfo()).version.slice(0, 30)
    } catch {}
    return headers
  }

  return { 'X-Device-Id': webDeviceId(), 'X-Client-Type': 'web' }
}

function randomId(): string {
  // crypto.getRandomValues works on plain-HTTP LAN dev servers too (randomUUID needs a secure context)
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

function webDeviceId(): string {
  try {
    const saved = localStorage.getItem(WEB_DEVICE_ID_KEY)
    if (saved && DEVICE_ID_PATTERN.test(saved)) return saved
    const created = `web-${randomId()}`
    localStorage.setItem(WEB_DEVICE_ID_KEY, created)
    return created
  } catch {
    return `web-${randomId()}`
  }
}

/** What to tell the user when the server ends their session (X-Auth-Reason header). */
export function signOutMessage(reason: string | null): string {
  switch (reason) {
    case 'admin_revoke':
    case 'admin_revoke_all':
      return 'An administrator signed you out of this device.'
    case 'blocked':
      return 'This device has been blocked. Contact your administrator.'
    case 'password_change':
      return 'Your password was changed. Sign in again.'
    case 'deactivated':
      return 'Your account has been deactivated. Contact your administrator.'
    case 'device_limit':
      return 'You were signed out because you signed in on another device.'
    case 'self_revoke':
      return 'This device was signed out from another device.'
    default:
      return 'Your session has ended. Sign in again.'
  }
}
