import type { Branding } from '@/lib/branding'

/* Customer greeting cards (Phase 5), drawn on a canvas with the company's logo and details (Admin → Invoice
   design + Company profile), then shared to WhatsApp. 1080 × 1350 px, the size WhatsApp shows best. */

export type GreetingCategory = 'Festivals' | 'Personal' | 'Business'

export interface GreetingTemplate {
  id: string
  label: string
  category: GreetingCategory
  title: string
  message: string
  colors: [string, string] // background gradient, top → bottom
  ink: string // title colour
  accent: string // decoration colour
  pattern: 'rays' | 'confetti' | 'dots' | 'waves' | 'stars' | 'petals'
}

export const TEMPLATES: GreetingTemplate[] = [
  { id: 'diwali', label: 'Diwali', category: 'Festivals', title: 'Happy Diwali', message: 'May the festival of lights fill your home and business with joy, health and prosperity.', colors: ['#3b0764', '#9a3412'], ink: '#fde68a', accent: '#f59e0b', pattern: 'rays' },
  { id: 'holi', label: 'Holi', category: 'Festivals', title: 'Happy Holi', message: 'Wishing you a colourful Holi full of happiness and good times.', colors: ['#fdf2f8', '#e0f2fe'], ink: '#be185d', accent: '#8b5cf6', pattern: 'confetti' },
  { id: 'eid', label: 'Eid', category: 'Festivals', title: 'Eid Mubarak', message: 'May this Eid bring peace, happiness and prosperity to you and your family.', colors: ['#064e3b', '#065f46'], ink: '#fef3c7', accent: '#fcd34d', pattern: 'stars' },
  { id: 'christmas', label: 'Christmas', category: 'Festivals', title: 'Merry Christmas', message: 'Warm wishes for a joyful Christmas and a wonderful season.', colors: ['#7f1d1d', '#14532d'], ink: '#ffffff', accent: '#fca5a5', pattern: 'stars' },
  { id: 'new-year', label: 'New Year', category: 'Festivals', title: 'Happy New Year', message: 'Thank you for your trust this year. Wishing you success and happiness in the new year.', colors: ['#0f172a', '#1e3a8a'], ink: '#fde68a', accent: '#60a5fa', pattern: 'confetti' },
  { id: 'independence', label: 'Independence Day', category: 'Festivals', title: 'Happy Independence Day', message: 'Celebrating the spirit of freedom together. Jai Hind!', colors: ['#fff7ed', '#f0fdf4'], ink: '#1e3a8a', accent: '#f97316', pattern: 'waves' },
  { id: 'rakhi', label: 'Raksha Bandhan', category: 'Festivals', title: 'Happy Raksha Bandhan', message: 'Wishing you and your family a festival full of love and togetherness.', colors: ['#fff1f2', '#fef9c3'], ink: '#9f1239', accent: '#f59e0b', pattern: 'petals' },
  { id: 'birthday', label: 'Birthday', category: 'Personal', title: 'Happy Birthday', message: 'Wishing you a wonderful birthday and a great year ahead.', colors: ['#ecfeff', '#fdf4ff'], ink: '#7e22ce', accent: '#06b6d4', pattern: 'confetti' },
  { id: 'anniversary', label: 'Anniversary', category: 'Personal', title: 'Happy Anniversary', message: 'Warm wishes on your special day.', colors: ['#fdf2f8', '#fff7ed'], ink: '#9d174d', accent: '#fb7185', pattern: 'petals' },
  { id: 'thank-you', label: 'Thank you', category: 'Business', title: 'Thank You', message: 'Thank you for doing business with us. We truly value your support.', colors: ['#f0fdf4', '#ecfeff'], ink: '#065f46', accent: '#10b981', pattern: 'dots' },
  { id: 'miss-you', label: 'We miss you', category: 'Business', title: 'We Miss You!', message: "It's been a while! New stock has arrived and we'd love to serve you again.", colors: ['#eff6ff', '#f5f3ff'], ink: '#1d4ed8', accent: '#a78bfa', pattern: 'waves' },
  { id: 'new-stock', label: 'New stock', category: 'Business', title: 'New Stock Arrived', message: 'Fresh stock is in. Call or WhatsApp us to place your order.', colors: ['#fefce8', '#ecfccb'], ink: '#3f6212', accent: '#eab308', pattern: 'dots' },
]

export const CARD_WIDTH = 1080
export const CARD_HEIGHT = 1350

function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise(resolve => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

function wrap(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const lines: string[] = []
  let line = ''
  for (const word of text.split(/\s+/)) {
    const next = line ? `${line} ${word}` : word
    if (ctx.measureText(next).width > maxWidth && line) {
      lines.push(line)
      line = word
    } else {
      line = next
    }
  }
  if (line) lines.push(line)
  return lines
}

/** A small seeded random, so a card looks the same every time it's drawn */
function seeded(seed: string) {
  let h = 2166136261
  for (const c of seed) h = Math.imul(h ^ c.charCodeAt(0), 16777619)
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507)
    h = Math.imul(h ^ (h >>> 13), 3266489909)
    return ((h ^= h >>> 16) >>> 0) / 4294967296
  }
}

