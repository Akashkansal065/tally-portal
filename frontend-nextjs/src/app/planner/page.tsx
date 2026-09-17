'use client'

import { useState, useEffect, useMemo } from 'react'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, cn } from '@/lib/utils'
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  MapPin,
  Navigation,
  Phone,
  MessageCircle,
  Plus,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
  RefreshCw,
  Share2,
  ShoppingCart,
  IndianRupee,
  Users,
  Route,
  Store,
  Sparkles,
  AlertCircle,
  X,
  FileSpreadsheet,
  Compass,
  ArrowRight,
  Check,
  Building,
  CalendarCheck,
  History
} from 'lucide-react'

interface BeatStop {
  id: number
  customer_key?: string
  customer_id?: number | null
  customer_profile_id?: number | null
  ledger_id: number | null
  customer_name?: string
  shop_name?: string
  contact_person?: string | null
  phone?: string | null
  whatsapp_number?: string | null
  address?: string | null
  locality?: string | null
  latitude: number | null
  longitude: number | null
  maps_url?: string | null
  stop_sequence?: number
  sequence_order?: number
  status: 'pending' | 'visited' | 'skipped'
  visited_at: string | null
  visit_id: number | null
  skip_reason: string | null
  notes: string | null
}

interface BeatPlanItem {
  id: number
  user_id: number
  salesperson_name?: string
  user?: { username: string; name?: string }
  plan_date: string
  name?: string
  route_name: string | null
  locality: string | null
  notes: string | null
  total_stops: number
  visited_stops: number
  skipped_stops: number
  pending_stops: number
  completion_percentage?: number
  completion_rate?: number
  status: 'draft' | 'assigned' | 'in_progress' | 'completed' | 'cancelled'
  stops: BeatStop[]
}

interface PlannerRoutesData {
  routes: { route_name: string; customer_count: number; gps_tagged_count?: number }[]
  localities: string[]
  salespersons: { user_id: number; username: string; email: string; role: string; name?: string }[]
}

interface EODSummary {
  date: string
  salesperson: any
  beat?: {
    total_planned: number
    visited_count: number
    skipped_count: number
    pending_count: number
    completion_rate: number
  }
  visits?: {
    count: number
  }
  orders?: {
    count: number
    total_amount: number
  }
  payments?: {
    count: number
    total_amount: number
    by_mode?: {
      cash: number
      upi: number
      cheque: number
      bank: number
    }
  }
  // Optional flat properties
  planned_stops?: number
  visited_stops?: number
  skipped_stops?: number
  completion_percentage?: number
  total_checkins?: number
  orders_count?: number
  total_order_value?: number
  payments_count?: number
  total_collected_value?: number
  collections_by_mode?: {
    cash: number
    upi: number
    cheque: number
    bank: number
  }
}

