import { isNativePlatform } from './capacitor'

/**
 * Shares plain text through the phone's share sheet (WhatsApp, SMS, ...). In the app that's the native sheet;
 * in a browser it's the Web Share sheet where available, otherwise the text is copied to the clipboard.
 */
export async function shareText(title: string, text: string): Promise<'shared' | 'copied' | 'cancelled'> {
  if (isNativePlatform()) {
    const { Share } = await import('@capacitor/share')
    try {
      await Share.share({ title, text, dialogTitle: title })
      return 'shared'
    } catch {
      return 'cancelled'
    }
  }
  if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
    try {
      await navigator.share({ title, text })
      return 'shared'
    } catch {
      return 'cancelled'
    }
  }
  await navigator.clipboard.writeText(text)
  return 'copied'
}
