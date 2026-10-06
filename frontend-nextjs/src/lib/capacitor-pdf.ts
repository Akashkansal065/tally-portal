import { isNativePlatform } from './capacitor'
import type jsPDF from 'jspdf'

/**
 * Safely saves or shares a jsPDF document.
 * - On Web (Desktop/Mobile Browser): downloads via doc.save(filename).
 * - On Native (Android/iOS): saves to cache and presents the native Android Share sheet
 *   (enabling instant WhatsApp sharing, Save to Downloads, Drive, or Print).
 */
export function saveOrSharePdf(doc: jsPDF, filename: string): void {
  if (typeof window === 'undefined') return

  if (isNativePlatform()) {
    Promise.all([
      import('@capacitor/filesystem'),
      import('@capacitor/share'),
    ])
      .then(([{ Filesystem, Directory }, { Share }]) => {
        const dataUri = doc.output('datauristring')
        const base64Data = dataUri.split(',')[1]

        return Filesystem.writeFile({
          path: filename,
          data: base64Data,
          directory: Directory.Cache,
        }).then((writeResult) => {
          return Share.share({
            title: filename,
            text: `Exported ${filename} from MyTally`,
            url: writeResult.uri,
            dialogTitle: 'Save or Share PDF',
          })
        })
      })
      .catch((err) => {
        console.warn('[saveOrSharePdf] Native share failed, falling back to doc.save():', err)
        doc.save(filename)
      })
    return
  }

  doc.save(filename)
}

/**
 * Share a PDF to WhatsApp, email apps, Drive...: the Android share sheet in the app, the Web Share API in mobile
 * browsers that can share files, otherwise a normal download. Resolves to what happened.
 */
export async function sharePdf(doc: jsPDF, filename: string, text?: string): Promise<'shared' | 'downloaded' | 'cancelled'> {
  if (typeof window === 'undefined') return 'cancelled'
  if (isNativePlatform()) {
    try {
      const [{ Filesystem, Directory }, { Share }] = await Promise.all([import('@capacitor/filesystem'), import('@capacitor/share')])
      const base64Data = doc.output('datauristring').split(',')[1]
      const written = await Filesystem.writeFile({ path: filename, data: base64Data, directory: Directory.Cache })
      await Share.share({ title: filename, text, url: written.uri, dialogTitle: 'Share PDF' })
      return 'shared'
    } catch {
      return 'cancelled'
    }
  }
  const file = new File([doc.output('blob')], filename, { type: 'application/pdf' })
  if (typeof navigator.canShare === 'function' && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: filename, text })
      return 'shared'
    } catch (e) {
      // AbortError: the person closed the share sheet
      if (e instanceof DOMException && e.name === 'AbortError') return 'cancelled'
    }
  }
  doc.save(filename)
  return 'downloaded'
}

/** Share a file (greeting card image, report CSV…) the same way as sharePdf: share sheet in the app or mobile
 *  browsers, otherwise a download. */
export async function shareFile(blob: Blob, filename: string, text?: string): Promise<'shared' | 'downloaded' | 'cancelled'> {
  if (typeof window === 'undefined') return 'cancelled'
  if (isNativePlatform()) {
    try {
      const [{ Filesystem, Directory }, { Share }] = await Promise.all([import('@capacitor/filesystem'), import('@capacitor/share')])
      const base64Data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result).split(',')[1])
        reader.onerror = () => reject(reader.error)
        reader.readAsDataURL(blob)
      })
      const written = await Filesystem.writeFile({ path: filename, data: base64Data, directory: Directory.Cache })
      await Share.share({ title: filename, text, url: written.uri, dialogTitle: 'Share' })
      return 'shared'
    } catch {
      return 'cancelled'
    }
  }
  const file = new File([blob], filename, { type: blob.type || 'application/octet-stream' })
  if (typeof navigator.canShare === 'function' && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], text })
      return 'shared'
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return 'cancelled'
    }
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
  return 'downloaded'
}
