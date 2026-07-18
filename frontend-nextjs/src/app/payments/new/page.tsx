'use client'

import { useEffect, useState, useRef, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, toTitleCase } from '@/lib/utils'
import { stampPhoto } from '@/lib/photo-stamping'
import { 
  ArrowLeft, 
  Search, 
  Store, 
  CheckCircle2, 
  Camera, 
  X, 
  AlertTriangle, 
  CheckCircle,
  IndianRupee
} from 'lucide-react'
import { cn } from '@/lib/utils'

type Ledger = { ledger_id: number; name: string; is_customer?: boolean }

const MODES = ['Cash', 'Cheque', 'Online']

export default function NewPaymentPage() {
  const { user, token } = useAuth()
  const router = useRouter()
  
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  // Cache data
  const [cachedShops, setCachedShops] = useState<Ledger[]>([])

  // Form State
  const [shopQuery, setShopQuery] = useState('')
  const [selectedShop, setSelectedShop] = useState<Ledger | null>(null)
  const [showShopDropdown, setShowShopDropdown] = useState(false)
  const shopDropdownRef = useRef<HTMLDivElement>(null)

  const [amount, setAmount] = useState('')
  const [mode, setMode] = useState('Cash')
  const [comments, setComments] = useState('')
  
  // GPS/Photo status
  const [gpsStatus, setGpsStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null)
  const [photo, setPhoto] = useState<string | null>(null)
  const [processingPhoto, setProcessingPhoto] = useState(false)

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    
    // Fetch cache
    fetch(`${API_BASE}/ledgers`, { headers: authHeaders(token) })
      .then(r => r.json())
      .then(data => {
        const customers = Array.isArray(data) ? data.filter((l: any) => l.is_customer) : []
        setCachedShops(customers)
      })
      .finally(() => setLoading(false))
  }, [user, token, router])

  // Handle clicking outside dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (shopDropdownRef.current && !shopDropdownRef.current.contains(event.target as Node)) {
        setShowShopDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Filtered Shops
  const filteredShops = useMemo(() => {
    if (shopQuery.trim().length < 2) return []
    return cachedShops.filter(s =>
      s.name.toLowerCase().includes(shopQuery.toLowerCase())
    ).slice(0, 15)
  }, [shopQuery, cachedShops])

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
    if (!selectedShop) { setError('Select a customer first.'); return }
    if (!amount || parseFloat(amount) <= 0) { setError('Enter a valid payment amount.'); return }
    
    setSubmitting(true)
    setError('')

    try {
      const payload = {
        ledger_id: selectedShop.ledger_id,
        amount: parseFloat(amount),
        payment_mode: mode,
        comments: comments.trim() || null,
        photo_base64: photo || null
      }

      const res = await fetch(`${API_BASE}/payment/collect`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to submit payment collect request')
      }

      router.push('/payments')
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      <div className="flex-1 overflow-y-auto px-4 py-5 max-w-xl mx-auto w-full space-y-4">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight flex items-center gap-1.5 text-foreground">
            <IndianRupee className="h-5.5 w-5.5 text-emerald-500" /> Collect Payment
          </h1>
          <p className="text-[11px] text-muted-foreground mt-0.5">Record customer payment collection with location watermark proofs</p>
        </div>

        {error && <div className="p-3.5 rounded-2xl bg-destructive/10 text-destructive text-xs font-bold">{error}</div>}

        <form onSubmit={handleSubmit} className="bg-card border border-border rounded-2xl p-5 space-y-4 shadow-sm">
          {/* Customer Selection */}
          <div className="relative" ref={shopDropdownRef}>
            <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Registered Customer Ledger</label>
            <div className="relative mt-1.5">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search customer shop name..."
                value={shopQuery}
                onChange={e => {
                  setShopQuery(e.target.value)
                  setShowShopDropdown(true)
                  if (selectedShop) setSelectedShop(null)
                }}
                onFocus={() => setShowShopDropdown(true)}
                className="w-full pl-9 pr-3 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            {showShopDropdown && shopQuery.trim().length >= 2 && (
              <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-xl shadow-lg max-h-60 overflow-y-auto divide-y divide-border/50">
                {filteredShops.length === 0 ? (
                  <p className="p-3.5 text-xs text-muted-foreground text-center">No customers found</p>
                ) : (
                  filteredShops.map(shop => (
                    <button
                      key={shop.ledger_id}
                      type="button"
                      onClick={() => {
                        setSelectedShop(shop)
                        setShopQuery(toTitleCase(shop.name))
                        setShowShopDropdown(false)
                      }}
                      className="w-full text-left p-3.5 hover:bg-muted text-xs font-semibold text-foreground flex items-center gap-2"
                    >
                      <Store className="h-4 w-4 text-emerald-500 shrink-0" />
                      <span>{toTitleCase(shop.name)}</span>
                    </button>
                  ))
                )}
              </div>
            )}

            {selectedShop && (
              <div className="bg-green-500/10 border border-green-500/20 text-green-600 dark:text-green-400 p-2.5 rounded-xl text-xs flex items-center gap-1.5 mt-2">
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                <span>Selected: <strong>{toTitleCase(selectedShop.name)}</strong></span>
              </div>
            )}
          </div>

          {/* Amount and Mode */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Amount Collected (₹)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="0.00"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Payment Mode</label>
              <select
                value={mode}
                onChange={e => setMode(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                {MODES.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Comments */}
          <div>
            <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Comments / Notes</label>
            <textarea
              placeholder="Cheque no., UPI transaction ID, bank details..."
              value={comments}
              onChange={e => setComments(e.target.value)}
              rows={2}
              className="mt-1.5 w-full px-3.5 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
            />
          </div>

          {/* Capture Receipt Proof Photo */}
          <div>
            <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Receipt Proof Photo (Optional)</label>
            {photo ? (
              <div className="relative rounded-2xl overflow-hidden border border-border mt-2 shadow-sm">
                <img src={photo} alt="payment receipt proof" className="w-full h-44 object-cover" />
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
                    <span className="font-bold">Take Geocoded Receipt Photo</span>
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
            disabled={submitting || processingPhoto || !selectedShop || !amount}
            className="w-full py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 disabled:opacity-50 transition-all shadow-md shadow-emerald-500/10 cursor-pointer animate-none"
          >
            {submitting && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
            Submit Collected Payment
          </button>
        </form>

        <div className="h-16" />
      </div>
    </div>
  )
}
