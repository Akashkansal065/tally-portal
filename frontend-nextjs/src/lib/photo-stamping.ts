import { formatDate } from './utils'

export interface StampingResult {
  photoBase64: string
  lat: number | null
  lng: number | null
  address: string | null
}

const drawFallbackMap = (ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number) => {
  ctx.fillStyle = '#1e293b'
  ctx.beginPath()
  ctx.roundRect?.(x, y, w, h, 8)
  ctx.fill()

  ctx.strokeStyle = 'rgba(16, 185, 129, 0.3)'
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.arc(x + w / 2, y + h / 2, 20, 0, Math.PI * 2)
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(x + w / 2, y + h / 2, 40, 0, Math.PI * 2)
  ctx.stroke()

  ctx.fillStyle = '#ef4444'
  ctx.beginPath()
  const pinX = x + w / 2
  const pinY = y + h / 2 - 5
  ctx.arc(pinX, pinY, 6, 0, Math.PI, true)
  ctx.lineTo(pinX, pinY + 12)
  ctx.closePath()
  ctx.fill()

  ctx.fillStyle = '#ffffff'
  ctx.beginPath()
  ctx.arc(pinX, pinY, 2.5, 0, Math.PI * 2)
  ctx.fill()
}

export async function stampPhoto(file: File): Promise<StampingResult> {
  let lat: number | null = null
  let lng: number | null = null
  let addressInfo: any = null
  let displayAddress: string | null = null

  // Geolocation wrapper
  const getCoords = () => {
    return new Promise<GeolocationPosition>((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error('Geolocation not supported'))
        return
      }
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000
      })
    })
  }

  try {
    const pos = await getCoords()
    lat = pos.coords.latitude
    lng = pos.coords.longitude
  } catch (err) {
    console.warn('High accuracy geolocation failed, trying low accuracy...', err)
    try {
      return new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: false,
          timeout: 8000
        })
      }).then(pos => {
        lat = pos.coords.latitude
        lng = pos.coords.longitude
        return pos
      }).catch(err2 => {
        console.warn('Low accuracy geolocation failed too', err2)
        return null as any
      })
    } catch (_) {}
  }

  // Get reverse geocoding if coords are captured
  if (lat !== null && lng !== null) {
    try {
      const geoRes = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`
      )
      if (geoRes.ok) {
        addressInfo = await geoRes.json()
        displayAddress = addressInfo?.display_name || null
      }
    } catch (err) {
      console.warn('OSM reverse geocoding failed', err)
    }
  }

  return new Promise<StampingResult>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (event) => {
      const img = new Image()
      img.onload = async () => {
        const canvas = document.createElement('canvas')
        const MAX_WIDTH = 1024
        const MAX_HEIGHT = 1024
        let width = img.width
        let height = img.height

        if (width > height) {
          if (width > MAX_WIDTH) {
            height *= MAX_WIDTH / width
            width = MAX_WIDTH
          }
        } else {
          if (height > MAX_HEIGHT) {
            width *= MAX_HEIGHT / height
            height = MAX_HEIGHT
          }
        }

        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        if (!ctx) {
          reject(new Error('Canvas context not available'))
          return
        }

        ctx.drawImage(img, 0, 0, width, height)

        const hasGPS = lat !== null && lng !== null
        const overlayHeight = hasGPS ? 160 : 70
        const overlayY = height - overlayHeight

        // Dark background overlay
        ctx.fillStyle = 'rgba(0, 0, 0, 0.72)'
        ctx.fillRect(0, overlayY, width, overlayHeight)

        // Accent strip (Green if GPS captured, Orange if not)
        ctx.fillStyle = hasGPS ? '#10b981' : '#f59e0b'
        ctx.fillRect(0, overlayY, width, 4)

        if (hasGPS && lat !== null && lng !== null) {
          // Draw map thumbnail
          const mapWidth = 120
          const mapHeight = 120
          const mapX = 20
          const mapY = overlayY + 20

          try {
            await new Promise<void>((resMap) => {
              const mapImg = new Image()
              mapImg.crossOrigin = 'anonymous'
              mapImg.onload = () => {
                ctx.save()
                ctx.beginPath()
                ctx.roundRect?.(mapX, mapY, mapWidth, mapHeight, 10)
                ctx.clip()
                ctx.drawImage(mapImg, mapX, mapY, mapWidth, mapHeight)
                ctx.restore()
                resMap()
              }
              mapImg.onerror = () => {
                drawFallbackMap(ctx, mapX, mapY, mapWidth, mapHeight)
                resMap()
              }
              mapImg.src = `https://static-maps.yandex.ru/1.x/?ll=${lng},${lat}&z=16&l=map&size=150,150&pt=${lng},${lat},pm2rdl`
            })
          } catch (e) {
            drawFallbackMap(ctx, mapX, mapY, mapWidth, mapHeight)
          }

          const textX = mapX + mapWidth + 20
          let textY = overlayY + 32

          // Title location name
          ctx.fillStyle = '#ffffff'
          ctx.font = 'bold 15px sans-serif'
          const addr = addressInfo?.address || {}
          const titleText = [
            addr.suburb || addr.village || addr.neighbourhood || addr.city_district || addr.city || '',
            addr.state || '',
            addr.country || ''
          ].filter(Boolean).join(', ') + (addr.country === 'India' ? ' 🇮🇳' : '')
          ctx.fillText(titleText || 'Location Captured', textX, textY)

          // Display address lines
          textY += 22
          ctx.fillStyle = '#e5e7eb'
          ctx.font = '11px sans-serif'
          const fullAddress = addressInfo?.display_name || 'Address details not available'
          const words = fullAddress.split(' ')
          let line = ''
          const maxTextWidth = width - textX - 25
          let addressLines = 0

          for (let n = 0; n < words.length; n++) {
            const testLine = line + words[n] + ' '
            const metrics = ctx.measureText(testLine)
            if (metrics.width > maxTextWidth && n > 0) {
              ctx.fillText(line, textX, textY)
              line = words[n] + ' '
              textY += 16
              addressLines++
              if (addressLines >= 2) break
            } else {
              line = testLine
            }
          }
          if (addressLines < 2) {
            ctx.fillText(line, textX, textY)
            textY += 16
          }

          // Lat/Lng info
          ctx.fillStyle = '#a1a1aa'
          ctx.font = '11px sans-serif'
          ctx.fillText(`Latitude: ${lat.toFixed(6)}°  Longitude: ${lng.toFixed(6)}°`, textX, textY)

          // Date time
          textY += 16
          const dateOptions: Intl.DateTimeFormatOptions = {
            weekday: 'long',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
          }
          const dateStr = new Intl.DateTimeFormat('en-IN', dateOptions).format(new Date())
          ctx.fillText(`${dateStr} GMT+05:30`, textX, textY)

          // GPS camera logo watermark
          ctx.fillStyle = 'rgba(255, 255, 255, 0.45)'
          ctx.font = 'bold 9px sans-serif'
          ctx.fillText('📷 GPS MAP CAMERA', width - 130, overlayY + 22)
        } else {
          // GPS details not captured
          const textX = 20
          let textY = overlayY + 28

          ctx.fillStyle = '#f59e0b'
          ctx.font = 'bold 13px sans-serif'
          ctx.fillText('⚠ GPS Unavailable — Location details could not be stamped', textX, textY)

          textY += 22
          ctx.fillStyle = '#e5e7eb'
          ctx.font = '12px sans-serif'
          const dateOptions: Intl.DateTimeFormatOptions = {
            weekday: 'long',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
          }
          const dateStr = new Intl.DateTimeFormat('en-IN', dateOptions).format(new Date())
          ctx.fillText(`📅 Stamped: ${dateStr} GMT+05:30`, textX, textY)

          ctx.fillStyle = 'rgba(255, 255, 255, 0.45)'
          ctx.font = 'bold 9px sans-serif'
          ctx.fillText('📷 GPS MAP CAMERA', width - 130, overlayY + 22)
        }

        const base64Str = canvas.toDataURL('image/jpeg', 0.7)
        resolve({
          photoBase64: base64Str,
          lat,
          lng,
          address: displayAddress
        })
      }
      img.src = event.target?.result as string
    }
    reader.readAsDataURL(file)
  })
}
