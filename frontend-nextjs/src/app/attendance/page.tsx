'use client'

import React, { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatDate } from '@/lib/utils'
import { stampPhoto } from '@/lib/photo-stamping'
import { 
  Clock, 
  MapPin, 
  Camera, 
  Loader2, 
  CheckCircle2, 
  ArrowLeft,
  ChevronRight,
  Users,
  Calendar,
  Search,
  CheckCircle,
  XCircle,
  FileText,
  LogOut
} from 'lucide-react'
import { cn } from '@/lib/utils'

type AttendanceRecord = {
  id: number
  userId: number
  username?: string
  checkInTime: string
  checkOutTime: string | null
  checkInLatitude: string | null
  checkInLongitude: string | null
  checkOutLatitude: string | null
  checkOutLongitude: string | null
  checkInPhotoUrl: string | null
  checkOutPhotoUrl: string | null
  checkInComments: string | null
  checkOutComments: string | null
  checkInIpAddress: string | null
  checkOutIpAddress: string | null
}

type TeamAttendanceItem = {
  userId: number
  username: string
  isActive: boolean
  attendance: AttendanceRecord | null
}

export default function AttendancePage() {
  const router = useRouter()
  const { token, user, permissions } = useAuth()
  
  // Navigation tabs
  const [activeTab, setActiveTab] = useState<'punch' | 'history' | 'admin'>('punch')
  const [adminSubTab, setAdminSubTab] = useState<'today' | 'history'>('today')

  // Attendance states
  const [todayAttendance, setTodayAttendance] = useState<AttendanceRecord | null>(null)
  const [history, setHistory] = useState<AttendanceRecord[]>([])
  const [teamAttendance, setTeamAttendance] = useState<TeamAttendanceItem[]>([])
  const [teamHistory, setTeamHistory] = useState<AttendanceRecord[]>([])
  
  // Punch inputs
  const [comments, setComments] = useState('')
  const [photo, setPhoto] = useState<string | null>(null)
  const [stampedCoords, setStampedCoords] = useState<{ lat: number | null, lng: number | null } | null>(null)
  const [processingPhoto, setProcessingPhoto] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  
  // Clock states
  const [currentTime, setCurrentTime] = useState<Date | null>(null)
  const [elapsedTime, setElapsedTime] = useState('00:00:00')

  // Admin filter states
  const [filterDate, setFilterDate] = useState<string>(new Date().toISOString().split('T')[0])
  const [rangeStart, setRangeStart] = useState<string>(new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const [rangeEnd, setRangeEnd] = useState<string>(new Date().toISOString().split('T')[0])
  const [searchTerm, setSearchTerm] = useState('')
  
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Redirect if not loaded or unauthorized
  useEffect(() => {
    if (!token && !localStorage.getItem('mytally_token')) {
      router.push('/login')
    } else if (permissions && !permissions.showAttendance) {
      router.replace('/')
    }
  }, [token, permissions, router])

  // Fetch initial personal details
  useEffect(() => {
    if (!token) return
    fetchTodayStatus()
    fetchPersonalHistory()
  }, [token])

  // Fetch team attendance when active
  useEffect(() => {
    if (!token || !user?.permissions?.isAdmin) return
    if (activeTab === 'admin') {
      if (adminSubTab === 'today') {
        fetchTeamAttendance()
      } else {
        fetchTeamHistory()
      }
    }
  }, [activeTab, adminSubTab, filterDate, token])

  // Refresh clock every second
  useEffect(() => {
    setCurrentTime(new Date())
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  // Calculate elapsed time
  useEffect(() => {
    if (!todayAttendance || todayAttendance.checkOutTime) {
      setElapsedTime('00:00:00')
      return
    }

    const interval = setInterval(() => {
      const checkIn = new Date(todayAttendance.checkInTime).getTime()
      const diff = Date.now() - checkIn
      
      const hrs = Math.floor(diff / 3600000)
      const mins = Math.floor((diff % 3600000) / 60000)
      const secs = Math.floor((diff % 60000) / 1000)
      
      const pad = (n: number) => String(n).padStart(2, '0')
      setElapsedTime(`${pad(hrs)}:${pad(mins)}:${pad(secs)}`)
    }, 1000)

    return () => clearInterval(interval)
  }, [todayAttendance])

  const fetchTodayStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/attendance/today`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setTodayAttendance(data.attendance)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const fetchPersonalHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/attendance/history`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setHistory(data.history || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const fetchTeamAttendance = async () => {
    try {
      const res = await fetch(`${API_BASE}/attendance/admin/today-team?dateStr=${filterDate}`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setTeamAttendance(data.data || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const fetchTeamHistory = async () => {
    try {
      setTeamHistory([])
      const res = await fetch(`${API_BASE}/attendance/admin/history-team?startDateStr=${rangeStart}&endDateStr=${rangeEnd}`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setTeamHistory(data.history || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setProcessingPhoto(true)
    try {
      const stamp = await stampPhoto(file)
      setPhoto(stamp.photoBase64)
      setStampedCoords({ lat: stamp.lat, lng: stamp.lng })
    } catch (err: any) {
      alert(err.message || 'Failed to capture geolocation or render canvas.')
    } finally {
      setProcessingPhoto(false)
    }
  }

  const handlePunch = async (punchType: 'in' | 'out') => {
    if (!photo) {
      alert('Selfie photo is required to punch attendance.')
      return
    }
    setSubmitting(true)
    try {
      const finger = Math.random().toString(36).substring(2, 15) // simple local finger
      const res = await fetch(`${API_BASE}/attendance/punch`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          type: punchType,
          latitude: stampedCoords?.lat || 0.0,
          longitude: stampedCoords?.lng || 0.0,
          deviceFingerprint: finger,
          photoBase64: photo,
          comments
        })
      })
      
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Punch failed')
      }

      alert(`Punched ${punchType === 'in' ? 'In' : 'Out'} successfully.`)
      setPhoto(null)
      setComments('')
      setStampedCoords(null)
      fetchTodayStatus()
      fetchPersonalHistory()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const formatTimeStr = (isoString: string | null) => {
    if (!isoString) return '--:--'
    return new Date(isoString).toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    })
  }

  const getWorkingDuration = (inTime: string, outTime: string | null) => {
    if (!outTime) return 'In Progress'
    const diff = new Date(outTime).getTime() - new Date(inTime).getTime()
    const hrs = Math.floor(diff / 3600000)
    const mins = Math.floor((diff % 3600000) / 60000)
    return `${hrs}h ${mins}m`
  }

  // Filtered lists
  const filteredTeamToday = teamAttendance.filter(item => 
    item.username.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const filteredTeamHistory = teamHistory.filter(item => 
    item.username?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="min-h-screen bg-background pb-12">
      {/* Header */}
      <div className="border-b border-border bg-card/50 backdrop-blur-md sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 h-16 flex items-center justify-between">
          <button 
            onClick={() => router.push('/')}
            className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            <ArrowLeft className="h-4 w-4" /> Back to Dashboard
          </button>
          
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-sky-500 animate-pulse" />
            <span className="text-xs font-bold text-foreground">
              {currentTime ? currentTime.toLocaleTimeString('en-IN', { hour12: true }) : '--:--:--'}
            </span>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 mt-6 space-y-6">
        {/* Title */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black tracking-tight text-foreground">Daily Attendance</h1>
            <p className="text-xs text-muted-foreground mt-0.5">Punch-in or checkout with secure GPS maps and selfie verification</p>
          </div>

          {user?.permissions?.isAdmin && (
            <div className="flex bg-muted/60 p-0.5 rounded-xl border border-border">
              <button
                onClick={() => setActiveTab('punch')}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
                  activeTab === 'punch' ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                )}
              >
                Log Attendance
              </button>
              <button
                onClick={() => setActiveTab('admin')}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1",
                  activeTab === 'admin' ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Users className="h-3.5 w-3.5" /> Team Logs
              </button>
            </div>
          )}
        </div>

        {activeTab === 'punch' ? (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
            {/* Punch Panel */}
            <div className="md:col-span-3 space-y-6">
              <div className="bg-card border border-border rounded-2xl p-5 shadow-sm space-y-5">
                <div className="flex justify-between items-start border-b pb-4">
                  <div>
                    <h2 className="font-bold text-sm text-foreground">Terminal Access</h2>
                    <p className="text-[10px] text-muted-foreground mt-0.5">Device verify shifts and break logs</p>
                  </div>
                  {todayAttendance ? (
                    <span className="text-[10px] py-1 px-2.5 rounded-full font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3" /> Punch-In Registered
                    </span>
                  ) : (
                    <span className="text-[10px] py-1 px-2.5 rounded-full font-bold bg-amber-500/10 text-amber-600 border border-amber-500/20">
                      Clock-In Pending
                    </span>
                  )}
                </div>

                {todayAttendance && !todayAttendance.checkOutTime && (
                  <div className="bg-sky-500/5 border border-sky-500/10 rounded-xl p-4 flex flex-col items-center justify-center gap-1.5">
                    <span className="text-[10px] text-muted-foreground uppercase font-black tracking-widest">Active Working Duration</span>
                    <span className="text-3xl font-black text-sky-600 tracking-tight">{elapsedTime}</span>
                    <span className="text-[10px] text-muted-foreground mt-1">Clocked in at {formatTimeStr(todayAttendance.checkInTime)}</span>
                  </div>
                )}

                {todayAttendance?.checkOutTime && (
                  <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-xl p-4 flex flex-col items-center justify-center gap-1.5">
                    <span className="text-[10px] text-muted-foreground uppercase font-black tracking-widest">Shift Completed</span>
                    <span className="text-sm font-bold text-emerald-600">You clocked out at {formatTimeStr(todayAttendance.checkOutTime)}</span>
                    <span className="text-[10px] text-muted-foreground">Total worked: {getWorkingDuration(todayAttendance.checkInTime, todayAttendance.checkOutTime)}</span>
                  </div>
                )}

                {!todayAttendance?.checkOutTime && (
                  <div className="space-y-4">
                    {/* Selfie Box */}
                    <div>
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide">Watermarked Verification Photo</label>
                      {photo ? (
                        <div className="relative rounded-2xl overflow-hidden border border-border mt-1.5">
                          <img src={photo} alt="selfie check-in" className="w-full h-48 object-cover" />
                          <button 
                            type="button" 
                            onClick={() => { setPhoto(null); setStampedCoords(null) }}
                            className="absolute top-3 right-3 bg-black/80 hover:bg-black text-white rounded-full p-2 text-xs transition-colors cursor-pointer"
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        </div>
                      ) : (
                        <label className="mt-1.5 w-full flex flex-col items-center justify-center gap-2 py-10 rounded-2xl border-2 border-dashed border-border hover:border-sky-500/50 cursor-pointer text-xs text-muted-foreground bg-muted/20 hover:bg-muted/30 transition-all">
                          {processingPhoto ? (
                            <>
                              <Loader2 className="h-5 w-5 text-sky-500 animate-spin" />
                              <span className="font-semibold text-foreground">Geocoding map watermark...</span>
                            </>
                          ) : (
                            <>
                              <Camera className="h-6 w-6 text-sky-500" />
                              <span className="font-semibold">Tap to Take Selfie</span>
                              <span className="text-[10px] text-muted-foreground/80">Stamps current GPS address and timestamp</span>
                            </>
                          )}
                          <input 
                            ref={fileInputRef} 
                            type="file" 
                            accept="image/*" 
                            capture="user" 
                            onChange={handlePhotoUpload} 
                            disabled={processingPhoto} 
                            className="hidden" 
                          />
                        </label>
                      )}
                    </div>

                    {/* Comments */}
                    <div>
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide">Remarks / Comments (Optional)</label>
                      <input 
                        type="text"
                        placeholder="Add checking notes..."
                        value={comments}
                        onChange={e => setComments(e.target.value)}
                        className="mt-1.5 w-full px-3.5 py-2 bg-muted/40 border border-border rounded-xl text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-sky-500 h-10"
                      />
                    </div>

                    {/* Action buttons */}
                    <div className="pt-2">
                      {!todayAttendance ? (
                        <button
                          onClick={() => handlePunch('in')}
                          disabled={submitting || !photo}
                          className="w-full py-3 bg-sky-500 hover:bg-sky-600 disabled:bg-muted disabled:text-muted-foreground font-bold text-white rounded-xl text-xs transition-all shadow-md flex items-center justify-center gap-1.5 cursor-pointer"
                        >
                          {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Clock className="h-3.5 w-3.5" />}
                          Punch-In Today
                        </button>
                      ) : (
                        <button
                          onClick={() => handlePunch('out')}
                          disabled={submitting || !photo}
                          className="w-full py-3 bg-rose-500 hover:bg-rose-600 disabled:bg-muted disabled:text-muted-foreground font-bold text-white rounded-xl text-xs transition-all shadow-md flex items-center justify-center gap-1.5 cursor-pointer"
                        >
                          {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <LogOut className="h-3.5 w-3.5" />}
                          Punch-Out Session
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Quick History List */}
            <div className="md:col-span-2 space-y-4">
              <div className="bg-card border border-border rounded-2xl p-5 shadow-sm space-y-4">
                <div>
                  <h2 className="font-bold text-sm text-foreground">Recent Activity</h2>
                  <p className="text-[10px] text-muted-foreground">Your last 30 log records</p>
                </div>

                <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
                  {history.length === 0 ? (
                    <p className="text-[11px] text-muted-foreground text-center py-6">No previous logs found</p>
                  ) : (
                    history.map(item => (
                      <div key={item.id} className="p-3 border border-border rounded-xl bg-muted/20 flex flex-col gap-1 text-xs">
                        <div className="flex justify-between items-center font-bold text-[11px] text-foreground">
                          <span>{formatDate(item.checkInTime.split('T')[0])}</span>
                          <span className="text-[10px] text-emerald-600 bg-emerald-500/10 py-0.5 px-2 rounded">
                            {getWorkingDuration(item.checkInTime, item.checkOutTime)}
                          </span>
                        </div>
                        <div className="text-[10px] text-muted-foreground flex justify-between mt-1">
                          <span>In: {formatTimeStr(item.checkInTime)}</span>
                          <span>Out: {formatTimeStr(item.checkOutTime)}</span>
                        </div>
                        {item.checkInComments && (
                          <p className="text-[10px] italic text-muted-foreground/80 mt-1 border-t pt-1 border-border/50">
                            Remarks: {item.checkInComments}
                          </p>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Admin Oversight Tab */
          <div className="space-y-5">
            {/* Filter controls */}
            <div className="bg-card border border-border rounded-2xl p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex bg-muted/65 p-0.5 rounded-lg border">
                <button
                  onClick={() => setAdminSubTab('today')}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-[11px] font-bold transition-all",
                    adminSubTab === 'today' ? "bg-card text-foreground shadow" : "text-muted-foreground"
                  )}
                >
                  Daily Status Overview
                </button>
                <button
                  onClick={() => setAdminSubTab('history')}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-[11px] font-bold transition-all",
                    adminSubTab === 'history' ? "bg-card text-foreground shadow" : "text-muted-foreground"
                  )}
                >
                  Historical Team logs
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                {adminSubTab === 'today' ? (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-muted-foreground">Date:</span>
                    <input 
                      type="date"
                      value={filterDate}
                      onChange={e => setFilterDate(e.target.value)}
                      className="px-2 py-1.5 border border-border rounded-lg bg-background text-xs font-bold text-foreground focus:outline-none"
                    />
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-muted-foreground">Range:</span>
                    <input 
                      type="date"
                      value={rangeStart}
                      onChange={e => setRangeStart(e.target.value)}
                      className="px-2 py-1 border border-border rounded-lg bg-background text-xs font-bold text-foreground focus:outline-none"
                    />
                    <span className="text-xs font-semibold text-muted-foreground">to</span>
                    <input 
                      type="date"
                      value={rangeEnd}
                      onChange={e => setRangeEnd(e.target.value)}
                      className="px-2 py-1 border border-border rounded-lg bg-background text-xs font-bold text-foreground focus:outline-none"
                    />
                  </div>
                )}

                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <input 
                    type="text"
                    placeholder="Search salesperson..."
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                    className="pl-8 pr-3 py-1.5 w-40 border border-border rounded-lg bg-background text-xs focus:outline-none"
                  />
                </div>
              </div>
            </div>

            {/* Admin Grid View */}
            {adminSubTab === 'today' ? (
              <div className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-muted/40 border-b border-border text-[10px] text-muted-foreground uppercase font-black tracking-wider">
                        <th className="p-4">Salesperson</th>
                        <th className="p-4">Punch In</th>
                        <th className="p-4">Punch Out</th>
                        <th className="p-4">GPS Address</th>
                        <th className="p-4">Duration</th>
                        <th className="p-4 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60 text-xs">
                      {filteredTeamToday.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="p-8 text-center text-muted-foreground">No records matched</td>
                        </tr>
                      ) : (
                        filteredTeamToday.map(item => (
                          <tr key={item.userId} className="hover:bg-muted/10">
                            <td className="p-4 font-bold text-foreground">{item.username}</td>
                            <td className="p-4 text-muted-foreground">{item.attendance ? formatTimeStr(item.attendance.checkInTime) : '--:--'}</td>
                            <td className="p-4 text-muted-foreground">{item.attendance ? formatTimeStr(item.attendance.checkOutTime) : '--:--'}</td>
                            <td className="p-4 text-muted-foreground max-w-[200px] truncate" title={item.attendance?.checkInPhotoUrl || ''}>
                              {item.attendance ? (
                                <span className="flex items-center gap-1">
                                  <MapPin className="h-3 w-3 text-sky-500" />
                                  <span>{item.attendance.checkInLatitude?.substring(0, 7)}, {item.attendance.checkInLongitude?.substring(0, 7)}</span>
                                </span>
                              ) : (
                                <span className="text-muted-foreground/60 italic">Not Checked In</span>
                              )}
                            </td>
                            <td className="p-4 font-semibold text-foreground">
                              {item.attendance ? getWorkingDuration(item.attendance.checkInTime, item.attendance.checkOutTime) : '--'}
                            </td>
                            <td className="p-4 text-center">
                              {item.attendance ? (
                                <span className="inline-flex py-0.5 px-2 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                                  Present
                                </span>
                              ) : (
                                <span className="inline-flex py-0.5 px-2 rounded-full text-[10px] font-bold bg-destructive/10 text-destructive border border-destructive/20">
                                  Absent
                                </span>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              /* History lists */
              <div className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-muted/40 border-b border-border text-[10px] text-muted-foreground uppercase font-black tracking-wider">
                        <th className="p-4">Date</th>
                        <th className="p-4">Username</th>
                        <th className="p-4">In Time</th>
                        <th className="p-4">Out Time</th>
                        <th className="p-4">GPS In Coords</th>
                        <th className="p-4">Working hours</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60 text-xs">
                      {filteredTeamHistory.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="p-8 text-center text-muted-foreground">No records in selected date range</td>
                        </tr>
                      ) : (
                        filteredTeamHistory.map(item => (
                          <tr key={item.id} className="hover:bg-muted/10">
                            <td className="p-4 font-bold text-foreground">{formatDate(item.checkInTime.split('T')[0])}</td>
                            <td className="p-4 font-semibold text-foreground">{item.username}</td>
                            <td className="p-4 text-muted-foreground">{formatTimeStr(item.checkInTime)}</td>
                            <td className="p-4 text-muted-foreground">{formatTimeStr(item.checkOutTime)}</td>
                            <td className="p-4 text-muted-foreground">
                              <span className="flex items-center gap-1">
                                <MapPin className="h-3.5 w-3.5 text-sky-500" />
                                <span>{item.checkInLatitude?.substring(0, 8)}, {item.checkInLongitude?.substring(0, 8)}</span>
                              </span>
                            </td>
                            <td className="p-4 font-bold text-foreground">{getWorkingDuration(item.checkInTime, item.checkOutTime)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
