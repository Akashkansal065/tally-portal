import { API_BASE, authHeaders } from '@/lib/utils'

/* What invoice and statement PDFs show about the current company (Admin → Invoice design + Company profile).
   See docs/livekeeping-parity-plan.md, Phase 3. */

export interface Branding {
  company: {
    name: string
    address_lines: string[]
    state: string | null
    pincode: string | null
    phone: string | null
    email: string | null
    website: string | null
    gstin: string | null
    pan: string | null
    upi_id: string | null
  }
  logo: string | null
  signature: string | null
  bank: { account_name: string | null; bank_name: string | null; account_no: string | null; ifsc: string | null; branch: string | null }
  declaration: string
  show_upi_qr: boolean
}

export type BrandingUpdate = Partial<{
  logo: string
  signature: string
  bank_account_name: string
  bank_name: string
  bank_account_no: string
  bank_ifsc: string
  bank_branch: string
  declaration: string
  show_upi_qr: boolean
}>

// One request per company and token until branding is saved
const cache = new Map<string, Promise<Branding>>()

export function getBranding(token: string, companyId?: number): Promise<Branding> {
  const key = `${companyId ?? ''}:${token.slice(-12)}`
  let pending = cache.get(key)
  if (!pending) {
    pending = fetch(`${API_BASE}/branding`, { headers: authHeaders(token) }).then(async res => {
      if (!res.ok) throw new Error('Could not load the invoice design')
      return res.json() as Promise<Branding>
    })
    pending.catch(() => cache.delete(key))
    cache.set(key, pending)
  }
  return pending
}

/** Forget cached branding, e.g. after the company profile (name, GSTIN, UPI ID) changes. */
export function forgetBranding() {
  cache.clear()
}

export async function saveBranding(token: string, changes: BrandingUpdate): Promise<Branding> {
  const res = await fetch(`${API_BASE}/branding`, { method: 'PUT', headers: authHeaders(token), body: JSON.stringify(changes) })
  if (!res.ok) {
    let detail = 'Could not save'
    try { detail = (await res.json()).detail || detail } catch {}
    throw new Error(detail)
  }
  cache.clear()
  return res.json()
}

/** Read an image file, shrink it to fit maxWidth × maxHeight, and return a PNG (keeps transparency) or JPEG data URL. */
export function imageFileToDataUrl(file: File, maxWidth: number, maxHeight: number, maxChars: number): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!/^image\/(png|jpeg|jpg|webp)$/.test(file.type)) {
      reject(new Error('Choose a PNG or JPEG image.'))
      return
    }
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      const scale = Math.min(1, maxWidth / img.width, maxHeight / img.height)
      const canvas = document.createElement('canvas')
      canvas.width = Math.max(1, Math.round(img.width * scale))
      canvas.height = Math.max(1, Math.round(img.height * scale))
      const ctx = canvas.getContext('2d')
      if (!ctx) { reject(new Error('Could not read the image.')); return }
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
      let data = canvas.toDataURL('image/png')
      if (data.length > maxChars) data = canvas.toDataURL('image/jpeg', 0.85)
      if (data.length > maxChars) data = canvas.toDataURL('image/jpeg', 0.6)
      if (data.length > maxChars) { reject(new Error('That image is too large even after shrinking it.')); return }
      resolve(data)
    }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Could not read the image.')) }
    img.src = url
  })
}

/** NPCI UPI link for paying `amount` to the company's UPI ID. */
export function upiUri(upiId: string, payeeName: string, amount: number, note?: string): string {
  const params = new URLSearchParams({ pa: upiId, pn: payeeName, am: amount.toFixed(2), cu: 'INR' })
  if (note) params.set('tn', note.slice(0, 50))
  return `upi://pay?${params.toString()}`
}

/** PNG data URL of a QR code (for jsPDF), drawn from qrcode.react's SVG so no extra package is needed. */
export async function qrPngDataUrl(value: string, size = 240): Promise<string> {
  const [{ createElement }, { renderToStaticMarkup }, { QRCodeSVG }] = await Promise.all([
    import('react'), import('react-dom/server'), import('qrcode.react'),
  ])
  let svg = renderToStaticMarkup(createElement(QRCodeSVG, { value, size, level: 'M', marginSize: 2, bgColor: '#ffffff', fgColor: '#000000' }))
  // An SVG only loads as an image with its namespace
  if (!svg.includes('xmlns=')) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')
  const svgUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = size
      canvas.height = size
      const ctx = canvas.getContext('2d')
      if (!ctx) { reject(new Error('Canvas not available')); return }
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, size, size)
      ctx.drawImage(img, 0, 0, size, size)
      resolve(canvas.toDataURL('image/png'))
    }
    img.onerror = () => reject(new Error('Could not draw the QR code'))
    img.src = svgUrl
  })
}

/** Image size in mm that fits inside a box, keeping the aspect ratio. */
export function fitImage(dataUrl: string, maxW: number, maxH: number): Promise<{ w: number; h: number }> {
  return new Promise(resolve => {
    const img = new Image()
    img.onload = () => {
      const scale = Math.min(maxW / img.width, maxH / img.height)
      resolve({ w: img.width * scale, h: img.height * scale })
    }
    img.onerror = () => resolve({ w: maxW, h: maxH })
    img.src = dataUrl
  })
}
