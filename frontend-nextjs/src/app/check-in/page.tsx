'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase } from '@/lib/utils'
import { stampPhoto } from '@/lib/photo-stamping'
import {
  queueOfflineCheckIn,
  getPendingCheckIns,
  syncPendingCheckIns,
  getCachedData,
  setCachedData,
  getAllCachedCustomers,
  OfflineCheckIn
} from '@/lib/offline-storage'
import { loadCustomers, loadRecentVisits } from '@/lib/data-sync-service'
import DataFreshnessIndicator from '@/components/DataFreshnessIndicator'
import Link from 'next/link'
import {
  MapPin,
  Camera,
  CheckCircle,
  Clock,
  AlertTriangle,
  ChevronLeft,
  Search,
  CheckCircle2,
  X,
  CloudOff,
  RefreshCw,
  History,
  CalendarCheck,
  Radio
} from 'lucide-react'
import { cn } from '@/lib/utils'

type RecentVisit = {
  id: number
  customShopName: string | null
  shopName: string | null
  status: string
  createdAt: string
  comments: string | null
  latitude: number | null
  longitude: number | null
  photoUrl: string | null
}

type ShopOption = {
  key: string
  ledger_id?: number | null
  profile_id?: number | null
  name: string
  locality?: string
  source: 'tally' | 'field_profile'
  latitude?: number | null
  longitude?: number | null
}

