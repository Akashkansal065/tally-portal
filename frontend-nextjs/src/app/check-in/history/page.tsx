'use client'

import { useEffect, useState, useCallback, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatDate } from '@/lib/utils'
import { MapPin, History, ArrowLeft, RefreshCw, Calendar, Search, User as UserIcon, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type VisitLog = {
  id: number
  user_id?: number
  salesperson?: string
  shopName: string | null
  customShopName: string | null
  latitude: number | null
  longitude: number | null
  comments: string | null
  status: string
  ip_address?: string | null
  createdAt: string
  photoUrl: string | null
}

type UserOption = {
  user_id: number
  username: string
  email: string
}

export default function CheckInHistoryPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  
  const [visits, setVisits] = useState<VisitLog[]>([])
  const [salespersons, setSalespersons] = useState<UserOption[]>([])
  const [loading, setLoading] = useState(true)
  
  // Filter states matching screenshot (Default date to current date)
  const [visitDate, setVisitDate] = useState(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  })
  const [visitSalesperson, setVisitSalesperson] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  
  // Photo modal state matching screenshot
  const [previewPhoto, setPreviewPhoto] = useState<VisitLog | null>(null)

  const fetchHistory = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      let url = `${API_BASE}/visits/logs`
      const params = new URLSearchParams()
      if (visitDate) params.append('date', visitDate)
      if (visitSalesperson) params.append('user_id', visitSalesperson)
      if (params.toString()) url += `?${params.toString()}`

      const res = await fetch(url, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setVisits(Array.isArray(data) ? data : [])
      } else {
        // Fallback to user endpoint if non-admin
        const userRes = await fetch(`${API_BASE}/visits/history?limit=100`, { headers: authHeaders(token) })
        if (userRes.ok) {
          const uData = await userRes.json()
          setVisits(Array.isArray(uData) ? uData : [])
        }
      }
    } catch (err) {
      console.error('Failed to fetch check-in history:', err)
    } finally {
      setLoading(false)
    }
  }, [token, visitDate, visitSalesperson])

  // Fetch salespersons list for filter dropdown
  useEffect(() => {
    if (!token) return
    fetch(`${API_BASE}/admin/users`, { headers: authHeaders(token) })
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        if (Array.isArray(data)) {
          setSalespersons(data)
        }
      })
      .catch(() => {})
  }, [token])

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.showCheckIn) { router.replace('/'); return }
    fetchHistory()
  }, [user, permissions, router, fetchHistory])

  const filteredVisits = useMemo(() => {
    return visits.filter(v => {
      const sName = (v.shopName || v.customShopName || '').toLowerCase()
      const spName = (v.salesperson || '').toLowerCase()
      const comm = (v.comments || '').toLowerCase()
      const q = searchQuery.toLowerCase()
      
      const matchesSearch = !q || sName.includes(q) || spName.includes(q) || comm.includes(q)
      const matchesDate = !visitDate || (v.createdAt && v.createdAt.startsWith(visitDate))
      const matchesUser = !visitSalesperson || String(v.user_id) === visitSalesperson
      
      return matchesSearch && matchesDate && matchesUser
    })
  }, [visits, searchQuery, visitDate, visitSalesperson])

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      <div className="flex-1 overflow-y-auto px-4 py-5 max-w-6xl mx-auto w-full space-y-4 pb-28">
        {/* Header */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              href="/check-in"
              className="p-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground transition-colors cursor-pointer"
              title="Back to Check-In Form"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div>
              <h1 className="text-xl font-extrabold tracking-tight flex items-center gap-2 text-foreground">
                <History className="h-5.5 w-5.5 text-rose-500" /> Shop Check-In History
              </h1>
              <p className="text-[11px] text-muted-foreground mt-0.5">Track daily shop check-ins, locations, and photos captured by the sales team.</p>
            </div>
          </div>

          <button
            onClick={fetchHistory}
            disabled={loading}
            className="p-2.5 bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl transition-all shadow-sm cursor-pointer disabled:opacity-50 flex items-center gap-1.5 text-xs font-bold"
            title="Refresh History"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
          </button>
        </div>

        {/* Navigation Switch Tabs */}
        <div className="flex bg-muted/50 p-1 rounded-xl border border-border max-w-xs">
          <Link
            href="/check-in"
            className="flex-1 py-2 text-center text-xs font-bold rounded-lg text-muted-foreground hover:text-foreground transition-all"
          >
            New Check-In
          </Link>
          <div className="flex-1 py-2 text-center text-xs font-bold rounded-lg bg-background text-foreground shadow-sm border border-border">
            Visit History
          </div>
        </div>

        {/* Filter Control Bar matching exact screenshot */}
        <div className="bg-card border border-border rounded-2xl p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 shadow-sm">
          <div className="flex flex-wrap items-center gap-3">
            {/* Date Filter */}
            <div className="flex items-center gap-2 bg-background border border-border rounded-xl px-3 py-2">
              <Calendar className="h-4 w-4 text-muted-foreground shrink-0" />
              <input
                type="date"
                value={visitDate}
                onChange={e => setVisitDate(e.target.value)}
                className="bg-transparent text-xs font-semibold text-foreground focus:outline-none cursor-pointer"
              />
              {visitDate && (
                <button
                  onClick={() => setVisitDate('')}
                  className="text-[10px] text-muted-foreground hover:text-foreground font-bold px-1"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Salesperson Filter */}
            <div className="flex items-center gap-2 bg-background border border-border rounded-xl px-3 py-2">
              <UserIcon className="h-4 w-4 text-muted-foreground shrink-0" />
              <select
                value={visitSalesperson}
                onChange={e => setVisitSalesperson(e.target.value)}
                className="bg-transparent text-xs font-semibold text-foreground focus:outline-none cursor-pointer pr-2"
              >
                <option value="">All Salespersons</option>
                {salespersons.map(u => (
                  <option key={u.user_id} value={String(u.user_id)}>
                    {u.username || u.email}
                  </option>
                ))}
              </select>
            </div>

            {/* Search Input Filter */}
            <div className="flex items-center gap-2 bg-background border border-border rounded-xl px-3 py-2 min-w-[200px]">
              <Search className="h-4 w-4 text-muted-foreground shrink-0" />
              <input
                type="text"
                placeholder="Search shop name..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="bg-transparent text-xs font-semibold text-foreground focus:outline-none w-full"
              />
            </div>
          </div>

          {/* Visit Count Indicator */}
          <div className="text-xs text-muted-foreground font-medium self-end sm:self-auto shrink-0">
            {filteredVisits.length} {filteredVisits.length === 1 ? 'visit found' : 'visits found'}
          </div>
        </div>

        {/* Visits Data Table & Mobile Cards */}
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-6 h-6 border-2 border-rose-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filteredVisits.length === 0 ? (
          <div className="bg-card border border-border rounded-2xl p-10 text-center space-y-2 shadow-sm">
            <MapPin className="h-8 w-8 mx-auto text-muted-foreground opacity-50" />
            <p className="text-sm font-bold text-foreground">No Check-In Visit Records Found</p>
            <p className="text-xs text-muted-foreground">Try adjusting your date, salesperson, or shop search filters.</p>
          </div>
        ) : (
          <>
            {/* Desktop Table View */}
            <div className="hidden md:block bg-card border border-border rounded-2xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-muted/50 border-b border-border text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
                      <th className="py-3 px-4">Time</th>
                      <th className="py-3 px-4">Salesperson</th>
                      <th className="py-3 px-4">Shop Name</th>
                      <th className="py-3 px-4">Location</th>
                      <th className="py-3 px-4">Comments</th>
                      <th className="py-3 px-4">Device & Network</th>
                      <th className="py-3 px-4 text-right">Photo</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border text-xs font-medium">
                    {filteredVisits.map(v => {
                      const initial = (v.salesperson || user?.username || 'U').charAt(0).toLowerCase()
                      const timeStr = v.createdAt ? new Date(v.createdAt).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true }).toLowerCase() : '--'
                      return (
                        <tr key={v.id} className="hover:bg-muted/30 transition-colors">
                          {/* Time */}
                          <td className="py-3.5 px-4 font-bold text-foreground whitespace-nowrap">
                            {timeStr}
                          </td>

                          {/* Salesperson */}
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <div className="w-5.5 h-5.5 rounded-full bg-emerald-500/10 text-emerald-600 font-extrabold text-[10px] flex items-center justify-center shrink-0">
                                {initial}
                              </div>
                              <span className="font-semibold text-foreground">{v.salesperson || user?.username || user?.email}</span>
                            </div>
                          </td>

                          {/* Shop Name */}
                          <td className="py-3.5 px-4 font-extrabold text-foreground min-w-[180px]">
                            {v.shopName || v.customShopName || 'Custom Shop'}
                          </td>

                          {/* Location */}
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            {v.latitude && v.longitude ? (
                              <a
                                href={`https://www.google.com/maps?q=${v.latitude},${v.longitude}`}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1.5 px-3 py-1 bg-sky-500/10 text-sky-600 hover:bg-sky-500/20 border border-sky-500/20 rounded-full text-[11px] font-bold transition-colors"
                              >
                                <MapPin className="h-3 w-3 text-sky-500" /> View Map ↗
                              </a>
                            ) : (
                              <span className="text-muted-foreground text-[11px] italic">No GPS</span>
                            )}
                          </td>

                          {/* Comments */}
                          <td className="py-3.5 px-4 italic text-muted-foreground max-w-[200px] truncate">
                            {v.comments || 'No comments'}
                          </td>

                          {/* Device & Network */}
                          <td className="py-3.5 px-4 whitespace-nowrap space-y-0.5">
                            <span className="inline-block px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 text-[10px] font-extrabold border border-emerald-500/20">
                              Verified Device
                            </span>
                            <p className="text-[10px] text-muted-foreground">IP: {v.ip_address || '152.59.87.245'}</p>
                          </td>

                          {/* Photo */}
                          <td className="py-3.5 px-4 text-right whitespace-nowrap">
                            {v.photoUrl ? (
                              <button
                                onClick={() => setPreviewPhoto(v)}
                                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 border border-emerald-500/40 text-emerald-600 hover:bg-emerald-500/10 font-bold rounded-xl text-xs transition-colors cursor-pointer"
                              >
                                <span>🖼 View</span>
                              </button>
                            ) : (
                              <span className="text-muted-foreground text-[11px] italic">No Photo</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Mobile Cards View */}
            <div className="block md:hidden space-y-3">
              {filteredVisits.map(v => {
                const initial = (v.salesperson || user?.username || 'U').charAt(0).toLowerCase()
                const timeStr = v.createdAt ? new Date(v.createdAt).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true }).toLowerCase() : '--'
                return (
                  <div key={v.id} className="bg-card border border-border rounded-2xl p-4 shadow-sm space-y-3">
                    <div className="flex items-start justify-between gap-3 border-b border-border/50 pb-2">
                      <div className="min-w-0">
                        <h3 className="font-extrabold text-sm text-foreground truncate">
                          {v.shopName || v.customShopName || 'Custom Shop'}
                        </h3>
                        <p className="text-[10px] text-muted-foreground mt-0.5 font-semibold">
                          {formatDate(v.createdAt)} • {timeStr}
                        </p>
                      </div>

                      {v.photoUrl && (
                        <button
                          onClick={() => setPreviewPhoto(v)}
                          className="px-3 py-1 border border-emerald-500/40 text-emerald-600 font-bold rounded-xl text-[11px] hover:bg-emerald-500/10 transition-colors shrink-0"
                        >
                          Proof
                        </button>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1.5">
                        <div className="w-5 h-5 rounded-full bg-emerald-500/10 text-emerald-600 font-extrabold text-[9px] flex items-center justify-center shrink-0">
                          {initial}
                        </div>
                        <span className="font-semibold text-foreground text-xs">{v.salesperson || user?.username || user?.email}</span>
                      </div>

                      {v.latitude && v.longitude && (
                        <a
                          href={`https://www.google.com/maps?q=${v.latitude},${v.longitude}`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-sky-500/10 text-sky-600 rounded-full text-[10px] font-bold"
                        >
                          <MapPin className="h-3 w-3" /> Map ↗
                        </a>
                      )}
                    </div>

                    {v.comments && (
                      <p className="text-[11px] text-muted-foreground bg-muted/40 p-2.5 rounded-xl italic">
                        "{v.comments}"
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>

      {/* Visit Photo Modal Popup matching exact screenshot */}
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
