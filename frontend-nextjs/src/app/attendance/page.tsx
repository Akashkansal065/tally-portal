'use client'

import React, { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import dynamic from 'next/dynamic'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatDate } from '@/lib/utils'

const AttendanceTrailMap = dynamic(
  () => import('@/components/AttendanceTrailMap'),
  {
    ssr: false,
    loading: () => (
      <div className="h-[360px] rounded-2xl bg-muted/30 border border-border flex flex-col items-center justify-center gap-2 text-muted-foreground animate-pulse">
        <div className="h-6 w-6 border-2 border-sky-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-semibold">Initializing interactive movement map...</span>
      </div>
    )
  }
)
import { stampPhoto } from '@/lib/photo-stamping'
import { 
  Clock, 
  MapPin, 
  Camera, 
  Loader2, 
  CheckCircle2, 
  ArrowLeft,
  ChevronRight,
  ChevronLeft,
  Users,
  Calendar,
  Search,
  CheckCircle,
  XCircle,
  FileText,
  LogOut,
  ExternalLink,
  AlertTriangle,
  Building,
  Download,
  FileSpreadsheet,
  Printer,
  Plus,
  Trash2,
  Edit2,
  Navigation,
  ShieldCheck,
  Compass,
  RefreshCw,
  Table as TableIcon,
  LayoutGrid,
  AlertCircle,
  CheckSquare,
  Square,
  Route,
  Footprints,
} from 'lucide-react'
import { LinkParams, LINKED_RECORD, idParam, useScrollToLinked } from '@/components/LinkParams'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { 
  exportMusterRollToPdf, 
  MusterRollDay, 
  EmployeeDayAttendance, 
  EmployeeMusterRoll, 
  CompanyMusterSummary 
} from '@/lib/attendance-export'
import { 
  startHeadlessNativeTracking, 
  stopHeadlessNativeTracking, 
  requestNativeBatteryExemption 
} from '@/lib/capacitor-native-tracking'

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
  isAutoPunchOut?: boolean
  autoPunchOutReason?: string | null
  checkInLocationTag?: string | null
  checkInDistanceMeters?: number | null
  checkInAccuracyMeters?: number | null
  checkInPlaceName?: string | null
  checkOutLocationTag?: string | null
  checkOutDistanceMeters?: number | null
  checkOutAccuracyMeters?: number | null
  checkOutPlaceName?: string | null
  lastKnownLatitude?: string | null
  lastKnownLongitude?: string | null
  lastKnownAccuracyMeters?: number | null
  lastKnownPlaceName?: string | null
  lastKnownTime?: string | null
  // Approvals Workflow Fields
  approvalStatus?: 'approved' | 'pending' | 'rejected' | null
  isOutOfOffice?: boolean | null
  approvedByUserId?: number | null
  approvedByUsername?: string | null
  approvedAt?: string | null
  rejectionReason?: string | null
}

type OfficeLocation = {
  id: number
  name: string
  address: string | null
  latitude: number
  longitude: number
  radiusMeters: number
  isActive: boolean
  createdAt?: string
}

type TeamAttendanceItem = {
  userId: number
  username: string
  isActive: boolean
  attendance: AttendanceRecord | null
}

type AutoPunchOutInfo = {
  targetTimeStr: string
  remainingText: string
  remainingSeconds: number
  reason: '9h' | 'midnight'
  urgency: 'normal' | 'warning' | 'urgent'
}

type MusterRollResponse = {
  success: boolean
  year: number
  month: number
  monthName: string
  totalDays: number
  days: MusterRollDay[]
  employees: EmployeeMusterRoll[]
  companySummary: CompanyMusterSummary
}

type LocationTrailPoint = {
  id: number
  latitude: number
  longitude: number
  accuracyMeters?: number | null
  distanceFromPrevMeters: number
  placeName?: string | null
  recordedAt: string
  mapsUrl: string
}

type LocationTrailResponse = {
  success: boolean
  attendanceId: number
  userId: number
  employeeName: string
  checkInTime: string
  checkOutTime?: string | null
  checkInPlace?: string | null
  checkOutPlace?: string | null
  lastKnownPlace?: string | null
  lastKnownTime?: string | null
  totalPoints: number
  totalDistanceMeters: number
  trail: LocationTrailPoint[]
  trailJson?: any[]
}

