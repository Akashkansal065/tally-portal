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
