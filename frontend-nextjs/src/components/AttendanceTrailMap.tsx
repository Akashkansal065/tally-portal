'use client'

import React, { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { 
  MapPin, 
  Navigation, 
  Layers, 
  Maximize2, 
  Minimize2, 
  Download, 
  Copy, 
  Check, 
  Code, 
  Compass, 
  Footprints,
  Clock,
  ExternalLink
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'

export type TrailPoint = {
  id: number
  latitude: number
  longitude: number
  accuracyMeters?: number | null
  distanceFromPrevMeters: number
  placeName?: string | null
  recordedAt: string
  mapsUrl?: string
}

interface AttendanceTrailMapProps {
  trail: TrailPoint[]
  isLive?: boolean
  employeeName?: string
  checkInTime?: string
  checkOutTime?: string | null
  totalDistanceMeters?: number
  height?: string
  rawJson?: any
}

export default function AttendanceTrailMap({
  trail = [],
  isLive = false,
  employeeName = 'Employee',
  checkInTime,
  checkOutTime,
  totalDistanceMeters = 0,
  height = '420px',
  rawJson,
}: AttendanceTrailMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<L.Map | null>(null)
  const layerGroupRef = useRef<L.LayerGroup | null>(null)
  const tileLayerRef = useRef<L.TileLayer | null>(null)

  const [activeView, setActiveView] = useState<'map' | 'json'>('map')
  const [mapType, setMapType] = useState<'street' | 'satellite'>('street')
  const [copied, setCopied] = useState(false)
  const [selectedPointIndex, setSelectedPointIndex] = useState<number | null>(null)

  // JSON representation of the entire movement trail
  const formattedTrailJson = React.useMemo(() => {
    if (rawJson && Array.isArray(rawJson) && rawJson.length > 0) {
      return rawJson
    }
    return trail.map((p, idx) => ({
      step: idx + 1,
      lat: p.latitude,
      lng: p.longitude,
      time: p.recordedAt,
      accuracyMeters: p.accuracyMeters != null ? Math.round(p.accuracyMeters) : null,
      distanceFromPrevMeters: p.distanceFromPrevMeters,
      place: p.placeName || null,
      mapsUrl: p.mapsUrl || `https://www.google.com/maps?q=${p.latitude},${p.longitude}`,
    }))
  }, [trail, rawJson])

  // Initialize and update the Leaflet map
  useEffect(() => {
    if (typeof window === 'undefined' || !mapContainerRef.current) return
    if (activeView !== 'map') return

    // Create map instance if not exists
    if (!mapInstanceRef.current) {
      const initialLat = trail.length > 0 ? trail[0].latitude : 28.6139
      const initialLng = trail.length > 0 ? trail[0].longitude : 77.2090

      const map = L.map(mapContainerRef.current, {
        center: [initialLat, initialLng],
        zoom: 15,
        zoomControl: true,
        attributionControl: false,
      })

      // Default tiles: CartoDB Positron / OSM
      const tileUrl = mapType === 'satellite'
        ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        : 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png'

      const tiles = L.tileLayer(tileUrl, {
        maxZoom: 19,
        subdomains: 'abcd',
      }).addTo(map)

      tileLayerRef.current = tiles
      layerGroupRef.current = L.layerGroup().addTo(map)
      mapInstanceRef.current = map
    }

    const map = mapInstanceRef.current
    const layerGroup = layerGroupRef.current

    if (!map || !layerGroup) return

    // Update tile layer if changed
    if (tileLayerRef.current) {
      const newUrl = mapType === 'satellite'
        ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
        : 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png'
      tileLayerRef.current.setUrl(newUrl)
    }

    layerGroup.clearLayers()

    if (trail.length === 0) return

    const latLngs: L.LatLngExpression[] = trail.map(p => [p.latitude, p.longitude])

    // Draw connecting route polyline
    if (latLngs.length > 1) {
      // Glow/Border line
      L.polyline(latLngs, {
        color: '#0369a1',
        weight: 6,
        opacity: 0.4,
      }).addTo(layerGroup)

      // Main line
      L.polyline(latLngs, {
        color: '#0284c7',
        weight: 4,
        opacity: 0.95,
        lineCap: 'round',
        lineJoin: 'round',
      }).addTo(layerGroup)
    }

    // Add Markers for each checkpoint
    trail.forEach((point, index) => {
      const isFirst = index === 0
      const isLast = index === trail.length - 1

      // Format timestamp for popup
      let timeFormatted = point.recordedAt
      try {
        const d = new Date(point.recordedAt)
        if (!isNaN(d.getTime())) {
          timeFormatted = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })
        }
      } catch {}

      let iconHtml = ''

      if (isFirst) {
        // Start marker: Green flag/badge
        iconHtml = `
          <div style="background:#10b981; color:white; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 8px rgba(16,185,129,0.5); border:2px solid white; font-weight:800; font-size:11px;">
            S
          </div>
        `
      } else if (isLast) {
        if (isLive) {
          // Current live location beacon
          iconHtml = `
            <div style="position:relative; width:28px; height:28px; display:flex; align-items:center; justify-content:center;">
              <span style="position:absolute; width:28px; height:28px; border-radius:50%; background:#0284c7; opacity:0.75; animation:ping 1.5s cubic-bezier(0,0,0.2,1) infinite;"></span>
              <div style="background:#0284c7; color:white; width:20px; height:20px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 0 10px rgba(2,132,199,0.8); border:2px solid white; font-weight:800; font-size:10px;">
                ●
              </div>
            </div>
          `
        } else {
          // End/Checkout marker: Rose
          iconHtml = `
            <div style="background:#f43f5e; color:white; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 2px 8px rgba(244,63,94,0.5); border:2px solid white; font-weight:800; font-size:11px;">
              E
            </div>
          `
        }
      } else {
        // Intermediate checkpoints: Small dot with step number
        iconHtml = `
          <div style="background:#ffffff; color:#0284c7; width:20px; height:20px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 1px 4px rgba(0,0,0,0.3); border:2px solid #0284c7; font-weight:700; font-size:9px;">
            ${index + 1}
          </div>
        `
      }

      const customIcon = L.divIcon({
        className: 'custom-trail-marker',
        html: iconHtml,
        iconSize: isFirst || isLast ? [28, 28] : [20, 20],
        iconAnchor: isFirst || isLast ? [14, 14] : [10, 10],
      })

      const marker = L.marker([point.latitude, point.longitude], { icon: customIcon })

      const popupHtml = `
        <div style="font-family: inherit; font-size: 11px; line-height: 1.4; min-width: 180px; padding: 2px;">
          <div style="font-weight: 800; color: #0f172a; margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between;">
            <span>${isFirst ? '🟢 Start (Clock-In)' : isLast ? (isLive ? '📍 Current Live Location' : '🔴 End (Clock-Out)') : `Stop #${index + 1}`}</span>
            <span style="font-family: monospace; color: #64748b; font-size: 10px;">${timeFormatted}</span>
          </div>
          ${point.placeName ? `<div style="color: #334155; margin-bottom: 4px; font-weight: 600;">📍 ${point.placeName}</div>` : ''}
          <div style="display: flex; gap: 8px; font-size: 10px; color: #64748b; margin-top: 4px; border-top: 1px solid #e2e8f0; padding-top: 4px;">
            <span>Dist: <b>+${point.distanceFromPrevMeters}m</b></span>
            ${point.accuracyMeters != null ? `<span>Acc: <b>±${Math.round(point.accuracyMeters)}m</b></span>` : ''}
          </div>
          <div style="margin-top: 6px; text-align: right;">
            <a href="https://www.google.com/maps?q=${point.latitude},${point.longitude}" target="_blank" rel="noopener noreferrer" style="color: #0284c7; text-decoration: underline; font-weight: 700; font-size: 10px;">
              Open in Google Maps ↗
            </a>
          </div>
        </div>
      `

      marker.bindPopup(popupHtml)
      marker.on('click', () => setSelectedPointIndex(index))
      marker.addTo(layerGroup)
    })

    // Auto-fit map to route bounds
    if (latLngs.length > 1) {
      map.fitBounds(L.latLngBounds(latLngs), { padding: [35, 35], maxZoom: 17 })
    } else if (latLngs.length === 1) {
      map.setView(latLngs[0], 16)
    }

    // Invalidate size to ensure container rendered cleanly
    setTimeout(() => {
      map.invalidateSize()
    }, 150)
  }, [trail, activeView, mapType, isLive])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [])

  const handleFitBounds = () => {
    if (!mapInstanceRef.current || trail.length === 0) return
    const latLngs = trail.map(p => [p.latitude, p.longitude] as [number, number])
    if (latLngs.length > 1) {
      mapInstanceRef.current.fitBounds(L.latLngBounds(latLngs), { padding: [35, 35] })
    } else {
      mapInstanceRef.current.setView(latLngs[0], 16)
    }
  }

  const handleFocusLatest = () => {
    if (!mapInstanceRef.current || trail.length === 0) return
    const last = trail[trail.length - 1]
    mapInstanceRef.current.setView([last.latitude, last.longitude], 17, { animate: true })
  }

  const handleCopyJson = () => {
    try {
      navigator.clipboard.writeText(JSON.stringify(formattedTrailJson, null, 2))
      setCopied(true)
      toast.success('Movement JSON copied to clipboard!')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('Failed to copy JSON.')
    }
  }

  const handleDownloadJson = () => {
    try {
      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(formattedTrailJson, null, 2))
      const downloadAnchor = document.createElement('a')
      downloadAnchor.setAttribute('href', dataStr)
      const datePart = (checkInTime || '').split('T')[0] || 'date'
      downloadAnchor.setAttribute('download', `movement_trail_${employeeName.toLowerCase().replace(/\\s+/g, '_')}_${datePart}.json`)
      document.body.appendChild(downloadAnchor)
      downloadAnchor.click()
      downloadAnchor.remove()
      toast.success('Movement JSON downloaded successfully!')
    } catch {
      toast.error('Failed to download JSON file.')
    }
  }

  return (
    <div className="flex flex-col rounded-2xl overflow-hidden border border-border bg-card shadow-sm">
      {/* Top Map Control Toolbar */}
      <div className="bg-muted/40 border-b border-border/80 px-3 py-2 flex items-center justify-between flex-wrap gap-2 text-xs">
        {/* Left: View Switcher Tabs */}
        <div className="flex bg-muted p-0.5 rounded-lg border border-border/60">
          <button
            type="button"
            onClick={() => setActiveView('map')}
            className={cn(
              "px-2.5 py-1 rounded-md font-bold text-[11px] transition-all flex items-center gap-1 cursor-pointer",
              activeView === 'map' ? "bg-card text-foreground shadow-2xs" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Compass className="h-3.5 w-3.5 text-sky-500" />
            <span>Interactive Map</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveView('json')}
            className={cn(
              "px-2.5 py-1 rounded-md font-bold text-[11px] transition-all flex items-center gap-1 cursor-pointer",
              activeView === 'json' ? "bg-card text-foreground shadow-2xs" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Code className="h-3.5 w-3.5 text-amber-500" />
            <span>Movement JSON ({formattedTrailJson.length})</span>
          </button>
        </div>

        {/* Right: Map style toggle and zoom controls */}
        {activeView === 'map' ? (
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              type="button"
              onClick={() => setMapType(t => t === 'street' ? 'satellite' : 'street')}
              className="inline-flex items-center gap-1 px-2 py-1 bg-background hover:bg-muted border border-border rounded-lg text-[10px] font-semibold text-foreground transition-colors cursor-pointer shadow-2xs"
              title="Toggle Street / Satellite imagery"
            >
              <Layers className="h-3 w-3 text-sky-500" />
              <span>{mapType === 'street' ? 'Satellite' : 'Street'}</span>
            </button>
            <button
              type="button"
              onClick={handleFitBounds}
              className="inline-flex items-center gap-1 px-2 py-1 bg-background hover:bg-muted border border-border rounded-lg text-[10px] font-semibold text-foreground transition-colors cursor-pointer shadow-2xs"
              title="Fit map to entire route"
            >
              <Navigation className="h-3 w-3 text-emerald-500" />
              <span>Fit Route</span>
            </button>
            {trail.length > 0 && (
              <button
                type="button"
                onClick={handleFocusLatest}
                className="inline-flex items-center gap-1 px-2 py-1 bg-sky-500/10 hover:bg-sky-500/20 text-sky-600 dark:text-sky-400 border border-sky-500/20 rounded-lg text-[10px] font-bold transition-colors cursor-pointer shadow-2xs"
                title="Focus on latest ping"
              >
                <MapPin className="h-3 w-3 text-sky-500" />
                <span>Latest Ping</span>
              </button>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleCopyJson}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-background hover:bg-muted border border-border rounded-lg text-[10px] font-semibold text-foreground transition-colors cursor-pointer shadow-2xs"
            >
              {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3 text-muted-foreground" />}
              <span>{copied ? 'Copied' : 'Copy JSON'}</span>
            </button>
            <button
              type="button"
              onClick={handleDownloadJson}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-[10px] font-bold transition-colors cursor-pointer shadow-2xs"
            >
              <Download className="h-3 w-3" />
              <span>Download .json</span>
            </button>
          </div>
        )}
      </div>

      {/* Main View Area */}
      {activeView === 'map' ? (
        <div className="relative w-full overflow-hidden" style={{ height }}>
          {/* Leaflet Map Mount Container */}
          <div ref={mapContainerRef} className="w-full h-full z-0" />

          {/* Empty fallback if no points */}
          {trail.length === 0 && (
            <div className="absolute inset-0 bg-background/80 backdrop-blur-xs flex flex-col items-center justify-center gap-2 p-4 text-center z-10">
              <Footprints className="h-8 w-8 text-muted-foreground/60 animate-bounce" />
              <p className="text-xs font-bold text-foreground">No GPS movement checkpoints recorded yet</p>
              <p className="text-[11px] text-muted-foreground max-w-xs">
                As the employee moves (threshold: 1 meter), the route and checkpoints will appear here interactively in real time.
              </p>
            </div>
          )}

          {/* Floating Map Legend */}
          {trail.length > 0 && (
            <div className="absolute bottom-2 left-2 z-10 bg-background/90 dark:bg-card/90 backdrop-blur-md border border-border/80 px-2.5 py-1.5 rounded-xl shadow-md text-[10px] flex items-center gap-3 font-semibold pointer-events-none">
              <span className="flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 border border-white" />
                <span>Start</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-full bg-sky-500 border border-white" />
                <span>Path</span>
              </span>
              <span className="flex items-center gap-1">
                <span className={cn("h-2.5 w-2.5 rounded-full border border-white", isLive ? "bg-sky-500 animate-ping" : "bg-rose-500")} />
                <span>{isLive ? 'Current Ping' : 'End'}</span>
              </span>
            </div>
          )}
        </div>
      ) : (
        /* JSON Data Inspector Tab */
        <div className="p-3 bg-muted/20 overflow-y-auto space-y-3" style={{ height }}>
          <div className="flex items-center justify-between text-xs border-b border-border/50 pb-2">
            <div className="flex items-center gap-1.5 text-muted-foreground text-[11px]">
              <span className="font-mono font-bold text-foreground">{formattedTrailJson.length}</span>
              <span>movement coordinates recorded in JSON</span>
            </div>
            <span className="text-[10px] text-muted-foreground font-mono">Structured Array Format</span>
          </div>

          <pre className="p-3 bg-card border border-border/80 rounded-xl text-[11px] font-mono text-foreground overflow-x-auto max-h-[340px] leading-relaxed shadow-inner">
            {JSON.stringify(formattedTrailJson, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