export default function AttendancePage() {
  const router = useRouter()
  const { token, user, permissions } = useAuth()
  
  // Navigation tabs
  const [activeTab, setActiveTab] = useState<'punch' | 'history' | 'admin'>('punch')
  const [adminSubTab, setAdminSubTab] = useState<'today' | 'approvals' | 'muster' | 'history' | 'offices'>('today')

  // Attendance states
  const [todayAttendance, setTodayAttendance] = useState<AttendanceRecord | null>(null)
  const [history, setHistory] = useState<AttendanceRecord[]>([])
  const [teamAttendance, setTeamAttendance] = useState<TeamAttendanceItem[]>([])
  const [teamHistory, setTeamHistory] = useState<AttendanceRecord[]>([])

  // Location Trail modal states
  const [trailModalOpen, setTrailModalOpen] = useState(false)
  const [loadingTrail, setLoadingTrail] = useState(false)
  const [trailData, setTrailData] = useState<LocationTrailResponse | null>(null)
  const [trailEmployeeTitle, setTrailEmployeeTitle] = useState('')

  // Approvals states
  const [approvalsFilter, setApprovalsFilter] = useState<'pending' | 'approved' | 'rejected' | 'all'>('pending')
  const [approvalsList, setApprovalsList] = useState<AttendanceRecord[]>([])
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0)
  const [loadingApprovals, setLoadingApprovals] = useState<boolean>(false)
  const [actionProcessingId, setActionProcessingId] = useState<number | null>(null)
  const [rejectingRecord, setRejectingRecord] = useState<AttendanceRecord | null>(null)
  const [rejectionReasonInput, setRejectionReasonInput] = useState<string>('')
  const [selectedApprovalIds, setSelectedApprovalIds] = useState<number[]>([])
  const [bulkApproving, setBulkApproving] = useState<boolean>(false)
  const [approvalSearchTerm, setApprovalSearchTerm] = useState<string>('')

  // Geofencing & Offices states
  const [offices, setOffices] = useState<OfficeLocation[]>([])
  const [showOfficeModal, setShowOfficeModal] = useState(false)
  const [editingOffice, setEditingOffice] = useState<OfficeLocation | null>(null)
  const [officeForm, setOfficeForm] = useState({
    name: '',
    address: '',
    latitude: '',
    longitude: '',
    radiusMeters: 200
  })
  const [locatingUser, setLocatingUser] = useState(false)

  // Muster Roll & Export states
  const todayIST = new Date()
  const [musterYear, setMusterYear] = useState<number>(todayIST.getFullYear())
  const [musterMonth, setMusterMonth] = useState<number>(todayIST.getMonth() + 1)
  const [musterData, setMusterData] = useState<MusterRollResponse | null>(null)
  const [musterLoading, setMusterLoading] = useState(false)
  const [exportingExcel, setExportingExcel] = useState(false)
  const [exportingPdf, setExportingPdf] = useState(false)
  const [selectedMusterCell, setSelectedMusterCell] = useState<{
    employee: EmployeeMusterRoll
    day: MusterRollDay
    attendance: EmployeeDayAttendance
  } | null>(null)
  const [musterMobileView, setMusterMobileView] = useState<'matrix' | 'cards'>('matrix')
  
  // Punch inputs
  const [comments, setComments] = useState('')
  const [photo, setPhoto] = useState<string | null>(null)
  const [stampedCoords, setStampedCoords] = useState<{ lat: number | null, lng: number | null, accuracy: number | null } | null>(null)
  const [processingPhoto, setProcessingPhoto] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [showPhotoRequiredModal, setShowPhotoRequiredModal] = useState(false)
  const [photoRequiredAction, setPhotoRequiredAction] = useState<'in' | 'out'>('out')
  const [previewPhotoUrl, setPreviewPhotoUrl] = useState<string | null>(null)
  
  // Clock & Auto Punch-Out countdown states
  const [currentTime, setCurrentTime] = useState<Date | null>(null)
  const [elapsedTime, setElapsedTime] = useState('00:00:00')
  const [autoPunchOutInfo, setAutoPunchOutInfo] = useState<AutoPunchOutInfo | null>(null)

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

  // Links from notifications: ?tab=admin&sub=approvals&id=55 (team) or ?tab=history&id=55 (own records)
  const [linkedId, setLinkedId] = useState<number | null>(null)
  const applyLink = (params: URLSearchParams) => {
    const tab = params.get('tab')
    const sub = params.get('sub')
    const id = idParam(params.get('id'))
    if (tab === 'admin') {
      setActiveTab('admin')
      if (sub === 'approvals' || sub === 'today' || sub === 'muster' || sub === 'history' || sub === 'offices') {
        setAdminSubTab(sub)
      }
      // The request may already be decided by another admin; show it either way
      if (sub === 'approvals' && id) setApprovalsFilter('all')
    } else if (tab === 'history' || tab === 'punch') {
      setActiveTab('punch')
    }
    setLinkedId(id)
  }
  useScrollToLinked(
    linkedId ? `attendance-${linkedId}` : null,
    `${activeTab}-${adminSubTab}-${approvalsList.length}-${history.length}`,
  )

  // Fetch initial personal details and offices
  useEffect(() => {
    if (!token) return
    fetchTodayStatus()
    fetchPersonalHistory()
    fetchOffices()
    if (user?.permissions?.isAdmin) {
      fetchPendingCountOnly()
    }
  }, [token, user?.permissions?.isAdmin])

  // Fetch admin sub-views when active
  useEffect(() => {
    if (!token || !user?.permissions?.isAdmin) return
    if (activeTab === 'admin') {
      fetchPendingCountOnly()
      if (adminSubTab === 'today') {
        fetchTeamAttendance()
      } else if (adminSubTab === 'approvals') {
        fetchApprovals(approvalsFilter)
      } else if (adminSubTab === 'history') {
        fetchTeamHistory()
      } else if (adminSubTab === 'muster') {
        fetchMusterRoll(musterYear, musterMonth)
      } else if (adminSubTab === 'offices') {
        fetchOffices()
      }
    }
  }, [activeTab, adminSubTab, filterDate, rangeStart, rangeEnd, musterYear, musterMonth, approvalsFilter, token])

  // Refresh clock every second
  useEffect(() => {
    setCurrentTime(new Date())
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const parseTimeMs = (isoString: string | null): number => {
    if (!isoString) return 0
    let normalized = isoString
    if (!normalized.includes('Z') && !normalized.includes('+') && !normalized.match(/-\d\d:\d\d$/)) {
      normalized += '+05:30'
    }
    return new Date(normalized).getTime()
  }

  // Calculate elapsed time and auto punch-out countdown
  useEffect(() => {
    if (!todayAttendance || todayAttendance.checkOutTime) {
      setElapsedTime('00:00:00')
      setAutoPunchOutInfo(null)
      return
    }

    const updateTimes = () => {
      const checkIn = parseTimeMs(todayAttendance.checkInTime)
      if (!checkIn) return
      const now = Date.now()
      const diff = Math.max(0, now - checkIn)
      
      const hrs = Math.max(0, Math.floor(diff / 3600000))
      const mins = Math.max(0, Math.floor((diff % 3600000) / 60000))
      const secs = Math.max(0, Math.floor((diff % 60000) / 1000))
      
      const pad = (n: number) => String(n).padStart(2, '0')
      setElapsedTime(`${pad(hrs)}:${pad(mins)}:${pad(secs)}`)

      // Auto punch-out target:
      // Target 1: 9 hours after check-in
      const nineHoursTarget = checkIn + 9 * 60 * 60 * 1000

      // Target 2: 23:58:00 IST on check-in date
      const checkInDate = new Date(checkIn)
      const dayEnd = new Date(checkInDate.getFullYear(), checkInDate.getMonth(), checkInDate.getDate(), 23, 58, 0, 0)
      const dayEndTarget = dayEnd.getTime()

      let targetMs = nineHoursTarget
      let reason: '9h' | 'midnight' = '9h'
      if (dayEndTarget < nineHoursTarget) {
        targetMs = dayEndTarget
        reason = 'midnight'
      }

      const remainingMs = targetMs - now
      const remainingSeconds = Math.max(0, Math.floor(remainingMs / 1000))

      let urgency: 'normal' | 'warning' | 'urgent' = 'normal'
      if (remainingSeconds <= 5 * 60) {
        urgency = 'urgent'
      } else if (remainingSeconds <= 15 * 60) {
        urgency = 'warning'
      }

      const remHrs = Math.floor(remainingSeconds / 3600)
      const remMins = Math.floor((remainingSeconds % 3600) / 60)
      const remSecs = remainingSeconds % 60

      let remainingText = ''
      if (remHrs > 0) {
        remainingText = `${remHrs}h ${remMins}m`
      } else if (remMins > 0) {
        remainingText = `${remMins}m ${remSecs}s`
      } else {
        remainingText = `${remSecs}s`
      }

      const targetDate = new Date(targetMs)
      const targetTimeStr = targetDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })

      setAutoPunchOutInfo({
        targetTimeStr,
        remainingText,
        remainingSeconds,
        reason,
        urgency
      })

      // If timer hits 0, trigger refresh
      if (remainingSeconds === 0) {
        fetchTodayStatus()
      }
    }

    updateTimes()
    const interval = setInterval(updateTimes, 1000)
    return () => clearInterval(interval)
  }, [todayAttendance])

  const fetchTodayStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/attendance/today`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setTodayAttendance(data.attendance)
        if (typeof window !== 'undefined') {
          if (data?.attendance && !data.attendance.checkOutTime) {
            localStorage.setItem('mytally_shift_active', '1')
          } else {
            localStorage.removeItem('mytally_shift_active')
          }
        }
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

  const fetchOffices = async () => {
    try {
      const res = await fetch(`${API_BASE}/attendance/offices`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setOffices(data.offices || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const fetchMusterRoll = async (y = musterYear, m = musterMonth) => {
    setMusterLoading(true)
    try {
      const res = await fetch(`${API_BASE}/attendance/admin/muster-roll?year=${y}&month=${m}`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setMusterData(data)
      } else {
        toast.error("Failed to load muster roll.")
      }
    } catch (e) {
      console.error(e)
      toast.error("Network error loading muster roll.")
    } finally {
      setMusterLoading(false)
    }
  }

  const calculateDistanceMeters = (lat1: number, lon1: number, lat2: number, lon2: number) => {
    const R = 6371000
    const toRad = (deg: number) => (deg * Math.PI) / 180
    const dLat = toRad(lat2 - lat1)
    const dLon = toRad(lon2 - lon1)
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2)
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
    return R * c
  }

  const getClosestOfficeInfo = (lat: number | null, lng: number | null) => {
    if (!lat || !lng || offices.length === 0) return null
    let closest: OfficeLocation | null = null
    let minDist = Infinity
    for (const off of offices) {
      if (!off.isActive) continue
      const dist = calculateDistanceMeters(lat, lng, off.latitude, off.longitude)
      if (dist < minDist) {
        minDist = dist
        closest = off
      }
    }
    if (!closest) return null
    const isInside = minDist <= closest.radiusMeters
    const distFormatted = minDist >= 1000 ? `${(minDist / 1000).toFixed(1)} km` : `${Math.round(minDist)}m`
    return { office: closest, distance: minDist, isInside, distFormatted }
  }

  const handleExportExcel = async () => {
    setExportingExcel(true)
    try {
      const res = await fetch(`${API_BASE}/attendance/admin/export-excel?year=${musterYear}&month=${musterMonth}`, {
        headers: authHeaders(token)
      })
      if (!res.ok) throw new Error("Excel export failed")
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const mName = musterData?.monthName || 'Month'
      a.download = `Attendance_Muster_Roll_${mName}_${musterYear}.xlsx`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success("Excel muster roll downloaded successfully!")
    } catch (e: any) {
      console.error(e)
      toast.error(e.message || "Failed to download Excel file.")
    } finally {
      setExportingExcel(false)
    }
  }

  const handleExportPdf = () => {
    if (!musterData || !musterData.employees || musterData.employees.length === 0) {
      toast.error("No muster roll data to export.")
      return
    }
    setExportingPdf(true)
    try {
      exportMusterRollToPdf({
        companyName: user?.company_name || user?.company?.name || 'Company Portal',
        monthName: musterData.monthName,
        year: musterData.year,
        days: musterData.days,
        employees: musterData.employees,
        companySummary: musterData.companySummary
      })
      toast.success("PDF timesheet generated successfully!")
    } catch (e: any) {
      console.error(e)
      toast.error("Failed to generate PDF timesheet.")
    } finally {
      setExportingPdf(false)
    }
  }

  const handleSaveOffice = async () => {
    if (!officeForm.name || !officeForm.latitude || !officeForm.longitude) {
      toast.error("Name, Latitude, and Longitude are required.")
      return
    }
    try {
      const lat = parseFloat(officeForm.latitude)
      const lng = parseFloat(officeForm.longitude)
      if (isNaN(lat) || isNaN(lng)) {
        toast.error("Invalid coordinates.")
        return
      }

      if (editingOffice) {
        const res = await fetch(`${API_BASE}/attendance/offices/${editingOffice.id}`, {
          method: 'PUT',
          headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: officeForm.name,
            address: officeForm.address,
            latitude: lat,
            longitude: lng,
            radius_meters: officeForm.radiusMeters
          })
        })
        if (!res.ok) throw new Error("Failed to update office")
        toast.success("Office geofence updated successfully!")
      } else {
        const res = await fetch(`${API_BASE}/attendance/offices`, {
          method: 'POST',
          headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: officeForm.name,
            address: officeForm.address,
            latitude: lat,
            longitude: lng,
            radius_meters: officeForm.radiusMeters
          })
        })
        if (!res.ok) throw new Error("Failed to create office")
        toast.success("Office geofence created successfully!")
      }
      setShowOfficeModal(false)
      setEditingOffice(null)
      fetchOffices()
    } catch (e: any) {
      toast.error(e.message || "Failed to save office.")
    }
  }

  const handleDeleteOffice = async (officeId: number) => {
    if (!confirm("Are you sure you want to delete this office geofence location?")) return
    try {
      const res = await fetch(`${API_BASE}/attendance/offices/${officeId}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      if (!res.ok) throw new Error("Failed to delete office")
      toast.success("Office location removed.")
      fetchOffices()
    } catch (e: any) {
      toast.error(e.message || "Failed to delete office.")
    }
  }

  const handleUseCurrentLocationForOffice = () => {
    if (!navigator.geolocation) {
      toast.error("Geolocation is not supported by your browser.")
      return
    }
    setLocatingUser(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setOfficeForm(prev => ({
          ...prev,
          latitude: pos.coords.latitude.toFixed(6),
          longitude: pos.coords.longitude.toFixed(6)
        }))
        setLocatingUser(false)
        toast.success("Current GPS coordinates acquired!")
      },
      (err) => {
        setLocatingUser(false)
        toast.error("Could not get your location: " + err.message)
      },
      { enableHighAccuracy: true, timeout: 10000 }
    )
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

  const handleOpenTrailModal = async (attendanceId: number, title?: string) => {
    setTrailEmployeeTitle(title || "Movement Route")
    setTrailModalOpen(true)
    setLoadingTrail(true)
    setTrailData(null)
    try {
      const res = await fetch(`${API_BASE}/attendance/${attendanceId}/trail`, {
        headers: authHeaders(token),
      })
      if (res.ok) {
        const data = await res.json()
        setTrailData(data)
      } else {
        const err = await res.json().catch(() => ({}))
        toast.error(err.detail || "Failed to load movement trail.")
      }
    } catch {
      toast.error("Network error loading movement trail.")
    } finally {
      setLoadingTrail(false)
    }
  }

  const fetchApprovals = async (status = approvalsFilter) => {
    setLoadingApprovals(true)
    try {
      const res = await fetch(`${API_BASE}/attendance/admin/approvals?status_filter=${status}`, {
        headers: authHeaders(token)
      })
      if (res.ok) {
        const data = await res.json()
        setApprovalsList(data.records || [])
        setPendingApprovalsCount(data.pendingCount || 0)
      } else {
        toast.error("Failed to fetch approvals list.")
      }
    } catch (e) {
      console.error(e)
      toast.error("Network error while loading approvals.")
    } finally {
      setLoadingApprovals(false)
    }
  }

  const fetchPendingCountOnly = async () => {
    try {
      const res = await fetch(`${API_BASE}/attendance/admin/approvals?status_filter=pending&limit=1`, {
        headers: authHeaders(token)
      })
      if (res.ok) {
        const data = await res.json()
        setPendingApprovalsCount(data.pendingCount || 0)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleApproveAttendance = async (attendanceId: number) => {
    setActionProcessingId(attendanceId)
    try {
      const res = await fetch(`${API_BASE}/attendance/admin/approve/${attendanceId}`, {
        method: 'POST',
        headers: authHeaders(token)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to approve attendance.")
      }
      toast.success("Attendance approved successfully!")
      fetchApprovals(approvalsFilter)
      fetchPendingCountOnly()
      if (adminSubTab === 'today') fetchTeamAttendance()
      if (adminSubTab === 'muster') fetchMusterRoll(musterYear, musterMonth)
      fetchTodayStatus()
    } catch (e: any) {
      toast.error(e.message || "Failed to approve attendance.")
    } finally {
      setActionProcessingId(null)
    }
  }

  const handleOpenRejectModal = (item: AttendanceRecord) => {
    setRejectingRecord(item)
    setRejectionReasonInput('')
  }

  const handleConfirmReject = async () => {
    if (!rejectingRecord) return
    setActionProcessingId(rejectingRecord.id)
    try {
      const res = await fetch(`${API_BASE}/attendance/admin/reject/${rejectingRecord.id}`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ reason: rejectionReasonInput.trim() || undefined })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Failed to reject attendance.")
      }
      toast.success("Attendance rejected.")
      setRejectingRecord(null)
      setRejectionReasonInput('')
      fetchApprovals(approvalsFilter)
      fetchPendingCountOnly()
      if (adminSubTab === 'today') fetchTeamAttendance()
      if (adminSubTab === 'muster') fetchMusterRoll(musterYear, musterMonth)
      fetchTodayStatus()
    } catch (e: any) {
      toast.error(e.message || "Failed to reject attendance.")
    } finally {
      setActionProcessingId(null)
    }
  }

  const handleBulkApprove = async () => {
    if (selectedApprovalIds.length === 0) return
    setBulkApproving(true)
    try {
      const res = await fetch(`${API_BASE}/attendance/admin/bulk-approve`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ attendance_ids: selectedApprovalIds })
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || "Bulk approval failed.")
      }
      toast.success(`Successfully approved ${selectedApprovalIds.length} attendance records!`)
      setSelectedApprovalIds([])
      fetchApprovals(approvalsFilter)
      fetchPendingCountOnly()
      if (adminSubTab === 'today') fetchTeamAttendance()
      if (adminSubTab === 'muster') fetchMusterRoll(musterYear, musterMonth)
      fetchTodayStatus()
    } catch (e: any) {
      toast.error(e.message || "Bulk approval failed.")
    } finally {
      setBulkApproving(false)
    }
  }

  const renderApprovalBadge = (status?: string | null, isOut?: boolean | null, className?: string) => {
    const s = status || 'approved'
    if (s === 'pending') {
      return (
        <span className={cn("inline-flex items-center gap-1 text-[10px] font-black px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30", className)}>
          <AlertTriangle className="h-2.5 w-2.5 shrink-0 text-amber-500 animate-pulse" />
          <span>Pending Admin Approval</span>
        </span>
      )
    }
    if (s === 'rejected') {
      return (
        <span className={cn("inline-flex items-center gap-1 text-[10px] font-black px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30", className)}>
          <XCircle className="h-2.5 w-2.5 shrink-0 text-rose-500" />
          <span>Rejected</span>
        </span>
      )
    }
    return (
      <span className={cn("inline-flex items-center gap-1 text-[10px] font-black px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30", className)}>
        <CheckCircle2 className="h-2.5 w-2.5 shrink-0 text-emerald-500" />
        <span>{isOut ? "Approved (Out of Office)" : "Approved"}</span>
      </span>
    )
  }

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setProcessingPhoto(true)
    try {
      const stamp = await stampPhoto(file)
      setPhoto(stamp.photoBase64)
      setStampedCoords({ lat: stamp.lat, lng: stamp.lng, accuracy: stamp.accuracy })
    } catch (err: any) {
      alert(err.message || 'Failed to capture geolocation or render canvas.')
    } finally {
      setProcessingPhoto(false)
    }
  }

  const handlePunch = async (punchType: 'in' | 'out') => {
    if (!photo) {
      setPhotoRequiredAction(punchType)
      setShowPhotoRequiredModal(true)
      toast.error(`Verification photo is required to punch ${punchType === 'out' ? 'out' : 'in'}.`)
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
          accuracyMeters: stampedCoords?.accuracy ?? null,
          deviceFingerprint: finger,
          photoBase64: photo,
          comments
        })
      })
      
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Punch failed')
      }

      const result = await res.json()
      if (result.approvalStatus === 'pending') {
        toast.warning(result.message || "Punched outside office geofence. Shift is pending Admin approval.", {
          description: result.locationTag ? `Location: ${result.locationTag}` : undefined,
          duration: 6000
        })
      } else {
        toast.success(result.message || `Punched ${punchType === 'in' ? 'In' : 'Out'} successfully.`, {
          description: result.locationTag ? `Location Tag: ${result.locationTag}` : undefined
        })
      }
      if (punchType === 'out') {
        localStorage.removeItem('mytally_shift_active')
        stopHeadlessNativeTracking().catch(() => {})
      } else if (punchType === 'in') {
        localStorage.setItem('mytally_shift_active', '1')
        if (token) {
          startHeadlessNativeTracking(token).catch(() => {})
          requestNativeBatteryExemption().catch(() => {})
        }
      }
      setPhoto(null)
      setComments('')
      setStampedCoords(null)
      fetchTodayStatus()
      fetchPersonalHistory()
      if (user?.permissions?.isAdmin) {
        fetchPendingCountOnly()
      }
    } catch (e: any) {
      alert(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const formatTimeStr = (isoString: string | null) => {
    if (!isoString) return '--:--'
    let normalized = isoString
    if (!normalized.includes('Z') && !normalized.includes('+') && !normalized.match(/-\d\d:\d\d$/)) {
      normalized += '+05:30'
    }
    return new Date(normalized).toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
      timeZone: 'Asia/Kolkata'
    })
  }

  const getWorkingDuration = (inTime: string, outTime: string | null) => {
    if (!outTime) return 'In Progress'
    const diff = parseTimeMs(outTime) - parseTimeMs(inTime)
    const hrs = Math.floor(diff / 3600000)
    const mins = Math.floor((diff % 3600000) / 60000)
    return `${hrs}h ${mins}m`
  }

  const handlePrevMonth = () => {
    if (musterMonth === 1) {
      setMusterMonth(12)
      setMusterYear(prev => prev - 1)
    } else {
      setMusterMonth(prev => prev - 1)
    }
  }

  const handleNextMonth = () => {
    if (musterMonth === 12) {
      setMusterMonth(1)
      setMusterYear(prev => prev + 1)
    } else {
      setMusterMonth(prev => prev + 1)
    }
  }

  // wrap: show long place names on up to two lines (phone cards) instead of cutting them to one
  const renderLocationBadge = (tag: string | null | undefined, distance?: number | null, placeName?: string | null, accuracy?: number | null, wrap = false) => {
    if (!tag) return null
    const isInside = tag.startsWith('In Office:')
    const isOutside = tag.startsWith('Outside Radius:')
    const titleParts = [tag]
    if (placeName) titleParts.push(`📍 ${placeName}`)
    if (accuracy != null) titleParts.push(`GPS accuracy: ±${accuracy}m`)
    
    return (
      <span 
        className={cn(
          "inline-flex max-w-full gap-1 text-[10px] font-bold px-2 py-0.5 rounded-md border",
          wrap ? "items-start" : "items-center",
          isInside ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/25" :
          isOutside ? "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/25" :
          "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/25"
        )}
        title={titleParts.join('\n')}
      >
        <Compass className={cn("h-2.5 w-2.5 shrink-0", wrap && "mt-[3px]")} />
        <span className={cn("min-w-0", wrap ? "line-clamp-2 break-words" : "truncate max-w-[180px]")}>{placeName ? `${placeName}` : tag}</span>
        {accuracy != null && <span className="text-[8px] opacity-60 shrink-0">±{accuracy}m</span>}
      </span>
    )
  }

  /**
   * One punch (in or out) on a phone card, full width: time and selfie on the first line, then the place
   * (up to two lines) and the GPS link underneath. Side-by-side columns were too narrow for place names.
   */
  const renderPunchRow = (p: {
    label: string
    time: string | null | undefined
    tone: 'in' | 'out'
    tag?: string | null
    distance?: number | null
    placeName?: string | null
    accuracy?: number | null
    lat?: string | null
    lng?: string | null
    photoUrl?: string | null
    /** Next to the time, e.g. the auto punch-out badge */
    extra?: React.ReactNode
    /** Shown instead of the GPS link when there are no coordinates */
    empty?: React.ReactNode
  }) => {
    const toneText = p.tone === 'in' ? 'text-sky-700 dark:text-sky-400' : 'text-emerald-700 dark:text-emerald-400'
    return (
      <div className="flex flex-col gap-1.5 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
            <span className="w-9 shrink-0 text-xs font-black uppercase tracking-wider text-muted-foreground">{p.label}</span>
            <span className="text-sm font-bold text-foreground">{formatTimeStr(p.time ?? null)}</span>
            {p.extra}
          </div>
          {p.photoUrl && (
            <button
              type="button"
              onClick={() => setPreviewPhotoUrl(p.photoUrl ?? null)}
              className={cn(
                "inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold transition-colors cursor-pointer",
                p.tone === 'in' ? "bg-sky-500/10 hover:bg-sky-500/20" : "bg-emerald-500/10 hover:bg-emerald-500/20",
                toneText,
              )}
            >
              <Camera className="h-3.5 w-3.5" /> Selfie
            </button>
          )}
        </div>
        {p.tag && <div className="pl-11">{renderLocationBadge(p.tag, p.distance, p.placeName, p.accuracy, true)}</div>}
        {p.lat && p.lng ? (
          <a
            href={`https://www.google.com/maps?q=${encodeURIComponent(`${p.lat},${p.lng}`)}`}
            target="_blank"
            rel="noopener noreferrer"
            className={cn("ml-11 inline-flex w-fit min-h-8 items-center gap-1 text-xs font-semibold hover:underline", toneText)}
            title="Open GPS location in Google Maps"
          >
            <MapPin className="h-3.5 w-3.5 shrink-0" />
            <span>{p.lat.substring(0, 7)}, {p.lng.substring(0, 7)}</span>
            <ExternalLink className="h-3 w-3 opacity-60" />
          </a>
        ) : p.empty ? (
          <div className="pl-11">{p.empty}</div>
        ) : null}
      </div>
    )
  }

  // Filtered lists
  const filteredTeamToday = teamAttendance.filter(item => 
    item.username.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const filteredTeamHistory = teamHistory.filter(item => 
    item.username?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const filteredMusterEmployees = (musterData?.employees || []).filter(emp =>
    emp.username.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="min-h-screen bg-background pb-12">
      <LinkParams onChange={applyLink} />
      {/* Header */}
      <div className="border-b border-border bg-card/50 backdrop-blur-md sticky top-0 z-10">
        <div className={cn("mx-auto px-3 sm:px-4 h-14 sm:h-16 flex items-center justify-between transition-all", activeTab === 'admin' && adminSubTab === 'muster' ? "max-w-7xl" : "max-w-4xl")}>
          <button 
            onClick={() => router.push('/')}
            className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            <ArrowLeft className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Back to Dashboard</span>
            <span className="sm:hidden">Dashboard</span>
          </button>
          
          <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
            <Clock className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-sky-500 animate-pulse shrink-0" />
            <span>
              {currentTime ? currentTime.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true, timeZone: 'Asia/Kolkata' }) : '--:--:--'}
            </span>
            <span className="text-[10px] text-muted-foreground font-normal hidden sm:inline">(IST)</span>
          </div>
        </div>
      </div>

      <div className={cn("mx-auto px-3 sm:px-4 mt-4 sm:mt-6 space-y-4 sm:space-y-6 transition-all", activeTab === 'admin' && adminSubTab === 'muster' ? "max-w-7xl" : "max-w-4xl")}>
        {/* Title */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-xl sm:text-2xl font-black tracking-tight text-foreground">Daily Attendance</h1>
            <p className="text-xs text-muted-foreground mt-0.5">Punch-in or checkout with secure GPS maps and selfie verification</p>
          </div>

          {user?.permissions?.isAdmin && (
            <div className="flex bg-muted/60 p-1 rounded-xl border border-border shrink-0 self-start sm:self-auto">
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
                  "px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5",
                  activeTab === 'admin' ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Users className="h-3.5 w-3.5" />
                <span>Team Logs</span>
                {pendingApprovalsCount > 0 && (
                  <span className="bg-amber-500 text-white text-[9px] font-black px-1.5 py-0.2 rounded-full min-w-4 text-center leading-tight">
                    {pendingApprovalsCount}
                  </span>
                )}
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

                {/* Out of Office Approval Status Banner */}
                {todayAttendance && (todayAttendance.isOutOfOffice || todayAttendance.approvalStatus !== 'approved') && (
                  <div className={cn(
                    "p-3.5 rounded-xl border text-xs flex items-start gap-2.5 shadow-2xs",
                    todayAttendance.approvalStatus === 'pending'
                      ? "bg-amber-500/10 border-amber-500/30 text-amber-800 dark:text-amber-200"
                      : todayAttendance.approvalStatus === 'rejected'
                        ? "bg-rose-500/10 border-rose-500/30 text-rose-800 dark:text-rose-200"
                        : "bg-emerald-500/10 border-emerald-500/30 text-emerald-800 dark:text-emerald-200"
                  )}>
                    <AlertCircle className={cn(
                      "h-4 w-4 shrink-0 mt-0.5",
                      todayAttendance.approvalStatus === 'pending'
                        ? "text-amber-500 animate-pulse"
                        : todayAttendance.approvalStatus === 'rejected'
                          ? "text-rose-500"
                          : "text-emerald-500"
                    )} />
                    <div className="space-y-0.5 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="font-bold text-xs">
                          {todayAttendance.approvalStatus === 'pending'
                            ? "Out-of-Office: Pending Admin Approval"
                            : todayAttendance.approvalStatus === 'rejected'
                              ? "Out-of-Office: Attendance Rejected"
                              : "Out-of-Office: Approved"}
                        </span>
                        {renderApprovalBadge(todayAttendance.approvalStatus, todayAttendance.isOutOfOffice)}
                      </div>
                      <p className="text-[11px] opacity-90 leading-snug">
                        {todayAttendance.approvalStatus === 'pending'
                          ? "Your punch was recorded outside registered office geofences and requires administrative approval."
                          : todayAttendance.approvalStatus === 'rejected'
                            ? (todayAttendance.rejectionReason ? `Reason: ${todayAttendance.rejectionReason}` : "This attendance record was rejected by an administrator.")
                            : `Verified and approved${todayAttendance.approvedByUsername ? ` by ${todayAttendance.approvedByUsername}` : ''}.`}
                      </p>
                    </div>
                  </div>
                )}

                {/* Imminent / Approaching Auto Punch-Out Warning Banners */}
                {todayAttendance && !todayAttendance.checkOutTime && autoPunchOutInfo && autoPunchOutInfo.urgency === 'urgent' && (
                  <div className="bg-rose-500/10 border-2 border-rose-500/40 rounded-xl p-3.5 flex items-start gap-3 animate-pulse shadow-xs">
                    <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
                    <div className="flex-1 text-xs">
                      <div className="font-bold text-rose-700 dark:text-rose-400 flex items-center justify-between flex-wrap gap-1">
                        <span>🚨 Auto Punch-Out Imminent ({autoPunchOutInfo.remainingText} remaining)</span>
                        <span className="text-[10px] font-mono font-bold bg-rose-500/20 text-rose-800 dark:text-rose-200 px-2 py-0.5 rounded">
                          At {autoPunchOutInfo.targetTimeStr}
                        </span>
                      </div>
                      <p className="text-rose-600/90 dark:text-rose-300/90 text-[11px] mt-1 leading-snug">
                        {autoPunchOutInfo.reason === 'midnight'
                          ? "Day-end cutoff (23:58 IST) is almost reached. Take your selfie and punch out now to record your complete shift."
                          : "Your 9-hour shift limit ends in under 5 minutes. You will be automatically punched out by the system if not clocked out now."}
                      </p>
                    </div>
                  </div>
                )}

                {todayAttendance && !todayAttendance.checkOutTime && autoPunchOutInfo && autoPunchOutInfo.urgency === 'warning' && (
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 flex items-start gap-2.5 shadow-xs">
                    <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                    <div className="flex-1 text-xs">
                      <div className="font-bold text-amber-700 dark:text-amber-400 flex items-center justify-between flex-wrap gap-1">
                        <span>⚠️ Approaching Auto Punch-Out ({autoPunchOutInfo.remainingText} remaining)</span>
                        <span className="text-[10px] font-mono font-bold bg-amber-500/20 text-amber-800 dark:text-amber-200 px-2 py-0.5 rounded">
                          At {autoPunchOutInfo.targetTimeStr}
                        </span>
                      </div>
                      <p className="text-amber-600/90 dark:text-amber-300/90 text-[11px] mt-1 leading-snug">
                        {autoPunchOutInfo.reason === 'midnight'
                          ? `Day-end boundary cutoff at ${autoPunchOutInfo.targetTimeStr}. Please prepare to punch out.`
                          : `9-hour auto punch-out scheduled at ${autoPunchOutInfo.targetTimeStr}. Please punch out when done.`}
                      </p>
                    </div>
                  </div>
                )}

                {todayAttendance && !todayAttendance.checkOutTime && (
                  <div className="bg-sky-500/5 border border-sky-500/10 rounded-xl p-4 flex flex-col items-center justify-center gap-1.5">
                    <span className="text-[10px] text-muted-foreground uppercase font-black tracking-widest">Active Working Duration</span>
                    <span className="text-3xl font-black text-sky-600 tracking-tight">{elapsedTime}</span>
                    
                    {autoPunchOutInfo && (
                      <div className="flex items-center gap-1.5 mt-1 bg-background/80 dark:bg-card/80 border border-border px-3 py-1 rounded-full text-[10px] shadow-xs">
                        <Clock className="h-3 w-3 text-sky-500 shrink-0" />
                        <span className="text-muted-foreground">Auto punch-out at</span>
                        <span className="font-bold text-foreground">{autoPunchOutInfo.targetTimeStr}</span>
                        <span className="text-muted-foreground font-medium">({autoPunchOutInfo.remainingText} left)</span>
                        {autoPunchOutInfo.reason === 'midnight' ? (
                          <span className="text-[9px] font-bold text-purple-600 dark:text-purple-400 bg-purple-500/10 px-1.5 py-0.2 rounded">🌙 Day End</span>
                        ) : (
                          <span className="text-[9px] font-bold text-amber-600 dark:text-amber-400 bg-amber-500/10 px-1.5 py-0.2 rounded">⚡ 9h Limit</span>
                        )}
                      </div>
                    )}

                    <div className="flex items-center gap-2 mt-1.5 flex-wrap justify-center">
                      <span className="text-[10px] text-muted-foreground">Clocked in at {formatTimeStr(todayAttendance.checkInTime)}</span>
                      {todayAttendance.checkInLocationTag && (
                        renderLocationBadge(todayAttendance.checkInLocationTag, todayAttendance.checkInDistanceMeters, todayAttendance.checkInPlaceName, todayAttendance.checkInAccuracyMeters)
                      )}
                      {renderApprovalBadge(todayAttendance.approvalStatus, todayAttendance.isOutOfOffice)}
                      {todayAttendance.checkInLatitude && todayAttendance.checkInLongitude && (
                        <a
                          href={`https://www.google.com/maps?q=${encodeURIComponent(`${todayAttendance.checkInLatitude},${todayAttendance.checkInLongitude}`)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[10px] font-bold text-sky-600 hover:text-sky-700 hover:underline bg-sky-500/10 px-2 py-0.5 rounded-md"
                          title="Open punch-in location in Google Maps"
                        >
                          <MapPin className="h-2.5 w-2.5" />
                          <span>View Map</span>
                          <ExternalLink className="h-2.5 w-2.5 opacity-70" />
                        </a>
                      )}
                    </div>

                    {todayAttendance.lastKnownTime && (
                      <div className="flex items-center gap-1.5 mt-2 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-xl text-[11px] text-emerald-700 dark:text-emerald-300 w-full justify-between flex-wrap">
                        <div className="flex items-center gap-1.5 truncate max-w-[280px]">
                          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping shrink-0" />
                          <span className="font-semibold text-[10px]">Live GPS:</span>
                          <span className="truncate text-[10px] font-medium">{todayAttendance.lastKnownPlaceName || "Coordinates locked"}</span>
                        </div>
                        <span className="text-[9px] opacity-75 font-mono">({formatTimeStr(todayAttendance.lastKnownTime)})</span>
                      </div>
                    )}

                    <div className="flex items-center gap-2 mt-2">
                      <button
                        type="button"
                        onClick={() => handleOpenTrailModal(todayAttendance.id, "My Movement Route")}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-sky-500/10 hover:bg-sky-500/20 text-sky-600 dark:text-sky-400 border border-sky-500/30 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-xs"
                      >
                        <Route className="h-3.5 w-3.5 text-sky-500" />
                        <span>View My Movement Trail</span>
                      </button>
                    </div>
                  </div>
                )}

                {todayAttendance?.checkOutTime && (
                  todayAttendance.isAutoPunchOut ? (
                    <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-4 flex flex-col items-center justify-center gap-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] py-0.5 px-2.5 rounded-full font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 flex items-center gap-1">
                          ⚡ {todayAttendance.autoPunchOutReason === 'midnight_boundary' ? 'Auto Out: Day-End Cutoff (23:58)' : 'Auto Out: 9-Hour Limit Reached'}
                        </span>
                      </div>
                      <span className="text-sm font-bold text-amber-700 dark:text-amber-300">
                        System clocked you out at {formatTimeStr(todayAttendance.checkOutTime)}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        Total logged: {getWorkingDuration(todayAttendance.checkInTime, todayAttendance.checkOutTime)}
                      </span>
                      <div className="flex items-center gap-2 mt-1 flex-wrap justify-center">
                        {todayAttendance.checkInLocationTag && (
                          renderLocationBadge(todayAttendance.checkInLocationTag, todayAttendance.checkInDistanceMeters, todayAttendance.checkInPlaceName, todayAttendance.checkInAccuracyMeters)
                        )}
                        {todayAttendance.checkOutLocationTag && (
                          renderLocationBadge(todayAttendance.checkOutLocationTag, todayAttendance.checkOutDistanceMeters, todayAttendance.checkOutPlaceName, todayAttendance.checkOutAccuracyMeters)
                        )}
                        {renderApprovalBadge(todayAttendance.approvalStatus, todayAttendance.isOutOfOffice)}
                        {todayAttendance.checkOutLatitude && todayAttendance.checkOutLongitude ? (
                          <a
                            href={`https://www.google.com/maps?q=${encodeURIComponent(`${todayAttendance.checkOutLatitude},${todayAttendance.checkOutLongitude}`)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-600 hover:text-amber-700 hover:underline bg-amber-500/10 px-2 py-0.5 rounded-md"
                            title="Open auto check-out location in Google Maps"
                          >
                            <MapPin className="h-2.5 w-2.5 text-amber-500" />
                            <span>Auto Check-Out Map</span>
                            <ExternalLink className="h-2.5 w-2.5 opacity-70" />
                          </a>
                        ) : todayAttendance.checkInLatitude && todayAttendance.checkInLongitude ? (
                          <a
                            href={`https://www.google.com/maps?q=${encodeURIComponent(`${todayAttendance.checkInLatitude},${todayAttendance.checkInLongitude}`)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[10px] font-bold text-sky-600 hover:text-sky-700 hover:underline bg-sky-500/10 px-2 py-0.5 rounded-md"
                            title="Open punch-in location in Google Maps"
                          >
                            <MapPin className="h-2.5 w-2.5 text-sky-500" />
                            <span>Punch-In Map</span>
                            <ExternalLink className="h-2.5 w-2.5 opacity-70" />
                          </a>
                        ) : null}
                        {todayAttendance.checkOutPlaceName ? (
                          <span className="text-[10px] text-amber-700 dark:text-amber-300 font-medium">📍 {todayAttendance.checkOutPlaceName}</span>
                        ) : (
                          <span className="text-[10px] text-muted-foreground/70 italic">Selfie/GPS out skipped by auto punch</span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-xl p-4 flex flex-col items-center justify-center gap-1.5">
                      <span className="text-[10px] text-muted-foreground uppercase font-black tracking-widest">Shift Completed</span>
                      <span className="text-sm font-bold text-emerald-600">You clocked out at {formatTimeStr(todayAttendance.checkOutTime)}</span>
                      <span className="text-[10px] text-muted-foreground">Total worked: {getWorkingDuration(todayAttendance.checkInTime, todayAttendance.checkOutTime)}</span>
                      <div className="flex items-center gap-2 mt-1 flex-wrap justify-center">
                        {todayAttendance.checkInLocationTag && (
                          renderLocationBadge(todayAttendance.checkInLocationTag, todayAttendance.checkInDistanceMeters, todayAttendance.checkInPlaceName, todayAttendance.checkInAccuracyMeters)
                        )}
                        {renderApprovalBadge(todayAttendance.approvalStatus, todayAttendance.isOutOfOffice)}
                        {todayAttendance.checkInLatitude && todayAttendance.checkInLongitude && (
                          <a
                            href={`https://www.google.com/maps?q=${encodeURIComponent(`${todayAttendance.checkInLatitude},${todayAttendance.checkInLongitude}`)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[10px] font-bold text-sky-600 hover:text-sky-700 hover:underline bg-sky-500/10 px-2 py-0.5 rounded-md"
                            title="Open punch-in location in Google Maps"
                          >
                            <MapPin className="h-2.5 w-2.5 text-sky-500" />
                            <span>Punch-In Map</span>
                            <ExternalLink className="h-2.5 w-2.5 opacity-70" />
                          </a>
                        )}
                        {todayAttendance.checkOutLocationTag && (
                          renderLocationBadge(todayAttendance.checkOutLocationTag, todayAttendance.checkOutDistanceMeters, todayAttendance.checkOutPlaceName, todayAttendance.checkOutAccuracyMeters)
                        )}
                        {todayAttendance.checkOutLatitude && todayAttendance.checkOutLongitude && (
                          <a
                            href={`https://www.google.com/maps?q=${encodeURIComponent(`${todayAttendance.checkOutLatitude},${todayAttendance.checkOutLongitude}`)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600 hover:text-emerald-700 hover:underline bg-emerald-500/10 px-2 py-0.5 rounded-md"
                            title="Open punch-out location in Google Maps"
                          >
                            <MapPin className="h-2.5 w-2.5 text-emerald-500" />
                            <span>Punch-Out Map</span>
                            <ExternalLink className="h-2.5 w-2.5 opacity-70" />
                          </a>
                        )}
                      </div>
                    </div>
                  )
                )}

                {!todayAttendance?.checkOutTime && (
                  <div className="space-y-4">
                    {/* Selfie Box */}
                    <div>
                      <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide">Watermarked Verification Photo</label>
                      {photo ? (
                        <div className="mt-1.5 space-y-2">
                          <div className="relative rounded-2xl overflow-hidden border border-border">
                            <img src={photo} alt="selfie check-in" className="w-full h-48 object-cover" />
                            <button 
                              type="button" 
                              onClick={() => { setPhoto(null); setStampedCoords(null) }}
                              className="absolute top-3 right-3 bg-black/80 hover:bg-black text-white rounded-full p-2 text-xs transition-colors cursor-pointer"
                            >
                              <XCircle className="h-4 w-4" />
                            </button>
                          </div>

                          {/* Live Geofence Detection Card */}
                          {stampedCoords && (() => {
                            const info = getClosestOfficeInfo(stampedCoords.lat, stampedCoords.lng)
                            if (!info) return null
                            return (
                              <div className="space-y-1.5">
                                <div className={cn(
                                  "p-2.5 rounded-xl border text-xs flex items-center justify-between gap-2 shadow-2xs",
                                  info.isInside 
                                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-800 dark:text-emerald-200"
                                    : "bg-amber-500/10 border-amber-500/30 text-amber-800 dark:text-amber-200"
                                )}>
                                  <div className="flex items-center gap-2 min-w-0">
                                    <ShieldCheck className={cn("h-4 w-4 shrink-0", info.isInside ? "text-emerald-500" : "text-amber-500")} />
                                    <div className="truncate">
                                      <span className="font-bold">{info.isInside ? "In Office: " : "Outside Radius: "}</span>
                                      <span className="font-semibold">{info.office.name}</span>
                                      <span className="text-[10px] opacity-80 block sm:inline sm:ml-1">
                                        ({info.distFormatted} away • radius {info.office.radiusMeters}m{stampedCoords.accuracy != null ? ` • GPS ±${stampedCoords.accuracy}m` : ''})
                                      </span>
                                    </div>
                                  </div>
                                  <span className={cn(
                                    "text-[9px] font-black uppercase px-2 py-0.5 rounded-md shrink-0 border",
                                    info.isInside 
                                      ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/40" 
                                      : "bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-500/40"
                                  )}>
                                    {info.isInside ? "In Office" : "Remote / Field"}
                                  </span>
                                </div>
                                {!info.isInside && (
                                  <div className="flex items-center gap-1.5 px-1 text-[11px] text-amber-700 dark:text-amber-300 font-medium">
                                    <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                                    <span>Outside office radius. Punch will require Admin approval.</span>
                                  </div>
                                )}
                              </div>
                            )
                          })()}
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
                          disabled={submitting || processingPhoto}
                          className="w-full py-3 bg-sky-500 hover:bg-sky-600 disabled:opacity-50 disabled:cursor-not-allowed font-bold text-white rounded-xl text-xs transition-all shadow-md flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.99]"
                        >
                          {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Clock className="h-3.5 w-3.5" />}
                          Punch-In Today
                        </button>
                      ) : (
                        <button
                          onClick={() => handlePunch('out')}
                          disabled={submitting || processingPhoto}
                          className="w-full py-3 bg-rose-500 hover:bg-rose-600 disabled:opacity-50 disabled:cursor-not-allowed font-bold text-white rounded-xl text-xs transition-all shadow-md flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.99]"
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
                      <div
                        key={item.id}
                        data-link-target={`attendance-${item.id}`}
                        className={cn("p-3 border border-border rounded-xl bg-muted/20 flex flex-col gap-1 text-xs", item.id === linkedId && LINKED_RECORD)}
                      >
                        <div className="flex justify-between items-center font-bold text-[11px] text-foreground">
                          <span>{formatDate(item.checkInTime.split('T')[0])}</span>
                          <div className="flex items-center gap-1.5 flex-wrap justify-end">
                            {renderApprovalBadge(item.approvalStatus, item.isOutOfOffice)}
                            {item.isAutoPunchOut && (
                              <span className="text-[9px] font-bold text-amber-600 bg-amber-500/10 border border-amber-500/20 py-0.5 px-1.5 rounded-full flex items-center gap-0.5" title={item.checkOutComments || "Auto Punched Out by System"}>
                                ⚡ {item.autoPunchOutReason === 'midnight_boundary' ? 'Auto Out (23:58)' : 'Auto Out (9h)'}
                              </span>
                            )}
                            <span className="text-[10px] text-emerald-600 bg-emerald-500/10 py-0.5 px-2 rounded">
                              {getWorkingDuration(item.checkInTime, item.checkOutTime)}
                            </span>
                          </div>
                        </div>
                        <div className="text-[10px] text-muted-foreground flex justify-between mt-1">
                          <span>In: {formatTimeStr(item.checkInTime)}</span>
                          <span>Out: {item.checkOutTime ? formatTimeStr(item.checkOutTime) : '--:--'}</span>
                        </div>
                        {item.checkInLocationTag && (
                          <div className="mt-1">
                            {renderLocationBadge(item.checkInLocationTag, item.checkInDistanceMeters, item.checkInPlaceName, item.checkInAccuracyMeters)}
                          </div>
                        )}
                        {item.checkOutLocationTag && (
                          <div className="mt-0.5">
                            {renderLocationBadge(item.checkOutLocationTag, item.checkOutDistanceMeters, item.checkOutPlaceName, item.checkOutAccuracyMeters)}
                          </div>
                        )}
                        {item.approvalStatus === 'rejected' && item.rejectionReason && (
                          <p className="text-[10px] font-medium text-rose-600 dark:text-rose-400 mt-0.5">
                            Rejection Reason: {item.rejectionReason}
                          </p>
                        )}
                        {item.checkInLatitude && item.checkInLongitude && (
                          <div className="mt-1 flex items-center justify-between text-[10px]">
                            <a
                              href={`https://www.google.com/maps?q=${encodeURIComponent(`${item.checkInLatitude},${item.checkInLongitude}`)}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sky-600 dark:text-sky-400 hover:underline inline-flex items-center gap-1 font-medium"
                              title="Open GPS location in Google Maps"
                            >
                              <MapPin className="h-2.5 w-2.5 text-sky-500" />
                              <span>{item.checkInLatitude.substring(0, 7)}, {item.checkInLongitude.substring(0, 7)}</span>
                              <ExternalLink className="h-2.5 w-2.5 opacity-60" />
                            </a>
                            <button
                              type="button"
                              onClick={() => handleOpenTrailModal(item.id, `My Route (${formatDate(item.checkInTime.split('T')[0])})`)}
                              className="inline-flex items-center gap-1 text-[10px] font-bold text-sky-600 dark:text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded hover:bg-sky-500/20 transition-colors cursor-pointer"
                            >
                              <Route className="h-2.5 w-2.5" />
                              <span>View Route</span>
                            </button>
                          </div>
                        )}
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
            <div className="bg-card border border-border rounded-2xl p-3 sm:p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4">
              <div className="flex overflow-x-auto no-scrollbar gap-1 bg-muted/65 p-1 rounded-xl border border-border w-full md:w-auto">
                <button
                  onClick={() => setAdminSubTab('today')}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-bold transition-all text-center whitespace-nowrap shrink-0 cursor-pointer",
                    adminSubTab === 'today' ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Daily Status
                </button>
                <button
                  onClick={() => setAdminSubTab('approvals')}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-bold transition-all text-center flex items-center justify-center gap-1.5 whitespace-nowrap shrink-0 cursor-pointer",
                    adminSubTab === 'approvals' ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <ShieldCheck className="h-3.5 w-3.5" />
                  <span>Approvals</span>
                  {pendingApprovalsCount > 0 && (
                    <span className="bg-amber-500 text-white text-[9px] font-black px-1.5 py-0.2 rounded-full min-w-4 text-center leading-tight">
                      {pendingApprovalsCount}
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setAdminSubTab('muster')}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-bold transition-all text-center flex items-center justify-center gap-1 whitespace-nowrap shrink-0 cursor-pointer",
                    adminSubTab === 'muster' ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Calendar className="h-3.5 w-3.5" />
                  Muster Roll
                </button>
                <button
                  onClick={() => setAdminSubTab('history')}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-bold transition-all text-center whitespace-nowrap shrink-0 cursor-pointer",
                    adminSubTab === 'history' ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Team History
                </button>
                <button
                  onClick={() => setAdminSubTab('offices')}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs font-bold transition-all text-center flex items-center justify-center gap-1 whitespace-nowrap shrink-0 cursor-pointer",
                    adminSubTab === 'offices' ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Building className="h-3.5 w-3.5" />
                  Geofences
                </button>
              </div>

              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3 w-full md:w-auto flex-wrap">
                {adminSubTab === 'today' && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-muted-foreground shrink-0">Date:</span>
                    <input 
                      type="date"
                      value={filterDate}
                      onChange={e => setFilterDate(e.target.value)}
                      className="px-2.5 py-1.5 border border-border rounded-lg bg-background text-xs font-bold text-foreground focus:outline-none flex-1 sm:flex-none"
                    />
                  </div>
                )}

                {adminSubTab === 'history' && (
                  <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
                    <span className="text-xs font-semibold text-muted-foreground shrink-0">Range:</span>
                    <input 
                      type="date"
                      value={rangeStart}
                      onChange={e => setRangeStart(e.target.value)}
                      className="px-2 py-1.5 border border-border rounded-lg bg-background text-xs font-bold text-foreground focus:outline-none flex-1 sm:flex-none"
                    />
                    <span className="text-xs font-semibold text-muted-foreground">to</span>
                    <input 
                      type="date"
                      value={rangeEnd}
                      onChange={e => setRangeEnd(e.target.value)}
                      className="px-2 py-1.5 border border-border rounded-lg bg-background text-xs font-bold text-foreground focus:outline-none flex-1 sm:flex-none"
                    />
                  </div>
                )}

                {adminSubTab === 'muster' && (
                  <div className="flex items-center justify-between sm:justify-start gap-2 w-full sm:w-auto">
                    {/* Month Picker Controls */}
                    <div className="flex items-center bg-muted/50 border border-border rounded-lg p-0.5 flex-1 sm:flex-none justify-between sm:justify-center">
                      <button
                        onClick={handlePrevMonth}
                        className="p-1.5 hover:bg-card text-muted-foreground hover:text-foreground rounded-md transition-colors cursor-pointer"
                        title="Previous Month"
                      >
                        <ChevronLeft className="h-3.5 w-3.5" />
                      </button>
                      <span className="text-xs font-black px-2 min-w-[95px] text-center text-foreground truncate">
                        {musterData?.monthName || 'Month'} {musterYear}
                      </span>
                      <button
                        onClick={handleNextMonth}
                        className="p-1.5 hover:bg-card text-muted-foreground hover:text-foreground rounded-md transition-colors cursor-pointer"
                        title="Next Month"
                      >
                        <ChevronRight className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    {/* Export Actions */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        onClick={handleExportExcel}
                        disabled={exportingExcel || musterLoading}
                        className="inline-flex items-center gap-1 px-2.5 sm:px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold transition-all shadow-xs cursor-pointer active:scale-95"
                        title="Download styled Excel (.xlsx)"
                      >
                        {exportingExcel ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileSpreadsheet className="h-3.5 w-3.5" />}
                        <span className="hidden sm:inline">Excel</span>
                      </button>

                      <button
                        onClick={handleExportPdf}
                        disabled={exportingPdf || musterLoading}
                        className="inline-flex items-center gap-1 px-2.5 sm:px-3 py-1.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold transition-all shadow-xs cursor-pointer active:scale-95"
                        title="Download printable PDF timesheet (.pdf)"
                      >
                        {exportingPdf ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Printer className="h-3.5 w-3.5" />}
                        <span className="hidden sm:inline">PDF</span>
                      </button>
                    </div>
                  </div>
                )}

                {adminSubTab === 'offices' && (
                  <button
                    onClick={() => {
                      setEditingOffice(null)
                      setOfficeForm({ name: '', address: '', latitude: '', longitude: '', radiusMeters: 200 })
                      setShowOfficeModal(true)
                    }}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-sky-500 hover:bg-sky-600 text-white rounded-lg text-xs font-bold transition-colors cursor-pointer shadow-xs ml-auto"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Add Office Geofence</span>
                  </button>
                )}

                {adminSubTab !== 'offices' && adminSubTab !== 'approvals' && (
                  <div className="relative w-full sm:w-48">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <input 
                      type="text"
                      placeholder="Search salesperson..."
                      value={searchTerm}
                      onChange={e => setSearchTerm(e.target.value)}
                      className="pl-8 pr-3 py-1.5 w-full border border-border rounded-lg bg-background text-xs focus:outline-none"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Admin Subtabs Content */}
            {/* 1. Daily Status Overview */}
            {adminSubTab === 'today' && (
              <div className="space-y-4">
                {/* Mobile Cards View (< md) */}
                <div className="block md:hidden space-y-3">
                  {filteredTeamToday.length === 0 ? (
                    <div className="p-8 text-center text-muted-foreground bg-card border border-border rounded-2xl shadow-sm text-xs">
                      No records matched
                    </div>
                  ) : (
                    filteredTeamToday.map(item => (
                      <div key={item.userId} className="p-4 border border-border rounded-2xl bg-card shadow-sm space-y-3">
                        {/* Header: User & Status Badge */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2.5">
                            <div className="h-9 w-9 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center uppercase shadow-inner">
                              {item.username.charAt(0)}
                            </div>
                            <div>
                              <h4 className="font-bold text-sm text-foreground leading-tight">{item.username}</h4>
                              <span className="text-[10px] text-muted-foreground">User #{item.userId}</span>
                            </div>
                          </div>
                          <div className="flex flex-col items-end gap-1">
                            <div className="flex items-center gap-1.5 flex-wrap justify-end">
                              {item.attendance && renderApprovalBadge(item.attendance.approvalStatus, item.attendance.isOutOfOffice)}
                              {item.attendance ? (
                                item.attendance.checkOutTime ? (
                                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                                    Present
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-sky-500/10 text-sky-600 border border-sky-500/20">
                                    <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-pulse" />
                                    In Progress
                                  </span>
                                )
                              ) : (
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-destructive/10 text-destructive border border-destructive/20">
                                  Absent
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Punch in / out, one full-width row each */}
                        <div className="divide-y divide-border/50 rounded-xl border border-border/50 bg-muted/30">
                          {renderPunchRow({
                            label: 'In',
                            tone: 'in',
                            time: item.attendance?.checkInTime,
                            tag: item.attendance?.checkInLocationTag,
                            distance: item.attendance?.checkInDistanceMeters,
                            placeName: item.attendance?.checkInPlaceName,
                            accuracy: item.attendance?.checkInAccuracyMeters,
                            lat: item.attendance?.checkInLatitude,
                            lng: item.attendance?.checkInLongitude,
                            photoUrl: item.attendance?.checkInPhotoUrl,
                            empty: (
                              <span className="text-xs italic text-muted-foreground">
                                {item.attendance ? 'GPS unavailable' : 'Not checked in'}
                              </span>
                            ),
                          })}
                          {renderPunchRow({
                            label: 'Out',
                            tone: 'out',
                            time: item.attendance?.checkOutTime,
                            tag: item.attendance?.checkOutLocationTag,
                            distance: item.attendance?.checkOutDistanceMeters,
                            placeName: item.attendance?.checkOutPlaceName,
                            accuracy: item.attendance?.checkOutAccuracyMeters,
                            lat: item.attendance?.checkOutLatitude,
                            lng: item.attendance?.checkOutLongitude,
                            photoUrl: item.attendance?.checkOutPhotoUrl,
                            extra: item.attendance?.isAutoPunchOut ? (
                              <span
                                className="rounded-full border border-amber-500/20 bg-amber-500/10 px-1.5 text-xs font-bold text-amber-700 dark:text-amber-400"
                                title={item.attendance.checkOutComments || 'Auto punched out by the system'}
                              >
                                ⚡ Auto
                              </span>
                            ) : undefined,
                            empty: item.attendance?.isAutoPunchOut ? (
                              <span className="text-xs font-medium italic text-amber-700 dark:text-amber-400">Closed by the system</span>
                            ) : item.attendance && !item.attendance.checkOutTime ? (
                              <span className="inline-flex items-center rounded bg-sky-500/10 px-1.5 py-0.5 text-xs font-semibold text-sky-700 dark:text-sky-400">
                                Still working
                              </span>
                            ) : undefined,
                          })}
                        </div>

                        {/* Working Duration & Remarks */}
                        {item.attendance && (
                          <div className="flex items-center justify-between pt-1 border-t border-border/50 text-[11px]">
                            <span className="text-muted-foreground font-medium">Working Duration:</span>
                            <span className="font-bold text-foreground bg-muted/60 px-2 py-0.5 rounded-md">
                              {getWorkingDuration(item.attendance.checkInTime, item.attendance.checkOutTime)}
                            </span>
                          </div>
                        )}

                        {item.attendance && (
                          <div className="flex items-center justify-between pt-2 border-t border-border/40 gap-2">
                            {item.attendance.lastKnownTime ? (
                              <div className="flex min-w-0 flex-1 items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-400 font-medium">
                                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
                                <span className="min-w-0 truncate" title={item.attendance.lastKnownPlaceName || undefined}>{item.attendance.lastKnownPlaceName || "Live GPS Active"}</span>
                                <span className="shrink-0 opacity-70 font-mono">({formatTimeStr(item.attendance.lastKnownTime)})</span>
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">GPS logged</span>
                            )}
                            <button
                              type="button"
                              onClick={() => handleOpenTrailModal(item.attendance!.id, `${item.username}'s Route`)}
                              className="inline-flex min-h-10 shrink-0 items-center gap-1.5 px-3 bg-sky-500/10 hover:bg-sky-500/20 text-sky-700 dark:text-sky-400 border border-sky-500/20 rounded-lg text-xs font-bold transition-colors cursor-pointer"
                            >
                              <Route className="h-3 w-3" />
                              <span>View Route</span>
                            </button>
                          </div>
                        )}
                        {item.attendance?.checkInComments && (
                          <p className="text-[10px] italic text-muted-foreground/80 bg-muted/20 p-2 rounded-lg border border-border/40">
                            Note: {item.attendance.checkInComments}
                          </p>
                        )}

                        {/* Pending Approval Quick Action Card */}
                        {item.attendance?.approvalStatus === 'pending' && (
                          <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/60 bg-amber-500/5 -mx-4 -mb-4 p-3 rounded-b-2xl border-t-amber-500/20">
                            <div className="flex items-center gap-1 text-[11px] font-bold text-amber-700 dark:text-amber-300">
                              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                              <span>Needs Admin Approval</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <button
                                type="button"
                                onClick={() => handleApproveAttendance(item.attendance!.id)}
                                disabled={actionProcessingId === item.attendance.id}
                                className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-[10px] font-bold shadow-2xs cursor-pointer disabled:opacity-50"
                              >
                                {actionProcessingId === item.attendance.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
                                Approve
                              </button>
                              <button
                                type="button"
                                onClick={() => handleOpenRejectModal(item.attendance!)}
                                disabled={actionProcessingId === item.attendance.id}
                                className="inline-flex items-center gap-1 px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[10px] font-bold shadow-2xs cursor-pointer disabled:opacity-50"
                              >
                                <XCircle className="h-3 w-3" />
                                Reject
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>

                {/* Desktop Table View (>= md) */}
                <div className="hidden md:block bg-card border border-border rounded-2xl shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-muted/40 border-b border-border text-[10px] text-muted-foreground uppercase font-black tracking-wider">
                          <th className="p-4">Salesperson</th>
                          <th className="p-4">Punch In</th>
                          <th className="p-4">Punch Out</th>
                          <th className="p-4">GPS In</th>
                          <th className="p-4">GPS Out</th>
                          <th className="p-4">Duration</th>
                          <th className="p-4 text-center">Status</th>
                          <th className="p-4 text-center">Approval</th>
                          <th className="p-4 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60 text-xs">
                        {filteredTeamToday.length === 0 ? (
                          <tr>
                            <td colSpan={9} className="p-8 text-center text-muted-foreground">No records matched</td>
                          </tr>
                        ) : (
                          filteredTeamToday.map(item => (
                            <tr key={item.userId} className="hover:bg-muted/10">
                              <td className="p-4 font-bold text-foreground">
                                <div className="flex items-center gap-2">
                                  <span>{item.username}</span>
                                  {item.attendance?.checkInPhotoUrl && (
                                    <button
                                      type="button"
                                      onClick={() => setPreviewPhotoUrl(item.attendance?.checkInPhotoUrl || null)}
                                      className="text-sky-500 hover:text-sky-600 transition-colors p-0.5 cursor-pointer"
                                      title="View punch-in selfie"
                                    >
                                      <Camera className="h-3.5 w-3.5" />
                                    </button>
                                  )}
                                </div>
                              </td>
                              <td className="p-4 text-muted-foreground">{item.attendance ? formatTimeStr(item.attendance.checkInTime) : '--:--'}</td>
                              <td className="p-4 text-muted-foreground">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span>{item.attendance ? formatTimeStr(item.attendance.checkOutTime) : '--:--'}</span>
                                  {item.attendance?.isAutoPunchOut && (
                                    <span className="text-[9px] font-bold text-amber-600 bg-amber-500/10 border border-amber-500/20 py-0.5 px-1.5 rounded-full inline-flex items-center gap-0.5" title={item.attendance.checkOutComments || "Auto Punched Out by System"}>
                                      ⚡ {item.attendance.autoPunchOutReason === 'midnight_boundary' ? 'Auto 23:58' : 'Auto 9h'}
                                    </span>
                                  )}
                                </div>
                              </td>
                              
                              {/* GPS In */}
                              <td className="p-4 text-muted-foreground">
                                <div className="space-y-1">
                                  {item.attendance?.checkInLocationTag && (
                                    <div>
                                      {renderLocationBadge(item.attendance.checkInLocationTag, item.attendance.checkInDistanceMeters, item.attendance.checkInPlaceName, item.attendance.checkInAccuracyMeters)}
                                    </div>
                                  )}
                                  {item.attendance && item.attendance.checkInLatitude && item.attendance.checkInLongitude ? (
                                    <a
                                      href={`https://www.google.com/maps?q=${encodeURIComponent(`${item.attendance.checkInLatitude},${item.attendance.checkInLongitude}`)}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-sky-600 dark:text-sky-400 hover:text-sky-700 hover:underline font-medium cursor-pointer transition-colors group text-[11px]"
                                      title="Open Punch-In location in Google Maps"
                                    >
                                      <MapPin className="h-3.5 w-3.5 text-sky-500 shrink-0 group-hover:scale-110 transition-transform" />
                                      <span>{item.attendance.checkInLatitude.substring(0, 8)}, {item.attendance.checkInLongitude.substring(0, 8)}</span>
                                      <ExternalLink className="h-3 w-3 opacity-60 group-hover:opacity-100 shrink-0 ml-0.5" />
                                    </a>
                                  ) : item.attendance ? (
                                    <span className="text-muted-foreground/60 italic text-[11px]">GPS Unavailable</span>
                                  ) : (
                                    <span className="text-muted-foreground/40 italic text-[11px]">Not Checked In</span>
                                  )}
                                </div>
                              </td>

                              {/* GPS Out */}
                              <td className="p-4 text-muted-foreground">
                                <div className="space-y-1">
                                  {item.attendance?.checkOutLocationTag && (
                                    <div>
                                      {renderLocationBadge(item.attendance.checkOutLocationTag, item.attendance.checkOutDistanceMeters, item.attendance.checkOutPlaceName, item.attendance.checkOutAccuracyMeters)}
                                    </div>
                                  )}
                                  {item.attendance && item.attendance.checkOutLatitude && item.attendance.checkOutLongitude ? (
                                    <a
                                      href={`https://www.google.com/maps?q=${encodeURIComponent(`${item.attendance.checkOutLatitude},${item.attendance.checkOutLongitude}`)}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 hover:underline font-medium cursor-pointer transition-colors group text-[11px]"
                                      title="Open Punch-Out location in Google Maps"
                                    >
                                      <MapPin className="h-3.5 w-3.5 text-emerald-500 shrink-0 group-hover:scale-110 transition-transform" />
                                      <span>{item.attendance.checkOutLatitude.substring(0, 8)}, {item.attendance.checkOutLongitude.substring(0, 8)}</span>
                                      <ExternalLink className="h-3 w-3 opacity-60 group-hover:opacity-100 shrink-0 ml-0.5" />
                                    </a>
                                  ) : item.attendance?.isAutoPunchOut ? (
                                    <span className="text-amber-600/80 italic text-[11px] font-medium">Auto System Punch</span>
                                  ) : item.attendance && !item.attendance.checkOutTime ? (
                                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sky-500/10 text-sky-600">
                                      In Progress
                                    </span>
                                  ) : (
                                    <span className="text-muted-foreground/40">--</span>
                                  )}
                                </div>
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
                              <td className="p-4 text-center">
                                {item.attendance ? (
                                  renderApprovalBadge(item.attendance.approvalStatus, item.attendance.isOutOfOffice)
                                ) : (
                                  <span className="text-muted-foreground/40 text-[11px]">--</span>
                                )}
                              </td>
                              <td className="p-4 text-right">
                                <div className="flex items-center justify-end gap-1.5 flex-wrap">
                                  {item.attendance && (
                                    <button
                                      type="button"
                                      onClick={() => handleOpenTrailModal(item.attendance!.id, `${item.username}'s Route`)}
                                      className="inline-flex items-center gap-1 px-2.5 py-1 bg-sky-500/10 hover:bg-sky-500/20 text-sky-600 dark:text-sky-400 border border-sky-500/20 rounded-lg text-[10px] font-bold transition-colors cursor-pointer"
                                      title="View movement trail & breadcrumbs"
                                    >
                                      <Route className="h-3 w-3" />
                                      <span>Route</span>
                                    </button>
                                  )}
                                  {item.attendance?.approvalStatus === 'pending' ? (
                                    <>
                                      <button
                                        type="button"
                                        onClick={() => handleApproveAttendance(item.attendance!.id)}
                                        disabled={actionProcessingId === item.attendance.id}
                                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-[10px] font-bold shadow-2xs cursor-pointer transition-colors disabled:opacity-50"
                                        title="Approve Out-of-Office Attendance"
                                      >
                                        {actionProcessingId === item.attendance.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
                                        <span>Approve</span>
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => handleOpenRejectModal(item.attendance!)}
                                        disabled={actionProcessingId === item.attendance.id}
                                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[10px] font-bold shadow-2xs cursor-pointer transition-colors disabled:opacity-50"
                                        title="Reject Out-of-Office Attendance"
                                      >
                                        <XCircle className="h-3 w-3" />
                                        <span>Reject</span>
                                      </button>
                                    </>
                                  ) : item.attendance?.approvalStatus === 'rejected' ? (
                                    <span className="text-[10px] font-medium text-rose-600 truncate max-w-[120px] inline-block" title={item.attendance.rejectionReason || "Rejected"}>
                                      {item.attendance.rejectionReason || "Rejected"}
                                    </span>
                                  ) : !item.attendance ? (
                                    <span className="text-muted-foreground/40 text-[11px]">--</span>
                                  ) : null}
                                </div>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* 2. Monthly Muster Roll Grid View */}
            {adminSubTab === 'muster' && (
              <div className="space-y-3 sm:space-y-4">
                {/* KPI Summary Cards */}
                {musterData && (
                  <div className="grid grid-cols-4 gap-1.5 sm:gap-3">
                    <div className="bg-card border border-border rounded-xl p-2 sm:p-3.5 shadow-xs flex flex-col justify-between">
                      <span className="text-[9px] sm:text-[10px] font-black uppercase text-muted-foreground tracking-wider truncate block">Staff</span>
                      <span className="text-base sm:text-xl font-black text-foreground mt-0.5 block">{musterData.companySummary.totalStaff}</span>
                      <span className="hidden sm:block text-[10px] text-muted-foreground">Active in roster</span>
                    </div>
                    <div className="bg-card border border-border rounded-xl p-2 sm:p-3.5 shadow-xs flex flex-col justify-between">
                      <span className="text-[9px] sm:text-[10px] font-black uppercase text-muted-foreground tracking-wider truncate block">Days</span>
                      <span className="text-base sm:text-xl font-black text-sky-600 dark:text-sky-400 mt-0.5 block">{musterData.companySummary.workingDaysElapsed}</span>
                      <span className="hidden sm:block text-[10px] text-muted-foreground">Excl. Sunday offs</span>
                    </div>
                    <div className="bg-card border border-border rounded-xl p-2 sm:p-3.5 shadow-xs flex flex-col justify-between">
                      <span className="text-[9px] sm:text-[10px] font-black uppercase text-muted-foreground tracking-wider truncate block">Attendance</span>
                      <span className="text-base sm:text-xl font-black text-emerald-600 dark:text-emerald-400 mt-0.5 block">{musterData.companySummary.avgAttendancePct}%</span>
                      <span className="hidden sm:block text-[10px] text-muted-foreground">Company average</span>
                    </div>
                    <div className="bg-card border border-border rounded-xl p-2 sm:p-3.5 shadow-xs flex flex-col justify-between">
                      <span className="text-[9px] sm:text-[10px] font-black uppercase text-muted-foreground tracking-wider truncate block">Hours</span>
                      <span className="text-base sm:text-xl font-black text-purple-600 dark:text-purple-400 mt-0.5 block">{musterData.companySummary.totalCompanyHours}h</span>
                      <span className="hidden sm:block text-[10px] text-muted-foreground">Logged this month</span>
                    </div>
                  </div>
                )}

                {/* Legend & quick instructions & Mobile view toggle */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs bg-muted/30 border border-border/60 rounded-xl px-3 py-2 sm:px-4 sm:py-2.5">
                  <div className="flex items-center gap-2 sm:gap-3 overflow-x-auto no-scrollbar py-0.5">
                    <span className="text-[10px] sm:text-[11px] font-bold text-muted-foreground uppercase tracking-wider shrink-0">Legend:</span>
                    <span className="inline-flex items-center gap-1 text-[10px] sm:text-[11px] font-semibold shrink-0">
                      <span className="min-w-5 h-5 px-0.5 rounded flex items-center justify-center font-bold text-[9px] sm:text-[10px] bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30">P</span>
                      <span>Present</span>
                    </span>
                    <span className="inline-flex items-center gap-1 text-[10px] sm:text-[11px] font-semibold shrink-0">
                      <span className="min-w-5 h-5 px-0.5 rounded flex items-center justify-center font-bold text-[9px] sm:text-[10px] bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30">HD</span>
                      <span>Half Day</span>
                    </span>
                    <span className="inline-flex items-center gap-1 text-[10px] sm:text-[11px] font-semibold shrink-0">
                      <span className="min-w-5 h-5 px-0.5 rounded flex items-center justify-center font-bold text-[9px] sm:text-[10px] bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30">A</span>
                      <span>Absent</span>
                    </span>
                    <span className="inline-flex items-center gap-1 text-[10px] sm:text-[11px] font-semibold shrink-0">
                      <span className="min-w-5 h-5 px-0.5 rounded flex items-center justify-center font-bold text-[9px] sm:text-[10px] bg-muted/60 text-muted-foreground border border-border">WO</span>
                      <span>Sunday Off</span>
                    </span>
                  </div>

                  <div className="flex items-center justify-between sm:justify-end gap-3 pt-1 sm:pt-0 border-t sm:border-t-0 border-border/40">
                    <span className="hidden lg:inline text-[11px] text-muted-foreground italic">Click cell to inspect punch details, GPS & selfie</span>
                    
                    {/* Mobile View Mode Switcher: Matrix vs Cards (shown on mobile < md) */}
                    <div className="flex md:hidden items-center gap-1 bg-card p-0.5 rounded-lg border border-border shadow-2xs ml-auto">
                      <button
                        type="button"
                        onClick={() => setMusterMobileView('matrix')}
                        className={cn(
                          "px-2.5 py-1 rounded-md text-[10px] font-bold transition-all flex items-center gap-1 cursor-pointer",
                          musterMobileView === 'matrix' ? "bg-primary text-primary-foreground shadow-2xs" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <TableIcon className="h-3 w-3" /> Matrix
                      </button>
                      <button
                        type="button"
                        onClick={() => setMusterMobileView('cards')}
                        className={cn(
                          "px-2.5 py-1 rounded-md text-[10px] font-bold transition-all flex items-center gap-1 cursor-pointer",
                          musterMobileView === 'cards' ? "bg-primary text-primary-foreground shadow-2xs" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <LayoutGrid className="h-3 w-3" /> Cards
                      </button>
                    </div>
                  </div>
                </div>

                {/* Mobile Cards View (< md when musterMobileView === 'cards') */}
                {musterMobileView === 'cards' && (
                  <div className="block md:hidden space-y-3">
                    {musterLoading ? (
                      <div className="p-12 flex flex-col items-center justify-center gap-3 text-muted-foreground bg-card border border-border rounded-2xl">
                        <Loader2 className="h-6 w-6 animate-spin text-sky-500" />
                        <span className="text-xs font-semibold">Loading muster roll for {musterMonth}/{musterYear}...</span>
                      </div>
                    ) : !musterData || filteredMusterEmployees.length === 0 ? (
                      <div className="p-8 text-center text-muted-foreground bg-card border border-border rounded-2xl shadow-sm text-xs">
                        No attendance records found for this period.
                      </div>
                    ) : (
                      filteredMusterEmployees.map(emp => (
                        <div key={emp.userId} className="p-3.5 border border-border rounded-2xl bg-card shadow-sm space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className="h-8 w-8 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center uppercase shrink-0">
                                {emp.username.charAt(0)}
                              </div>
                              <div className="min-w-0">
                                <h4 className="font-bold text-xs text-foreground leading-tight truncate">{emp.username}</h4>
                                <span className="text-[9px] text-muted-foreground font-normal">ID #{emp.userId}</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-1 text-[11px] font-black text-purple-600 bg-purple-500/10 px-2 py-0.5 rounded-lg shrink-0">
                              <Clock className="h-3 w-3" /> {emp.summary.totalHours}h
                            </div>
                          </div>

                          {/* 4 Counter Pills */}
                          <div className="grid grid-cols-4 gap-1.5 text-center">
                            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg py-1 px-1">
                              <span className="text-[9px] font-bold text-emerald-600 block">Present</span>
                              <span className="text-xs font-black text-emerald-700 dark:text-emerald-300">{emp.summary.totalPresent}</span>
                            </div>
                            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg py-1 px-1">
                              <span className="text-[9px] font-bold text-amber-600 block">Half Day</span>
                              <span className="text-xs font-black text-amber-700 dark:text-amber-300">{emp.summary.totalHalfDay}</span>
                            </div>
                            <div className="bg-rose-500/10 border border-rose-500/20 rounded-lg py-1 px-1">
                              <span className="text-[9px] font-bold text-rose-600 block">Absent</span>
                              <span className="text-xs font-black text-rose-700 dark:text-rose-300">{emp.summary.totalAbsent}</span>
                            </div>
                            <div className="bg-muted/60 border border-border rounded-lg py-1 px-1">
                              <span className="text-[9px] font-bold text-muted-foreground block">Off</span>
                              <span className="text-xs font-black text-muted-foreground">{emp.summary.totalWeekOff}</span>
                            </div>
                          </div>

                          {/* Horizontal Swipeable Timeline of Days */}
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                              <span className="font-semibold uppercase tracking-wider text-[9px]">Timeline (Days 1–{musterData.totalDays})</span>
                              <span className="italic text-[9px]">Tap cell to inspect</span>
                            </div>
                            <div className="flex items-center gap-1 overflow-x-auto pb-1.5 pt-0.5 no-scrollbar touch-pan-x">
                              {musterData.days.map(d => {
                                const dayAtt = emp.days[String(d.day)] || {
                                  status: (d.isSunday ? 'WO' : 'A') as 'P' | 'HD' | 'A' | 'WO' | '-',
                                  checkIn: null,
                                  checkOut: null,
                                  hours: 0,
                                  locationTag: null,
                                  isAutoPunchOut: false,
                                  photoUrl: null
                                }
                                const code = dayAtt.status
                                return (
                                  <button
                                    key={d.day}
                                    type="button"
                                    onClick={() => setSelectedMusterCell({ employee: emp, day: d, attendance: dayAtt })}
                                    className={cn(
                                      "flex flex-col items-center justify-center p-1 rounded-lg min-w-[28px] border transition-all active:scale-95 cursor-pointer shrink-0 select-none",
                                      d.isSunday && "border-rose-500/30 bg-rose-500/5",
                                      code === 'P' && "bg-emerald-500/15 border-emerald-500/40 text-emerald-700 dark:text-emerald-300",
                                      code === 'HD' && "bg-amber-500/15 border-amber-500/40 text-amber-700 dark:text-amber-300",
                                      code === 'A' && "bg-rose-500/15 border-rose-500/30 text-rose-700 dark:text-rose-300",
                                      code === 'WO' && "bg-muted/40 border-border text-muted-foreground",
                                      code === '-' && "bg-muted/10 border-border/40 text-muted-foreground/40"
                                    )}
                                  >
                                    <span className="text-[8px] font-mono font-bold opacity-75">{d.day}</span>
                                    <span className="text-[10px] font-black">{code}</span>
                                  </button>
                                )
                              })}
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* Table Container (Always on desktop md:, or on mobile when musterMobileView === 'matrix') */}
                <div className={cn(
                  "bg-card border border-border rounded-2xl shadow-sm overflow-hidden",
                  musterMobileView === 'cards' ? "hidden md:block" : "block"
                )}>
                  {musterLoading ? (
                    <div className="p-12 flex flex-col items-center justify-center gap-3 text-muted-foreground">
                      <Loader2 className="h-6 w-6 animate-spin text-sky-500" />
                      <span className="text-xs font-semibold">Loading muster roll for {musterMonth}/{musterYear}...</span>
                    </div>
                  ) : !musterData || filteredMusterEmployees.length === 0 ? (
                    <div className="p-12 text-center text-muted-foreground text-xs">
                      No attendance records found for this period.
                    </div>
                  ) : (
                    <div className="overflow-x-auto max-h-[650px] relative touch-pan-x overscroll-x-contain">
                      <table className="w-full text-xs text-left border-collapse min-w-[700px] sm:min-w-[900px]">
                        <thead className="bg-muted/70 text-foreground uppercase font-black text-[10px] tracking-wider sticky top-0 z-20 backdrop-blur-xs border-b border-border">
                          <tr>
                            <th className="p-2 sm:p-3 sticky left-0 z-30 bg-muted/95 w-[105px] sm:w-[180px] min-w-[105px] sm:min-w-[180px] shadow-sm">
                              Employee
                            </th>
                            {musterData.days.map(d => (
                              <th 
                                key={d.day} 
                                className={cn(
                                  "p-1 sm:p-1.5 text-center min-w-[28px] sm:min-w-[34px] border-r border-border/40 font-mono",
                                  d.isSunday && "bg-rose-500/10 text-rose-600 dark:text-rose-400 font-black"
                                )}
                              >
                                <div className="text-[10px] sm:text-xs font-bold">{d.day}</div>
                                <div className="text-[7px] sm:text-[8px] font-normal opacity-70">{d.weekday.slice(0, 2)}</div>
                              </th>
                            ))}
                            <th className="p-1 sm:p-2 text-center bg-muted/95 min-w-[32px] sm:min-w-[45px] text-emerald-600 text-[10px] sm:text-xs">P</th>
                            <th className="p-1 sm:p-2 text-center bg-muted/95 min-w-[32px] sm:min-w-[45px] text-amber-600 text-[10px] sm:text-xs">HD</th>
                            <th className="p-1 sm:p-2 text-center bg-muted/95 min-w-[32px] sm:min-w-[45px] text-rose-600 text-[10px] sm:text-xs">A</th>
                            <th className="p-1 sm:p-2 text-center bg-muted/95 min-w-[42px] sm:min-w-[60px] text-purple-600 text-[10px] sm:text-xs">Hrs</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          {filteredMusterEmployees.map(emp => (
                            <tr key={emp.userId} className="hover:bg-muted/30 transition-colors">
                              <td className="p-2 sm:p-3 sticky left-0 z-10 bg-card hover:bg-muted/50 font-bold text-foreground border-r border-border shadow-xs w-[105px] sm:w-[180px] min-w-[105px] sm:min-w-[180px]">
                                <div className="flex items-center gap-1.5 sm:gap-2">
                                  <div className="h-6 w-6 sm:h-7 sm:w-7 rounded-full bg-primary/10 text-primary font-bold text-[9px] sm:text-[10px] flex items-center justify-center uppercase shrink-0">
                                    {emp.username.charAt(0)}
                                  </div>
                                  <div className="truncate min-w-0">
                                    <div className="truncate text-[11px] sm:text-xs font-bold leading-tight">{emp.username}</div>
                                    <div className="hidden sm:block text-[9px] text-muted-foreground font-normal">ID #{emp.userId}</div>
                                  </div>
                                </div>
                              </td>
                              {musterData.days.map(d => {
                                const dayAtt = emp.days[String(d.day)] || {
                                  status: (d.isSunday ? 'WO' : 'A') as 'P' | 'HD' | 'A' | 'WO' | '-',
                                  checkIn: null,
                                  checkOut: null,
                                  hours: 0,
                                  locationTag: null,
                                  isAutoPunchOut: false,
                                  photoUrl: null
                                }
                                const code = dayAtt.status
                                const isP = code === 'P'
                                const isHD = code === 'HD'
                                const isA = code === 'A'
                                const isWO = code === 'WO'

                                return (
                                  <td 
                                    key={d.day}
                                    onClick={() => setSelectedMusterCell({ employee: emp, day: d, attendance: dayAtt })}
                                    className={cn(
                                      "p-0.5 sm:p-1 text-center border-r border-border/30 cursor-pointer transition-all hover:scale-105 active:scale-95 select-none",
                                      d.isSunday && "bg-muted/20"
                                    )}
                                    title={`${emp.username} - Day ${d.day} (${d.weekday}): ${code} ${dayAtt.hours > 0 ? `(${dayAtt.hours}h)` : ''}`}
                                  >
                                    <span className={cn(
                                      "inline-block min-w-6 h-6 px-0.5 leading-6 rounded sm:rounded-md font-bold text-[9px] sm:text-[10px] shadow-2xs",
                                      isP && "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30",
                                      isHD && "bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/40 hover:bg-amber-500/30",
                                      isA && "bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/30 hover:bg-rose-500/25",
                                      isWO && "bg-muted/40 text-muted-foreground/60 border border-transparent"
                                    )}>
                                      {code}
                                    </span>
                                  </td>
                                )
                              })}
                              <td className="p-1 sm:p-2 text-center font-bold text-emerald-600 bg-emerald-500/5 text-[10px] sm:text-xs">{emp.summary.totalPresent}</td>
                              <td className="p-1 sm:p-2 text-center font-bold text-amber-600 bg-amber-500/5 text-[10px] sm:text-xs">{emp.summary.totalHalfDay}</td>
                              <td className="p-1 sm:p-2 text-center font-bold text-rose-600 bg-rose-500/5 text-[10px] sm:text-xs">{emp.summary.totalAbsent}</td>
                              <td className="p-1 sm:p-2 text-center font-black text-purple-600 bg-purple-500/5 whitespace-nowrap text-[10px] sm:text-xs">{emp.summary.totalHours}h</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 3. Historical Team Logs */}
            {adminSubTab === 'history' && (
              <div className="space-y-4">
                {/* Mobile Cards View (< md) */}
                <div className="block md:hidden space-y-3">
                  {filteredTeamHistory.length === 0 ? (
                    <div className="p-8 text-center text-muted-foreground bg-card border border-border rounded-2xl shadow-sm text-xs">
                      No records in selected date range
                    </div>
                  ) : (
                    filteredTeamHistory.map(item => (
                      <div key={item.id} className="p-4 border border-border rounded-2xl bg-card shadow-sm space-y-3">
                        {/* Top row: Salesperson, Date, and Duration */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2.5">
                            <div className="h-9 w-9 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center uppercase shadow-inner">
                              {(item.username || 'U').charAt(0)}
                            </div>
                            <div>
                              <h4 className="font-bold text-sm text-foreground leading-tight">{item.username}</h4>
                              <span className="text-[10px] text-muted-foreground font-medium">
                                {formatDate(item.checkInTime.split('T')[0])}
                              </span>
                            </div>
                          </div>
                          <span className="text-[10px] font-bold text-emerald-600 bg-emerald-500/10 border border-emerald-500/20 py-0.5 px-2.5 rounded-full">
                            {getWorkingDuration(item.checkInTime, item.checkOutTime)}
                          </span>
                        </div>

                        {/* In / out, one full-width row each */}
                        <div className="divide-y divide-border/50 rounded-xl border border-border/50 bg-muted/30">
                          {renderPunchRow({
                            label: 'In',
                            tone: 'in',
                            time: item.checkInTime,
                            tag: item.checkInLocationTag,
                            distance: item.checkInDistanceMeters,
                            placeName: item.checkInPlaceName,
                            accuracy: item.checkInAccuracyMeters,
                            lat: item.checkInLatitude,
                            lng: item.checkInLongitude,
                            photoUrl: item.checkInPhotoUrl,
                          })}
                          {renderPunchRow({
                            label: 'Out',
                            tone: 'out',
                            time: item.checkOutTime,
                            tag: item.checkOutLocationTag,
                            distance: item.checkOutDistanceMeters,
                            placeName: item.checkOutPlaceName,
                            accuracy: item.checkOutAccuracyMeters,
                            lat: item.checkOutLatitude,
                            lng: item.checkOutLongitude,
                            photoUrl: item.checkOutPhotoUrl,
                            empty: !item.checkOutTime ? (
                              <span className="text-xs italic text-muted-foreground">Not clocked out</span>
                            ) : undefined,
                          })}
                        </div>

                        <button
                          type="button"
                          onClick={() => handleOpenTrailModal(item.id, `${item.username}'s Route (${formatDate(item.checkInTime.split('T')[0])})`)}
                          className="flex min-h-11 w-full items-center justify-center gap-1.5 rounded-xl border border-sky-500/20 bg-sky-500/10 text-sm font-bold text-sky-700 transition-colors hover:bg-sky-500/20 dark:text-sky-400 cursor-pointer"
                        >
                          <Route className="h-4 w-4" />
                          View route for the day
                        </button>

                        {item.checkInComments && (
                          <p className="text-[10px] italic text-muted-foreground/80 bg-muted/20 p-2 rounded-lg border border-border/40">
                            Note: {item.checkInComments}
                          </p>
                        )}
                      </div>
                    ))
                  )}
                </div>

                {/* Desktop Table View (>= md) */}
                <div className="hidden md:block bg-card border border-border rounded-2xl shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-muted/40 border-b border-border text-[10px] text-muted-foreground uppercase font-black tracking-wider">
                          <th className="p-4">Date</th>
                          <th className="p-4">Username</th>
                          <th className="p-4">In Time</th>
                          <th className="p-4">Out Time</th>
                          <th className="p-4">GPS In</th>
                          <th className="p-4">GPS Out</th>
                          <th className="p-4">Working hours</th>
                          <th className="p-4 text-right">Route</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60 text-xs">
                        {filteredTeamHistory.length === 0 ? (
                          <tr>
                            <td colSpan={8} className="p-8 text-center text-muted-foreground">No records in selected date range</td>
                          </tr>
                        ) : (
                          filteredTeamHistory.map(item => (
                            <tr key={item.id} className="hover:bg-muted/10">
                              <td className="p-4 font-bold text-foreground">{formatDate(item.checkInTime.split('T')[0])}</td>
                              <td className="p-4 font-semibold text-foreground">
                                <div className="flex items-center gap-2">
                                  <span>{item.username}</span>
                                  {item.checkInPhotoUrl && (
                                    <button
                                      type="button"
                                      onClick={() => setPreviewPhotoUrl(item.checkInPhotoUrl)}
                                      className="text-sky-500 hover:text-sky-600 transition-colors p-0.5 cursor-pointer"
                                      title="View punch-in selfie"
                                    >
                                      <Camera className="h-3.5 w-3.5" />
                                    </button>
                                  )}
                                </div>
                              </td>
                              <td className="p-4 text-muted-foreground">{formatTimeStr(item.checkInTime)}</td>
                              <td className="p-4 text-muted-foreground">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span>{formatTimeStr(item.checkOutTime)}</span>
                                  {item.isAutoPunchOut && (
                                    <span className="text-[9px] font-bold text-amber-600 bg-amber-500/10 border border-amber-500/20 py-0.5 px-1.5 rounded-full inline-flex items-center gap-0.5" title={item.checkOutComments || "Auto Punched Out by System"}>
                                      ⚡ {item.autoPunchOutReason === 'midnight_boundary' ? 'Auto 23:58' : 'Auto 9h'}
                                    </span>
                                  )}
                                </div>
                              </td>
                              
                              {/* GPS In */}
                              <td className="p-4 text-muted-foreground">
                                <div className="space-y-1">
                                  {item.checkInLocationTag && (
                                    <div>
                                      {renderLocationBadge(item.checkInLocationTag, item.checkInDistanceMeters, item.checkInPlaceName, item.checkInAccuracyMeters)}
                                    </div>
                                  )}
                                  {item.checkInLatitude && item.checkInLongitude ? (
                                    <a
                                      href={`https://www.google.com/maps?q=${encodeURIComponent(`${item.checkInLatitude},${item.checkInLongitude}`)}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-sky-600 dark:text-sky-400 hover:text-sky-700 hover:underline font-medium cursor-pointer transition-colors group text-[11px]"
                                      title="Open Punch-In location in Google Maps"
                                    >
                                      <MapPin className="h-3.5 w-3.5 text-sky-500 shrink-0 group-hover:scale-110 transition-transform" />
                                      <span>{item.checkInLatitude.substring(0, 8)}, {item.checkInLongitude.substring(0, 8)}</span>
                                      <ExternalLink className="h-3 w-3 opacity-60 group-hover:opacity-100 shrink-0 ml-0.5" />
                                    </a>
                                  ) : (
                                    <span className="text-muted-foreground/50">--</span>
                                  )}
                                </div>
                              </td>

                              {/* GPS Out */}
                              <td className="p-4 text-muted-foreground">
                                <div className="space-y-1">
                                  {item.checkOutLocationTag && (
                                    <div>
                                      {renderLocationBadge(item.checkOutLocationTag, item.checkOutDistanceMeters, item.checkOutPlaceName, item.checkOutAccuracyMeters)}
                                    </div>
                                  )}
                                  {item.checkOutLatitude && item.checkOutLongitude ? (
                                    <a
                                      href={`https://www.google.com/maps?q=${encodeURIComponent(`${item.checkOutLatitude},${item.checkOutLongitude}`)}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 hover:underline font-medium cursor-pointer transition-colors group text-[11px]"
                                      title="Open Punch-Out location in Google Maps"
                                    >
                                      <MapPin className="h-3.5 w-3.5 text-emerald-500 shrink-0 group-hover:scale-110 transition-transform" />
                                      <span>{item.checkOutLatitude.substring(0, 8)}, {item.checkOutLongitude.substring(0, 8)}</span>
                                      <ExternalLink className="h-3 w-3 opacity-60 group-hover:opacity-100 shrink-0 ml-0.5" />
                                    </a>
                                  ) : item.isAutoPunchOut ? (
                                    <span className="text-amber-600/80 italic text-[11px] font-medium">Auto System Punch</span>
                                  ) : (
                                    <span className="text-muted-foreground/50">--</span>
                                  )}
                                </div>
                              </td>

                              <td className="p-4 font-bold text-foreground">{getWorkingDuration(item.checkInTime, item.checkOutTime)}</td>
                              <td className="p-4 text-right">
                                <button
                                  type="button"
                                  onClick={() => handleOpenTrailModal(item.id, `${item.username}'s Route (${formatDate(item.checkInTime.split('T')[0])})`)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 bg-sky-500/10 hover:bg-sky-500/20 text-sky-600 dark:text-sky-400 border border-sky-500/20 rounded-lg text-[10px] font-bold transition-colors cursor-pointer"
                                  title="View movement route trail"
                                >
                                  <Route className="h-3 w-3" />
                                  <span>Route</span>
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* 4. Office Geofences Management View */}
            {adminSubTab === 'offices' && (
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-card border border-border rounded-2xl p-4 shadow-sm">
                  <div>
                    <h3 className="font-bold text-sm text-foreground">Office Locations & Geofence Boundaries</h3>
                    <p className="text-[11px] text-muted-foreground">
                      Punches within configured radii will be tagged as &quot;In Office: [Name]&quot;. Punches outside will indicate distance from nearest office.
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setEditingOffice(null)
                      setOfficeForm({ name: '', address: '', latitude: '', longitude: '', radiusMeters: 200 })
                      setShowOfficeModal(true)
                    }}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-sky-500 hover:bg-sky-600 text-white rounded-xl text-xs font-bold transition-all shadow-sm cursor-pointer shrink-0 self-start sm:self-auto"
                  >
                    <Plus className="h-3.5 w-3.5" /> Add Office Location
                  </button>
                </div>

                {offices.length === 0 ? (
                  <div className="bg-card border border-dashed border-border rounded-2xl p-12 text-center space-y-3">
                    <Building className="h-10 w-10 text-muted-foreground/40 mx-auto" />
                    <div>
                      <h4 className="font-bold text-sm text-foreground">No Office Geofences Configured</h4>
                      <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                        Set up your head office, branch, or warehouses with GPS coordinates and radius in meters. The portal will automatically calculate distances and tag employee punch-ins.
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setEditingOffice(null)
                        setOfficeForm({ name: '', address: '', latitude: '', longitude: '', radiusMeters: 200 })
                        setShowOfficeModal(true)
                      }}
                      className="inline-flex items-center gap-1.5 px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white rounded-xl text-xs font-bold transition-all shadow-sm cursor-pointer"
                    >
                      <Plus className="h-4 w-4" /> Add First Office Location
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {offices.map(off => (
                      <div key={off.id} className="bg-card border border-border rounded-2xl p-4 shadow-sm space-y-3 flex flex-col justify-between">
                        <div className="space-y-2">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <div className="h-9 w-9 rounded-xl bg-sky-500/10 text-sky-600 flex items-center justify-center shrink-0 border border-sky-500/20">
                                <Building className="h-4 w-4" />
                              </div>
                              <div>
                                <h4 className="font-bold text-sm text-foreground leading-tight">{off.name}</h4>
                                <span className="text-[10px] text-muted-foreground font-medium">Radius: {off.radiusMeters} meters</span>
                              </div>
                            </div>
                            <span className={cn(
                              "text-[9px] font-extrabold uppercase px-2 py-0.5 rounded-full border",
                              off.isActive 
                                ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20" 
                                : "bg-muted text-muted-foreground border-border"
                            )}>
                              {off.isActive ? 'Active' : 'Inactive'}
                            </span>
                          </div>

                          {off.address && (
                            <p className="text-xs text-muted-foreground line-clamp-2">
                              {off.address}
                            </p>
                          )}

                          <div className="flex items-center gap-2 pt-1 text-xs">
                            <a
                              href={`https://www.google.com/maps?q=${encodeURIComponent(`${off.latitude},${off.longitude}`)}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-[11px] font-bold text-sky-600 dark:text-sky-400 hover:underline bg-sky-500/10 px-2.5 py-1 rounded-lg"
                              title="Open location in Google Maps"
                            >
                              <MapPin className="h-3 w-3 text-sky-500 shrink-0" />
                              <span>{off.latitude.toFixed(6)}, {off.longitude.toFixed(6)}</span>
                              <ExternalLink className="h-2.5 w-2.5 opacity-70 ml-0.5" />
                            </a>
                          </div>
                        </div>

                        <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/60">
                          <button
                            onClick={() => {
                              setEditingOffice(off)
                              setOfficeForm({
                                name: off.name,
                                address: off.address || '',
                                latitude: off.latitude.toString(),
                                longitude: off.longitude.toString(),
                                radiusMeters: off.radiusMeters
                              })
                              setShowOfficeModal(true)
                            }}
                            className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-border hover:bg-muted text-foreground transition-colors cursor-pointer"
                          >
                            <Edit2 className="h-3 w-3 text-muted-foreground" /> Edit
                          </button>
                          <button
                            onClick={() => handleDeleteOffice(off.id)}
                            className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-rose-500/20 hover:bg-rose-500/10 text-rose-600 transition-colors cursor-pointer"
                          >
                            <Trash2 className="h-3 w-3" /> Delete
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Dedicated Out-of-Office Approvals View */}
            {adminSubTab === 'approvals' && (
              <div className="space-y-4">
                {/* Header card with status pill filters & bulk actions */}
                <div className="bg-card border border-border rounded-2xl p-4 shadow-sm space-y-3.5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="h-5 w-5 text-sky-500" />
                        <h3 className="font-extrabold text-sm text-foreground">
                          Out-of-Office Attendance Approvals
                        </h3>
                        {pendingApprovalsCount > 0 && (
                          <span className="bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30 text-[10px] font-bold px-2 py-0.5 rounded-full">
                            {pendingApprovalsCount} Pending Review
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        Verify and approve or reject employee attendance punches made outside configured office geofences.
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => fetchApprovals(approvalsFilter)}
                        disabled={loadingApprovals}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-semibold hover:bg-muted text-foreground transition-colors cursor-pointer"
                        title="Refresh approvals"
                      >
                        <RefreshCw className={cn("h-3.5 w-3.5", loadingApprovals && "animate-spin text-sky-500")} />
                        <span>Refresh</span>
                      </button>
                    </div>
                  </div>

                  {/* Filter tabs and search */}
                  <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-2.5 pt-1 border-t border-border/60">
                    <div className="flex overflow-x-auto no-scrollbar gap-1 bg-muted/60 p-1 rounded-xl border border-border w-full md:w-auto">
                      {(['pending', 'approved', 'rejected', 'all'] as const).map(tab => (
                        <button
                          key={tab}
                          type="button"
                          onClick={() => {
                            setApprovalsFilter(tab)
                            setSelectedApprovalIds([])
                            fetchApprovals(tab)
                          }}
                          className={cn(
                            "px-3 py-1.5 rounded-lg text-xs font-bold transition-all capitalize whitespace-nowrap cursor-pointer flex items-center gap-1.5",
                            approvalsFilter === tab
                              ? "bg-card text-foreground shadow-sm"
                              : "text-muted-foreground hover:text-foreground"
                          )}
                        >
                          <span>{tab === 'all' ? 'All Records' : tab}</span>
                          {tab === 'pending' && pendingApprovalsCount > 0 && (
                            <span className="bg-amber-500 text-white text-[9px] font-black px-1.5 py-0.2 rounded-full min-w-4 text-center leading-tight">
                              {pendingApprovalsCount}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>

                    <div className="flex items-center gap-2 flex-1 md:justify-end">
                      <div className="relative w-full md:w-64">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                        <input
                          type="text"
                          placeholder="Search salesperson or location..."
                          value={approvalSearchTerm}
                          onChange={e => setApprovalSearchTerm(e.target.value)}
                          className="pl-8 pr-3 py-1.5 w-full border border-border rounded-lg bg-background text-xs focus:outline-none"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Bulk action toolbar when in 'pending' filter */}
                  {approvalsFilter === 'pending' && approvalsList.length > 0 && (
                    <div className="flex items-center justify-between gap-3 pt-2 border-t border-border/40 text-xs">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            const pendingItems = approvalsList.filter(a => a.approvalStatus === 'pending')
                            if (selectedApprovalIds.length === pendingItems.length) {
                              setSelectedApprovalIds([])
                            } else {
                              setSelectedApprovalIds(pendingItems.map(a => a.id))
                            }
                          }}
                          className="flex items-center gap-1.5 text-xs font-bold text-foreground cursor-pointer hover:text-sky-600 transition-colors"
                        >
                          {selectedApprovalIds.length > 0 && selectedApprovalIds.length === approvalsList.filter(a => a.approvalStatus === 'pending').length ? (
                            <CheckSquare className="h-4 w-4 text-sky-500" />
                          ) : (
                            <Square className="h-4 w-4 text-muted-foreground" />
                          )}
                          <span>
                            {selectedApprovalIds.length === approvalsList.filter(a => a.approvalStatus === 'pending').length
                              ? "Deselect All"
                              : `Select All Pending (${approvalsList.filter(a => a.approvalStatus === 'pending').length})`}
                          </span>
                        </button>
                        {selectedApprovalIds.length > 0 && (
                          <span className="text-[11px] text-muted-foreground">
                            ({selectedApprovalIds.length} selected)
                          </span>
                        )}
                      </div>

                      {selectedApprovalIds.length > 0 && (
                        <button
                          type="button"
                          onClick={handleBulkApprove}
                          disabled={bulkApproving}
                          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold shadow-2xs cursor-pointer inline-flex items-center gap-1.5 transition-all"
                        >
                          {bulkApproving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                          <span>Approve Selected ({selectedApprovalIds.length})</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Approvals list */}
                {loadingApprovals ? (
                  <div className="p-12 flex flex-col items-center justify-center gap-3 text-muted-foreground bg-card border border-border rounded-2xl shadow-sm">
                    <Loader2 className="h-7 w-7 animate-spin text-sky-500" />
                    <span className="text-xs font-semibold">Loading out-of-office attendances...</span>
                  </div>
                ) : (() => {
                  const filteredApprovals = approvalsList.filter(item => {
                    if (!approvalSearchTerm.trim()) return true
                    const term = approvalSearchTerm.toLowerCase()
                    return (
                      item.username?.toLowerCase().includes(term) ||
                      item.checkInLocationTag?.toLowerCase().includes(term) ||
                      item.checkOutLocationTag?.toLowerCase().includes(term) ||
                      item.checkInComments?.toLowerCase().includes(term) ||
                      item.rejectionReason?.toLowerCase().includes(term)
                    )
                  })

                  if (filteredApprovals.length === 0) {
                    return (
                      <div className="bg-card border border-dashed border-border rounded-2xl p-12 text-center space-y-2.5">
                        <ShieldCheck className="h-10 w-10 text-muted-foreground/40 mx-auto" />
                        <h4 className="font-bold text-sm text-foreground">
                          {approvalsFilter === 'pending'
                            ? "No Pending Approvals"
                            : "No Records Found"}
                        </h4>
                        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                          {approvalsFilter === 'pending'
                            ? "All out-of-office punches have been reviewed. Any new punches outside configured office geofences will appear here."
                            : `No attendance records found under '${approvalsFilter}' filter.`}
                        </p>
                      </div>
                    )
                  }

                  return (
                    <div className="space-y-3">
                      {filteredApprovals.map(item => {
                        const isSelected = selectedApprovalIds.includes(item.id)
                        const isPending = item.approvalStatus === 'pending'
                        return (
                          <div
                            key={item.id}
                            data-link-target={`attendance-${item.id}`}
                            className={cn(
                              "bg-card border rounded-2xl p-4 shadow-sm space-y-3 transition-all",
                              isPending ? "border-amber-500/30 bg-amber-500/[0.02]" : "border-border",
                              isSelected && "ring-2 ring-sky-500/40 border-sky-500",
                              item.id === linkedId && LINKED_RECORD
                            )}
                          >
                            {/* Top Row: User details & Approval Status */}
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 border-b border-border/50 pb-3">
                              <div className="flex items-center gap-3">
                                {isPending && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      if (isSelected) {
                                        setSelectedApprovalIds(prev => prev.filter(id => id !== item.id))
                                      } else {
                                        setSelectedApprovalIds(prev => [...prev, item.id])
                                      }
                                    }}
                                    className="text-muted-foreground hover:text-sky-600 cursor-pointer p-0.5"
                                  >
                                    {isSelected ? (
                                      <CheckSquare className="h-4 w-4 text-sky-500" />
                                    ) : (
                                      <Square className="h-4 w-4 text-muted-foreground" />
                                    )}
                                  </button>
                                )}
                                <div className="h-9 w-9 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center uppercase shadow-inner shrink-0">
                                  {(item.username || 'U').charAt(0)}
                                </div>
                                <div>
                                  <div className="flex items-center gap-2">
                                    <h4 className="font-bold text-sm text-foreground leading-tight">
                                      {item.username || `User #${item.userId}`}
                                    </h4>
                                    <span className="text-[10px] text-muted-foreground font-mono">
                                      #{item.id}
                                    </span>
                                  </div>
                                  <span className="text-[11px] text-muted-foreground font-medium">
                                    {formatDate(item.checkInTime.split('T')[0])}
                                  </span>
                                </div>
                              </div>

                              <div className="flex items-center gap-2 self-start sm:self-auto">
                                {renderApprovalBadge(item.approvalStatus, item.isOutOfOffice)}
                                <span className="text-[11px] font-bold bg-muted/60 text-foreground px-2 py-0.5 rounded-md">
                                  {getWorkingDuration(item.checkInTime, item.checkOutTime)}
                                </span>
                              </div>
                            </div>

                            {/* Grid with Check-in / Check-out info & GPS & Selfies */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-muted/20 border border-border/50 rounded-xl p-3">
                              {/* Check-In Details */}
                              <div className="space-y-1.5">
                                <div className="flex items-center justify-between">
                                  <span className="text-[10px] font-black uppercase text-muted-foreground tracking-wider">
                                    Clock In
                                  </span>
                                  <span className="font-extrabold text-foreground text-xs">
                                    {formatTimeStr(item.checkInTime)}
                                  </span>
                                </div>

                                {item.checkInLocationTag && (
                                  <div>
                                    {renderLocationBadge(item.checkInLocationTag, item.checkInDistanceMeters, item.checkInPlaceName, item.checkInAccuracyMeters)}
                                  </div>
                                )}

                                {item.checkInLatitude && item.checkInLongitude ? (
                                  <a
                                    href={`https://www.google.com/maps?q=${encodeURIComponent(`${item.checkInLatitude},${item.checkInLongitude}`)}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-sky-600 dark:text-sky-400 hover:underline"
                                    title="Open check-in coordinates in Google Maps"
                                  >
                                    <MapPin className="h-3 w-3 text-sky-500 shrink-0" />
                                    <span>{item.checkInLatitude.substring(0, 8)}, {item.checkInLongitude.substring(0, 8)}</span>
                                    <ExternalLink className="h-2.5 w-2.5 opacity-70" />
                                  </a>
                                ) : (
                                  <span className="text-[10px] text-muted-foreground/60 italic block">No GPS coordinates</span>
                                )}

                                {item.checkInPhotoUrl && (
                                  <div className="pt-0.5">
                                    <button
                                      type="button"
                                      onClick={() => setPreviewPhotoUrl(item.checkInPhotoUrl || null)}
                                      className="inline-flex items-center gap-1 text-[10px] font-semibold text-sky-600 bg-sky-500/10 px-2 py-0.5 rounded-md hover:bg-sky-500/20 transition-colors cursor-pointer"
                                    >
                                      <Camera className="h-3 w-3" /> View Punch-In Selfie
                                    </button>
                                  </div>
                                )}

                                {item.checkInComments && (
                                  <p className="text-[10px] italic text-muted-foreground bg-muted/40 p-1.5 rounded border border-border/40">
                                    &quot;{item.checkInComments}&quot;
                                  </p>
                                )}
                              </div>

                              {/* Check-Out Details */}
                              <div className="space-y-1.5 md:border-l md:border-border/60 md:pl-3">
                                <div className="flex items-center justify-between">
                                  <span className="text-[10px] font-black uppercase text-muted-foreground tracking-wider">
                                    Clock Out
                                  </span>
                                  <div className="flex items-center gap-1">
                                    <span className="font-extrabold text-foreground text-xs">
                                      {item.checkOutTime ? formatTimeStr(item.checkOutTime) : '--:--'}
                                    </span>
                                    {item.isAutoPunchOut && (
                                      <span className="text-[9px] font-bold text-amber-600 bg-amber-500/10 border border-amber-500/20 py-0.2 px-1 rounded-full" title={item.checkOutComments || "Auto Punch-Out"}>
                                        ⚡ Auto
                                      </span>
                                    )}
                                  </div>
                                </div>

                                {item.checkOutLocationTag && (
                                  <div>
                                    {renderLocationBadge(item.checkOutLocationTag, item.checkOutDistanceMeters, item.checkOutPlaceName, item.checkOutAccuracyMeters)}
                                  </div>
                                )}

                                {item.checkOutLatitude && item.checkOutLongitude ? (
                                  <a
                                    href={`https://www.google.com/maps?q=${encodeURIComponent(`${item.checkOutLatitude},${item.checkOutLongitude}`)}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 hover:underline"
                                    title="Open check-out coordinates in Google Maps"
                                  >
                                    <MapPin className="h-3 w-3 text-emerald-500 shrink-0" />
                                    <span>{item.checkOutLatitude.substring(0, 8)}, {item.checkOutLongitude.substring(0, 8)}</span>
                                    <ExternalLink className="h-2.5 w-2.5 opacity-70" />
                                  </a>
                                ) : item.isAutoPunchOut ? (
                                  <span className="text-[10px] text-amber-600/90 font-medium italic block">System Auto Cutoff</span>
                                ) : item.checkOutTime ? (
                                  <span className="text-[10px] text-muted-foreground/60 italic block">No GPS coordinates</span>
                                ) : (
                                  <span className="text-[10px] text-sky-600 font-semibold italic block">Shift currently in progress</span>
                                )}

                                {item.checkOutPhotoUrl && (
                                  <div className="pt-0.5">
                                    <button
                                      type="button"
                                      onClick={() => setPreviewPhotoUrl(item.checkOutPhotoUrl || null)}
                                      className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-md hover:bg-emerald-500/20 transition-colors cursor-pointer"
                                    >
                                      <Camera className="h-3 w-3" /> View Punch-Out Selfie
                                    </button>
                                  </div>
                                )}

                                {item.checkOutComments && (
                                  <p className="text-[10px] italic text-muted-foreground bg-muted/40 p-1.5 rounded border border-border/40">
                                    &quot;{item.checkOutComments}&quot;
                                  </p>
                                )}
                              </div>
                            </div>

                            {/* Audit Info or Action Buttons */}
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-border/50 text-xs">
                              <div className="text-[11px] text-muted-foreground">
                                {item.approvalStatus === 'approved' && item.approvedAt && (
                                  <span>
                                    Approved by <span className="font-bold text-foreground">{item.approvedByUsername || 'Admin'}</span> on {formatDate(item.approvedAt.split('T')[0])} at {formatTimeStr(item.approvedAt)}
                                  </span>
                                )}
                                {item.approvalStatus === 'rejected' && (
                                  <span className="text-rose-600 dark:text-rose-400 font-medium">
                                    Rejected: {item.rejectionReason || "No reason specified"}
                                  </span>
                                )}
                                {item.approvalStatus === 'pending' && (
                                  <span className="text-amber-600 dark:text-amber-400 font-semibold flex items-center gap-1">
                                    <AlertTriangle className="h-3 w-3 shrink-0" />
                                    <span>Punch was made outside office geofence boundary. Requires decision.</span>
                                  </span>
                                )}
                              </div>

                              <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                                {isPending ? (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => handleApproveAttendance(item.id)}
                                      disabled={actionProcessingId === item.id}
                                      className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold shadow-2xs cursor-pointer inline-flex items-center gap-1.5 transition-colors"
                                    >
                                      {actionProcessingId === item.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                                      <span>Approve</span>
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleOpenRejectModal(item)}
                                      disabled={actionProcessingId === item.id}
                                      className="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold shadow-2xs cursor-pointer inline-flex items-center gap-1.5 transition-colors"
                                    >
                                      <XCircle className="h-3.5 w-3.5" />
                                      <span>Reject</span>
                                    </button>
                                  </>
                                ) : item.approvalStatus === 'rejected' ? (
                                  <button
                                    type="button"
                                    onClick={() => handleApproveAttendance(item.id)}
                                    disabled={actionProcessingId === item.id}
                                    className="px-3 py-1 bg-emerald-600/10 hover:bg-emerald-600 text-emerald-700 hover:text-white border border-emerald-500/30 rounded-xl text-xs font-bold cursor-pointer inline-flex items-center gap-1 transition-colors"
                                  >
                                    {actionProcessingId === item.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                                    <span>Re-Approve</span>
                                  </button>
                                ) : null}
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )
                })()}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Location Trail & Breadcrumbs Modal */}
      {trailModalOpen && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setTrailModalOpen(false)}
        >
          <div 
            className="bg-card border border-border rounded-3xl p-5 sm:p-6 shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col space-y-4 animate-in zoom-in-95 duration-200 relative overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border/70 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="h-9 w-9 rounded-2xl bg-sky-500/15 border border-sky-500/30 flex items-center justify-center text-sky-600 dark:text-sky-400">
                  <Route className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-sm sm:text-base text-foreground leading-tight">
                    {trailEmployeeTitle || "Movement Route"}
                  </h3>
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground mt-0.5">
                    <span className="inline-flex items-center gap-1 text-emerald-600 font-semibold">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      1-Meter Accuracy Tracking
                    </span>
                    <span>•</span>
                    <span>Background Geolocation</span>
                  </div>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => setTrailModalOpen(false)}
                className="text-muted-foreground hover:text-foreground p-1.5 rounded-xl hover:bg-muted transition-colors cursor-pointer"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            {/* Content Body */}
            {loadingTrail ? (
              <div className="py-16 flex flex-col items-center justify-center gap-3 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin text-sky-500" />
                <p className="text-xs font-semibold">Loading continuous movement route & GPS trail...</p>
              </div>
            ) : !trailData || trailData.trail.length === 0 ? (
              <div className="py-12 px-4 text-center space-y-3">
                <div className="h-12 w-12 rounded-full bg-muted/60 text-muted-foreground flex items-center justify-center mx-auto">
                  <Footprints className="h-6 w-6 opacity-60" />
                </div>
                <div className="space-y-1">
                  <h4 className="font-bold text-sm text-foreground">No Movement Checkpoints Yet</h4>
                  <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                    As the employee moves with their device (threshold: 1 meter), real-time background GPS pings will record their path chronologically here.
                  </p>
                </div>
                {trailData?.lastKnownPlace && (
                  <div className="p-3 bg-muted/30 border border-border/50 rounded-xl text-xs inline-flex items-center gap-2">
                    <MapPin className="h-3.5 w-3.5 text-sky-500 shrink-0" />
                    <span className="font-semibold text-foreground">Last Recorded Location:</span>
                    <span className="text-muted-foreground">{trailData.lastKnownPlace}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="min-h-0 flex-1 overflow-y-auto space-y-4 pr-1">
                {/* Interactive Leaflet Route Map & JSON Trail Viewer */}
                <div className="rounded-2xl overflow-hidden border border-border/70 shadow-sm">
                  <AttendanceTrailMap 
                    trail={trailData.trail}
                    isLive={!trailData.checkOutTime}
                    employeeName={trailData.employeeName}
                    checkInTime={trailData.checkInTime}
                    checkOutTime={trailData.checkOutTime}
                    totalDistanceMeters={trailData.totalDistanceMeters}
                    height="min(380px, 45dvh)"
                    rawJson={trailData.trailJson}
                  />
                </div>

                {/* Stats Summary Bar */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="bg-muted/40 border border-border/60 rounded-2xl p-3 text-center space-y-0.5">
                    <span className="text-[10px] uppercase font-black text-muted-foreground tracking-wider block">Checkpoints</span>
                    <span className="text-lg font-black text-foreground">{trailData.totalPoints}</span>
                  </div>
                  <div className="bg-sky-500/10 border border-sky-500/20 rounded-2xl p-3 text-center space-y-0.5">
                    <span className="text-[10px] uppercase font-black text-sky-600 dark:text-sky-400 tracking-wider block">Total Moved</span>
                    <span className="text-lg font-black text-sky-600 dark:text-sky-400">
                      {trailData.totalDistanceMeters >= 1000 
                        ? `${(trailData.totalDistanceMeters / 1000).toFixed(2)} km` 
                        : `${Math.round(trailData.totalDistanceMeters)} m`}
                    </span>
                  </div>
                  <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-3 text-center space-y-0.5">
                    <span className="text-[10px] uppercase font-black text-emerald-600 dark:text-emerald-400 tracking-wider block">Status</span>
                    <span className="text-xs font-black text-emerald-600 dark:text-emerald-400 truncate block">
                      {trailData.checkOutTime ? 'Shift Completed' : 'In Field (Active)'}
                    </span>
                  </div>
                </div>

                {/* Direct Google Maps Action Buttons */}
                <div className="flex items-center gap-2 flex-wrap">
                  {trailData.trail.length > 0 && (
                    <a
                      href={`https://www.google.com/maps/search/?api=1&query=${trailData.trail[trailData.trail.length - 1].latitude},${trailData.trail[trailData.trail.length - 1].longitude}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 py-2 px-3 bg-sky-600 hover:bg-sky-700 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-1.5 shadow-sm transition-all"
                    >
                      <MapPin className="h-3.5 w-3.5" />
                      <span>Open Latest Pin in Maps</span>
                      <ExternalLink className="h-3 w-3 opacity-80" />
                    </a>
                  )}
                  {trailData.trail.length > 1 && (
                    <a
                      href={`https://www.google.com/maps/dir/?api=1&origin=${trailData.trail[0].latitude},${trailData.trail[0].longitude}&destination=${trailData.trail[trailData.trail.length - 1].latitude},${trailData.trail[trailData.trail.length - 1].longitude}&travelmode=walking`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="py-2 px-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-1.5 shadow-sm transition-all"
                    >
                      <Navigation className="h-3.5 w-3.5" />
                      <span>Directions</span>
                      <ExternalLink className="h-3 w-3 opacity-80" />
                    </a>
                  )}
                </div>

                {/* Timeline List of Points */}
                <div className="space-y-2 pt-2">
                  <span className="text-[11px] font-black text-muted-foreground uppercase tracking-wider block">
                    Recorded Movement History (Chronological)
                  </span>

                  <div className="relative pl-5 border-l-2 border-sky-500/30 space-y-3 my-2">
                    {trailData.trail.map((point, idx) => {
                      const isFirst = idx === 0
                      const isLast = idx === trailData.trail.length - 1
                      return (
                        <div key={point.id} className="relative group">
                          {/* Node circle */}
                          <div className={cn(
                            "absolute -left-[27px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-card flex items-center justify-center transition-transform group-hover:scale-125",
                            isLast ? "bg-emerald-500 ring-4 ring-emerald-500/20" : isFirst ? "bg-sky-500" : "bg-muted-foreground/60"
                          )} />

                          <div className="p-3 bg-card border border-border/70 hover:border-sky-500/40 rounded-2xl shadow-2xs space-y-1 transition-all">
                            <div className="flex items-center justify-between gap-2 flex-wrap">
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-bold text-xs text-foreground">
                                  {formatTimeStr(point.recordedAt)}
                                </span>
                                {isFirst && (
                                  <span className="text-[9px] font-bold bg-sky-500/15 text-sky-600 border border-sky-500/20 px-1.5 py-0.2 rounded-full">
                                    Start / Clock-In
                                  </span>
                                )}
                                {isLast && (
                                  <span className="text-[9px] font-bold bg-emerald-500/15 text-emerald-600 border border-emerald-500/20 px-1.5 py-0.2 rounded-full flex items-center gap-1">
                                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                    Latest Point
                                  </span>
                                )}
                              </div>

                              <div className="flex items-center gap-2">
                                {!isFirst && (
                                  <span className="text-[10px] font-bold text-sky-600 dark:text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded-md">
                                    +{point.distanceFromPrevMeters >= 1000 ? `${(point.distanceFromPrevMeters / 1000).toFixed(2)} km` : `${point.distanceFromPrevMeters} m`}
                                  </span>
                                )}
                                {point.accuracyMeters != null && (
                                  <span className="text-[9px] text-muted-foreground font-mono">
                                    ±{Math.round(point.accuracyMeters)}m
                                  </span>
                                )}
                              </div>
                            </div>

                            <div className="flex items-start justify-between gap-3 pt-0.5">
                              <p className="text-[11px] text-foreground font-medium flex items-center gap-1.5">
                                <MapPin className="h-3 w-3 text-sky-500 shrink-0 mt-0.5" />
                                <span>{point.placeName || `${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)}`}</span>
                              </p>
                              
                              <a
                                href={point.mapsUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="shrink-0 text-[10px] font-bold text-sky-600 hover:text-sky-700 hover:underline flex items-center gap-1"
                              >
                                <span>Pin</span>
                                <ExternalLink className="h-2.5 w-2.5 opacity-70" />
                              </a>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            )}

            <button
              type="button"
              onClick={() => setTrailModalOpen(false)}
              className="w-full py-2.5 bg-muted/60 hover:bg-muted text-foreground font-bold rounded-xl text-xs transition-colors cursor-pointer mt-1"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Selfie Preview Modal */}
      {previewPhotoUrl && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setPreviewPhotoUrl(null)}
        >
          <div 
            className="bg-card border border-border rounded-3xl p-4 shadow-2xl max-w-sm w-full space-y-4 animate-in zoom-in-95 duration-200 relative overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2">
                <Camera className="h-4 w-4 text-sky-500" />
                <h3 className="font-extrabold text-sm text-foreground">Selfie Verification</h3>
              </div>
              <button 
                type="button"
                onClick={() => setPreviewPhotoUrl(null)}
                className="text-muted-foreground hover:text-foreground p-1 rounded-lg hover:bg-muted transition-colors cursor-pointer"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            <div className="rounded-2xl overflow-hidden border border-border bg-black/10 flex items-center justify-center max-h-[60vh]">
              <img 
                src={previewPhotoUrl} 
                alt="Verification selfie" 
                className="w-full max-h-[60vh] object-contain rounded-2xl" 
              />
            </div>

            <button
              type="button"
              onClick={() => setPreviewPhotoUrl(null)}
              className="w-full py-2.5 bg-muted/60 hover:bg-muted text-foreground font-semibold rounded-xl text-xs transition-colors cursor-pointer"
            >
              Close Preview
            </button>
          </div>
        </div>
      )}

      {/* Photo Required Error Popup Modal */}
      {showPhotoRequiredModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/65 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-card border border-border/80 rounded-3xl p-6 shadow-2xl max-w-sm w-full space-y-5 animate-in zoom-in-95 duration-200 relative overflow-hidden">
            {/* Top accent glow */}
            <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-rose-500 via-amber-500 to-rose-500" />
            
            <div className="flex items-start gap-4">
              <div className="h-12 w-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-500 shrink-0 shadow-inner">
                <Camera className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <h3 className="font-extrabold text-base text-foreground tracking-tight">Photo Required</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  You cannot {photoRequiredAction === 'out' ? 'punch out' : 'punch in'} without taking a selfie verification photo.
                </p>
              </div>
            </div>

            <div className="p-3.5 bg-amber-500/10 border border-amber-500/25 rounded-2xl flex items-center gap-3 text-xs text-amber-800 dark:text-amber-300 font-medium">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
              <span>Stamps your live GPS address and timestamp for proof of attendance.</span>
            </div>

            <div className="flex flex-col gap-2 pt-1">
              <button
                type="button"
                onClick={() => {
                  setShowPhotoRequiredModal(false)
                  setTimeout(() => {
                    fileInputRef.current?.click()
                  }, 120)
                }}
                className="w-full py-3 bg-rose-500 hover:bg-rose-600 active:scale-[0.98] text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 transition-all shadow-md cursor-pointer"
              >
                <Camera className="h-4 w-4" />
                Take Selfie Now
              </button>
              <button
                type="button"
                onClick={() => setShowPhotoRequiredModal(false)}
                className="w-full py-2.5 bg-muted/60 hover:bg-muted text-muted-foreground hover:text-foreground font-semibold rounded-xl text-xs transition-colors cursor-pointer"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Selected Muster Roll Cell Detail Inspection Modal */}
      {selectedMusterCell && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setSelectedMusterCell(null)}
        >
          <div 
            className="bg-card border border-border rounded-3xl p-5 shadow-2xl max-w-sm w-full space-y-4 animate-in zoom-in-95 duration-200 relative overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h3 className="font-extrabold text-sm text-foreground">{selectedMusterCell.employee.username}</h3>
                <p className="text-[10px] text-muted-foreground">
                  {selectedMusterCell.day.weekday}, {selectedMusterCell.day.date}
                </p>
              </div>
              <button 
                type="button"
                onClick={() => setSelectedMusterCell(null)}
                className="text-muted-foreground hover:text-foreground p-1 rounded-lg hover:bg-muted transition-colors cursor-pointer"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            {/* Status Pill Banner */}
            <div className="flex items-center justify-between p-3 rounded-2xl bg-muted/40 border border-border">
              <span className="text-xs font-semibold text-muted-foreground">Daily Status:</span>
              <span className={cn(
                "px-2.5 py-1 rounded-full text-xs font-black uppercase flex items-center gap-1.5",
                selectedMusterCell.attendance.status === 'P' && "bg-emerald-500/15 text-emerald-600 border border-emerald-500/30",
                selectedMusterCell.attendance.status === 'HD' && "bg-amber-500/15 text-amber-600 border border-amber-500/30",
                selectedMusterCell.attendance.status === 'A' && "bg-rose-500/15 text-rose-600 border border-rose-500/30",
                selectedMusterCell.attendance.status === 'WO' && "bg-muted text-muted-foreground border border-border"
              )}>
                {selectedMusterCell.attendance.status === 'P' ? '✓ Present' :
                 selectedMusterCell.attendance.status === 'HD' ? '⚡ Half Day' :
                 selectedMusterCell.attendance.status === 'A' ? '✗ Absent' : '🌴 Sunday Off'}
              </span>
            </div>

            {/* Time / Location details */}
            <div className="space-y-2.5 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div className="p-3 bg-muted/20 border border-border/60 rounded-xl space-y-1">
                  <span className="text-[10px] uppercase font-bold text-muted-foreground block">Clock In</span>
                  <div className="font-bold text-foreground text-xs">
                    {selectedMusterCell.attendance.checkIn || '--:--'}
                  </div>
                  {selectedMusterCell.attendance.locationTag && (
                    <div className="pt-0.5">
                      {renderLocationBadge(selectedMusterCell.attendance.locationTag)}
                    </div>
                  )}
                </div>

                <div className="p-3 bg-muted/20 border border-border/60 rounded-xl space-y-1">
                  <span className="text-[10px] uppercase font-bold text-muted-foreground block">Clock Out</span>
                  <div className="font-bold text-foreground text-xs">
                    {selectedMusterCell.attendance.checkOut || '--:--'}
                  </div>
                  {selectedMusterCell.attendance.isAutoPunchOut && (
                    <span className="inline-block text-[9px] font-bold text-amber-600 bg-amber-500/10 px-1.5 py-0.5 rounded">
                      ⚡ Auto Punch
                    </span>
                  )}
                </div>
              </div>

              <div className="p-3 bg-muted/20 border border-border/60 rounded-xl flex items-center justify-between">
                <span className="text-muted-foreground font-semibold">Total Logged:</span>
                <span className="font-black text-sm text-foreground">
                  {selectedMusterCell.attendance.hours > 0 
                    ? `${selectedMusterCell.attendance.hours} hrs` 
                    : selectedMusterCell.attendance.checkIn && !selectedMusterCell.attendance.checkOut 
                      ? 'In Progress' 
                      : '--'}
                </span>
              </div>

              {/* Approval status in muster cell */}
              {selectedMusterCell.attendance.approvalStatus && (
                <div className="p-3 bg-muted/20 border border-border/60 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-muted-foreground">Approval Status</span>
                    {renderApprovalBadge(selectedMusterCell.attendance.approvalStatus, selectedMusterCell.attendance.isOutOfOffice)}
                  </div>
                  {selectedMusterCell.attendance.approvalStatus === 'rejected' && selectedMusterCell.attendance.rejectionReason && (
                    <p className="text-[11px] text-rose-600 dark:text-rose-400 font-medium">
                      Reason: {selectedMusterCell.attendance.rejectionReason}
                    </p>
                  )}
                  {selectedMusterCell.attendance.approvalStatus === 'pending' && user?.permissions?.isAdmin && selectedMusterCell.attendance.attendanceId && (
                    <div className="pt-1.5 flex items-center justify-between gap-2 border-t border-border/40">
                      <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400">Needs Approval</span>
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={async () => {
                            if (selectedMusterCell.attendance.attendanceId) {
                              await handleApproveAttendance(selectedMusterCell.attendance.attendanceId)
                              setSelectedMusterCell(null)
                              fetchMusterRoll(musterYear, musterMonth)
                            }
                          }}
                          disabled={actionProcessingId === selectedMusterCell.attendance.attendanceId}
                          className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-[10px] font-bold shadow-2xs cursor-pointer inline-flex items-center gap-1 disabled:opacity-50"
                        >
                          {actionProcessingId === selectedMusterCell.attendance.attendanceId ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
                          <span>Approve</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (selectedMusterCell.attendance.attendanceId) {
                              setRejectingRecord({
                                id: selectedMusterCell.attendance.attendanceId,
                                userId: selectedMusterCell.employee.userId,
                                username: selectedMusterCell.employee.username,
                                checkInTime: `${musterYear}-${String(musterMonth).padStart(2, '0')}-${String(selectedMusterCell.day.day).padStart(2, '0')}T00:00:00`,
                                checkOutTime: null,
                                checkInLatitude: null,
                                checkInLongitude: null,
                                checkOutLatitude: null,
                                checkOutLongitude: null,
                                checkInPhotoUrl: null,
                                checkOutPhotoUrl: null,
                                checkInComments: null,
                                checkOutComments: null,
                                checkInIpAddress: null,
                                checkOutIpAddress: null
                              })
                              setSelectedMusterCell(null)
                            }
                          }}
                          disabled={actionProcessingId === selectedMusterCell.attendance.attendanceId}
                          className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-[10px] font-bold shadow-2xs cursor-pointer inline-flex items-center gap-1 disabled:opacity-50"
                        >
                          <XCircle className="h-3 w-3" />
                          <span>Reject</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {selectedMusterCell.attendance.photoUrl && (
                <div className="space-y-1 pt-1">
                  <span className="text-[10px] uppercase font-bold text-muted-foreground">Selfie Verification</span>
                  <div 
                    onClick={() => setPreviewPhotoUrl(selectedMusterCell.attendance.photoUrl || null)}
                    className="relative rounded-xl overflow-hidden border border-border group cursor-pointer h-28 bg-black/10"
                  >
                    <img 
                      src={selectedMusterCell.attendance.photoUrl} 
                      alt="Verification selfie" 
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform" 
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity text-white text-xs font-bold gap-1">
                      <Camera className="h-4 w-4" /> Tap to Enlarge
                    </div>
                  </div>
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => setSelectedMusterCell(null)}
              className="w-full py-2.5 bg-muted/60 hover:bg-muted text-foreground font-semibold rounded-xl text-xs transition-colors cursor-pointer"
            >
              Close Details
            </button>
          </div>
        </div>
      )}

      {/* Office Geofence Configuration Modal */}
      {showOfficeModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setShowOfficeModal(false)}
        >
          <div 
            className="bg-card border border-border rounded-3xl p-5 shadow-2xl max-w-md w-full space-y-4 animate-in zoom-in-95 duration-200 relative overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2">
                <Building className="h-4 w-4 text-sky-500" />
                <h3 className="font-extrabold text-sm text-foreground">
                  {editingOffice ? "Edit Office Geofence" : "New Office Geofence"}
                </h3>
              </div>
              <button 
                type="button"
                onClick={() => setShowOfficeModal(false)}
                className="text-muted-foreground hover:text-foreground p-1 rounded-lg hover:bg-muted transition-colors cursor-pointer"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3.5 text-xs">
              <div>
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide">Office / Branch Name *</label>
                <input 
                  type="text"
                  placeholder="e.g. Headquarters - Mumbai or North Hub"
                  value={officeForm.name}
                  onChange={e => setOfficeForm(prev => ({ ...prev, name: e.target.value }))}
                  className="mt-1 w-full px-3.5 py-2 bg-muted/40 border border-border rounded-xl text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-sky-500 h-9"
                />
              </div>

              <div>
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide">Physical Address</label>
                <input 
                  type="text"
                  placeholder="e.g. Plot 12, Tech Park, Andheri East"
                  value={officeForm.address}
                  onChange={e => setOfficeForm(prev => ({ ...prev, address: e.target.value }))}
                  className="mt-1 w-full px-3.5 py-2 bg-muted/40 border border-border rounded-xl text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-sky-500 h-9"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide">GPS Coordinates *</label>
                  <button
                    type="button"
                    onClick={handleUseCurrentLocationForOffice}
                    disabled={locatingUser}
                    className="inline-flex items-center gap-1 text-[10px] font-bold text-sky-600 hover:text-sky-700 bg-sky-500/10 hover:bg-sky-500/20 px-2.5 py-0.5 rounded cursor-pointer transition-colors disabled:opacity-50"
                  >
                    {locatingUser ? <Loader2 className="h-3 w-3 animate-spin" /> : <Navigation className="h-3 w-3" />}
                    <span>Use Current GPS</span>
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <input 
                      type="text"
                      placeholder="Latitude (e.g. 19.0760)"
                      value={officeForm.latitude}
                      onChange={e => setOfficeForm(prev => ({ ...prev, latitude: e.target.value }))}
                      className="w-full px-3 py-1.5 bg-muted/40 border border-border rounded-xl text-xs font-mono font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-sky-500"
                    />
                  </div>
                  <div>
                    <input 
                      type="text"
                      placeholder="Longitude (e.g. 72.8777)"
                      value={officeForm.longitude}
                      onChange={e => setOfficeForm(prev => ({ ...prev, longitude: e.target.value }))}
                      className="w-full px-3 py-1.5 bg-muted/40 border border-border rounded-xl text-xs font-mono font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-sky-500"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide">Geofence Radius</label>
                  <span className="text-xs font-black text-sky-600 dark:text-sky-400 font-mono">{officeForm.radiusMeters} meters</span>
                </div>
                <input 
                  type="range"
                  min={50}
                  max={1000}
                  step={25}
                  value={officeForm.radiusMeters}
                  onChange={e => setOfficeForm(prev => ({ ...prev, radiusMeters: parseInt(e.target.value) || 200 }))}
                  className="w-full accent-sky-500 cursor-pointer"
                />
                <div className="flex justify-between text-[9px] text-muted-foreground font-mono">
                  <span>50m (Strict)</span>
                  <span>200m (Standard)</span>
                  <span>500m</span>
                  <span>1000m (Campus)</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => setShowOfficeModal(false)}
                className="px-3.5 py-2 bg-muted hover:bg-muted/80 text-foreground font-semibold rounded-xl text-xs transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveOffice}
                className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white font-bold rounded-xl text-xs transition-colors shadow-sm cursor-pointer"
              >
                {editingOffice ? "Update Geofence" : "Save Geofence"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rejection Reason Modal */}
      {rejectingRecord && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => {
            if (!actionProcessingId) {
              setRejectingRecord(null)
              setRejectionReasonInput('')
            }
          }}
        >
          <div 
            className="bg-card border border-border rounded-3xl p-5 shadow-2xl max-w-md w-full space-y-4 animate-in zoom-in-95 duration-200"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2">
                <XCircle className="h-5 w-5 text-rose-500" />
                <h3 className="font-extrabold text-sm text-foreground">
                  Reject Out-of-Office Attendance
                </h3>
              </div>
              <button 
                type="button"
                onClick={() => {
                  setRejectingRecord(null)
                  setRejectionReasonInput('')
                }}
                disabled={!!actionProcessingId}
                className="text-muted-foreground hover:text-foreground p-1 rounded-lg hover:bg-muted transition-colors cursor-pointer"
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-muted-foreground">
                You are rejecting the out-of-office attendance for <span className="font-bold text-foreground">{rejectingRecord.username || `User #${rejectingRecord.userId}`}</span> on <span className="font-bold text-foreground">{formatDate(rejectingRecord.checkInTime.split('T')[0])}</span>. This day will be marked as Absent.
              </p>

              <div>
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wide block mb-1">
                  Rejection Reason *
                </label>
                <textarea
                  rows={3}
                  placeholder="Specify why this out-of-office punch is rejected (e.g., Unapproved client visit, Invalid location)..."
                  value={rejectionReasonInput}
                  onChange={e => setRejectionReasonInput(e.target.value)}
                  className="w-full px-3 py-2 bg-muted/40 border border-border rounded-xl text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-rose-500 resize-none font-medium"
                />
              </div>

              {/* Quick Preset Buttons */}
              <div className="space-y-1">
                <span className="text-[10px] text-muted-foreground font-semibold">Quick Reasons:</span>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    "Unapproved field work",
                    "Location verification mismatch",
                    "Selfie verification failed",
                    "Did not inform manager in advance"
                  ].map(reason => (
                    <button
                      key={reason}
                      type="button"
                      onClick={() => setRejectionReasonInput(reason)}
                      className="px-2 py-0.5 rounded-md text-[10px] bg-muted hover:bg-muted/80 border border-border text-foreground transition-colors cursor-pointer"
                    >
                      {reason}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => {
                  setRejectingRecord(null)
                  setRejectionReasonInput('')
                }}
                disabled={!!actionProcessingId}
                className="px-3.5 py-2 bg-muted hover:bg-muted/80 text-foreground font-semibold rounded-xl text-xs transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmReject}
                disabled={!rejectionReasonInput.trim() || !!actionProcessingId}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white font-bold rounded-xl text-xs transition-colors shadow-sm cursor-pointer inline-flex items-center gap-1.5"
              >
                {actionProcessingId ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <XCircle className="h-3.5 w-3.5" />}
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