export default function DailyBeatPlannerPage() {
  const { user, token, permissions } = useAuth()
  const isAdmin = Boolean(
    permissions?.isAdmin ||
    user?.role?.toLowerCase() === 'admin' ||
    user?.role?.toLowerCase() === 'superadmin' ||
    user?.role?.toLowerCase() === 'owner'
  )

  // Date selection state (YYYY-MM-DD)
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    const today = new Date()
    return today.toISOString().split('T')[0]
  })

  // Selected Salesperson filter (admin can filter)
  const [selectedUserId, setSelectedUserId] = useState<string>('')

  // Data states
  const [plans, setPlans] = useState<BeatPlanItem[]>([])
  const [routesData, setRoutesData] = useState<PlannerRoutesData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [toastMsg, setToastMsg] = useState<string | null>(null)

  // Modals
  const [showAssignModal, setShowAssignModal] = useState(false)
  const [showSkipModal, setShowSkipModal] = useState(false)
  const [selectedStopForSkip, setSelectedStopForSkip] = useState<BeatStop | null>(null)
  const [skipReason, setSkipReason] = useState('Shop Closed')
  const [skipNotes, setSkipNotes] = useState('')
  const [savingStopStatus, setSavingStopStatus] = useState(false)

  // EOD Summary Modal
  const [showEODModal, setShowEODModal] = useState(false)
  const [eodSummary, setEodSummary] = useState<EODSummary | null>(null)
  const [loadingEOD, setLoadingEOD] = useState(false)

  // Assign Form
  const [assignForm, setAssignForm] = useState({
    user_id: '',
    plan_date: '',
    name: '',
    route_name: '',
    locality: '',
    notes: '',
    auto_optimize: true,
  })
  const [assigning, setAssigning] = useState(false)

  // Toast Helper
  const showToast = (msg: string) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(null), 4000)
  }

  // Fetch Routes & Salespersons (For Assignment Modal)
  const fetchRoutes = async () => {
    if (!token) return
    try {
      const res = await fetch(`${API_BASE}/planner/routes`, {
        headers: authHeaders(token),
      })
      if (res.ok) {
        const data = await res.json()
        setRoutesData(data)
      }
    } catch (err) {
      console.error('Failed to fetch routes data', err)
    }
  }

  // Fetch Daily Beat Plans
  const fetchPlans = async (isRefresh = false) => {
    if (!token) return
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setErrorMsg(null)

    try {
      let url = `${API_BASE}/planner/daily?plan_date=${selectedDate}`
      if (selectedUserId) {
        url += `&user_id=${selectedUserId}`
      }

      const res = await fetch(url, {
        headers: authHeaders(token),
      })

      if (res.ok) {
        const data = await res.json()
        const rawPlans = Array.isArray(data) ? data : (data.plans || [])
        setPlans(rawPlans)
      } else {
        const err = await res.json()
        setErrorMsg(err.detail || 'Failed to load beat plans.')
      }
    } catch (err) {
      setErrorMsg('Network error connecting to beat planner service.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchRoutes()
  }, [token])

  useEffect(() => {
    fetchPlans()
  }, [selectedDate, selectedUserId, token])

  // Change Date helper
  const handleStepDate = (days: number) => {
    const current = new Date(selectedDate)
    current.setDate(current.getDate() + days)
    setSelectedDate(current.toISOString().split('T')[0])
  }

  // Mark Stop Visited or Skipped
  const handleUpdateStopStatus = async (
    stopId: number,
    status: 'visited' | 'skipped',
    reason?: string,
    notes?: string
  ) => {
    if (!token) return
    setSavingStopStatus(true)
    try {
      const res = await fetch(`${API_BASE}/planner/stops/${stopId}/status`, {
        method: 'PATCH',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          status,
          skip_reason: reason || null,
          notes: notes || null,
        }),
      })

      if (res.ok) {
        showToast(status === 'visited' ? 'Stop marked as visited!' : 'Stop marked as skipped.')
        setShowSkipModal(false)
        setSelectedStopForSkip(null)
        setSkipNotes('')
        fetchPlans(true)
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to update stop status.')
      }
    } catch (err) {
      alert('Network error while updating stop status.')
    } finally {
      setSavingStopStatus(false)
    }
  }

  // Handle Create Beat Plan Assignment
  const handleAssignBeat = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    if (!assignForm.user_id) {
      alert('Please select a salesperson.')
      return
    }
    if (!assignForm.route_name && !assignForm.locality) {
      alert('Please select either a Route or a Locality.')
      return
    }

    setAssigning(true)
    try {
      const res = await fetch(`${API_BASE}/planner/assign`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: parseInt(assignForm.user_id),
          plan_date: assignForm.plan_date || selectedDate,
          name: assignForm.name || `${assignForm.route_name || assignForm.locality} Beat`,
          route_name: assignForm.route_name || null,
          locality: assignForm.locality || null,
          notes: assignForm.notes || null,
          auto_optimize: assignForm.auto_optimize,
        }),
      })

      if (res.ok) {
        const data = await res.json()
        showToast(`Beat assigned successfully with ${data.total_stops} sequenced stops!`)
        setShowAssignModal(false)
        fetchPlans(true)
      } else {
        const err = await res.json()
        alert(err.detail || 'Failed to assign beat plan.')
      }
    } catch (err) {
      alert('Network error while creating beat assignment.')
    } finally {
      setAssigning(false)
    }
  }

  // Fetch End-of-Day Scorecard
  const handleOpenEODSummary = async (plan?: BeatPlanItem) => {
    if (!token) return
    setLoadingEOD(true)
    setShowEODModal(true)
    setEodSummary(null)

    const targetUserId = plan ? plan.user_id : (selectedUserId || (user?.id ? user.id.toString() : ''))

    try {
      let url = `${API_BASE}/planner/summary?plan_date=${selectedDate}`
      if (targetUserId) {
        url += `&user_id=${targetUserId}`
      }

      const res = await fetch(url, {
        headers: authHeaders(token),
      })

      if (res.ok) {
        const data = await res.json()
        setEodSummary(data)
      } else {
        const err = await res.json()
        alert(err.detail || 'Could not generate EOD summary.')
      }
    } catch (err) {
      alert('Failed to connect to summary service.')
    } finally {
      setLoadingEOD(false)
    }
  }

  // Share EOD Summary on WhatsApp
  const handleShareEODWhatsApp = () => {
    if (!eodSummary) return

    const repName = typeof eodSummary.salesperson === 'object' ? eodSummary.salesperson?.username : (eodSummary.salesperson || 'Salesperson')
    const plannedStops = eodSummary.beat?.total_planned ?? eodSummary.planned_stops ?? 0
    const visitedStops = eodSummary.beat?.visited_count ?? eodSummary.visited_stops ?? 0
    const skippedStops = eodSummary.beat?.skipped_count ?? eodSummary.skipped_stops ?? 0
    const completionPct = eodSummary.beat?.completion_rate ?? eodSummary.completion_percentage ?? 0
    const checkinCount = eodSummary.visits?.count ?? eodSummary.total_checkins ?? 0
    const ordersCount = eodSummary.orders?.count ?? eodSummary.orders_count ?? 0
    const orderValue = eodSummary.orders?.total_amount ?? eodSummary.total_order_value ?? 0
    const collectedValue = eodSummary.payments?.total_amount ?? eodSummary.total_collected_value ?? 0
    const cash = eodSummary.payments?.by_mode?.cash ?? eodSummary.collections_by_mode?.cash ?? 0
    const upi = eodSummary.payments?.by_mode?.upi ?? eodSummary.collections_by_mode?.upi ?? 0
    const cheque = eodSummary.payments?.by_mode?.cheque ?? eodSummary.collections_by_mode?.cheque ?? 0

    let text = `*📊 Daily Beat End-of-Day Summary*\n`
    text += `Date: *${new Date(eodSummary.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}*\n`
    text += `Salesperson: *${repName}*\n`
    text += `━━━━━━━━━━━━━━━━━━━━━\n`
    text += `🎯 *Beat Execution:*\n`
    text += `• Planned Stops: *${plannedStops}*\n`
    text += `• Visited: *${visitedStops}* (${completionPct}%)\n`
    text += `• Skipped: *${skippedStops}*\n`
    text += `• Check-Ins Logged: *${checkinCount}*\n`
    text += `━━━━━━━━━━━━━━━━━━━━━\n`
    text += `📦 *Sales Orders:* ${ordersCount} orders (₹${orderValue.toLocaleString('en-IN')})\n`
    text += `💰 *Collections:* ₹${collectedValue.toLocaleString('en-IN')}\n`
    text += `   Cash: ₹${cash.toLocaleString('en-IN')}\n`
    text += `   UPI: ₹${upi.toLocaleString('en-IN')}\n`
    text += `   Cheque: ₹${cheque.toLocaleString('en-IN')}\n`
    text += `━━━━━━━━━━━━━━━━━━━━━\n`
    text += `Generated automatically from MyTally Field Ops.`

    const url = `https://wa.me/?text=${encodeURIComponent(text)}`
    window.open(url, '_blank')
  }

  // Today label helper
  const isToday = useMemo(() => {
    const today = new Date().toISOString().split('T')[0]
    return selectedDate === today
  }, [selectedDate])

  return (
    <div className="min-h-screen bg-background text-foreground pb-24">
      {/* Toast Alert */}
      {toastMsg && (
        <div className="fixed top-20 right-4 z-50 bg-emerald-600 text-white px-4 py-3 rounded-2xl shadow-xl flex items-center gap-3 animate-in fade-in slide-in-from-top-4 duration-300">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm font-semibold">{toastMsg}</p>
        </div>
      )}

      {/* Top Controls Bar */}
      <div className="bg-card border-b border-border sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Breadcrumb / Title */}
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-primary/10 text-primary">
              <CalendarCheck className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-black tracking-tight text-foreground flex items-center gap-2">
                Salesperson Daily Planner
              </h1>
              <p className="text-xs text-muted-foreground">
                Optimized route beats, planned vs actual visits & live EOD scorecard
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 flex-wrap self-start sm:self-auto">
            {isAdmin && (
              <button
                onClick={() => {
                  setAssignForm({
                    user_id: routesData?.salespersons?.[0]?.user_id ? routesData.salespersons[0].user_id.toString() : '',
                    plan_date: selectedDate,
                    name: '',
                    route_name: routesData?.routes?.[0]?.route_name || '',
                    locality: '',
                    notes: '',
                    auto_optimize: true,
                  })
                  setShowAssignModal(true)
                }}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-primary text-primary-foreground font-bold text-xs hover:bg-primary/90 transition-colors shadow-sm"
              >
                <Plus className="w-4 h-4" />
                <span>Assign Beat</span>
              </button>
            )}

            <button
              onClick={() => handleOpenEODSummary()}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-border bg-background hover:bg-muted font-bold text-xs text-foreground transition-colors shadow-sm"
              title="Generate End-of-Day Scorecard"
            >
              <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
              <span>EOD Report</span>
            </button>

            <button
              onClick={() => fetchPlans(true)}
              disabled={refreshing}
              className="p-2 rounded-xl border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              title="Refresh planner"
            >
              <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin text-primary')} />
            </button>
          </div>
        </div>

        {/* Date Filter & Salesperson Dropdown Bar */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 border-t border-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          {/* Date Picker Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleStepDate(-1)}
              className="p-1.5 rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground"
              title="Previous Day"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="px-3 py-1.5 rounded-xl border border-border bg-background font-bold text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />

            <button
              onClick={() => handleStepDate(1)}
              className="p-1.5 rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground"
              title="Next Day"
            >
              <ChevronRight className="w-4 h-4" />
            </button>

            {!isToday && (
              <button
                onClick={() => {
                  const today = new Date().toISOString().split('T')[0]
                  setSelectedDate(today)
                }}
                className="px-2.5 py-1.5 rounded-lg bg-primary/10 text-primary font-bold hover:bg-primary/20 text-xs transition-colors"
              >
                Today
              </button>
            )}

            <span className="text-muted-foreground font-medium ml-1 hidden md:inline">
              {new Date(selectedDate).toLocaleDateString('en-IN', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </span>
          </div>

          {/* Salesperson Filter (Admin only) */}
          {isAdmin && routesData && (
            <div className="flex items-center gap-2 self-start sm:self-auto">
              <span className="text-muted-foreground font-medium">Salesperson:</span>
              <select
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="px-3 py-1.5 rounded-xl border border-border bg-background font-semibold text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="">All Salespersons ({routesData.salespersons.length})</option>
                {routesData.salespersons.map((s) => (
                  <option key={s.user_id} value={s.user_id.toString()}>
                    {s.name || s.username} ({s.role})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Field Ops Navigation Switch Tabs */}
        <div className="flex bg-muted/50 p-1 rounded-xl border border-border max-w-sm sm:max-w-md">
          <div className="flex-1 py-2 text-center text-xs font-bold rounded-lg bg-background text-foreground shadow-sm border border-border flex items-center justify-center gap-1.5">
            <CalendarCheck className="w-3.5 h-3.5 text-primary" />
            <span>Daily Planner</span>
          </div>
          <Link
            href="/check-in"
            className="flex-1 py-2 text-center text-xs font-bold rounded-lg text-muted-foreground hover:text-foreground transition-all flex items-center justify-center gap-1.5"
          >
            <MapPin className="w-3.5 h-3.5 text-rose-500" />
            <span>Check-In</span>
          </Link>
          <Link
            href="/check-in/history"
            className="flex-1 py-2 text-center text-xs font-bold rounded-lg text-muted-foreground hover:text-foreground transition-all flex items-center justify-center gap-1.5"
          >
            <History className="w-3.5 h-3.5" />
            <span>Visit History</span>
          </Link>
        </div>
        {loading ? (
          <div className="py-24 text-center space-y-3">
            <RefreshCw className="w-8 h-8 mx-auto text-primary animate-spin opacity-70" />
            <p className="text-xs font-semibold text-muted-foreground">Loading beat plans and stop sequences...</p>
          </div>
        ) : errorMsg ? (
          <div className="p-6 rounded-3xl bg-rose-500/10 border border-rose-500/20 text-rose-600 text-center space-y-2">
            <AlertCircle className="w-8 h-8 mx-auto" />
            <p className="font-bold text-sm">{errorMsg}</p>
          </div>
        ) : plans.length === 0 ? (
          <div className="py-20 text-center border-2 border-dashed border-border rounded-3xl p-8 space-y-4">
            <Route className="w-12 h-12 mx-auto text-muted-foreground opacity-30" />
            <div>
              <h3 className="text-base font-extrabold text-foreground">No Beat Plans for this Date</h3>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                {isAdmin
                  ? 'Click "Assign Beat" above to assign a route or locality to a salesperson with GPS auto-route sequence.'
                  : 'You have no assigned beat plan for this date. Check with your manager.'}
              </p>
            </div>

            {isAdmin && (
              <button
                onClick={() => {
                  setAssignForm({
                    user_id: routesData?.salespersons?.[0]?.user_id ? routesData.salespersons[0].user_id.toString() : '',
                    plan_date: selectedDate,
                    name: '',
                    route_name: routesData?.routes?.[0]?.route_name || '',
                    locality: '',
                    notes: '',
                    auto_optimize: true,
                  })
                  setShowAssignModal(true)
                }}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-primary-foreground font-bold text-xs hover:bg-primary/90 transition-colors shadow-sm"
              >
                <Plus className="w-4 h-4" />
                <span>Create Beat Plan Now</span>
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-8">
            {plans.map((plan) => {
              const planTitle = plan.name || `${plan.route_name || plan.locality || 'Daily'} Beat`
              const planCompletion = plan.completion_rate ?? plan.completion_percentage ?? 0
              return (
              <div
                key={plan.id}
                className="bg-card border border-border rounded-3xl p-6 sm:p-8 shadow-sm space-y-6 relative overflow-hidden"
              >
                {/* Header Glow Bar */}
                <div
                  className={cn(
                    'absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r',
                    planCompletion === 100
                      ? 'from-emerald-500 to-teal-500'
                      : 'from-primary via-indigo-500 to-purple-500'
                  )}
                />

                {/* Plan Header Card */}
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-border pb-5">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <h2 className="text-xl font-black text-foreground">{planTitle}</h2>
                      <span className={cn(
                        'px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider',
                        planCompletion === 100
                          ? 'bg-emerald-500/15 text-emerald-600'
                          : plan.visited_stops > 0
                          ? 'bg-blue-500/15 text-blue-600'
                          : 'bg-amber-500/15 text-amber-600'
                      )}>
                        {planCompletion === 100 ? 'Completed' : plan.visited_stops > 0 ? 'In Progress' : 'Pending'}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                      <span className="font-semibold text-foreground flex items-center gap-1">
                        <Users className="w-3.5 h-3.5 text-primary" />
                        {plan.salesperson_name}
                      </span>
                      {plan.route_name && (
                        <span>• Route: <strong className="text-foreground">{plan.route_name}</strong></span>
                      )}
                      {plan.locality && (
                        <span>• Locality: <strong className="text-foreground">{plan.locality}</strong></span>
                      )}
                    </div>
                  </div>

                  {/* Quick Action for Plan */}
                  <div className="flex items-center gap-2 self-start lg:self-auto">
                    <button
                      onClick={() => handleOpenEODSummary(plan)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-border bg-background hover:bg-muted font-semibold text-xs text-foreground transition-colors"
                    >
                      <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
                      <span>EOD Summary</span>
                    </button>
                  </div>
                </div>

                {/* Progress Bar & KPI Stats Grid */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground font-semibold">Beat Completion</span>
                    <span className="font-black text-foreground font-mono">{planCompletion}% Completed</span>
                  </div>

                  <div className="w-full h-3 bg-muted rounded-full overflow-hidden flex">
                    <div
                      style={{ width: `${(plan.visited_stops / (plan.total_stops || 1)) * 100}%` }}
                      className="bg-emerald-500 h-full transition-all duration-500"
                      title={`${plan.visited_stops} Visited`}
                    />
                    <div
                      style={{ width: `${(plan.skipped_stops / (plan.total_stops || 1)) * 100}%` }}
                      className="bg-rose-500 h-full transition-all duration-500"
                      title={`${plan.skipped_stops} Skipped`}
                    />
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1 text-xs">
                    <div className="p-3 rounded-2xl bg-muted/40 border border-border">
                      <span className="text-muted-foreground font-medium block">Total Planned</span>
                      <span className="text-lg font-black text-foreground mt-0.5 block">{plan.total_stops} Shops</span>
                    </div>

                    <div className="p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20">
                      <span className="text-emerald-600 dark:text-emerald-400 font-bold block">Visited Shops</span>
                      <span className="text-lg font-black text-emerald-600 dark:text-emerald-400 mt-0.5 block">
                        {plan.visited_stops} Shops
                      </span>
                    </div>

                    <div className="p-3 rounded-2xl bg-rose-500/10 border border-rose-500/20">
                      <span className="text-rose-600 dark:text-rose-400 font-bold block">Skipped Shops</span>
                      <span className="text-lg font-black text-rose-600 dark:text-rose-400 mt-0.5 block">
                        {plan.skipped_stops} Shops
                      </span>
                    </div>

                    <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20">
                      <span className="text-amber-600 dark:text-amber-400 font-bold block">Remaining Pending</span>
                      <span className="text-lg font-black text-amber-600 dark:text-amber-400 mt-0.5 block">
                        {plan.pending_stops} Shops
                      </span>
                    </div>
                  </div>
                </div>

                {/* Sequenced Route Stops List */}
                <div className="space-y-3 pt-2">
                  <div className="flex items-center justify-between border-b border-border pb-2">
                    <h3 className="font-extrabold text-base text-foreground flex items-center gap-2">
                      <Navigation className="w-4 h-4 text-primary" />
                      <span>Optimized Stop Sequence ({plan.stops.length})</span>
                    </h3>
                    <span className="text-xs text-muted-foreground">Order calculated via nearest-neighbor TSP</span>
                  </div>

                  <div className="space-y-3">
                    {plan.stops.map((stop, idx) => {
                      const stopName = stop.shop_name || stop.customer_name || 'Shop'
                      const seqNum = stop.sequence_order ?? stop.stop_sequence ?? (idx + 1)
                      const customerUrl = stop.customer_key
                        ? `/customers/${stop.customer_key}`
                        : (stop.customer_profile_id
                        ? `/customers/profile_${stop.customer_profile_id}`
                        : (stop.ledger_id
                        ? `/customers/tally_${stop.ledger_id}`
                        : '#'))
                      const mapsUrl = stop.maps_url || (stop.latitude && stop.longitude
                        ? `https://www.google.com/maps/dir/?api=1&destination=${stop.latitude},${stop.longitude}`
                        : undefined)
                      const checkInUrl = `/check-in?${stop.ledger_id ? `ledger_id=${stop.ledger_id}` : (stop.customer_profile_id ? `profile_id=${stop.customer_profile_id}` : '')}&name=${encodeURIComponent(stopName)}`

                      return (
                      <div
                        key={stop.id}
                        className={cn(
                          'p-4 sm:p-5 rounded-2xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4',
                          stop.status === 'visited'
                            ? 'bg-emerald-500/5 border-emerald-500/30'
                            : stop.status === 'skipped'
                            ? 'bg-rose-500/5 border-rose-500/30'
                            : 'bg-card border-border hover:border-primary/40 shadow-xs'
                        )}
                      >
                        {/* Left: Sequence Number + Shop Info */}
                        <div className="flex items-start gap-3.5">
                          {/* Sequence Number Circle */}
                          <div
                            className={cn(
                              'w-10 h-10 rounded-2xl flex items-center justify-center font-black text-sm flex-shrink-0 border shadow-xs',
                              stop.status === 'visited'
                                ? 'bg-emerald-600 text-white border-emerald-700'
                                : stop.status === 'skipped'
                                ? 'bg-rose-600 text-white border-rose-700'
                                : 'bg-primary/10 text-primary border-primary/20'
                            )}
                          >
                            {stop.status === 'visited' ? (
                              <Check className="w-5 h-5" />
                            ) : stop.status === 'skipped' ? (
                              <X className="w-5 h-5" />
                            ) : (
                              `#${seqNum}`
                            )}
                          </div>

                          <div className="space-y-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <Link
                                href={customerUrl}
                                className="font-extrabold text-sm sm:text-base text-foreground hover:text-primary transition-colors truncate max-w-[280px] sm:max-w-md"
                              >
                                {stopName}
                              </Link>

                              {/* Status Badge */}
                              <span
                                className={cn(
                                  'px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase',
                                  stop.status === 'visited'
                                    ? 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20'
                                    : stop.status === 'skipped'
                                    ? 'bg-rose-500/10 text-rose-600 border border-rose-500/20'
                                    : 'bg-amber-500/10 text-amber-600 border border-amber-500/20'
                                )}
                              >
                                {stop.status}
                              </span>

                              {stop.latitude && stop.longitude && (
                                <span className="px-1.5 py-0.5 rounded-md bg-blue-500/10 text-blue-600 text-[10px] font-bold flex items-center gap-0.5">
                                  <Compass className="w-3 h-3" />
                                  <span>GPS Tagged</span>
                                </span>
                              )}
                            </div>

                            {/* Contact Person & Address */}
                            <div className="text-xs text-muted-foreground flex items-center gap-2 flex-wrap">
                              {stop.contact_person && (
                                <span>Contact: <strong className="text-foreground">{stop.contact_person}</strong></span>
                              )}
                              {stop.locality && (
                                <span>• Locality: <strong className="text-foreground">{stop.locality}</strong></span>
                              )}
                              {stop.address && (
                                <span className="truncate max-w-[220px] hidden md:inline">• {stop.address}</span>
                              )}
                            </div>

                            {/* Visited or Skipped Extra Details */}
                            {stop.status === 'visited' && stop.visited_at && (
                              <p className="text-[11px] text-emerald-600 font-semibold pt-0.5">
                                Visited on {new Date(stop.visited_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                              </p>
                            )}

                            {stop.status === 'skipped' && stop.skip_reason && (
                              <p className="text-[11px] text-rose-600 font-semibold pt-0.5">
                                Skipped Reason: {stop.skip_reason} {stop.notes ? `(${stop.notes})` : ''}
                              </p>
                            )}
                          </div>
                        </div>

                        {/* Right: Quick Stop Actions */}
                        <div className="flex items-center gap-2 flex-wrap self-end sm:self-center">
                          {/* Call / WhatsApp */}
                          {(stop.phone || stop.whatsapp_number) && (
                            <div className="flex items-center gap-1">
                              {stop.phone && (
                                <a
                                  href={`tel:${stop.phone}`}
                                  className="p-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground transition-colors"
                                  title={`Call ${stopName}`}
                                >
                                  <Phone className="w-3.5 h-3.5" />
                                </a>
                              )}
                              {(stop.whatsapp_number || stop.phone) && (
                                <a
                                  href={`https://wa.me/91${(stop.whatsapp_number || stop.phone || '').replace(/\D/g, '')}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="p-2 rounded-xl bg-[#25D366]/10 text-[#25D366] hover:bg-[#25D366]/20 transition-colors"
                                  title="WhatsApp"
                                >
                                  <MessageCircle className="w-3.5 h-3.5" />
                                </a>
                              )}
                            </div>
                          )}

                          {/* Navigation in Google Maps */}
                          {mapsUrl && (
                            <a
                              href={mapsUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 px-3 py-2 rounded-xl border border-border bg-background hover:bg-muted text-xs font-semibold text-foreground transition-colors shadow-xs"
                              title="Directions in Google Maps"
                            >
                              <Navigation className="w-3.5 h-3.5 text-primary" />
                              <span className="hidden sm:inline">Directions</span>
                            </a>
                          )}

                          {/* Primary 1-Tap Check-In */}
                          <Link
                            href={checkInUrl}
                            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-xs transition-colors"
                            title="Perform GPS Check-In Visit"
                          >
                            <MapPin className="w-3.5 h-3.5" />
                            <span>Check-In</span>
                          </Link>

                          {/* Skip Button (Only if pending) */}
                          {stop.status === 'pending' && (
                            <button
                              onClick={() => {
                                setSelectedStopForSkip(stop)
                                setSkipReason('Shop Closed')
                                setSkipNotes('')
                                setShowSkipModal(true)
                              }}
                              className="p-2 rounded-xl hover:bg-rose-500/10 text-muted-foreground hover:text-rose-600 transition-colors"
                              title="Skip this stop"
                            >
                              <XCircle className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    )})}
                  </div>
                </div>
              </div>
            )})}
          </div>
        )}
      </div>

      {/* ─── MODAL: Assign Beat Plan (Admin) ─── */}
      {showAssignModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-lg w-full p-6 sm:p-7 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3.5">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <Route className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-foreground">Assign Daily Beat Plan</h3>
                  <p className="text-xs text-muted-foreground">Allocate route & auto-sequence stops via GPS</p>
                </div>
              </div>
              <button
                onClick={() => setShowAssignModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAssignBeat} className="space-y-4 text-xs">
              {/* Salesperson */}
              <div>
                <label className="font-semibold block mb-1 text-foreground">Assigned Salesperson *</label>
                <select
                  value={assignForm.user_id}
                  onChange={(e) => setAssignForm({ ...assignForm, user_id: e.target.value })}
                  required
                  className="w-full px-3.5 py-2.5 rounded-xl bg-background border border-border font-semibold text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="">Select Salesperson</option>
                  {routesData?.salespersons.map((s) => (
                    <option key={s.user_id} value={s.user_id.toString()}>
                      {s.name || s.username} ({s.role})
                    </option>
                  ))}
                </select>
              </div>

              {/* Date & Beat Name */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1 text-foreground">Plan Date *</label>
                  <input
                    type="date"
                    value={assignForm.plan_date || selectedDate}
                    onChange={(e) => setAssignForm({ ...assignForm, plan_date: e.target.value })}
                    required
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border font-bold text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1 text-foreground">Beat Plan Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Mandi Morning Beat"
                    value={assignForm.name}
                    onChange={(e) => setAssignForm({ ...assignForm, name: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              {/* Route OR Locality Selection */}
              <div className="p-4 rounded-2xl bg-muted/40 border border-border space-y-3">
                <span className="font-bold text-foreground block">Select Geographic Territory</span>

                <div>
                  <label className="font-medium text-muted-foreground block mb-1">By Master Route:</label>
                  <select
                    value={assignForm.route_name}
                    onChange={(e) => setAssignForm({ ...assignForm, route_name: e.target.value, locality: '' })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border font-semibold text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="">Select Route</option>
                    {routesData?.routes.map((r) => (
                      <option key={r.route_name} value={r.route_name}>
                        {r.route_name} ({r.customer_count} shops)
                      </option>
                    ))}
                  </select>
                </div>

                <div className="text-center text-[11px] text-muted-foreground uppercase font-bold">— OR —</div>

                <div>
                  <label className="font-medium text-muted-foreground block mb-1">By Locality:</label>
                  <select
                    value={assignForm.locality}
                    onChange={(e) => setAssignForm({ ...assignForm, locality: e.target.value, route_name: '' })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border font-semibold text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="">Select Locality</option>
                    {routesData?.localities.map((loc) => (
                      <option key={loc} value={loc}>
                        {loc}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Auto-Route Optimize Checkbox */}
              <div className="flex items-center gap-2.5 p-3 rounded-2xl bg-primary/5 border border-primary/20">
                <input
                  type="checkbox"
                  id="auto_opt"
                  checked={assignForm.auto_optimize}
                  onChange={(e) => setAssignForm({ ...assignForm, auto_optimize: e.target.checked })}
                  className="w-4 h-4 rounded text-primary accent-primary"
                />
                <label htmlFor="auto_opt" className="text-xs cursor-pointer select-none">
                  <strong className="text-foreground block">Auto-Optimize GPS Route Sequence</strong>
                  <span className="text-muted-foreground text-[11px]">
                    Sorts stops to minimize travel distance and fuel consumption.
                  </span>
                </label>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowAssignModal(false)}
                  className="px-4 py-2 rounded-xl border border-border bg-background hover:bg-muted font-bold text-xs text-foreground transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={assigning}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-xs shadow-sm transition-colors"
                >
                  {assigning ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Optimizing & Assigning...</span>
                    </>
                  ) : (
                    <span>Assign Beat Plan</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL: Skip Stop Reason ─── */}
      {showSkipModal && selectedStopForSkip && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="font-extrabold text-base text-foreground">Skip Stop: {selectedStopForSkip.customer_name}</h3>
              <button
                onClick={() => setShowSkipModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold block mb-1 text-foreground">Reason for Skipping *</label>
                <select
                  value={skipReason}
                  onChange={(e) => setSkipReason(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-background border border-border font-semibold text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="Shop Closed">🔒 Shop Closed / Shutter Down</option>
                  <option value="Owner Unavailable">👤 Owner / Decision Maker Unavailable</option>
                  <option value="Stock Sufficient">📦 Stock Full / No Order Required</option>
                  <option value="Payment Dispute">⚠️ Payment Dispute / Credit Issue</option>
                  <option value="Route Diverted">🚗 Traffic / Route Diverted</option>
                  <option value="Other">📝 Other Reason</option>
                </select>
              </div>

              <div>
                <label className="font-semibold block mb-1 text-foreground">Additional Notes (Optional)</label>
                <textarea
                  rows={2}
                  value={skipNotes}
                  onChange={(e) => setSkipNotes(e.target.value)}
                  placeholder="e.g. Shop owner on leave, visit scheduled tomorrow morning"
                  className="w-full p-3 rounded-xl bg-background border border-border text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => setShowSkipModal(false)}
                  className="px-4 py-2 rounded-xl border border-border bg-background hover:bg-muted font-bold text-xs text-foreground"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={savingStopStatus}
                  onClick={() => handleUpdateStopStatus(selectedStopForSkip.id, 'skipped', skipReason, skipNotes)}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs transition-colors shadow-sm"
                >
                  {savingStopStatus ? 'Saving...' : 'Confirm Skip'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL: End of Day Scorecard ─── */}
      {showEODModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-lg w-full p-6 sm:p-7 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3.5">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-600">
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-base text-foreground">Daily End-of-Day Scorecard</h3>
                  <p className="text-xs text-muted-foreground">Aggregated field performance & commercial recap</p>
                </div>
              </div>
              <button
                onClick={() => setShowEODModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {loadingEOD ? (
              <div className="py-16 text-center space-y-2">
                <RefreshCw className="w-7 h-7 mx-auto text-primary animate-spin" />
                <p className="text-xs text-muted-foreground">Calculating day scorecard...</p>
              </div>
            ) : !eodSummary ? (
              <div className="py-12 text-center text-muted-foreground text-xs">
                Could not load summary data.
              </div>
            ) : (
              <div className="space-y-4 text-xs">
                {/* Meta Header */}
                <div className="p-3.5 rounded-2xl bg-muted/40 border border-border flex items-center justify-between">
                  <div>
                    <span className="text-muted-foreground block text-[11px]">Representative:</span>
                    <strong className="text-sm font-bold text-foreground">
                      {typeof eodSummary.salesperson === 'object' ? eodSummary.salesperson?.username : (eodSummary.salesperson || 'Salesperson')}
                    </strong>
                  </div>
                  <div className="text-right">
                    <span className="text-muted-foreground block text-[11px]">Date:</span>
                    <strong className="text-foreground">{new Date(eodSummary.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</strong>
                  </div>
                </div>

                {/* Scorecard Grid */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-4 rounded-2xl bg-card border border-border space-y-1">
                    <span className="text-muted-foreground font-medium text-[11px]">Beat Completion</span>
                    <div className="text-2xl font-black text-foreground font-mono">
                      {eodSummary.beat?.completion_rate ?? eodSummary.completion_percentage ?? 0}%
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      {eodSummary.beat?.visited_count ?? eodSummary.visited_stops ?? 0} of {eodSummary.beat?.total_planned ?? eodSummary.planned_stops ?? 0} planned shops
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-card border border-border space-y-1">
                    <span className="text-muted-foreground font-medium text-[11px]">Check-In Visits</span>
                    <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 font-mono">
                      {eodSummary.visits?.count ?? eodSummary.total_checkins ?? 0}
                    </div>
                    <p className="text-[11px] text-muted-foreground">Logged GPS visits</p>
                  </div>

                  <div className="p-4 rounded-2xl bg-blue-500/5 border border-blue-500/20 space-y-1">
                    <span className="text-blue-600 dark:text-blue-400 font-bold text-[11px]">Sales Orders</span>
                    <div className="text-xl font-black text-foreground font-mono">
                      ₹{(eodSummary.orders?.total_amount ?? eodSummary.total_order_value ?? 0).toLocaleString('en-IN')}
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      {eodSummary.orders?.count ?? eodSummary.orders_count ?? 0} orders booked
                    </p>
                  </div>

                  <div className="p-4 rounded-2xl bg-emerald-500/5 border border-emerald-500/20 space-y-1">
                    <span className="text-emerald-600 dark:text-emerald-400 font-bold text-[11px]">Payments Collected</span>
                    <div className="text-xl font-black text-emerald-600 dark:text-emerald-400 font-mono">
                      ₹{(eodSummary.payments?.total_amount ?? eodSummary.total_collected_value ?? 0).toLocaleString('en-IN')}
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      {eodSummary.payments?.count ?? eodSummary.payments_count ?? 0} receipts logged
                    </p>
                  </div>
                </div>

                {/* Collections Breakdown by Mode */}
                <div className="p-4 rounded-2xl bg-muted/30 border border-border space-y-2">
                  <span className="font-bold text-foreground text-[11px] uppercase tracking-wider block">
                    Payment Mode Breakdown
                  </span>
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="p-2 rounded-xl bg-card border border-border/60">
                      <span className="text-muted-foreground text-[10px] block">Cash</span>
                      <strong className="font-mono text-foreground">
                        ₹{(eodSummary.payments?.by_mode?.cash ?? eodSummary.collections_by_mode?.cash ?? 0).toLocaleString('en-IN')}
                      </strong>
                    </div>
                    <div className="p-2 rounded-xl bg-card border border-border/60">
                      <span className="text-muted-foreground text-[10px] block">UPI / Online</span>
                      <strong className="font-mono text-foreground">
                        ₹{(eodSummary.payments?.by_mode?.upi ?? eodSummary.collections_by_mode?.upi ?? 0).toLocaleString('en-IN')}
                      </strong>
                    </div>
                    <div className="p-2 rounded-xl bg-card border border-border/60">
                      <span className="text-muted-foreground text-[10px] block">Cheque</span>
                      <strong className="font-mono text-foreground">
                        ₹{(eodSummary.payments?.by_mode?.cheque ?? eodSummary.collections_by_mode?.cheque ?? 0).toLocaleString('en-IN')}
                      </strong>
                    </div>
                  </div>
                </div>

                {/* WhatsApp Dispatch Button */}
                <button
                  type="button"
                  onClick={handleShareEODWhatsApp}
                  className="w-full inline-flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#25D366] hover:bg-[#20bd5a] text-white font-extrabold text-xs shadow-md transition-colors"
                >
                  <Share2 className="w-4 h-4" />
                  <span>Share Daily Summary on WhatsApp</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