function drawPattern(ctx: CanvasRenderingContext2D, t: GreetingTemplate) {
  const W = CARD_WIDTH, H = CARD_HEIGHT
  const rand = seeded(t.id)
  ctx.save()
  ctx.globalAlpha = 0.35
  ctx.fillStyle = t.accent
  ctx.strokeStyle = t.accent
  if (t.pattern === 'rays') {
    ctx.translate(W / 2, 330)
    for (let i = 0; i < 36; i++) {
      ctx.rotate((Math.PI * 2) / 36)
      ctx.beginPath()
      ctx.moveTo(0, 0)
      ctx.lineTo(-18, -700)
      ctx.lineTo(18, -700)
      ctx.closePath()
      ctx.globalAlpha = i % 2 ? 0.12 : 0.22
      ctx.fill()
    }
  } else if (t.pattern === 'confetti') {
    for (let i = 0; i < 90; i++) {
      ctx.save()
      ctx.translate(rand() * W, rand() * H * 0.7)
      ctx.rotate(rand() * Math.PI)
      ctx.fillStyle = [t.accent, t.ink, '#f59e0b', '#22c55e'][i % 4]
      ctx.fillRect(-10, -4, 20, 8)
      ctx.restore()
    }
  } else if (t.pattern === 'dots') {
    for (let x = 40; x < W; x += 80) for (let y = 40; y < H * 0.72; y += 80) {
      ctx.beginPath()
      ctx.arc(x, y, 6, 0, Math.PI * 2)
      ctx.fill()
    }
  } else if (t.pattern === 'waves') {
    ctx.lineWidth = 10
    for (let k = 0; k < 6; k++) {
      ctx.beginPath()
      for (let x = 0; x <= W; x += 20) ctx.lineTo(x, 120 + k * 120 + Math.sin(x / 90 + k) * 30)
      ctx.stroke()
    }
  } else if (t.pattern === 'stars') {
    for (let i = 0; i < 60; i++) {
      const x = rand() * W, y = rand() * H * 0.7, r = 4 + rand() * 10
      ctx.beginPath()
      for (let p = 0; p < 10; p++) {
        const a = (p * Math.PI) / 5, rr = p % 2 ? r / 2.5 : r
        ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr)
      }
      ctx.closePath()
      ctx.fill()
    }
  } else if (t.pattern === 'petals') {
    for (let i = 0; i < 40; i++) {
      ctx.save()
      ctx.translate(rand() * W, rand() * H * 0.7)
      ctx.rotate(rand() * Math.PI)
      ctx.beginPath()
      ctx.ellipse(0, 0, 26, 11, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()
    }
  }
  ctx.restore()
}

/** Draw the card; returns the canvas. `name` personalises it ("Dear Gupta Electricals"). */
export async function drawGreeting(t: GreetingTemplate, branding: Branding | null, message: string, name?: string): Promise<HTMLCanvasElement> {
  const W = CARD_WIDTH, H = CARD_HEIGHT
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!
  const bg = ctx.createLinearGradient(0, 0, 0, H)
  bg.addColorStop(0, t.colors[0])
  bg.addColorStop(1, t.colors[1])
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, W, H)
  drawPattern(ctx, t)

  const font = (weight: number, size: number) => `${weight} ${size}px Outfit, system-ui, -apple-system, "Segoe UI", sans-serif`
  ctx.textAlign = 'center'
  ctx.fillStyle = t.ink
  ctx.font = font(800, 104)
  let y = 330
  for (const line of wrap(ctx, t.title, W - 140)) {
    ctx.fillText(line, W / 2, y)
    y += 116
  }
  y += 30
  if (name) {
    ctx.font = font(600, 48)
    ctx.fillText(`Dear ${name},`, W / 2, y)
    y += 80
  }
  ctx.font = font(400, 44)
  for (const line of wrap(ctx, message, W - 200).slice(0, 6)) {
    ctx.fillText(line, W / 2, y)
    y += 62
  }

  // Footer band with the business's branding
  const bandTop = H - 300
  ctx.fillStyle = 'rgba(255,255,255,0.94)'
  ctx.fillRect(0, bandTop, W, 300)
  ctx.fillStyle = t.accent
  ctx.fillRect(0, bandTop, W, 10)
  const c = branding?.company
  let textX = 70
  ctx.textAlign = 'left'
  if (branding?.logo) {
    const logo = await loadImage(branding.logo)
    if (logo) {
      const scale = Math.min(180 / logo.width, 180 / logo.height)
      const w = logo.width * scale, h = logo.height * scale
      ctx.drawImage(logo, 70, bandTop + 60 + (180 - h) / 2, w, h)
      textX = 70 + w + 40
    }
  }
  ctx.fillStyle = '#0f172a'
  ctx.font = font(800, 54)
  ctx.fillText(c?.name || '', textX, bandTop + 110, W - textX - 60)
  ctx.font = font(400, 34)
  ctx.fillStyle = '#334155'
  const details = [
    [c?.phone && `📞 ${c.phone}`, c?.email].filter(Boolean).join('   '),
    [...(c?.address_lines || []), c?.pincode].filter(Boolean).join(', '),
  ].filter(Boolean)
  details.forEach((line, i) => ctx.fillText(line as string, textX, bandTop + 170 + i * 50, W - textX - 60))
  return canvas
}

export function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => canvas.toBlob(b => (b ? resolve(b) : reject(new Error('Could not make the image'))), 'image/png'))
}
