'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase } from '@/lib/utils'
import { stampPhoto } from '@/lib/photo-stamping'
import { queueOfflineCheckIn, getPendingCheckIns, syncPendingCheckIns, OfflineCheckIn } from '@/lib/offline-storage'
import Link from 'next/link'
import { MapPin, Camera, CheckCircle, Clock, AlertTriangle, ChevronLeft, Search, CheckCircle2, X, CloudOff, RefreshCw, History, CalendarCheck } from 'lucide-react'
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
  const [photo, setPhoto] = useState<string | null>(null)
  const [processingPhoto, setProcessingPhoto] = useState(false)
  const [previewPhoto, setPreviewPhoto] = useState<RecentVisit | null>(null)
  const [expandedProofId, setExpandedProofId] = useState<number | null>(null)

  // Pre-fill from query params (e.g. from Customer Directory or Route Planner)
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

  // Monitor offline queue & online synchronization
  useEffect(() => {
    setPendingCheckIns(getPendingCheckIns())

    const handleOnline = async () => {
      if (token) {
        setSyncingOffline(true)
        const res = await syncPendingCheckIns(API_BASE, authHeaders, token)
        if (res.synced > 0) {
          setSuccess(`✓ Synced ${res.synced} offline check-in(s) successfully!`)
        }
        setPendingCheckIns(getPendingCheckIns())
        setSyncingOffline(false)
      }
    }

    window.addEventListener('online', handleOnline)
    return () => window.removeEventListener('online', handleOnline)
  }, [token])

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showCheckIn) { router.replace('/'); return }

    // Instant initial render from localStorage cache
    try {
      const cachedShops = localStorage.getItem('mytally_cached_customer_shops')
      if (cachedShops) {
        const parsed = JSON.parse(cachedShops)
        if (Array.isArray(parsed) && parsed.length > 0) {
          setShops(parsed)
          setLoading(false)
        }
      }
    } catch (e) {}

    // Fetch unified customers list to support both Tally Debtors & Field Profiles
    Promise.all([
      fetch(`${API_BASE}/customers`, { headers: authHeaders(token) })
        .then(r => r.ok ? r.json() : null)
        .catch(() => null),
      fetch(`${API_BASE}/visits/recent`, { headers: authHeaders(token) })
        .then(r => r.ok ? r.json() : [])
        .catch(() => []),
    ]).then(([custData, vs]) => {
      if (custData && Array.isArray(custData.customers)) {
        const mappedShops: ShopOption[] = custData.customers.map((c: any) => ({
          key: c.key,
          ledger_id: c.ledger_id,
          profile_id: c.profile_id,
          name: c.name,
          locality: c.locality,
          source: c.source,
        }))
        setShops(mappedShops)
        try {
          localStorage.setItem('mytally_cached_customer_shops', JSON.stringify(mappedShops))
        } catch (e) {}
      }
      setRecentVisits(Array.isArray(vs) ? vs : (vs?.data ?? []))
    }).finally(() => setLoading(false))
  }, [user, token, router, permissions.showCheckIn])

  const handlePhotoCapture = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setProcessingPhoto(true)
    setGpsStatus('loading')
    try {
      const result = await stampPhoto(file)
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

  const handleManualSync = async () => {
    if (!token) return
    setSyncingOffline(true)
    const res = await syncPendingCheckIns(API_BASE, authHeaders, token)
    setPendingCheckIns(getPendingCheckIns())
    setSyncingOffline(false)
    if (res.synced > 0) {
      setSuccess(`✓ Synced ${res.synced} offline check-in(s)!`)
    } else if (res.failed > 0) {
      setError(`Failed to sync ${res.failed} check-in(s). Check internet connection.`)
    }
  }

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

    const payload = {
      ledger_id: selectedLedger ? parseInt(selectedLedger) : null,
      customer_profile_id: selectedProfileId || null,
      custom_shop_name: customShop || searchQuery || null,
      latitude: coords?.lat || 0,
      longitude: coords?.lng || 0,
      comments,
      photo_base64: photo,
    }

    // Check if offline
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      queueOfflineCheckIn({
        ...payload,
        shop_name: searchQuery || customShop || 'Customer Shop',
      })
      setPendingCheckIns(getPendingCheckIns())
      setSuccess('✓ You are offline. Check-in saved locally and will auto-sync when network returns!')
      setSelectedLedger('')
      setSelectedProfileId(null)
      setCustomShop('')
      setComments('')
      setPhoto(null)
      setCoords(null)
      setGpsStatus('idle')
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
      setGpsStatus('idle')
      
      // Refresh recent visits
      const vs = await fetch(`${API_BASE}/visits/recent`, { headers: authHeaders(token) }).then(r => r.json()).catch(() => [])
      setRecentVisits(Array.isArray(vs) ? vs : (vs?.data ?? []))
    } catch (err: any) {
      // If network error, offer offline queue fallback
      if (err.message && (err.message.includes('Failed to fetch') || err.message.includes('NetworkError'))) {
        queueOfflineCheckIn({
          ...payload,
          shop_name: searchQuery || customShop || 'Customer Shop',
        })
        setPendingCheckIns(getPendingCheckIns())
        setSuccess('✓ Network unavailable. Check-in queued locally and will auto-sync when online!')
        setSelectedLedger('')
        setSelectedProfileId(null)
        setCustomShop('')
        setComments('')
        setPhoto(null)
        setCoords(null)
        setGpsStatus('idle')
      } else {
        setError(err.message || 'Failed to record check-in')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const filteredShops = useMemo(() => {
    return shops.filter(s =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (s.locality && s.locality.toLowerCase().includes(searchQuery.toLowerCase()))
    ).slice(0, 50)
  }, [searchQuery, shops])

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      {/* Main content scroll */}
      <div className="flex-1 overflow-y-auto px-4 py-5 max-w-xl mx-auto w-full space-y-4">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight flex items-center gap-1.5 text-foreground">
            <MapPin className="h-5.5 w-5.5 text-rose-500" /> Shop Check-In
          </h1>
          <p className="text-[11px] text-muted-foreground mt-0.5">Capture salesperson customer location verification</p>
        </div>

        {/* Navigation Switch Tabs */}
        <div className="flex bg-muted/50 p-1 rounded-xl border border-border max-w-sm sm:max-w-md">
          <Link
            href="/planner"
            className="flex-1 py-2 text-center text-xs font-bold rounded-lg text-muted-foreground hover:text-foreground transition-all flex items-center justify-center gap-1.5"
          >
            <CalendarCheck className="w-3.5 h-3.5" />
            <span>Daily Planner</span>
          </Link>
          <div className="flex-1 py-2 text-center text-xs font-bold rounded-lg bg-background text-foreground shadow-sm border border-border flex items-center justify-center gap-1.5">
            <MapPin className="w-3.5 h-3.5 text-rose-500" />
            <span>Check-In</span>
          </div>
          <Link
            href="/check-in/history"
            className="flex-1 py-2 text-center text-xs font-bold rounded-lg text-muted-foreground hover:text-foreground transition-all flex items-center justify-center gap-1.5"
          >
            <History className="w-3.5 h-3.5" />
            <span>Visit History</span>
          </Link>
        </div>

        {pendingCheckIns.length > 0 && (
          <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 text-xs flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 font-semibold">
              <CloudOff className="w-4 h-4 text-amber-600 shrink-0" />
              <span>{pendingCheckIns.length} check-in(s) queued offline</span>
            </div>
            <button
              type="button"
              onClick={handleManualSync}
              disabled={syncingOffline}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-bold transition-colors"
            >
              <RefreshCw className={cn("w-3 h-3", syncingOffline && "animate-spin")} />
              <span>{syncingOffline ? 'Syncing...' : 'Sync Now'}</span>
            </button>
          </div>
        )}

        {success && <div className="p-3.5 rounded-2xl bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs font-bold">{success}</div>}
        {error && <div className="p-3.5 rounded-2xl bg-destructive/10 text-destructive text-xs font-bold">{error}</div>}

        <form onSubmit={handleSubmit} className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
          {/* Shop selection */}
          <div className="relative">
            <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Customer Shop / Outlet</label>
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
              className="mt-1.5 w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
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
                        className="w-full text-left px-4 py-3 text-xs font-bold hover:bg-muted text-foreground transition-colors flex items-center justify-between"
                      >
                        <div>
                          <span>{toTitleCase(s.name)}</span>
                          {s.locality && (
                            <span className="block text-[10px] text-muted-foreground font-normal">{s.locality}</span>
                          )}
                        </div>
                        {s.source === 'field_profile' ? (
                          <span className="text-[10px] font-semibold text-blue-600 bg-blue-500/10 px-1.5 py-0.5 rounded">Field Lead</span>
                        ) : null}
                      </button>
                    ))
                  )}
                </div>
              </>
            )}

            {(selectedLedger || selectedProfileId) && (
              <div className="bg-green-500/10 border border-green-500/20 text-green-600 dark:text-green-400 p-2.5 rounded-xl text-xs flex items-center gap-1.5 mt-2">
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                <span>Selected: <strong>{searchQuery}</strong></span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2"><div className="flex-1 h-px bg-border" /><span className="text-[10px] text-muted-foreground uppercase font-bold">or</span><div className="flex-1 h-px bg-border" /></div>

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
            <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Comments</label>
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
                  onClick={() => { setPhoto(null); setCoords(null); setGpsStatus('idle') }} 
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
                    <span className="font-bold">Watermarking Map & Address...</span>
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
                    <span className="text-muted-foreground">Getting accurate location...</span>
                  </>
                )}
                {gpsStatus === 'ok' && (
                  <>
                    <CheckCircle className="h-4 w-4 text-emerald-500 shrink-0" />
                    <span className="text-emerald-600">GPS verified: {coords?.lat.toFixed(5)}°, {coords?.lng.toFixed(5)}°</span>
                  </>
                )}
                {gpsStatus === 'error' && (
                  <>
                    <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                    <span className="text-amber-600">Location captured without precise GPS coordinates.</span>
                  </>
                )}
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={submitting || processingPhoto || !photo}
            className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 disabled:opacity-50 transition-all shadow-md shadow-emerald-500/10 cursor-pointer"
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
            <p className="text-xs text-muted-foreground italic">No visits recorded today yet.</p>
          ) : (
            <div className="space-y-2">
              {recentVisits.map(v => (
                <div key={v.id} className="bg-card border border-border rounded-xl p-3.5 space-y-2 shadow-sm hover:border-emerald-500/20 transition-all">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-rose-50 flex items-center justify-center shrink-0">
                      <MapPin className="h-4 w-4 text-rose-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-bold text-xs text-foreground truncate">{v.shopName || v.customShopName || 'Unknown Shop'}</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">{formatDate(v.createdAt)}</p>
                    </div>
                    {v.photoUrl && (
                      <button 
                        onClick={() => setPreviewPhoto(v)}
                        className="text-[10px] font-bold text-emerald-600 border border-emerald-500/30 px-2.5 py-1 rounded-lg hover:bg-emerald-500/10 transition-colors shrink-0 cursor-pointer"
                      >
                        Proof
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="h-16" />
      </div>

      {/* Visit Photo Modal Popup */}
      {previewPhoto && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card w-full max-w-2xl rounded-3xl overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-200 border border-border p-6 space-y-4">
            {/* Modal Header */}
            <div className="flex items-center justify-between">
              <h3 className="font-extrabold text-base text-foreground truncate pr-2">
                Visit Photo - {previewPhoto.shopName || previewPhoto.customShopName || 'Customer Shop'}
              </h3>
              <button
                onClick={() => setPreviewPhoto(null)}
                className="w-8 h-8 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 transition-colors flex items-center justify-center cursor-pointer shrink-0"
              >
                <X className="w-4.5 h-4.5" />
              </button>
            </div>

            {/* Modal Image Display Area */}
            <div className="bg-muted/50 p-4 sm:p-6 rounded-2xl flex items-center justify-center border border-border/50">
              {previewPhoto.photoUrl && (previewPhoto.photoUrl.startsWith('data:') || previewPhoto.photoUrl.startsWith('http')) ? (
                <img
                  src={previewPhoto.photoUrl}
                  alt={`Visit Photo - ${previewPhoto.shopName || previewPhoto.customShopName}`}
                  className="max-h-[72vh] w-auto object-contain rounded-xl shadow-sm"
                />
              ) : (
                <div className="py-12 text-center space-y-2">
                  <MapPin className="h-10 w-10 mx-auto text-emerald-500 opacity-60" />
                  <p className="text-sm font-bold text-foreground">Verified Check-In Record</p>
                  <p className="text-xs text-muted-foreground">{previewPhoto.photoUrl || 'GPS Verified Visit'}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
