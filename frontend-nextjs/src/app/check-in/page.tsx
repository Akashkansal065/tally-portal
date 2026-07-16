'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, formatDate, toTitleCase } from '@/lib/utils'
import { MapPin, Camera, CheckCircle, Clock, AlertTriangle } from 'lucide-react'
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
  const [gpsStatus, setGpsStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null)
  const [photo, setPhoto] = useState<string | null>(null)

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
      setLedgers(customers.slice(0, 200))
      setRecentVisits(Array.isArray(vs) ? vs : (vs?.data ?? []))
    }).finally(() => setLoading(false))
  }, [user, token, router])

  const getGPSCoordinates = (): Promise<{ lat: number; lng: number }> => {
    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        pos => {
          const c = { lat: pos.coords.latitude, lng: pos.coords.longitude }
          setCoords(c)
          setGpsStatus('ok')
          resolve(c)
        },
        () => {
          setGpsStatus('error')
          reject(new Error('GPS capture failed. Please enable location permissions.'))
        },
        { enableHighAccuracy: true, timeout: 10000 }
      )
    })
  }

  const getGPS = () => {
    setGpsStatus('loading')
    getGPSCoordinates().catch(() => {})
  }

  const handlePhoto = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => setPhoto(ev.target?.result as string)
    reader.readAsDataURL(file)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedLedger && !customShop) { setError('Select a shop or enter custom shop name.'); return }
    setSubmitting(true); setError(''); setSuccess('')

    let currentCoords = coords
    if (!currentCoords) {
      setGpsStatus('loading')
      try {
        currentCoords = await getGPSCoordinates()
      } catch (err: any) {
        setError(err.message)
        setSubmitting(false)
        return
      }
    }

    try {
      const res = await fetch(`${API_BASE}/visits/check-in`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          ledger_id: selectedLedger ? parseInt(selectedLedger) : null,
          custom_shop_name: customShop || null,
          latitude: currentCoords.lat,
          longitude: currentCoords.lng,
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
  const filteredLedgers = ledgers.filter(l =>
    l.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="p-4 max-w-2xl mx-auto space-y-5">
      <h1 className="text-xl font-extrabold flex items-center gap-2">
        <MapPin className="h-5 w-5 text-rose-500" /> Shop Check-In
      </h1>

      {success && <div className="p-3 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-sm font-medium">{success}</div>}
      {error && <div className="p-3 rounded-xl bg-destructive/10 text-destructive text-sm">{error}</div>}

      <form onSubmit={handleSubmit} className="bg-card border border-border rounded-2xl p-5 space-y-4">
        {/* Shop selection */}
        <div className="relative">
          <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Shop (from Ledger)</label>
          <input
            type="text"
            className="w-full px-4 py-3 rounded-xl border border-border bg-muted/40 text-sm focus:outline-none focus:ring-2 focus:ring-primary font-medium text-foreground"
            placeholder="Search & select party..."
            value={searchQuery}
            onChange={e => {
              setSearchQuery(e.target.value)
              if (e.target.value === '') {
                setSelectedLedger('')
              }
              setIsOpen(true)
            }}
            onFocus={() => setIsOpen(true)}
          />
          {isOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
              <div className="absolute left-0 right-0 mt-1 max-h-60 overflow-y-auto bg-card border border-border rounded-xl shadow-lg z-50 divide-y divide-border/50">
                {filteredLedgers.length === 0 ? (
                  <div className="p-3 text-xs text-muted-foreground text-center">No parties found</div>
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
                      className="w-full text-left px-4 py-3 text-sm hover:bg-muted font-medium transition-colors text-foreground"
                    >
                      {toTitleCase(l.name)}
                    </button>
                  ))
                )}
              </div>
            </>
          )}
        </div>

        <div className="flex items-center gap-2"><div className="flex-1 h-px bg-border" /><span className="text-xs text-muted-foreground">or</span><div className="flex-1 h-px bg-border" /></div>

        <div>
          <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Custom Shop Name</label>
          <input type="text" className="w-full px-4 py-3 rounded-xl border border-border bg-muted/40 text-sm focus:outline-none focus:ring-2 focus:ring-primary" placeholder="Enter shop name..." value={customShop} onChange={e => setCustomShop(e.target.value)} />
        </div>

        {/* GPS */}
        <div>
          <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">GPS Location</label>
          <button type="button" onClick={getGPS} className={cn('w-full py-3 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-all', gpsStatus === 'ok' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30' : gpsStatus === 'error' ? 'bg-destructive/10 text-destructive' : 'bg-muted hover:bg-muted/80 text-muted-foreground')}>
            {gpsStatus === 'loading' && <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />}
            {gpsStatus === 'ok' && <CheckCircle className="h-4 w-4" />}
            {gpsStatus === 'error' && <AlertTriangle className="h-4 w-4" />}
            {gpsStatus === 'idle' && <MapPin className="h-4 w-4" />}
            {gpsStatus === 'idle' ? 'Capture GPS Location' : gpsStatus === 'loading' ? 'Getting location...' : gpsStatus === 'ok' ? `${coords?.lat.toFixed(5)}, ${coords?.lng.toFixed(5)}` : 'GPS failed — tap to retry'}
          </button>
        </div>

        {/* Photo */}
        <div>
          <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Verification Photo (Optional)</label>
          {photo ? (
            <div className="relative rounded-xl overflow-hidden border border-border">
              <img src={photo} alt="preview" className="w-full h-36 object-cover" />
              <button type="button" onClick={() => setPhoto(null)} className="absolute top-2 right-2 bg-black/60 text-white rounded-full p-1"><Camera className="h-3 w-3" /></button>
            </div>
          ) : (
            <label className="w-full flex flex-col items-center py-6 rounded-xl border-2 border-dashed border-border hover:border-primary/50 hover:bg-muted/30 cursor-pointer transition-all">
              <Camera className="h-7 w-7 text-muted-foreground mb-1" />
              <span className="text-xs text-muted-foreground">Tap to capture shop photo</span>
              <input type="file" accept="image/*" capture="environment" className="hidden" onChange={handlePhoto} />
            </label>
          )}
        </div>

        <div>
          <label className="block text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Notes / Collection Details</label>
          <textarea className="w-full px-4 py-3 rounded-xl border border-border bg-muted/40 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none" rows={2} placeholder="Visit notes, amounts collected..." value={comments} onChange={e => setComments(e.target.value)} />
        </div>

        <button type="submit" disabled={submitting} className="w-full py-3 bg-primary hover:bg-primary/90 text-white font-bold rounded-xl transition-all active:scale-[0.98] disabled:opacity-50 text-sm flex items-center justify-center gap-2">
          {submitting && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
          {submitting ? 'Checking In...' : 'Confirm Check-In'}
        </button>
      </form>

      {/* Recent visits */}
      <div>
        <h2 className="font-bold text-sm mb-3 text-muted-foreground uppercase tracking-wider">Recent Visits</h2>
        <div className="space-y-2">
          {recentVisits.length === 0 && !loading && (
            <p className="text-xs text-muted-foreground text-center py-4">No recent visits logged.</p>
          )}
          {recentVisits.map(v => (
            <div key={v.id} className="bg-card border border-border rounded-2xl p-4 flex items-start gap-3">
              <div className="w-8 h-8 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center shrink-0">
                <CheckCircle className="h-4 w-4 text-emerald-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm">{toTitleCase(v.shopName || v.customShopName || 'Unknown Shop')}</p>
                <p className="text-xs text-muted-foreground">{formatDate(v.createdAt)}</p>
                {v.comments && <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{v.comments}</p>}
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 rounded-full shrink-0">Verified</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