export default function CheckInPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()

  const [shops, setShops] = useState<ShopOption[]>([])
  const [recentVisits, setRecentVisits] = useState<RecentVisit[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')

  // Offline queue state
  const [pendingCheckIns, setPendingCheckIns] = useState<OfflineCheckIn[]>([])
  const [syncingOffline, setSyncingOffline] = useState(false)

  // Form state
  const [selectedLedger, setSelectedLedger] = useState('')
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [customShop, setCustomShop] = useState('')
  const [comments, setComments] = useState('')
  
  // GPS/Photo states
  const [gpsStatus, setGpsStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null)
  const [prewarmedCoords, setPrewarmedCoords] = useState<{ lat: number; lng: number } | null>(null)
  const [prewarmedAccuracy, setPrewarmedAccuracy] = useState<number | null>(null)

  const [photo, setPhoto] = useState<string | null>(null)
  const [processingPhoto, setProcessingPhoto] = useState(false)
  const [previewPhoto, setPreviewPhoto] = useState<RecentVisit | null>(null)
  const [expandedProofId, setExpandedProofId] = useState<number | null>(null)

  // ─── 1. GPS Pre-Warming on Page Mount ───────────────────────────────────────
  // Continuously monitors satellite coordinates in the background while the rep
  // selects a shop, ensuring instant 0ms lock when the camera shutter is pressed.
  useEffect(() => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) return

    setGpsStatus('loading')
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        setPrewarmedCoords({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        })
        setPrewarmedAccuracy(pos.coords.accuracy)
        setGpsStatus('ok')
      },
      (err) => {
        console.warn('[CheckIn] Pre-warming watchPosition:', err.message)
        // If not locked yet and no coords, keep idle or loading
      },
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 10000,
      }
    )

    return () => {
      navigator.geolocation.clearWatch(watchId)
    }
  }, [])

  // ─── 2. Pre-fill from query params (e.g. from Customer Profile or Planner) ───
  useEffect(() => {
    const qLedger = searchParams.get('ledger_id')
    const qProfile = searchParams.get('profile_id')
    const qName = searchParams.get('name')

    if (qLedger) {
      setSelectedLedger(qLedger)
      setSelectedProfileId(null)
      if (qName) setSearchQuery(qName)
    } else if (qProfile) {
      setSelectedProfileId(parseInt(qProfile))
      setSelectedLedger('')
      if (qName) {
        setSearchQuery(qName)
        setCustomShop(qName)
      }
    }
  }, [searchParams])

  useEffect(() => {
    if (selectedLedger === '' && !selectedProfileId) {
      setSearchQuery('')
    }
  }, [selectedLedger, selectedProfileId])

  // ─── 3. Monitor Offline Queue & Global Online Sync ───────────────────────────
  useEffect(() => {
    const refreshQueue = async () => {
      const items = await getPendingCheckIns()
      setPendingCheckIns(items)
    }
    refreshQueue()

    const handleSyncedEvent = () => refreshQueue()

    const handleOnline = async () => {
      if (token) {
        setSyncingOffline(true)
        const res = await syncPendingCheckIns(API_BASE, authHeaders, token)
        if (res.synced > 0) {
          setSuccess(`✓ Synced ${res.synced} offline check-in(s) successfully!`)
        }
        await refreshQueue()
        setSyncingOffline(false)
      }
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('mytally:checkins-synced', handleSyncedEvent)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('mytally:checkins-synced', handleSyncedEvent)
    }
  }, [token])

  // ─── 4. Smart Stale-While-Revalidate Caching for Shops Directory ──────────────
  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showCheckIn) { router.replace('/'); return }

    // Instant 0ms render from shared IndexedDB Customers Store
    getAllCachedCustomers().then((cachedCusts) => {
      if (Array.isArray(cachedCusts) && cachedCusts.length > 0) {
        const mappedShops: ShopOption[] = cachedCusts.map((c: any) => ({
          key: c.key,
          ledger_id: c.ledger_id,
          profile_id: c.profile_id,
          name: c.name,
          locality: c.locality,
          source: c.source,
          latitude: c.latitude,
          longitude: c.longitude,
        }))
        setShops(mappedShops)
        setLoading(false)
      }
    })

    loadRecentVisits(token).then(({ visits }) => {
      if (visits && visits.length > 0) {
        setRecentVisits(visits)
      }
    })

    // SWR: Silent delta sync in background using shared loadCustomers
    loadCustomers(token).then(({ customers: freshCusts }) => {
      if (Array.isArray(freshCusts) && freshCusts.length > 0) {
        const mappedShops: ShopOption[] = freshCusts.map((c: any) => ({
          key: c.key,
          ledger_id: c.ledger_id,
          profile_id: c.profile_id,
          name: c.name,
          locality: c.locality,
          source: c.source,
          latitude: c.latitude,
          longitude: c.longitude,
        }))
        setShops(mappedShops)
      }
    }).finally(() => setLoading(false))
  }, [user, token, router, permissions.showCheckIn])

  // Listen for background data sync events
  useEffect(() => {
    const handleDataUpdated = async (e: Event) => {
      const detail = (e as CustomEvent).detail
      if (!detail?.domain || detail.domain === 'customers') {
        const cached = await getAllCachedCustomers()
        if (cached && cached.length > 0) {
          setShops(cached.map((c: any) => ({
            key: c.key,
            ledger_id: c.ledger_id,
            profile_id: c.profile_id,
            name: c.name,
            locality: c.locality,
            source: c.source,
            latitude: c.latitude,
            longitude: c.longitude,
          })))
        }
      }
      if (!detail?.domain || detail.domain === 'recent_visits') {
        const { visits } = await loadRecentVisits(token)
        if (visits && visits.length > 0) {
          setRecentVisits(visits)
        }
      }
    }
    window.addEventListener('mytally:data-updated', handleDataUpdated)
    return () => window.removeEventListener('mytally:data-updated', handleDataUpdated)
  }, [token])

  // ─── 5. Selected Shop Object & Client-Side Geofencing Proximity ───────────────
  const selectedShopObj = useMemo(() => {
    if (selectedLedger) {
      return shops.find(s => String(s.ledger_id) === String(selectedLedger))
    }
    if (selectedProfileId) {
      return shops.find(s => s.profile_id === selectedProfileId)
    }
    return null
  }, [selectedLedger, selectedProfileId, shops])

  const distanceInfo = useMemo(() => {
    const currentLoc = coords || prewarmedCoords
    if (!currentLoc || !selectedShopObj) return null

    if (!selectedShopObj.latitude || !selectedShopObj.longitude) {
      return { status: 'NO_BASE_COORDINATE' as const, distanceMeters: null }
    }

    // Haversine distance formula in meters
    const R = 6371000 // Earth's mean radius in meters
    const dLat = (selectedShopObj.latitude - currentLoc.lat) * (Math.PI / 180)
    const dLon = (selectedShopObj.longitude - currentLoc.lng) * (Math.PI / 180)
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(currentLoc.lat * (Math.PI / 180)) *
        Math.cos(selectedShopObj.latitude * (Math.PI / 180)) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2)
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
    const dist = Math.round(R * c)

    return {
      status: dist <= 30 ? ('MATCH' as const) : dist <= 100 ? ('NEAR' as const) : ('FAR' as const),
      distanceMeters: dist,
    }
  }, [coords, prewarmedCoords, selectedShopObj])

  // ─── 6. Photo Capture & Fast Stamping ─────────────────────────────────────────
  const handlePhotoCapture = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setProcessingPhoto(true)
    setGpsStatus('loading')
    try {
      // Pass pre-warmed GPS coordinates for instant lock
      const activeCoords = prewarmedCoords || coords
      const result = await stampPhoto(file, activeCoords)
      setPhoto(result.photoBase64)
      if (result.lat && result.lng) {
        setCoords({ lat: result.lat, lng: result.lng })
        setGpsStatus('ok')
      } else {
        setGpsStatus('error')
      }
    } catch (err: any) {
      setError(err.message || 'Photo processing failed')
      setGpsStatus('error')
    } finally {
      setProcessingPhoto(false)
    }
  }

  // ─── 7. Manual Sync Action ───────────────────────────────────────────────────
  const handleManualSync = async () => {
    if (!token) return
    setSyncingOffline(true)
    const res = await syncPendingCheckIns(API_BASE, authHeaders, token)
    const items = await getPendingCheckIns()
    setPendingCheckIns(items)
    setSyncingOffline(false)
    if (res.synced > 0) {
      setSuccess(`✓ Synced ${res.synced} offline check-in(s)!`)
    } else if (res.failed > 0) {
      setError(`Failed to sync ${res.failed} check-in(s). Check internet connection.`)
    }
  }

  // ─── 8. Form Submit Action ───────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedLedger && !selectedProfileId && !customShop) {
      setError('Select a shop or enter custom shop name.')
      return
    }
    if (!photo) {
      setError('Please capture a watermarked photo first.')
      return
    }

    setSubmitting(true)
    setError('')
    setSuccess('')

    const activeLoc = coords || prewarmedCoords

    const payload = {
      ledger_id: selectedLedger ? parseInt(selectedLedger) : null,
      customer_profile_id: selectedProfileId || null,
      custom_shop_name: customShop || searchQuery || null,
      latitude: activeLoc?.lat || 0,
      longitude: activeLoc?.lng || 0,
      comments,
      photo_base64: photo,
    }

    // Check if offline
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      await queueOfflineCheckIn({
        ...payload,
        shop_name: searchQuery || customShop || 'Customer Shop',
      })
      const items = await getPendingCheckIns()
      setPendingCheckIns(items)
      setSuccess('✓ You are offline. Check-in saved securely on device (IndexedDB) and will auto-sync when network returns!')
      setSelectedLedger('')
      setSelectedProfileId(null)
      setCustomShop('')
      setComments('')
      setPhoto(null)
      setCoords(null)
      setGpsStatus(prewarmedCoords ? 'ok' : 'idle')
      setSubmitting(false)
      return
    }

    try {
      const res = await fetch(`${API_BASE}/visits/check-in`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      const data = await res.json()
      
      if (data.location_established) {
        setSuccess('✓ Check-in recorded! Master GPS location established & verified for this shop.')
      } else if (data.verification_status === 'MISMATCH_FAR') {
        const dist = data.distance_from_base_meters ? `${Math.round(data.distance_from_base_meters)}m` : ''
        setSuccess(`⚠️ Check-in recorded with Location Discrepancy (${dist ? `${dist} away from shop` : '>20m away'}). Flagged for audit.`)
      } else {
        setSuccess('✓ Check-in recorded successfully!')
      }

      setSelectedLedger('')
      setSelectedProfileId(null)
      setCustomShop('')
      setComments('')
      setPhoto(null)
      setCoords(null)
      setGpsStatus(prewarmedCoords ? 'ok' : 'idle')
      
      // Refresh recent visits
      const vs = await fetch(`${API_BASE}/visits/recent`, { headers: authHeaders(token) }).then(r => r.json()).catch(() => [])
      const updatedVisits = Array.isArray(vs) ? vs : (vs?.data ?? [])
      setRecentVisits(updatedVisits)
      if (updatedVisits.length > 0) {
        await setCachedData('recent_visits', updatedVisits, 15 * 60 * 1000)
      }
    } catch (err: any) {
      // If network error, queue in IndexedDB
      if (err.message && (err.message.includes('Failed to fetch') || err.message.includes('NetworkError'))) {
        await queueOfflineCheckIn({
          ...payload,
          shop_name: searchQuery || customShop || 'Customer Shop',
        })
        const items = await getPendingCheckIns()
        setPendingCheckIns(items)
        setSuccess('✓ Network unavailable. Check-in saved securely on device (IndexedDB) and will auto-sync when online!')
        setSelectedLedger('')
        setSelectedProfileId(null)
        setCustomShop('')
        setComments('')
        setPhoto(null)
        setCoords(null)
        setGpsStatus(prewarmedCoords ? 'ok' : 'idle')
      } else {
        setError(err.message || 'Failed to record check-in')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const filteredShops = useMemo(() => {
    if (!searchQuery) return shops.slice(0, 30)
    const q = searchQuery.toLowerCase()
    return shops.filter(s => s.name.toLowerCase().includes(q) || (s.locality && s.locality.toLowerCase().includes(q))).slice(0, 30)
  }, [shops, searchQuery])

  return (
    <div className="max-w-xl mx-auto px-4 py-4 space-y-4 pb-24">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link href="/" className="p-2 -ml-2 rounded-xl text-muted-foreground hover:text-foreground">
            <ChevronLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-xl font-black text-foreground flex items-center gap-2">
              <MapPin className="h-5.5 w-5.5 text-rose-500" /> Shop Check-In
            </h1>
            <p className="text-[11px] text-muted-foreground mt-0.5">Capture real-time location and verified proof of shop visit</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <DataFreshnessIndicator domain="customers" showRefreshButton={false} />
          {/* Action Toggle Pills */}
          <div className="flex items-center gap-1 bg-muted/60 p-1 rounded-xl border border-border">
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-background text-foreground font-bold text-xs rounded-lg shadow-sm">
            <MapPin className="h-3.5 w-3.5 text-rose-500" />
            <span>Check-In</span>
          </div>
          <Link
            href="/check-in/history"
            className="flex items-center gap-1.5 px-3 py-1.5 text-muted-foreground hover:text-foreground font-semibold text-xs rounded-lg transition-colors"
          >
            <History className="h-3.5 w-3.5 text-slate-500" />
            <span>History</span>
          </Link>
        </div>
      </div>
    </div>

      {/* Offline Warning & Manual Sync Strip */}
      {pendingCheckIns.length > 0 && (
        <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 text-xs flex items-center justify-between gap-2 shadow-sm animate-in fade-in duration-200">
          <div className="flex items-center gap-1.5 font-semibold">
            <CloudOff className="w-4 h-4 text-amber-600 shrink-0" />
            <span>{pendingCheckIns.length} check-in(s) stored offline (IndexedDB)</span>
          </div>
          <button
            type="button"
            onClick={handleManualSync}
            disabled={syncingOffline}
            className="inline-flex items-center gap-1 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold transition-all cursor-pointer active:scale-95"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", syncingOffline && "animate-spin")} />
            <span>{syncingOffline ? 'Syncing...' : 'Sync Now'}</span>
          </button>
        </div>
      )}

      {success && (
        <div className="p-3.5 rounded-2xl bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs font-bold shadow-sm">
          {success}
        </div>
      )}
      {error && (
        <div className="p-3.5 rounded-2xl bg-destructive/10 text-destructive text-xs font-bold shadow-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
        {/* Shop selection */}
        <div className="relative">
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">
              Customer Shop / Outlet
            </label>
            {/* Live GPS Pre-Warming Status Badge */}
            {prewarmedCoords ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded-full border border-emerald-500/20">
                <Radio className="w-2.5 h-2.5 animate-pulse text-emerald-500" />
                <span>GPS Ready ({prewarmedAccuracy ? `±${Math.round(prewarmedAccuracy)}m` : 'Locked'})</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                <div className="w-2 h-2 border border-muted-foreground border-t-transparent rounded-full animate-spin" />
                <span>Locking GPS...</span>
              </span>
            )}
          </div>

          <input
            type="text"
            placeholder="Search customer shop name..."
            value={searchQuery}
            onChange={e => {
              setSearchQuery(e.target.value)
              setIsOpen(true)
              if (e.target.value === '') {
                setSelectedLedger('')
                setSelectedProfileId(null)
              }
            }}
            onFocus={() => setIsOpen(true)}
            className="w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />

          {isOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
              <div className="absolute left-0 right-0 mt-1 max-h-56 overflow-y-auto bg-popover border border-border rounded-xl shadow-lg z-50 divide-y divide-border/50">
                {filteredShops.length === 0 ? (
                  <div className="p-3.5 text-xs text-muted-foreground text-center">No customers found</div>
                ) : (
                  filteredShops.map(s => (
                    <button
                      key={s.key}
                      type="button"
                      onClick={() => {
                        if (s.ledger_id) {
                          setSelectedLedger(String(s.ledger_id))
                          setSelectedProfileId(null)
                        } else if (s.profile_id) {
                          setSelectedProfileId(s.profile_id)
                          setSelectedLedger('')
                        }
                        setSearchQuery(toTitleCase(s.name))
                        setIsOpen(false)
                      }}
                      className="w-full text-left px-4 py-3 text-xs font-bold hover:bg-muted text-foreground transition-colors flex items-center justify-between cursor-pointer"
                    >
                      <div>
                        <span>{toTitleCase(s.name)}</span>
                        {s.locality && (
                          <span className="block text-[10px] text-muted-foreground font-normal">{s.locality}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        {s.latitude && s.longitude ? (
                          <span className="text-[9px] font-mono text-emerald-600 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                            GPS Saved
                          </span>
                        ) : null}
                        {s.source === 'field_profile' ? (
                          <span className="text-[9px] font-semibold text-blue-600 bg-blue-500/10 px-1.5 py-0.5 rounded">
                            Field Lead
                          </span>
                        ) : null}
                      </div>
                    </button>
                  ))
                )}
              </div>
            </>
          )}

          {(selectedLedger || selectedProfileId) && (
            <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 p-2.5 rounded-xl text-xs flex items-center gap-1.5 mt-2">
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
              <span>Selected: <strong>{searchQuery}</strong></span>
            </div>
          )}

          {/* Live Client-Side Geofencing Proximity Feedback */}
          {(selectedLedger || selectedProfileId) && distanceInfo && (
            <div className={cn(
              "p-2.5 rounded-xl text-xs font-semibold flex items-center justify-between border mt-2 transition-all",
              distanceInfo.status === 'MATCH'
                ? "bg-emerald-50 dark:bg-emerald-950/30 border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
                : distanceInfo.status === 'NEAR'
                ? "bg-amber-50 dark:bg-amber-950/30 border-amber-500/30 text-amber-700 dark:text-amber-300"
                : distanceInfo.status === 'FAR'
                ? "bg-rose-50 dark:bg-rose-950/30 border-rose-500/30 text-rose-700 dark:text-rose-300"
                : "bg-blue-50 dark:bg-blue-950/30 border-blue-500/30 text-blue-700 dark:text-blue-300"
            )}>
              <div className="flex items-center gap-1.5">
                <MapPin className={cn(
                  "w-4 h-4 shrink-0",
                  distanceInfo.status === 'MATCH' ? "text-emerald-600" :
                  distanceInfo.status === 'NEAR' ? "text-amber-600" :
                  distanceInfo.status === 'FAR' ? "text-rose-600" :
                  "text-blue-600"
                )} />
                <span>
                  {distanceInfo.status === 'MATCH' && `✓ At Shop Location (~${distanceInfo.distanceMeters}m away)`}
                  {distanceInfo.status === 'NEAR' && `⚠️ Near Shop (~${distanceInfo.distanceMeters}m away)`}
                  {distanceInfo.status === 'FAR' && `⚠️ Outside Shop Range (~${distanceInfo.distanceMeters}m away — will flag for audit)`}
                  {distanceInfo.status === 'NO_BASE_COORDINATE' && `📍 First Visit — Will establish verified GPS base coordinates`}
                </span>
              </div>
              {prewarmedAccuracy && (
                <span className="text-[10px] font-mono opacity-75 shrink-0">
                  ±{Math.round(prewarmedAccuracy)}m
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <div className="flex-1 h-px bg-border" />
          <span className="text-[10px] text-muted-foreground uppercase font-bold">or</span>
          <div className="flex-1 h-px bg-border" />
        </div>

        <div>
          <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Custom / New Shop Name</label>
          <input
            type="text"
            placeholder="Enter customer shop name..."
            value={customShop}
            onChange={e => setCustomShop(e.target.value)}
            className="mt-1.5 w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>

        <div>
          <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Comments / Visit Notes</label>
          <textarea
            placeholder="Brief check-in remarks..."
            value={comments}
            onChange={e => setComments(e.target.value)}
            rows={2}
            className="mt-1.5 w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
          />
        </div>

        {/* Stamped GPS Photo Uploader */}
        <div>
          <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Required Watermarked Photo</label>
          {photo ? (
            <div className="relative rounded-2xl overflow-hidden border border-border mt-2 shadow-sm">
              <img src={photo} alt="check-in proof" className="w-full h-44 object-cover" />
              <button 
                type="button" 
                onClick={() => {
                  setPhoto(null)
                  setCoords(null)
                  setGpsStatus(prewarmedCoords ? 'ok' : 'idle')
                }} 
                className="absolute top-3 right-3 bg-black/75 hover:bg-black text-white rounded-full p-2 text-xs transition-colors cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <label className="mt-2 w-full flex flex-col items-center justify-center gap-2 py-8 rounded-2xl border-2 border-dashed border-border hover:border-emerald-500/50 cursor-pointer text-xs text-muted-foreground transition-all">
              {processingPhoto ? (
                <>
                  <div className="w-6 h-6 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                  <span className="font-bold">Watermarking Map & Location...</span>
                </>
              ) : (
                <>
                  <Camera className="h-7 w-7 text-muted-foreground opacity-70" />
                  <span className="font-bold">Take Geocoded Check-In Photo</span>
                  <input 
                    type="file" 
                    accept="image/*" 
                    capture="environment" 
                    className="hidden" 
                    onChange={handlePhotoCapture} 
                  />
                </>
              )}
            </label>
          )}

          {/* GPS Indicator */}
          {gpsStatus !== 'idle' && (
            <div className="mt-2.5 flex items-center gap-2.5 px-3 py-2 border rounded-xl text-[11px] font-semibold">
              {gpsStatus === 'loading' && (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-muted-foreground">Getting accurate GPS location...</span>
                </>
              )}
              {gpsStatus === 'ok' && (
                <>
                  <CheckCircle className="h-4 w-4 text-emerald-500 shrink-0" />
                  <span className="text-emerald-600 dark:text-emerald-400">
                    GPS Locked: {(coords || prewarmedCoords)?.lat.toFixed(5)}°, {(coords || prewarmedCoords)?.lng.toFixed(5)}°
                  </span>
                </>
              )}
              {gpsStatus === 'error' && (
                <>
                  <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                  <span className="text-amber-600">Location captured without high-precision GPS.</span>
                </>
              )}
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting || processingPhoto || !photo}
          className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 disabled:opacity-50 transition-all shadow-md shadow-emerald-500/10 cursor-pointer active:scale-95"
        >
          {submitting && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
          Confirm Check-In
        </button>
      </form>

      {/* Recent visits list */}
      <div className="space-y-2.5">
        <h3 className="font-black text-sm text-foreground uppercase tracking-wide">Recent Visits Today</h3>
        {loading ? (
          <div className="flex justify-center py-5">
            <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : recentVisits.length === 0 ? (
          <div className="p-4 bg-card border border-border rounded-xl text-center text-xs text-muted-foreground">
            No check-in visits recorded today yet.
          </div>
        ) : (
          <div className="divide-y divide-border border border-border rounded-2xl bg-card overflow-hidden">
            {recentVisits.map(v => (
              <div key={v.id} className="p-3.5 space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-foreground">{toTitleCase(v.shopName || v.customShopName || 'Customer Visit')}</span>
                  <span className="text-[10px] text-muted-foreground">{new Date(v.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
                {v.comments && <p className="text-[11px] text-muted-foreground leading-relaxed">{v.comments}</p>}
                
                <div className="flex items-center justify-between pt-1">
                  {v.latitude && v.longitude ? (
                    <a 
                      href={`https://www.google.com/maps/search/?api=1&query=${v.latitude},${v.longitude}`} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-[10px] font-bold text-blue-600 hover:underline flex items-center gap-1"
                    >
                      <MapPin className="h-3 w-3" />
                      <span>{v.latitude.toFixed(4)}, {v.longitude.toFixed(4)}</span>
                    </a>
                  ) : <span className="text-[10px] text-muted-foreground">No GPS</span>}

                  {v.photoUrl && (
                    <button
                      type="button"
                      onClick={() => setExpandedProofId(expandedProofId === v.id ? null : v.id)}
                      className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded cursor-pointer"
                    >
                      {expandedProofId === v.id ? 'Hide Proof' : 'View Proof'}
                    </button>
                  )}
                </div>

                {/* Inline Proof Viewer */}
                {expandedProofId === v.id && v.photoUrl && (
                  <div className="mt-2 pt-2 border-t border-border">
                    <img 
                      src={v.photoUrl} 
                      alt="Verified Check-In Proof" 
                      className="w-full rounded-xl border border-border object-cover max-h-56" 
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
