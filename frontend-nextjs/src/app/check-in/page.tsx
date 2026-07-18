'use client'

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase } from '@/lib/utils'
import { stampPhoto } from '@/lib/photo-stamping'
import { MapPin, Camera, CheckCircle, Clock, AlertTriangle, ChevronLeft, Search, CheckCircle2, X } from 'lucide-react'
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

type Ledger = { ledger_id: number; name: string; is_customer?: boolean }

export default function CheckInPage() {
  const { user, token } = useAuth()
  const router = useRouter()
  const [ledgers, setLedgers] = useState<Ledger[]>([])
  const [recentVisits, setRecentVisits] = useState<RecentVisit[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')

  // Form state
  const [selectedLedger, setSelectedLedger] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [customShop, setCustomShop] = useState('')
  const [comments, setComments] = useState('')
  
  // GPS/Photo states
  const [gpsStatus, setGpsStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null)
  const [photo, setPhoto] = useState<string | null>(null)
  const [processingPhoto, setProcessingPhoto] = useState(false)

  useEffect(() => {
    if (selectedLedger === '') {
      setSearchQuery('')
    }
  }, [selectedLedger])

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    Promise.all([
      fetch(`${API_BASE}/ledgers`, { headers: authHeaders(token) }).then(r => r.json()),
      fetch(`${API_BASE}/visits/recent`, { headers: authHeaders(token) }).then(r => r.json()).catch(() => []),
    ]).then(([ls, vs]) => {
      const customers = Array.isArray(ls) ? ls.filter((l: any) => l.is_customer) : []
      setLedgers(customers)
      setRecentVisits(Array.isArray(vs) ? vs : (vs?.data ?? []))
    }).finally(() => setLoading(false))
  }, [user, token, router])

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedLedger && !customShop) { setError('Select a shop or enter custom shop name.'); return }
    if (!photo) { setError('Please capture a watermarked photo first.'); return }

    setSubmitting(true)
    setError('')
    setSuccess('')

    try {
      const res = await fetch(`${API_BASE}/visits/check-in`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          ledger_id: selectedLedger ? parseInt(selectedLedger) : null,
          custom_shop_name: customShop || null,
          latitude: coords?.lat || null,
          longitude: coords?.lng || null,
          comments,
          photo_base64: photo,
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Failed')
      setSuccess('✓ Check-in recorded successfully!')
      setSelectedLedger(''); setCustomShop(''); setComments(''); setPhoto(null); setCoords(null); setGpsStatus('idle')
      
      // Refresh recent
      const vs = await fetch(`${API_BASE}/visits/recent`, { headers: authHeaders(token) }).then(r => r.json()).catch(() => [])
      setRecentVisits(Array.isArray(vs) ? vs : (vs?.data ?? []))
    } catch (err: any) {
      setError(err.message || 'Failed to check-in')
    } finally {
      setSubmitting(false)
    }
  }

  const filteredLedgers = useMemo(() => {
    return ledgers.filter(l =>
      l.name.toLowerCase().includes(searchQuery.toLowerCase())
    ).slice(0, 15)
  }, [searchQuery, ledgers])

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

        {success && <div className="p-3.5 rounded-2xl bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs font-bold">{success}</div>}
        {error && <div className="p-3.5 rounded-2xl bg-destructive/10 text-destructive text-xs font-bold">{error}</div>}

        <form onSubmit={handleSubmit} className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
          {/* Shop selection */}
          <div className="relative">
            <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Registered Customer Ledger</label>
            <input
              type="text"
              placeholder="Search customer shop name..."
              value={searchQuery}
              onChange={e => {
                setSearchQuery(e.target.value)
                setIsOpen(true)
                if (e.target.value === '') {
                  setSelectedLedger('')
                }
              }}
              onFocus={() => setIsOpen(true)}
              className="mt-1.5 w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            {isOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
                <div className="absolute left-0 right-0 mt-1 max-h-56 overflow-y-auto bg-popover border border-border rounded-xl shadow-lg z-50 divide-y divide-border/50">
                  {filteredLedgers.length === 0 ? (
                    <div className="p-3.5 text-xs text-muted-foreground text-center">No customers found</div>
                  ) : (
                    filteredLedgers.map(l => (
                      <button
                        key={l.ledger_id}
                        type="button"
                        onClick={() => {
                          setSelectedLedger(String(l.ledger_id))
                          setSearchQuery(toTitleCase(l.name))
                          setIsOpen(false)
                        }}
                        className="w-full text-left px-4 py-3.5 text-xs font-bold hover:bg-muted text-foreground transition-colors"
                      >
                        {toTitleCase(l.name)}
                      </button>
                    ))
                  )}
                </div>
              </>
            )}

            {selectedLedger && (
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
                <div key={v.id} className="bg-card border border-border rounded-xl p-3.5 flex items-center gap-3 shadow-sm hover:border-emerald-500/20 transition-all">
                  <div className="w-8 h-8 rounded-lg bg-rose-50 flex items-center justify-center shrink-0">
                    <MapPin className="h-4 w-4 text-rose-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-bold text-xs text-foreground truncate">{v.shopName || v.customShopName || 'Unknown Shop'}</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">{formatDate(v.createdAt)}</p>
                  </div>
                  {v.photoUrl && (
                    <button 
                      onClick={() => window.open(v.photoUrl || '', '_blank')}
                      className="text-[10px] font-bold text-emerald-500 border border-emerald-500/20 px-2 py-1 rounded hover:bg-emerald-500/5 transition-colors shrink-0"
                    >
                      Proof
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="h-16" />
      </div>
    </div>
  )
}
