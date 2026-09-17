'use client'

import { useState, useEffect, useMemo, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, cn } from '@/lib/utils'
import {
  Users,
  MapPin,
  Navigation,
  Phone,
  MessageCircle,
  Search,
  Filter,
  Plus,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Building,
  Building2,
  ChevronDown,
  CheckCircle2,
  X,
  Compass,
  History,
  Edit2,
  Map,
  Tag,
  ChevronRight,
  ChevronLeft,
  ArrowUp,
  ArrowDown,
  TrendingUp,
  SlidersHorizontal,
  Loader2,
  Info,
  LayoutList,
  LayoutGrid,
  ArrowUpDown,
  Link2,
  User as UserIcon,
  Trash2,
  Activity,
  CloudOff,
  Milestone,
  Radio,
  HeartPulse,
  Check
} from 'lucide-react'
import { saveOfflineDirectory, getOfflineDirectory } from '@/lib/offline-storage'

interface LocalityItem {
  name: string
  count: number
}

interface OwnerSummary {
  id: number
  name: string
  designation?: string
  phone?: string
  whatsapp_number?: string
  is_primary: boolean
  photo_url?: string
}

interface Customer {
  key: string
  source: 'tally' | 'field_profile'
  ledger_id: number | null
  profile_id: number | null
  name: string
  contact_person: string
  phone: string
  mobile: string
  whatsapp_number: string
  email: string
  address: string
  locality: string
  city: string
  state: string
  pincode: string
  route_name: string
  shop_type: string
  tags: string[]
  priority: string
  latitude: number | null
  longitude: number | null
  has_location: boolean
  location_verified: boolean
  maps_url: string
  distance_from_me_meters: number | null
  last_visit_at: string | null
  total_visits: number
  notes: string
  latest_verification_status: string
  latest_checkin_distance: number | null
  latest_checkin_at: string | null
  owners_count?: number
  owners?: OwnerSummary[]
  days_since_last_visit?: number | null
  visit_recency_category?: 'today' | 'recent' | 'due_soon' | 'overdue' | 'critical' | 'never'
  visit_recency_label?: string
  health_score?: {
    score: number
    grade: 'A' | 'B' | 'C' | 'D'
    status: 'Healthy' | 'Fair' | 'At Risk'
    breakdown: {
      visit_cadence_score: number
      order_recency_score: number
      txn_depth_score: number
      profile_verification_score: number
    }
  }
}

interface LocationLog {
  id: number
  latitude: number
  longitude: number
  distance_from_base_meters: number | null
  verification_status: string
  source: string
  user_id: number
  salesperson: string
  notes: string | null
  created_at: string | null
  maps_url: string
}

export default function CustomersPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()

  const [customers, setCustomers] = useState<Customer[]>([])
  const [metrics, setMetrics] = useState({
    total: 0,
    tagged: 0,
    missing_location: 0,
    mismatch_count: 0,
    verified_count: 0,
  })
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  // Filters & Search
  const [search, setSearch] = useState('')
  const [selectedLocality, setSelectedLocality] = useState('all')
  const [selectedCity, setSelectedCity] = useState('all')
  const [selectedRoute, setSelectedRoute] = useState('all')
  const [locationFilter, setLocationFilter] = useState<'all' | 'tagged' | 'missing'>('all')
  const [verificationFilter, setVerificationFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<string>('name_asc')
  const [myCoords, setMyCoords] = useState<{ lat: number; lon: number } | null>(null)
  const [geoLocating, setGeoLocating] = useState(false)
  const [viewMode, setViewMode] = useState<'list' | 'grid' | 'route'>('list')
  const [selectedRadius, setSelectedRadius] = useState<number | null>(null)
  const [selectedRecency, setSelectedRecency] = useState<string>('all')
  const [selectedHealthGrade, setSelectedHealthGrade] = useState<string>('all')
  const [plannerRoute, setPlannerRoute] = useState<string>('all')
  const [isOffline, setIsOffline] = useState(false)
  const [offlineCachedAt, setOfflineCachedAt] = useState<string | null>(null)
  const [activeHealthCustomer, setActiveHealthCustomer] = useState<Customer | null>(null)

  // Offline network status tracking
  useEffect(() => {
    const handleOnline = () => setIsOffline(false)
    const handleOffline = () => setIsOffline(true)
    setIsOffline(typeof navigator !== 'undefined' ? !navigator.onLine : false)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  // Dropdown lists
  const [localitiesList, setLocalitiesList] = useState<LocalityItem[]>([])
  const [citiesList, setCitiesList] = useState<LocalityItem[]>([])
  const [routesList, setRoutesList] = useState<string[]>([])

  // Modals state
  const [showAddModal, setShowAddModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showTagModal, setShowTagModal] = useState(false)
  const [showHistoryModal, setShowHistoryModal] = useState(false)
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null)
  const [historyLogs, setHistoryLogs] = useState<LocationLog[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  // Admin privilege check for mapping field profiles to Tally ledgers
  const isAdmin = Boolean(
    permissions?.isAdmin ||
    user?.role?.toLowerCase() === 'admin' ||
    user?.role?.toLowerCase() === 'superadmin' ||
    user?.role?.toLowerCase() === 'owner'
  )

  // Link Ledger Modal state (Admin Only, for unmapped profiles without ledger_id)
  const [showLinkModal, setShowLinkModal] = useState(false)
  const [unlinkedLedgers, setUnlinkedLedgers] = useState<{
    ledger_id: number
    name: string
    address: string
    mobile: string
    state: string
    pincode: string
  }[]>([])
  const [loadingUnlinkedLedgers, setLoadingUnlinkedLedgers] = useState(false)
  const [selectedLedgerId, setSelectedLedgerId] = useState<number | null>(null)
  const [ledgerSearch, setLedgerSearch] = useState('')
  const [linkingLedger, setLinkingLedger] = useState(false)

  // Form states
  const [addForm, setAddForm] = useState({
    name: '',
    contact_person: '',
    phone: '',
    whatsapp_number: '',
    address: '',
    locality: '',
    city: '',
    state: '',
    pincode: '',
    route_name: '',
    shop_type: 'Retailer',
    tags: '',
    priority: 'medium',
    notes: '',
    latitude: '',
    longitude: '',
  })
  const [editForm, setEditForm] = useState({
    contact_person: '',
    phone: '',
    whatsapp_number: '',
    address: '',
    locality: '',
    city: '',
    state: '',
    pincode: '',
    route_name: '',
    shop_type: 'Retailer',
    tags: '',
    priority: 'medium',
    notes: '',
  })
  const [tagForm, setTagForm] = useState({
    latitude: '',
    longitude: '',
    reason: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  // Delete Wrong Tagging Modal State
  const [customerToDelete, setCustomerToDelete] = useState<Customer | null>(null)
  const [deletingCustomer, setDeletingCustomer] = useState(false)

  // Fetch localities and routes
  const fetchLocalities = async () => {
    if (!token) return
    try {
      const res = await fetch(`${API_BASE}/customers/localities`, {
        headers: authHeaders(token),
      })
      if (res.ok) {
        const data = await res.json()
        setLocalitiesList(data.localities || [])
        setCitiesList(data.cities || [])
        setRoutesList(data.routes || [])
      }
    } catch (e) {
      console.error('Failed to load localities', e)
    }
  }

  const localityScrollRef = useRef<HTMLDivElement>(null)

  const scrollLocalities = (direction: 'left' | 'right') => {
    if (localityScrollRef.current) {
      const scrollAmount = direction === 'left' ? -260 : 260
      localityScrollRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' })
    }
  }

  // Fetch customers list with instant override support & offline caching
  const fetchCustomers = async (
    isRefresh = false,
    overrideCoords: { lat: number; lon: number } | null = myCoords,
    overrideSort: string = sortBy,
    overrideLocality: string = selectedLocality,
    overrideRadius: number | null = selectedRadius,
    overrideRecency: string = selectedRecency,
    overrideHealth: string = selectedHealthGrade
  ) => {
    if (!token) return
    if (isRefresh) setRefreshing(true)
    else setLoading(true)

    try {
      const activeSort = overrideSort || sortBy
      const activeCoords = overrideCoords !== undefined ? overrideCoords : myCoords
      const activeLoc = overrideLocality !== undefined ? overrideLocality : selectedLocality
      const activeRadius = overrideRadius !== undefined ? overrideRadius : selectedRadius
      const activeRecency = overrideRecency !== undefined ? overrideRecency : selectedRecency
      const activeHealth = overrideHealth !== undefined ? overrideHealth : selectedHealthGrade

      let url = `${API_BASE}/customers?location_status=${locationFilter}&sort_by=${activeSort}`
      if (search) url += `&search=${encodeURIComponent(search)}`
      if (activeLoc !== 'all') url += `&locality=${encodeURIComponent(activeLoc)}`
      if (selectedCity !== 'all') url += `&city=${encodeURIComponent(selectedCity)}`
      if (selectedRoute !== 'all') url += `&route_name=${encodeURIComponent(selectedRoute)}`
      if (verificationFilter !== 'all') url += `&verification_filter=${encodeURIComponent(verificationFilter)}`
      if (activeRadius !== null) url += `&radius_km=${activeRadius}`
      if (activeRecency !== 'all') url += `&visit_recency=${encodeURIComponent(activeRecency)}`
      if (activeHealth !== 'all') url += `&health_grade=${encodeURIComponent(activeHealth)}`

      if (activeCoords) {
        url += `&my_lat=${activeCoords.lat}&my_lon=${activeCoords.lon}`
      }

      const res = await fetch(url, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        const custList = data.customers || []
        setCustomers(custList)
        setMetrics(data.metrics || {
          total: 0,
          tagged: 0,
          missing_location: 0,
          mismatch_count: 0,
          verified_count: 0,
        })
        // Save fresh directory snapshot to local offline storage
        saveOfflineDirectory({ customers: custList })
        setOfflineCachedAt(null)
      } else {
        throw new Error(`Server returned ${res.status}`)
      }
    } catch (e) {
      console.error('Failed to load customers, attempting offline cache fallback', e)
      const cached = getOfflineDirectory()
      if (cached && cached.customers?.length > 0) {
        setCustomers(cached.customers)
        setOfflineCachedAt(new Date(cached.cachedAt).toLocaleTimeString())
        setIsOffline(true)
      }
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchCustomers()
    fetchLocalities()
  }, [token, locationFilter, selectedLocality, selectedCity, selectedRoute, verificationFilter, sortBy, myCoords, selectedRadius, selectedRecency, selectedHealthGrade])

  // Handle sort change with auto-GPS trigger if nearest is chosen
  const handleSortChange = (newSort: string) => {
    setSortBy(newSort)
    if (newSort === 'nearest') {
      if (!myCoords) {
        handleGetLocation()
        return
      }
    }
    fetchCustomers(false, myCoords, newSort)
  }

  // Toggle Name sort A-Z <-> Z-A
  const handleToggleNameSort = () => {
    const nextSort = sortBy === 'name_asc' ? 'name_desc' : 'name_asc'
    handleSortChange(nextSort)
  }

  // Handle Locality change
  const handleSelectLocality = (loc: string) => {
    setSelectedLocality(loc)
    fetchCustomers(false, myCoords, sortBy, loc)
  }

  // Get User Device Coordinates
  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser')
      return
    }
    setGeoLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = {
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
        }
        setMyCoords(coords)
        setSortBy('nearest')
        setGeoLocating(false)
        setActionSuccess('GPS location acquired! Sorting customers nearest to you.')
        setTimeout(() => setActionSuccess(null), 3500)
        fetchCustomers(false, coords, 'nearest')
      },
      (err) => {
        console.warn('Geolocation error:', err)
        alert('Could not retrieve your location. Please check browser location permissions.')
        setGeoLocating(false)
      },
      { enableHighAccuracy: true, timeout: 10000 }
    )
  }

  // Handle Search submit
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    fetchCustomers()
  }

  // Open Location History Modal
  const handleOpenHistory = async (cust: Customer) => {
    setSelectedCustomer(cust)
    setShowHistoryModal(true)
    setLoadingHistory(true)
    try {
      const targetId = cust.ledger_id ? `ledger_${cust.ledger_id}` : `profile_${cust.profile_id}`
      const res = await fetch(`${API_BASE}/customers/${targetId}/location-history`, {
        headers: authHeaders(token),
      })
      if (res.ok) {
        const data = await res.json()
        setHistoryLogs(data.history || [])
      }
    } catch (err) {
      console.error('Failed to load location history', err)
    } finally {
      setLoadingHistory(false)
    }
  }

  // Open Edit Profile Modal
  const handleOpenEdit = (cust: Customer) => {
    setSelectedCustomer(cust)
    setEditForm({
      contact_person: cust.contact_person || '',
      phone: cust.phone || '',
      whatsapp_number: cust.whatsapp_number || cust.mobile || '',
      address: cust.address || '',
      locality: cust.locality || '',
      city: cust.city || '',
      state: cust.state || '',
      pincode: cust.pincode || '',
      route_name: cust.route_name || '',
      shop_type: cust.shop_type || 'Retailer',
      tags: cust.tags ? cust.tags.join(', ') : '',
      priority: cust.priority || 'medium',
      notes: cust.notes || '',
    })
    setShowEditModal(true)
  }

  // Submit Edit Profile
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedCustomer) return
    setSubmitting(true)
    try {
      const targetId = selectedCustomer.ledger_id
        ? `ledger_${selectedCustomer.ledger_id}`
        : `profile_${selectedCustomer.profile_id}`

      const res = await fetch(`${API_BASE}/customers/${targetId}/profile`, {
        method: 'PUT',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editForm),
      })
      if (res.ok) {
        setShowEditModal(false)
        setActionSuccess('Customer details updated successfully!')
        setTimeout(() => setActionSuccess(null), 3500)
        fetchCustomers()
        fetchLocalities()
      } else {
        alert('Failed to update customer details')
      }
    } catch (err) {
      alert('Error updating customer profile')
    } finally {
      setSubmitting(false)
    }
  }

  // Open Tag Location Modal
  const handleOpenTag = (cust: Customer) => {
    setSelectedCustomer(cust)
    setTagForm({
      latitude: cust.latitude ? cust.latitude.toString() : '',
      longitude: cust.longitude ? cust.longitude.toString() : '',
      reason: 'Calibrate master shop location',
    })
    setShowTagModal(true)
  }

  // Auto-fill Current GPS in Tag Modal
  const handleCaptureTagLocation = () => {
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setTagForm((prev) => ({
          ...prev,
          latitude: pos.coords.latitude.toFixed(6),
          longitude: pos.coords.longitude.toFixed(6),
        }))
      },
      () => alert('Could not get current coordinates. Check GPS permissions.'),
      { enableHighAccuracy: true }
    )
  }

  // Submit Tag Location
  const handleSaveTagLocation = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedCustomer || !tagForm.latitude || !tagForm.longitude) return
    setSubmitting(true)
    try {
      const targetId = selectedCustomer.ledger_id
        ? `ledger_${selectedCustomer.ledger_id}`
        : `profile_${selectedCustomer.profile_id}`

      const res = await fetch(`${API_BASE}/customers/${targetId}/tag-location`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          latitude: parseFloat(tagForm.latitude),
          longitude: parseFloat(tagForm.longitude),
          reason: tagForm.reason,
        }),
      })
      if (res.ok) {
        setShowTagModal(false)
        setActionSuccess('Shop GPS coordinates successfully saved!')
        setTimeout(() => setActionSuccess(null), 3500)
        fetchCustomers()
      } else {
        alert('Failed to save shop GPS location')
      }
    } catch (err) {
      alert('Error saving shop GPS location')
    } finally {
      setSubmitting(false)
    }
  }

  // Submit Add Field Customer
  const handleCreateCustomer = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!addForm.name.trim()) {
      alert('Please enter a shop name')
      return
    }
    setSubmitting(true)
    try {
      const payload = {
        ...addForm,
        latitude: addForm.latitude ? parseFloat(addForm.latitude) : null,
        longitude: addForm.longitude ? parseFloat(addForm.longitude) : null,
      }
      const res = await fetch(`${API_BASE}/customers`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        setShowAddModal(false)
        setAddForm({
          name: '',
          contact_person: '',
          phone: '',
          whatsapp_number: '',
          address: '',
          locality: '',
          city: '',
          state: '',
          pincode: '',
          route_name: '',
          shop_type: 'Retailer',
          tags: '',
          priority: 'medium',
          notes: '',
          latitude: '',
          longitude: '',
        })
        setActionSuccess('New customer profile added to Portal! (Zero accounting modified)')
        setTimeout(() => setActionSuccess(null), 4000)
        fetchCustomers()
        fetchLocalities()
      } else {
        alert('Failed to create customer profile')
      }
    } catch (err) {
      alert('Error creating customer profile')
    } finally {
      setSubmitting(false)
    }
  }

  // Open Link Ledger Modal (Admin Only, for unmapped field profiles)
  const handleOpenLinkLedger = (cust: Customer) => {
    setSelectedCustomer(cust)
    setSelectedLedgerId(null)
    setLedgerSearch('')
    setShowLinkModal(true)
    fetchUnlinkedLedgers()
  }

  // Fetch unlinked Tally Debtors
  const fetchUnlinkedLedgers = async (searchTerm = '') => {
    if (!token) return
    setLoadingUnlinkedLedgers(true)
    try {
      let url = `${API_BASE}/customers/unlinked-ledgers`
      if (searchTerm.trim()) {
        url += `?search=${encodeURIComponent(searchTerm.trim())}`
      }
      const res = await fetch(url, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        setUnlinkedLedgers(data.unlinked_ledgers || [])
      } else {
        setUnlinkedLedgers([])
      }
    } catch (e) {
      console.error('Failed to load unlinked ledgers', e)
    } finally {
      setLoadingUnlinkedLedgers(false)
    }
  }

  // Submit Link Ledger Request (Admin Only)
  const handleConfirmLinkLedger = async () => {
    if (!selectedCustomer || !selectedLedgerId) return
    setLinkingLedger(true)
    try {
      const targetId = selectedCustomer.profile_id
        ? `profile_${selectedCustomer.profile_id}`
        : selectedCustomer.key.replace('profile_', '')

      const res = await fetch(`${API_BASE}/customers/${targetId}/link-ledger`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ledger_id: selectedLedgerId }),
      })

      if (res.ok) {
        const data = await res.json()
        setShowLinkModal(false)
        setActionSuccess(data.message || `Successfully linked "${selectedCustomer.name}" to Tally ledger!`)
        setTimeout(() => setActionSuccess(null), 4000)
        fetchCustomers(true)
        fetchLocalities()
      } else {
        const err = await res.json().catch(() => null)
        alert(err?.detail || 'Failed to link customer to Tally ledger')
      }
    } catch (err) {
      alert('Error linking customer to Tally ledger')
    } finally {
      setLinkingLedger(false)
    }
  }

  // Delete unmapped customer lead (wrong tagging)
  const handleDeleteCustomer = async () => {
    if (!token || !customerToDelete || customerToDelete.ledger_id) return

    setDeletingCustomer(true)
    try {
      const res = await fetch(`${API_BASE}/customers/${customerToDelete.key}`, {
        method: 'DELETE',
        headers: authHeaders(token),
      })

      if (res.ok) {
        setActionSuccess(`Customer lead "${customerToDelete.name}" deleted successfully.`)
        // Remove from local list immediately
        setCustomers((prev) => prev.filter((c) => c.key !== customerToDelete.key))
        setCustomerToDelete(null)
        setTimeout(() => setActionSuccess(null), 3500)
        fetchLocalities()
      } else {
        const err = await res.json().catch(() => null)
        alert(err?.detail || 'Failed to delete customer lead')
      }
    } catch (e) {
      console.error('Delete error', e)
      alert('Network error while deleting customer')
    } finally {
      setDeletingCustomer(false)
    }
  }

  // Haversine distance calculator between 2 coordinates in km
  const haversineKm = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
    const R = 6371
    const dLat = (lat2 - lat1) * (Math.PI / 180)
    const dLon = (lon2 - lon1) * (Math.PI / 180)
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * (Math.PI / 180)) * Math.cos(lat2 * (Math.PI / 180)) * Math.sin(dLon / 2) * Math.sin(dLon / 2)
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
    return R * c
  }

  // Optimized route sequencing (Nearest Neighbor algorithm)
  const routeStops = useMemo(() => {
    let pool = customers.filter((c) => c.has_location && c.latitude && c.longitude)
    if (plannerRoute !== 'all') {
      pool = pool.filter((c) => (c.route_name || '').toLowerCase() === plannerRoute.toLowerCase())
    }
    if (pool.length === 0) return []

    // Start point: salesperson device GPS if available, else first shop
    let currentLat = myCoords ? myCoords.lat : (pool[0].latitude as number)
    let currentLon = myCoords ? myCoords.lon : (pool[0].longitude as number)

    const remaining = [...pool]
    const sequenced: (Customer & { legDistanceKm: number; cumulativeKm: number })[] = []
    let totalKm = 0

    while (remaining.length > 0) {
      let nearestIdx = 0
      let minDist = Infinity
      for (let i = 0; i < remaining.length; i++) {
        const d = haversineKm(currentLat, currentLon, remaining[i].latitude as number, remaining[i].longitude as number)
        if (d < minDist) {
          minDist = d
          nearestIdx = i
        }
      }
      const [nextStop] = remaining.splice(nearestIdx, 1)
      const legDist = minDist === Infinity ? 0 : minDist
      totalKm += legDist
      sequenced.push({
        ...nextStop,
        legDistanceKm: legDist,
        cumulativeKm: totalKm,
      })
      currentLat = nextStop.latitude as number
      currentLon = nextStop.longitude as number
    }

    return sequenced
  }, [customers, plannerRoute, myCoords])

  // Route metrics summary
  const routeMetrics = useMemo(() => {
    const totalStops = routeStops.length
    const totalDistanceKm = routeStops.length > 0 ? routeStops[routeStops.length - 1].cumulativeKm : 0
    const visitedToday = routeStops.filter((s) => s.visit_recency_category === 'today').length
    const pendingVisits = totalStops - visitedToday
    return {
      totalStops,
      totalDistanceKm: totalDistanceKm.toFixed(1),
      visitedToday,
      pendingVisits,
    }
  }, [routeStops])

  // Recency badge helper
  const renderRecencyBadge = (cust: Customer) => {
    const cat = cust.visit_recency_category || 'never'
    const label = cust.visit_recency_label || 'Never Visited'

    switch (cat) {
      case 'today':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            Visited Today
          </span>
        )
      case 'recent':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/10 text-blue-600 border border-blue-500/20">
            <Clock className="w-3 h-3" />
            {label}
          </span>
        )
      case 'due_soon':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-600 border border-amber-500/20">
            <Clock className="w-3 h-3" />
            {label}
          </span>
        )
      case 'overdue':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-orange-500/10 text-orange-600 border border-orange-500/20">
            <AlertTriangle className="w-3 h-3" />
            {label}
          </span>
        )
      case 'critical':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-600 border border-rose-500/20 animate-pulse">
            <AlertTriangle className="w-3 h-3" />
            {label}
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground border border-border">
            <Clock className="w-3 h-3" />
            Never Visited
          </span>
        )
    }
  }

  // Health Pill helper
  const renderHealthPill = (cust: Customer) => {
    if (!cust.health_score) return null
    const { score, grade, status } = cust.health_score

    let colorClasses = 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20 hover:bg-emerald-500/20'
    if (status === 'Fair') {
      colorClasses = 'bg-amber-500/10 text-amber-600 border-amber-500/20 hover:bg-amber-500/20'
    } else if (status === 'At Risk') {
      colorClasses = 'bg-rose-500/10 text-rose-600 border-rose-500/20 hover:bg-rose-500/20'
    }

    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setActiveHealthCustomer(cust)
        }}
        className={cn(
          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold border transition-colors shadow-sm cursor-pointer',
          colorClasses
        )}
        title={`Health Score: ${score}/100 (${grade} - ${status}). Click for factor breakdown.`}
      >
        <HeartPulse className="w-3 h-3" />
        <span>{score}</span>
        <span className="opacity-70 text-[10px]">({grade})</span>
      </button>
    )
  }

  // Format status badge helper
  const renderVerificationBadge = (cust: Customer) => {
    const status = cust.latest_verification_status
    const dist = cust.latest_checkin_distance

    if (status === 'VERIFIED_ON_SITE') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 whitespace-normal break-words">
          <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
          <span>Verified On-Site ({dist !== null ? `${Math.round(dist)}m` : '0m'})</span>
        </span>
      )
    }
    if (status === 'NEARBY') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-amber-500/10 text-amber-600 border border-amber-500/20 whitespace-normal break-words">
          <MapPin className="w-3.5 h-3.5 shrink-0" />
          <span>Nearby Market ({dist !== null ? `${Math.round(dist)}m` : ''})</span>
        </span>
      )
    }
    if (status === 'MISMATCH_FAR') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-rose-500/10 text-rose-600 border border-rose-500/20 whitespace-normal break-words">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>Location Mismatch ({dist !== null ? `${(dist / 1000).toFixed(1)}km` : ''})</span>
        </span>
      )
    }
    if (status === 'ESTABLISHED_BASE') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-blue-500/10 text-blue-600 border border-blue-500/20 whitespace-normal break-words">
          <MapPin className="w-3.5 h-3.5 shrink-0" />
          <span>Base Location Established</span>
        </span>
      )
    }
    if (!cust.has_location) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-muted text-muted-foreground whitespace-normal break-words">
          <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" />
          <span>Needs GPS Tag</span>
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-muted text-muted-foreground whitespace-normal break-words">
        <Clock className="w-3 h-3 shrink-0" />
        <span>No Check-in Log</span>
      </span>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground pb-24">
      {/* Toast Alert */}
      {actionSuccess && (
        <div className="fixed top-20 right-4 z-50 bg-emerald-600 text-white px-4 py-3 rounded-xl shadow-xl flex items-center gap-3 animate-in fade-in slide-in-from-top-4 duration-300">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm font-medium">{actionSuccess}</p>
        </div>
      )}

      {/* Offline Mode Alert Banner */}
      {isOffline && (
        <div className="bg-amber-500/15 border-b border-amber-500/30 text-amber-800 dark:text-amber-200 px-4 py-2.5">
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-3 text-xs font-semibold">
            <div className="flex items-center gap-2">
              <CloudOff className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <span>
                Offline Mode Active: Showing cached customer directory from your device{offlineCachedAt ? ` (cached at ${offlineCachedAt})` : ''}.
                Check-ins performed offline will be saved in your offline queue and auto-synced once connection is restored.
              </span>
            </div>
            <button
              onClick={() => fetchCustomers(true)}
              className="px-2.5 py-1 rounded-lg bg-amber-600/20 hover:bg-amber-600/30 text-amber-900 dark:text-amber-100 text-xs font-bold transition-colors whitespace-nowrap"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Hero Header Section */}
      <div className="bg-card border-b border-border shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="inline-flex p-2 rounded-xl bg-primary/10 text-primary">
                  <Users className="w-6 h-6" />
                </span>
                <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Customer Directory</h1>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Field-sales customer map, locality routing & GPS check-in audit history.
                <span className="ml-1 text-xs text-primary font-medium">(Read-only Tally data • Zero Accounting Modifications)</span>
              </p>
            </div>

            <div className="flex items-center gap-2.5">
              <button
                onClick={() => fetchCustomers(true)}
                disabled={refreshing}
                className="flex items-center gap-2 px-3 py-2 rounded-xl border border-border bg-background hover:bg-muted text-sm font-medium transition-colors"
                title="Refresh list"
              >
                <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin text-primary')} />
                <span className="hidden sm:inline">Refresh</span>
              </button>

              <button
                onClick={() => setShowAddModal(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 shadow-md hover:shadow-lg transition-all"
              >
                <Plus className="w-4 h-4" />
                <span>Add Customer</span>
              </button>
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
            <div
              onClick={() => setLocationFilter('all')}
              className={cn(
                'p-3.5 rounded-2xl border transition-all cursor-pointer hover:border-primary/50',
                locationFilter === 'all' ? 'bg-primary/5 border-primary/40 shadow-sm' : 'bg-muted/40 border-border'
              )}
            >
              <div className="text-xs text-muted-foreground font-medium flex items-center justify-between">
                <span>Total Directory</span>
                <Users className="w-3.5 h-3.5 text-primary" />
              </div>
              <div className="text-2xl font-bold mt-1">{metrics.total}</div>
              <div className="text-[11px] text-muted-foreground mt-0.5">Shops & Debtors</div>
            </div>

            <div
              onClick={() => setLocationFilter('tagged')}
              className={cn(
                'p-3.5 rounded-2xl border transition-all cursor-pointer hover:border-emerald-500/50',
                locationFilter === 'tagged' ? 'bg-emerald-500/10 border-emerald-500/40 shadow-sm' : 'bg-muted/40 border-border'
              )}
            >
              <div className="text-xs text-muted-foreground font-medium flex items-center justify-between">
                <span>GPS Tagged</span>
                <MapPin className="w-3.5 h-3.5 text-emerald-500" />
              </div>
              <div className="text-2xl font-bold mt-1 text-emerald-600">{metrics.tagged}</div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                {metrics.total > 0 ? `${Math.round((metrics.tagged / metrics.total) * 100)}% mapped` : '0%'}
              </div>
            </div>

            <div
              onClick={() => setLocationFilter('missing')}
              className={cn(
                'p-3.5 rounded-2xl border transition-all cursor-pointer hover:border-amber-500/50',
                locationFilter === 'missing' ? 'bg-amber-500/10 border-amber-500/40 shadow-sm' : 'bg-muted/40 border-border'
              )}
            >
              <div className="text-xs text-muted-foreground font-medium flex items-center justify-between">
                <span>Needs GPS Tag</span>
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
              </div>
              <div className="text-2xl font-bold mt-1 text-amber-600">{metrics.missing_location}</div>
              <div className="text-[11px] text-muted-foreground mt-0.5">Pending coordinates</div>
            </div>

            <div
              onClick={() => setVerificationFilter(verificationFilter === 'mismatch' ? 'all' : 'mismatch')}
              className={cn(
                'p-3.5 rounded-2xl border transition-all cursor-pointer hover:border-rose-500/50',
                verificationFilter === 'mismatch' ? 'bg-rose-500/10 border-rose-500/40 shadow-sm' : 'bg-muted/40 border-border'
              )}
            >
              <div className="text-xs text-muted-foreground font-medium flex items-center justify-between">
                <span>Audit Discrepancies</span>
                <ShieldCheck className="w-3.5 h-3.5 text-rose-500" />
              </div>
              <div className="text-2xl font-bold mt-1 text-rose-600">{metrics.mismatch_count}</div>
              <div className="text-[11px] text-rose-500 font-medium mt-0.5">Check-in {'>'} 250m away</div>
            </div>
          </div>
        </div>
      </div>      {/* Filters, Locality & Sort Command Center */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden divide-y divide-border">
          
          {/* 1. TOP LOCALITY FILTER SECTION */}
          <div className="p-3.5 sm:p-4 bg-muted/15">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
              {/* Left: Title & Active Indicator */}
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="p-1.5 rounded-xl bg-primary/10 border border-primary/20 text-primary flex items-center justify-center flex-shrink-0">
                  <MapPin className="w-4 h-4" />
                </span>
                <div className="min-w-0 flex items-center gap-2 flex-wrap">
                  <h2 className="text-xs sm:text-sm font-bold text-foreground tracking-tight whitespace-nowrap">
                    Locality & Territory
                  </h2>
                  {selectedLocality !== 'all' && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                      <span>{selectedLocality}</span>
                      <button
                        type="button"
                        onClick={() => handleSelectLocality('all')}
                        className="hover:text-primary/70"
                        title="Clear locality filter"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  )}
                </div>
              </div>

              {/* Right: Dropdown Pickers (Responsive 2-column grid on mobile, inline on desktop) */}
              <div className="grid grid-cols-2 sm:flex sm:items-center gap-2 w-full sm:w-auto">
                {/* Locality Dropdown */}
                <div className="relative flex-1 sm:flex-initial">
                  <MapPin className="w-3.5 h-3.5 text-primary pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 z-10" />
                  <select
                    value={selectedLocality}
                    onChange={(e) => handleSelectLocality(e.target.value)}
                    className="w-full sm:w-auto min-w-[130px] max-w-full sm:max-w-[190px] text-xs bg-background hover:bg-muted/40 border border-border/80 rounded-xl pl-7 pr-7 py-1.5 text-foreground font-semibold appearance-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary cursor-pointer transition-all shadow-xs truncate"
                  >
                    <option value="all">All Localities ({metrics.total})</option>
                    {localitiesList.map((loc) => {
                      const name = typeof loc === 'string' ? loc : loc.name
                      const count = typeof loc === 'string' ? '' : ` (${loc.count})`
                      return (
                        <option key={name} value={name}>
                          {name}{count}
                        </option>
                      )
                    })}
                  </select>
                  <ChevronDown className="w-3.5 h-3.5 text-muted-foreground pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 z-10" />
                </div>

                {/* City Dropdown */}
                {citiesList.length > 0 && (
                  <div className="relative flex-1 sm:flex-initial">
                    <Building2 className="w-3.5 h-3.5 text-muted-foreground pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 z-10" />
                    <select
                      value={selectedCity}
                      onChange={(e) => setSelectedCity(e.target.value)}
                      className="w-full sm:w-auto min-w-[110px] max-w-full sm:max-w-[160px] text-xs bg-background hover:bg-muted/40 border border-border/80 rounded-xl pl-7 pr-7 py-1.5 text-foreground font-semibold appearance-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary cursor-pointer transition-all shadow-xs truncate"
                    >
                      <option value="all">All Cities</option>
                      {citiesList.map((c) => {
                        const name = typeof c === 'string' ? c : c.name
                        const count = typeof c === 'string' ? '' : ` (${c.count})`
                        return (
                          <option key={name} value={name}>
                            {name}{count}
                          </option>
                        )
                      })}
                    </select>
                    <ChevronDown className="w-3.5 h-3.5 text-muted-foreground pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 z-10" />
                  </div>
                )}
              </div>
            </div>

            {/* Scrollable Locality Chips with Scroll Arrows */}
            <div className="relative flex items-center mt-2.5">
              <button
                type="button"
                onClick={() => scrollLocalities('left')}
                className="hidden sm:flex items-center justify-center w-6 h-6 rounded-full bg-background/90 backdrop-blur border border-border/80 shadow-xs text-muted-foreground hover:text-foreground hover:bg-background absolute -left-1 z-10 transition-all"
                title="Scroll left"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>

              <div
                ref={localityScrollRef}
                className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-1 px-0.5 sm:px-5 w-full scroll-smooth"
              >
                {/* All Localities Pill */}
                <button
                  type="button"
                  onClick={() => handleSelectLocality('all')}
                  className={cn(
                    'px-3 py-1 rounded-xl text-xs font-semibold whitespace-nowrap transition-all flex-shrink-0 flex items-center gap-1.5 border shadow-2xs',
                    selectedLocality === 'all'
                      ? 'bg-primary text-primary-foreground border-primary shadow-primary/20'
                      : 'bg-background border-border/70 text-foreground hover:bg-muted hover:border-border'
                  )}
                >
                  <span>All Localities</span>
                  <span className={cn(
                    'text-[10px] px-1.5 py-0.2 rounded-full font-bold',
                    selectedLocality === 'all' ? 'bg-white/20 text-white' : 'bg-muted text-muted-foreground'
                  )}>
                    {metrics.total}
                  </span>
                </button>

                {/* Individual Locality Chips */}
                {localitiesList.slice(0, 35).map((loc) => {
                  const locName = typeof loc === 'string' ? loc : loc.name
                  const locCount = typeof loc === 'string' ? null : loc.count
                  const isSelected = selectedLocality.toLowerCase() === locName.toLowerCase()

                  return (
                    <button
                      key={locName}
                      type="button"
                      onClick={() => handleSelectLocality(isSelected ? 'all' : locName)}
                      className={cn(
                        'px-2.5 py-1 rounded-xl text-xs font-semibold whitespace-nowrap transition-all flex-shrink-0 flex items-center gap-1.5 border shadow-2xs',
                        isSelected
                          ? 'bg-primary text-primary-foreground border-primary shadow-primary/20 ring-2 ring-primary/20'
                          : 'bg-background border-border/70 text-foreground hover:bg-muted hover:border-border'
                      )}
                    >
                      <MapPin className={cn('w-3 h-3', isSelected ? 'text-white' : 'text-primary')} />
                      <span>{locName}</span>
                      {locCount !== null && (
                        <span className={cn(
                          'text-[10px] px-1.5 py-0.2 rounded-full font-bold',
                          isSelected ? 'bg-white/20 text-white' : 'bg-muted text-muted-foreground'
                        )}>
                          {locCount}
                        </span>
                      )}
                      {isSelected && <X className="w-3 h-3 ml-0.5 hover:text-rose-200" />}
                    </button>
                  )
                })}
              </div>

              <button
                type="button"
                onClick={() => scrollLocalities('right')}
                className="hidden sm:flex items-center justify-center w-6 h-6 rounded-full bg-background/90 backdrop-blur border border-border/80 shadow-xs text-muted-foreground hover:text-foreground hover:bg-background absolute -right-1 z-10 transition-all"
                title="Scroll right"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* 2. SEARCH & CONTROLS ROW */}
          <div className="p-4 space-y-3">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
              {/* Main search input */}
              <form onSubmit={handleSearchSubmit} className="flex gap-2 flex-1 max-w-xl">
                <div className="relative flex-1">
                  <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search by shop name, contact, phone, locality..."
                    className="w-full pl-10 pr-4 py-2 rounded-xl bg-background border border-border text-xs sm:text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all"
                  />
                  {search && (
                    <button
                      type="button"
                      onClick={() => setSearch('')}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <button
                  type="submit"
                  className="px-3.5 py-2 rounded-xl bg-primary/10 text-primary hover:bg-primary/20 text-xs sm:text-sm font-semibold transition-colors flex items-center gap-1.5"
                >
                  <span>Search</span>
                </button>
              </form>

              {/* View Mode Toggle */}
              <div className="flex items-center justify-end gap-2">
                <div className="flex items-center bg-muted/60 p-0.5 rounded-xl border border-border">
                  <button
                    type="button"
                    onClick={() => setViewMode('list')}
                    className={cn(
                      'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                      viewMode === 'list'
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                    )}
                    title="List View"
                  >
                    <LayoutList className="w-3.5 h-3.5" />
                    <span>List</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('grid')}
                    className={cn(
                      'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                      viewMode === 'grid'
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                    )}
                    title="Grid View"
                  >
                    <LayoutGrid className="w-3.5 h-3.5" />
                    <span>Grid</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('route')}
                    className={cn(
                      'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all',
                      viewMode === 'route'
                        ? 'bg-primary text-primary-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                    )}
                    title="Route Planner View (Sequenced stops)"
                  >
                    <Milestone className="w-3.5 h-3.5" />
                    <span>Route</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Quick Intelligence Filter Strips (Radius, Recency, Health) */}
            <div className="pt-2 border-t border-border/60 space-y-2">
              {/* Radius / Distance Filter */}
              <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-0.5 text-xs">
                <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider whitespace-nowrap flex items-center gap-1 mr-1">
                  <Radio className="w-3 h-3 text-primary" />
                  Near Me:
                </span>
                {[
                  { label: 'All', val: null },
                  { label: '<500m', val: 0.5 },
                  { label: '<1km', val: 1.0 },
                  { label: '<3km', val: 3.0 },
                  { label: '<5km', val: 5.0 },
                ].map((r) => {
                  const isActive = selectedRadius === r.val
                  return (
                    <button
                      key={r.label}
                      type="button"
                      onClick={() => {
                        setSelectedRadius(r.val)
                        if (r.val !== null && !myCoords) {
                          handleGetLocation()
                        }
                      }}
                      className={cn(
                        'px-2.5 py-1 rounded-lg font-semibold whitespace-nowrap transition-all text-xs border',
                        isActive
                          ? 'bg-emerald-600 text-white border-emerald-600 shadow-sm'
                          : 'bg-background border-border text-foreground hover:bg-muted'
                      )}
                    >
                      {r.label}
                    </button>
                  )
                })}
              </div>

              {/* Recency Filter */}
              <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-0.5 text-xs">
                <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider whitespace-nowrap flex items-center gap-1 mr-1">
                  <Clock className="w-3 h-3 text-primary" />
                  Recency:
                </span>
                {[
                  { label: 'All', val: 'all' },
                  { label: 'Visited ≤7d', val: 'recent' },
                  { label: 'Due Soon (8-14d)', val: 'due_soon' },
                  { label: 'Overdue (>14d)', val: 'overdue' },
                  { label: 'Critical (>30d)', val: 'critical' },
                  { label: 'Never Visited', val: 'never' },
                ].map((item) => {
                  const isActive = selectedRecency === item.val
                  return (
                    <button
                      key={item.val}
                      type="button"
                      onClick={() => setSelectedRecency(item.val)}
                      className={cn(
                        'px-2.5 py-1 rounded-lg font-semibold whitespace-nowrap transition-all text-xs border',
                        isActive
                          ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                          : 'bg-background border-border text-foreground hover:bg-muted'
                      )}
                    >
                      {item.label}
                    </button>
                  )
                })}
              </div>

              {/* Health Score Filter */}
              <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-0.5 text-xs">
                <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider whitespace-nowrap flex items-center gap-1 mr-1">
                  <HeartPulse className="w-3 h-3 text-primary" />
                  Health:
                </span>
                {[
                  { label: 'All', val: 'all' },
                  { label: '🟢 Healthy (80+)', val: 'healthy' },
                  { label: '🟡 Fair (50-79)', val: 'fair' },
                  { label: '🔴 At Risk (<50)', val: 'at_risk' },
                ].map((item) => {
                  const isActive = selectedHealthGrade === item.val
                  return (
                    <button
                      key={item.val}
                      type="button"
                      onClick={() => setSelectedHealthGrade(item.val)}
                      className={cn(
                        'px-2.5 py-1 rounded-lg font-semibold whitespace-nowrap transition-all text-xs border',
                        isActive
                          ? 'bg-violet-600 text-white border-violet-600 shadow-sm'
                          : 'bg-background border-border text-foreground hover:bg-muted'
                      )}
                    >
                      {item.label}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* 3. DEDICATED SORT OPTIONS TOOLBAR */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border/60">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider mr-1 flex items-center gap-1">
                  <ArrowUpDown className="w-3.5 h-3.5 text-primary" />
                  Sort:
                </span>

                {/* Quick Sort Button: Name (A-Z / Z-A) */}
                <button
                  type="button"
                  onClick={handleToggleNameSort}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all shadow-sm',
                    sortBy === 'name_asc' || sortBy === 'name_desc'
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background border-border text-foreground hover:bg-muted'
                  )}
                  title="Toggle alphabetical sort"
                >
                  <span>🔤 Name</span>
                  {sortBy === 'name_asc' && <ArrowUp className="w-3 h-3" />}
                  {sortBy === 'name_desc' && <ArrowDown className="w-3 h-3" />}
                  {sortBy !== 'name_asc' && sortBy !== 'name_desc' && <span className="text-[10px] opacity-70">A-Z</span>}
                </button>

                {/* Quick Sort Button: Near to Me (GPS) */}
                <button
                  type="button"
                  onClick={() => handleSortChange('nearest')}
                  disabled={geoLocating}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all shadow-sm',
                    sortBy === 'nearest'
                      ? 'bg-emerald-600 text-white border-emerald-600 shadow-emerald-500/20'
                      : 'bg-background border-border text-foreground hover:bg-muted'
                  )}
                  title="Sort shops nearest to your current location"
                >
                  {geoLocating ? (
                    <RefreshCw className="w-3 h-3 animate-spin" />
                  ) : (
                    <Compass className="w-3.5 h-3.5 text-emerald-400" />
                  )}
                  <span>Near to Me</span>
                  {sortBy === 'nearest' && myCoords && (
                    <span className="text-[10px] px-1 py-0.2 rounded bg-white/20 font-mono">
                      GPS Active
                    </span>
                  )}
                </button>

                {/* Quick Sort Button: Health High */}
                <button
                  type="button"
                  onClick={() => handleSortChange('health_desc')}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all shadow-sm hidden md:flex',
                    sortBy === 'health_desc'
                      ? 'bg-violet-600 text-white border-violet-600'
                      : 'bg-background border-border text-foreground hover:bg-muted'
                  )}
                  title="Highest Health Score first"
                >
                  <HeartPulse className="w-3.5 h-3.5 text-violet-400" />
                  <span>Top Health</span>
                </button>

                {/* Quick Sort Button: Needs GPS Tag */}
                <button
                  type="button"
                  onClick={() => handleSortChange('missing_gps')}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all shadow-sm',
                    sortBy === 'missing_gps'
                      ? 'bg-amber-600 text-white border-amber-600'
                      : 'bg-background border-border text-foreground hover:bg-muted'
                  )}
                  title="Show customers without GPS coordinates first"
                >
                  <AlertTriangle className="w-3 h-3 text-amber-400" />
                  <span>Needs GPS First</span>
                </button>

                {/* Quick Sort Button: Recently Visited */}
                <button
                  type="button"
                  onClick={() => handleSortChange('last_visited')}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all shadow-sm hidden sm:flex',
                    sortBy === 'last_visited'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-background border-border text-foreground hover:bg-muted'
                  )}
                  title="Recently visited check-ins first"
                >
                  <Clock className="w-3 h-3 text-blue-400" />
                  <span>Recently Visited</span>
                </button>
              </div>

              {/* More Sort Dropdown + Audit Filter */}
              <div className="flex items-center gap-2 ml-auto">
                {/* Audit Status Filter */}
                <div className="relative">
                  <select
                    value={verificationFilter}
                    onChange={(e) => setVerificationFilter(e.target.value)}
                    className="text-xs bg-background border border-border rounded-xl px-2.5 py-1.5 text-foreground appearance-none focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
                  >
                    <option value="all">🛡️ Audit: All</option>
                    <option value="verified">✅ Verified (≤75m)</option>
                    <option value="nearby">📍 Nearby (75-250m)</option>
                    <option value="mismatch">🚨 Mismatch (&gt;250m)</option>
                  </select>
                </div>

                {/* Comprehensive Sort Dropdown */}
                <div className="relative">
                  <select
                    value={sortBy}
                    onChange={(e) => handleSortChange(e.target.value)}
                    className="text-xs bg-background border border-border rounded-xl pl-2.5 pr-7 py-1.5 text-foreground font-semibold appearance-none focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer shadow-sm"
                  >
                    <option value="name_asc">🔤 Name (A → Z)</option>
                    <option value="name_desc">🔤 Name (Z → A)</option>
                    <option value="nearest">🧭 Nearest to Me (GPS)</option>
                    <option value="health_desc">💚 Health Score (Highest)</option>
                    <option value="health_asc">💔 Health Score (Lowest)</option>
                    <option value="missing_gps">📍 Needs GPS Tag First</option>
                    <option value="last_visited">🕒 Recently Visited</option>
                  </select>
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground text-[10px]">▼</div>
                </div>

                {/* Recalibrate GPS button */}
                {myCoords && (
                  <button
                    type="button"
                    onClick={handleGetLocation}
                    disabled={geoLocating}
                    className="p-1.5 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 transition-all"
                    title={`Recalibrate GPS (${myCoords.lat.toFixed(4)}, ${myCoords.lon.toFixed(4)})`}
                  >
                    <RefreshCw className={cn('w-3.5 h-3.5', geoLocating && 'animate-spin')} />
                  </button>
                )}
              </div>
            </div>

          </div>

          {/* 4. ACTIVE FILTER BADGES BAR */}
          {(selectedLocality !== 'all' || selectedCity !== 'all' || selectedRoute !== 'all' || verificationFilter !== 'all' || selectedRadius !== null || selectedRecency !== 'all' || selectedHealthGrade !== 'all' || sortBy !== 'name_asc' || search || myCoords) && (
            <div className="flex items-center justify-between text-xs bg-muted/30 px-4 py-2 text-muted-foreground">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-semibold text-foreground">Active:</span>
                {selectedLocality !== 'all' && (
                  <button
                    onClick={() => handleSelectLocality('all')}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-primary/10 text-primary font-semibold hover:bg-primary/20 transition-colors"
                  >
                    <span>📍 {selectedLocality}</span>
                    <X className="w-3 h-3" />
                  </button>
                )}
                {selectedCity !== 'all' && (
                  <button
                    onClick={() => setSelectedCity('all')}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-secondary text-secondary-foreground font-semibold hover:bg-muted transition-colors"
                  >
                    <span>🏙️ {selectedCity}</span>
                    <X className="w-3 h-3" />
                  </button>
                )}
                {selectedRadius !== null && (
                  <button
                    onClick={() => setSelectedRadius(null)}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-semibold hover:bg-emerald-500/25 transition-colors"
                  >
                    <span>🎯 &lt;{selectedRadius}km Radius</span>
                    <X className="w-3 h-3" />
                  </button>
                )}
                {selectedRecency !== 'all' && (
                  <button
                    onClick={() => setSelectedRecency('all')}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-blue-500/15 text-blue-700 dark:text-blue-300 font-semibold hover:bg-blue-500/25 transition-colors"
                  >
                    <span>🕒 Recency: {selectedRecency}</span>
                    <X className="w-3 h-3" />
                  </button>
                )}
                {selectedHealthGrade !== 'all' && (
                  <button
                    onClick={() => setSelectedHealthGrade('all')}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-violet-500/15 text-violet-700 dark:text-violet-300 font-semibold hover:bg-violet-500/25 transition-colors"
                  >
                    <span>💚 Health: {selectedHealthGrade}</span>
                    <X className="w-3 h-3" />
                  </button>
                )}
                {sortBy !== 'name_asc' && (
                  <button
                    onClick={() => handleSortChange('name_asc')}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-muted text-foreground font-semibold hover:bg-muted/80 transition-colors"
                  >
                    <span>
                      Sorted: {sortBy === 'nearest' ? 'Nearest to Me' : sortBy === 'name_desc' ? 'Name (Z→A)' : sortBy === 'health_desc' ? 'Top Health' : sortBy === 'health_asc' ? 'Low Health' : sortBy === 'missing_gps' ? 'Needs GPS First' : sortBy === 'last_visited' ? 'Recently Visited' : sortBy}
                    </span>
                    <X className="w-3 h-3" />
                  </button>
                )}
                {myCoords && (
                  <span className="text-[11px] text-emerald-600 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-lg font-mono flex items-center gap-1">
                    <Compass className="w-3 h-3" />
                    GPS: {myCoords.lat.toFixed(3)}°, {myCoords.lon.toFixed(3)}°
                  </span>
                )}
                {search && (
                  <button
                    onClick={() => setSearch('')}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-muted text-foreground font-medium hover:bg-muted/80 transition-colors"
                  >
                    <span>Search: &quot;{search}&quot;</span>
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>

              <button
                type="button"
                onClick={() => {
                  setSelectedLocality('all')
                  setSelectedCity('all')
                  setSelectedRoute('all')
                  setVerificationFilter('all')
                  setSelectedRadius(null)
                  setSelectedRecency('all')
                  setSelectedHealthGrade('all')
                  setSortBy('name_asc')
                  setSearch('')
                }}
                className="text-primary hover:underline font-semibold flex items-center gap-1 ml-2 flex-shrink-0 text-xs"
              >
                <X className="w-3.5 h-3.5" />
                <span>Reset All</span>
              </button>
            </div>
          )}

        </div>
      </div>

      {/* Customer Directory List / Grid Container */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div className="space-y-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <p className="text-sm font-medium">Loading customer directory & GPS logs...</p>
            </div>
          ) : customers.length === 0 ? (
            <div className="bg-card border border-border rounded-2xl p-12 text-center shadow-sm">
              <Users className="w-12 h-12 text-muted-foreground/50 mx-auto mb-3" />
              <h3 className="text-lg font-bold">No customers found</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
                No customers match your current search or filter criteria. Try clearing the filters or add a new customer.
              </p>
              <button
                onClick={() => {
                  setSearch('')
                  setSelectedLocality('all')
                  setSelectedCity('all')
                  setSelectedRoute('all')
                  setLocationFilter('all')
                  setVerificationFilter('all')
                }}
                className="mt-4 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-semibold"
              >
                Reset All Filters
              </button>
            </div>
          ) : viewMode === 'list' ? (
            /* ─── LIST VIEW (Table on Desktop, Compact Row Cards on Mobile) ─── */
            <div className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden">
              {/* Desktop Table View */}
              <div className="hidden md:block w-full overflow-x-auto">
                <table className="w-full table-fixed text-left text-xs">
                  <thead className="bg-muted/60 text-muted-foreground border-b border-border font-semibold uppercase tracking-wider text-[11px]">
                    <tr>
                      <th
                        onClick={handleToggleNameSort}
                        className="w-[26%] py-3.5 px-3.5 cursor-pointer hover:text-foreground transition-colors group select-none"
                        title="Click to toggle Name sort"
                      >
                        <div className="flex items-center gap-1.5">
                          <span>Customer & Shop</span>
                          {sortBy === 'name_asc' ? (
                            <ArrowUp className="w-3.5 h-3.5 text-primary shrink-0" />
                          ) : sortBy === 'name_desc' ? (
                            <ArrowDown className="w-3.5 h-3.5 text-primary shrink-0" />
                          ) : (
                            <ArrowUpDown className="w-3 h-3 opacity-40 group-hover:opacity-100 shrink-0" />
                          )}
                        </div>
                      </th>
                      <th className="w-[24%] py-3.5 px-3.5">Locality & Address</th>
                      <th className="w-[14%] py-3.5 px-3.5">Contact</th>
                      <th
                        onClick={() => handleSortChange(sortBy === 'nearest' ? 'missing_gps' : 'nearest')}
                        className="w-[16%] py-3.5 px-3.5 cursor-pointer hover:text-foreground transition-colors group select-none"
                        title="Click to sort by Nearest / Needs GPS"
                      >
                        <div className="flex items-center gap-1.5">
                          <span>GPS & Verification</span>
                          {sortBy === 'nearest' ? (
                            <Compass className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                          ) : sortBy === 'missing_gps' ? (
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                          ) : (
                            <ArrowUpDown className="w-3 h-3 opacity-40 group-hover:opacity-100 shrink-0" />
                          )}
                        </div>
                      </th>
                      <th className="w-[20%] py-3.5 px-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {customers.map((cust) => (
                      <tr
                        key={cust.key}
                        className="hover:bg-muted/40 transition-colors group"
                      >
                        {/* 1. Customer & Shop */}
                        <td className="w-[26%] py-3 px-3.5 align-top break-words whitespace-normal">
                          <Link
                            href={`/customers/${cust.key}`}
                            className="font-bold text-sm text-foreground group-hover:text-primary transition-colors hover:underline break-words whitespace-normal block"
                          >
                            {cust.name}
                          </Link>
                          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                            {renderHealthPill(cust)}
                            {renderRecencyBadge(cust)}
                          </div>
                          {Boolean(cust.contact_person || (cust.owners_count && cust.owners_count > 0)) ? (
                            <div className="text-muted-foreground text-[11px] mt-1 flex items-center gap-1.5 flex-wrap break-words whitespace-normal">
                              <span>Attn: <span className="text-foreground font-medium">{cust.contact_person || cust.owners?.[0]?.name}</span></span>
                              {cust.owners_count && cust.owners_count > 1 ? (
                                <span
                                  className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold text-[10px]"
                                  title={cust.owners?.map(o => `${o.name} (${o.designation || 'Owner'})`).join(', ')}
                                >
                                  <Users className="w-2.5 h-2.5 shrink-0" />
                                  +{cust.owners_count - 1} partner{cust.owners_count - 1 > 1 ? 's' : ''}
                                </span>
                              ) : null}
                            </div>
                          ) : null}
                          {cust.distance_from_me_meters !== null && (
                            <div className="text-emerald-600 font-semibold text-[11px] mt-0.5 flex items-center gap-1">
                              <Compass className="w-3 h-3 shrink-0" />
                              <span>{(cust.distance_from_me_meters / 1000).toFixed(1)} km away</span>
                            </div>
                          )}
                        </td>

                        {/* 2. Locality & Address */}
                        <td className="w-[24%] py-3 px-3.5 align-top break-words whitespace-normal">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {cust.locality ? (
                              <span className="inline-flex items-center gap-1 font-semibold text-foreground bg-muted px-2 py-0.5 rounded-md text-[11px]">
                                <MapPin className="w-3 h-3 text-primary shrink-0" />
                                <span>{cust.locality}</span>
                              </span>
                            ) : (
                              <span className="text-muted-foreground italic text-[11px]">No locality</span>
                            )}
                            {cust.city && (
                              <span className="text-muted-foreground text-[11px]">{cust.city}</span>
                            )}
                          </div>
                          {cust.address && (
                            <p className="text-muted-foreground text-[11px] mt-1 break-words whitespace-normal leading-relaxed" title={cust.address}>
                              {cust.address}
                            </p>
                          )}
                        </td>

                        {/* 3. Contact */}
                        <td className="w-[14%] py-3 px-3.5 align-top break-words whitespace-normal">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {(cust.phone || cust.mobile) ? (
                              <a
                                href={`tel:${cust.phone || cust.mobile}`}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-muted hover:bg-muted/80 text-foreground text-xs font-medium transition-colors break-all"
                                title="Call customer"
                              >
                                <Phone className="w-3 h-3 text-primary shrink-0" />
                                <span>{cust.phone || cust.mobile}</span>
                              </a>
                            ) : (
                              <span className="text-muted-foreground italic text-[11px]">No phone</span>
                            )}
                            {cust.whatsapp_number && (
                              <a
                                href={`https://wa.me/${cust.whatsapp_number.replace(/\D/g, '')}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="p-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 transition-colors shrink-0"
                                title="WhatsApp"
                              >
                                <MessageCircle className="w-3.5 h-3.5" />
                              </a>
                            )}
                          </div>
                        </td>

                        {/* 4. GPS & Verification */}
                        <td className="w-[16%] py-3 px-3.5 align-top break-words whitespace-normal">
                          <div className="space-y-1 break-words whitespace-normal">
                            <div>{renderVerificationBadge(cust)}</div>
                            {cust.has_location ? (
                              <button
                                onClick={() => handleOpenTag(cust)}
                                className="text-[10px] text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 break-all"
                                title="Recalibrate shop coordinates"
                              >
                                <Compass className="w-2.5 h-2.5 shrink-0" />
                                <span>{cust.latitude?.toFixed(4)}, {cust.longitude?.toFixed(4)}</span>
                              </button>
                            ) : (
                              <button
                                onClick={() => handleOpenTag(cust)}
                                className="text-[10px] text-amber-600 hover:text-amber-700 font-semibold flex items-center gap-1"
                              >
                                <Plus className="w-2.5 h-2.5 shrink-0" />
                                <span>Tag GPS</span>
                              </button>
                            )}
                          </div>
                        </td>

                        {/* 5. Actions */}
                        <td className="w-[20%] py-3 px-3.5 align-top text-right">
                          <div className="flex items-center justify-end gap-1 flex-wrap">
                            <a
                              href={cust.maps_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={cn(
                                'inline-flex items-center gap-1 p-1.5 rounded-lg text-xs font-bold transition-all shadow-sm shrink-0',
                                cust.has_location
                                  ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
                              )}
                              title={cust.has_location ? 'Open directions in Google Maps' : 'Search on Google Maps'}
                            >
                              <Navigation className="w-3.5 h-3.5" />
                              <span className="hidden 2xl:inline">{cust.has_location ? 'Navigate' : 'Search'}</span>
                            </a>

                            <Link
                              href={cust.ledger_id ? `/check-in?ledger_id=${cust.ledger_id}` : `/check-in?profile_id=${cust.profile_id}&name=${encodeURIComponent(cust.name)}`}
                              className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 transition-colors text-xs font-semibold shrink-0"
                              title="1-Tap Check-In at this shop"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span className="hidden xl:inline">Check In</span>
                            </Link>

                            <button
                              onClick={() => handleOpenHistory(cust)}
                              className="p-1.5 rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-colors shrink-0"
                              title="View GPS check-in audit history"
                            >
                              <History className="w-3.5 h-3.5" />
                            </button>

                            <Link
                              href={`/customers/${cust.key}`}
                              className="p-1.5 rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-colors shrink-0"
                              title="View full customer profile & photos"
                            >
                              <UserIcon className="w-3.5 h-3.5" />
                            </Link>

                            <button
                              onClick={() => handleOpenEdit(cust)}
                              className="p-1.5 rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-colors shrink-0"
                              title="Edit locality, contact, or notes"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>

                            {/* Link to Tally Ledger (Admin only, unmapped customers only) */}
                            {isAdmin && !cust.ledger_id && (
                              <button
                                onClick={() => handleOpenLinkLedger(cust)}
                                className="p-1.5 xl:px-2 xl:py-1.5 rounded-lg border border-primary/40 bg-primary/10 hover:bg-primary/20 text-primary transition-colors flex items-center gap-1 text-xs font-semibold shrink-0"
                                title="Admin Only: Link this shop to a Tally Ledger"
                              >
                                <Link2 className="w-3.5 h-3.5" />
                                <span className="hidden 2xl:inline">Link Ledger</span>
                              </button>
                            )}

                            {/* Delete Wrong Tagging (Only for unmapped leads) */}
                            {!cust.ledger_id && (
                              <button
                                onClick={() => setCustomerToDelete(cust)}
                                className="p-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 transition-colors shrink-0"
                                title="Delete wrongly tagged customer lead"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile Compact List Rows */}
              <div className="md:hidden divide-y divide-border">
                {customers.map((cust) => (
                  <div key={cust.key} className="p-3.5 space-y-2 hover:bg-muted/50 transition-colors even:bg-primary/5 dark:even:bg-primary/10">
                    {/* Top Row: Shop Name + Distance */}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <Link
                          href={`/customers/${cust.key}`}
                          className="font-bold text-sm text-foreground hover:text-primary transition-colors line-clamp-1 flex items-center gap-1.5"
                        >
                          <span>{cust.name}</span>
                          <UserIcon className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                        </Link>
                        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                          {renderHealthPill(cust)}
                          {renderRecencyBadge(cust)}
                        </div>
                        {Boolean(cust.contact_person || (cust.owners_count && cust.owners_count > 0)) ? (
                          <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 flex-wrap mt-1">
                            <span>Attn: <span className="font-medium text-foreground">{cust.contact_person || cust.owners?.[0]?.name}</span></span>
                            {cust.owners_count && cust.owners_count > 1 ? (
                              <span
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold text-[10px]"
                                title={cust.owners?.map(o => `${o.name} (${o.designation || 'Owner'})`).join(', ')}
                              >
                                <Users className="w-2.5 h-2.5" />
                                +{cust.owners_count - 1} partner{cust.owners_count - 1 > 1 ? 's' : ''}
                              </span>
                            ) : null}
                          </div>
                        ) : null}
                      </div>

                      {cust.distance_from_me_meters !== null && (
                        <span className="text-[11px] font-semibold text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-md flex-shrink-0 flex items-center gap-1">
                          <Compass className="w-3 h-3" />
                          <span>{(cust.distance_from_me_meters / 1000).toFixed(1)} km</span>
                        </span>
                      )}
                    </div>

                    {/* Middle: Locality & Address */}
                    <div className="flex items-center gap-1.5 flex-wrap text-xs">
                      {cust.locality && (
                        <span className="inline-flex items-center gap-1 font-semibold text-foreground bg-muted px-1.5 py-0.5 rounded text-[11px]">
                          <MapPin className="w-3 h-3 text-primary" />
                          {cust.locality}
                        </span>
                      )}
                      {cust.address && (
                        <span className="text-muted-foreground text-[11px] truncate max-w-[240px]">
                          {cust.address}
                        </span>
                      )}
                    </div>

                    {/* Bottom Row: Verification Badge + Actions */}
                    <div className="flex flex-col gap-2 pt-2 border-t border-border/50">
                      <div>{renderVerificationBadge(cust)}</div>

                      <div className="flex flex-wrap items-center justify-end gap-1.5">
                        {(cust.phone || cust.mobile) && (
                          <a
                            href={`tel:${cust.phone || cust.mobile}`}
                            className="p-1.5 rounded-lg bg-muted text-foreground hover:bg-muted/80"
                            title="Call"
                          >
                            <Phone className="w-3.5 h-3.5 text-primary" />
                          </a>
                        )}
                        {cust.whatsapp_number && (
                          <a
                            href={`https://wa.me/${cust.whatsapp_number.replace(/\D/g, '')}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20"
                            title="WhatsApp"
                          >
                            <MessageCircle className="w-3.5 h-3.5" />
                          </a>
                        )}
                        <a
                          href={cust.maps_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-bold"
                        >
                          <Navigation className="w-3 h-3" />
                          <span>Navigate</span>
                        </a>
                        <Link
                          href={cust.ledger_id ? `/check-in?ledger_id=${cust.ledger_id}` : `/check-in?profile_id=${cust.profile_id}&name=${encodeURIComponent(cust.name)}`}
                          className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 text-xs font-bold"
                          title="1-Tap Check In"
                        >
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Check In</span>
                        </Link>
                        <Link
                          href={`/customers/${cust.key}`}
                          className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-primary hover:bg-muted/50 transition-colors"
                          title="View 360° Profile & Photos"
                        >
                          <UserIcon className="w-3.5 h-3.5" />
                        </Link>
                        <button
                          onClick={() => handleOpenHistory(cust)}
                          className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground"
                          title="View GPS history"
                        >
                          <History className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleOpenEdit(cust)}
                          className="p-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground"
                          title="Edit details"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>

                        {/* Link to Tally Ledger (Admin only, unmapped customers only) */}
                        {isAdmin && !cust.ledger_id && (
                          <button
                            onClick={() => handleOpenLinkLedger(cust)}
                            className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 transition-colors text-xs font-semibold"
                            title="Admin Only: Link this shop to a Tally Ledger"
                          >
                            <Link2 className="w-3.5 h-3.5" />
                            <span>Link</span>
                          </button>
                        )}

                        {/* Delete Wrong Tagging (Only for unmapped leads) */}
                        {!cust.ledger_id && (
                          <button
                            onClick={() => setCustomerToDelete(cust)}
                            className="p-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 transition-colors"
                            title="Delete wrongly tagged customer lead"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : viewMode === 'route' ? (
            /* ─── ROUTE PLANNER VIEW (Sequenced stops, TSP Nearest-Neighbor) ─── */
            <div className="space-y-4">
              {/* Route Controls & Beat Selector Banner */}
              <div className="bg-card border border-border rounded-2xl p-4 sm:p-5 shadow-sm space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="p-2 rounded-xl bg-primary/10 text-primary">
                      <Milestone className="w-5 h-5" />
                    </span>
                    <div>
                      <h2 className="text-base font-bold text-foreground flex items-center gap-2">
                        <span>Route Planner & Beat Optimizer</span>
                        <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-primary/10 text-primary border border-primary/20">
                          Automated TSP Sequence
                        </span>
                      </h2>
                      <p className="text-xs text-muted-foreground">
                        Nearest-neighbor route planning starting from your current GPS location
                      </p>
                    </div>
                  </div>

                  {/* Beat / Route Filter Dropdown */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-muted-foreground whitespace-nowrap">Beat:</span>
                    <div className="relative min-w-[160px]">
                      <select
                        value={plannerRoute}
                        onChange={(e) => setPlannerRoute(e.target.value)}
                        className="w-full text-xs bg-background border border-border rounded-xl pl-3 pr-8 py-2 text-foreground font-semibold appearance-none focus:outline-none focus:ring-1 focus:ring-primary shadow-sm"
                      >
                        <option value="all">🗺️ All Routes ({customers.filter(c => c.has_location).length} GPS shops)</option>
                        {routesList.map((r) => (
                          <option key={r} value={r}>
                            📍 {r}
                          </option>
                        ))}
                      </select>
                      <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground text-[10px]">▼</div>
                    </div>
                  </div>
                </div>

                {/* Route Metrics Summary Cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-border">
                  <div className="p-3 rounded-xl bg-muted/40 border border-border">
                    <div className="text-[11px] font-semibold text-muted-foreground flex items-center justify-between">
                      <span>Total Stops</span>
                      <MapPin className="w-3.5 h-3.5 text-primary" />
                    </div>
                    <div className="text-xl font-bold text-foreground mt-1">{routeMetrics.totalStops}</div>
                    <div className="text-[10px] text-muted-foreground">Mapped destinations</div>
                  </div>

                  <div className="p-3 rounded-xl bg-muted/40 border border-border">
                    <div className="text-[11px] font-semibold text-muted-foreground flex items-center justify-between">
                      <span>Estimated Tour</span>
                      <Navigation className="w-3.5 h-3.5 text-blue-500" />
                    </div>
                    <div className="text-xl font-bold text-blue-600 mt-1">{routeMetrics.totalDistanceKm} km</div>
                    <div className="text-[10px] text-muted-foreground">Total road distance</div>
                  </div>

                  <div className="p-3 rounded-xl bg-muted/40 border border-border">
                    <div className="text-[11px] font-semibold text-muted-foreground flex items-center justify-between">
                      <span>Visited Today</span>
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    </div>
                    <div className="text-xl font-bold text-emerald-600 mt-1">{routeMetrics.visitedToday}</div>
                    <div className="text-[10px] text-emerald-600 font-medium">Check-ins completed</div>
                  </div>

                  <div className="p-3 rounded-xl bg-muted/40 border border-border">
                    <div className="text-[11px] font-semibold text-muted-foreground flex items-center justify-between">
                      <span>Remaining</span>
                      <Clock className="w-3.5 h-3.5 text-amber-500" />
                    </div>
                    <div className="text-xl font-bold text-amber-600 mt-1">{routeMetrics.pendingVisits}</div>
                    <div className="text-[10px] text-muted-foreground">Pending stops today</div>
                  </div>
                </div>
              </div>

              {/* Sequenced Route Stops List */}
              {routeStops.length === 0 ? (
                <div className="bg-card border border-border rounded-2xl p-12 text-center shadow-sm">
                  <Milestone className="w-12 h-12 text-muted-foreground/40 mx-auto mb-3" />
                  <h3 className="text-base font-bold text-foreground">No GPS-Tagged Customers on This Route</h3>
                  <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                    To generate an optimized route plan, customers need GPS coordinates. Please tag customer shop coordinates or switch to "All Routes".
                  </p>
                  <button
                    onClick={() => setPlannerRoute('all')}
                    className="mt-4 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-semibold"
                  >
                    View All Routes
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {routeStops.map((cust, idx) => (
                    <div
                      key={cust.key}
                      className={cn(
                        'bg-card border rounded-2xl p-4 sm:p-5 shadow-sm transition-all hover:shadow-md relative overflow-hidden group',
                        cust.visit_recency_category === 'today'
                          ? 'border-emerald-500/30 bg-emerald-500/[0.02]'
                          : 'border-border hover:border-primary/40'
                      )}
                    >
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        {/* Stop Sequence & Shop Details */}
                        <div className="flex items-start gap-3.5 flex-1">
                          {/* Sequence Badge */}
                          <div className={cn(
                            'w-9 h-9 sm:w-10 sm:h-10 rounded-xl font-black text-sm sm:text-base flex items-center justify-center flex-shrink-0 shadow-sm',
                            cust.visit_recency_category === 'today'
                              ? 'bg-emerald-600 text-white shadow-emerald-500/20'
                              : 'bg-primary text-primary-foreground shadow-primary/20'
                          )}>
                            #{idx + 1}
                          </div>

                          <div className="space-y-1 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <Link
                                href={`/customers/${cust.key}`}
                                className="font-bold text-base text-foreground hover:text-primary transition-colors hover:underline"
                              >
                                {cust.name}
                              </Link>
                              {cust.route_name && (
                                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground">
                                  {cust.route_name}
                                </span>
                              )}
                            </div>

                            {/* Attn & Locality */}
                            <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
                              {cust.contact_person && (
                                <span>Attn: <span className="text-foreground font-medium">{cust.contact_person}</span></span>
                              )}
                              {cust.locality && (
                                <span className="inline-flex items-center gap-1 font-semibold text-foreground bg-muted/60 px-1.5 py-0.5 rounded text-[11px]">
                                  <MapPin className="w-3 h-3 text-primary" />
                                  {cust.locality}
                                </span>
                              )}
                              {cust.address && (
                                <span className="truncate max-w-[260px] text-[11px]">{cust.address}</span>
                              )}
                            </div>

                            {/* Distance breakdown */}
                            <div className="flex items-center gap-2 text-[11px] pt-1">
                              <span className="font-semibold text-emerald-600 flex items-center gap-1">
                                <Compass className="w-3 h-3" />
                                {idx === 0
                                  ? myCoords
                                    ? `${cust.legDistanceKm.toFixed(1)} km from your location (Stop #1)`
                                    : 'Starting Stop'
                                  : `+${cust.legDistanceKm.toFixed(1)} km from Stop #${idx} (${cust.cumulativeKm.toFixed(1)} km tour cumulative)`}
                              </span>
                            </div>

                            {/* Intelligence Badges */}
                            <div className="flex items-center gap-2 pt-1 flex-wrap">
                              {renderHealthPill(cust)}
                              {renderRecencyBadge(cust)}
                              {renderVerificationBadge(cust)}
                            </div>
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center gap-2 flex-wrap justify-end pt-2 md:pt-0 border-t md:border-t-0 border-border">
                          {/* Navigate on Google Maps */}
                          <a
                            href={cust.maps_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-bold shadow-sm hover:bg-primary/90 transition-all"
                          >
                            <Navigation className="w-3.5 h-3.5" />
                            <span>Navigate</span>
                          </a>

                          {/* 1-Tap Check In */}
                          <Link
                            href={cust.ledger_id ? `/check-in?ledger_id=${cust.ledger_id}` : `/check-in?profile_id=${cust.profile_id}&name=${encodeURIComponent(cust.name)}`}
                            className={cn(
                              'inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border shadow-sm transition-all',
                              cust.visit_recency_category === 'today'
                                ? 'bg-emerald-600/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 hover:bg-emerald-600/20'
                                : 'bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700 shadow-emerald-500/20'
                            )}
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>{cust.visit_recency_category === 'today' ? 'Checked In ✓' : 'Check In'}</span>
                          </Link>

                          {/* Call */}
                          {(cust.phone || cust.mobile) && (
                            <a
                              href={`tel:${cust.phone || cust.mobile}`}
                              className="p-2 rounded-xl border border-border hover:bg-muted text-foreground transition-colors"
                              title="Call"
                            >
                              <Phone className="w-4 h-4 text-primary" />
                            </a>
                          )}

                          {/* WhatsApp */}
                          {cust.whatsapp_number && (
                            <a
                              href={`https://wa.me/${cust.whatsapp_number.replace(/\D/g, '')}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 transition-colors"
                              title="WhatsApp"
                            >
                              <MessageCircle className="w-4 h-4" />
                            </a>
                          )}

                          {/* Profile */}
                          <Link
                            href={`/customers/${cust.key}`}
                            className="p-2 rounded-xl border border-border hover:bg-muted text-muted-foreground hover:text-primary transition-colors"
                            title="View Full Profile"
                          >
                            <UserIcon className="w-4 h-4" />
                          </Link>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* ─── GRID VIEW (Cards) ─── */
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {customers.map((cust) => (
                <div
                  key={cust.key}
                  className="bg-card border border-border rounded-2xl p-4 sm:p-5 shadow-sm hover:shadow-md transition-all flex flex-col justify-between group hover:border-primary/40 relative overflow-hidden"
                >
                  {/* Top Bar: Shop Name + Distance */}
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <Link
                          href={`/customers/${cust.key}`}
                          className="font-bold text-base sm:text-lg text-foreground hover:text-primary transition-colors line-clamp-1 block"
                        >
                          {cust.name}
                        </Link>
                        <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                          {renderHealthPill(cust)}
                          {renderRecencyBadge(cust)}
                        </div>
                        {Boolean(cust.contact_person || (cust.owners_count && cust.owners_count > 0)) ? (
                          <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1.5 flex-wrap">
                            <span>Attn: <span className="font-medium text-foreground">{cust.contact_person || cust.owners?.[0]?.name}</span></span>
                            {cust.owners_count && cust.owners_count > 1 ? (
                              <span
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold text-[10px]"
                                title={cust.owners?.map(o => `${o.name} (${o.designation || 'Owner'})`).join(', ')}
                              >
                                <Users className="w-2.5 h-2.5" />
                                +{cust.owners_count - 1} partner{cust.owners_count - 1 > 1 ? 's' : ''}
                              </span>
                            ) : null}
                          </p>
                        ) : null}
                      </div>

                      {cust.distance_from_me_meters !== null && (
                        <span className="text-[11px] font-semibold text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-md flex-shrink-0 flex items-center gap-1">
                          <Compass className="w-3 h-3" />
                          <span>{(cust.distance_from_me_meters / 1000).toFixed(1)} km away</span>
                        </span>
                      )}
                    </div>

                    {/* Address & Locality */}
                    <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                      {cust.locality && (
                        <div className="inline-flex items-center gap-1 font-semibold text-foreground bg-muted/60 px-2 py-0.5 rounded-md mr-1">
                          <MapPin className="w-3 h-3 text-primary" />
                          <span>{cust.locality}</span>
                          {cust.city && <span className="text-muted-foreground font-normal">, {cust.city}</span>}
                        </div>
                      )}
                      {cust.route_name && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium bg-secondary/80 text-secondary-foreground px-2 py-0.5 rounded-md">
                          Route: {cust.route_name}
                        </span>
                      )}
                      {cust.address && (
                        <p className="line-clamp-2 text-muted-foreground mt-1">
                          {cust.address}
                        </p>
                      )}
                    </div>

                    {/* Contact Channels (Phone & WhatsApp) */}
                    <div className="flex items-center gap-2 mt-3.5">
                      {(cust.phone || cust.mobile) ? (
                        <a
                          href={`tel:${cust.phone || cust.mobile}`}
                          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-muted hover:bg-muted/80 text-foreground text-xs font-medium transition-colors"
                        >
                          <Phone className="w-3.5 h-3.5 text-primary" />
                          <span>{cust.phone || cust.mobile}</span>
                        </a>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">No phone saved</span>
                      )}

                      {cust.whatsapp_number && (
                        <a
                          href={`https://wa.me/${cust.whatsapp_number.replace(/\D/g, '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 text-xs font-semibold transition-colors"
                        >
                          <MessageCircle className="w-3.5 h-3.5" />
                          <span>WhatsApp</span>
                        </a>
                      )}
                    </div>

                    {/* GPS Tag & Verification Audit Badge */}
                    <div className="mt-3 pt-2.5 border-t border-border flex items-center justify-between gap-2 flex-wrap">
                      <div>{renderVerificationBadge(cust)}</div>

                      {cust.has_location ? (
                        <button
                          onClick={() => handleOpenTag(cust)}
                          className="text-[11px] text-muted-foreground hover:text-primary transition-colors flex items-center gap-1"
                          title="Click to recalibrate shop coordinates"
                        >
                          <Compass className="w-3 h-3" />
                          <span>{cust.latitude?.toFixed(4)}, {cust.longitude?.toFixed(4)}</span>
                        </button>
                      ) : (
                        <button
                          onClick={() => handleOpenTag(cust)}
                          className="text-[11px] text-amber-600 hover:text-amber-700 font-semibold flex items-center gap-1"
                        >
                          <Plus className="w-3 h-3" />
                          <span>Tag GPS</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Card Bottom Actions */}
                  <div className="mt-4 pt-3 border-t border-border flex items-center justify-between gap-2">
                    {/* Primary Google Maps Navigation Link */}
                    <a
                      href={cust.maps_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={cn(
                        'flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold transition-all shadow-sm flex-1',
                        cust.has_location
                          ? 'bg-primary text-primary-foreground hover:bg-primary/90 hover:shadow'
                          : 'bg-muted text-muted-foreground hover:bg-muted/80'
                      )}
                    >
                      <Navigation className="w-3.5 h-3.5" />
                      <span>{cust.has_location ? 'Navigate (Maps)' : 'Search on Maps'}</span>
                      <ExternalLink className="w-3 h-3 opacity-70" />
                    </a>

                    {/* 1-Tap Check-In */}
                    <Link
                      href={cust.ledger_id ? `/check-in?ledger_id=${cust.ledger_id}` : `/check-in?profile_id=${cust.profile_id}&name=${encodeURIComponent(cust.name)}`}
                      className="p-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 transition-colors flex items-center justify-center"
                      title="1-Tap Check In at this shop"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                    </Link>

                    {/* View Profile */}
                    <Link
                      href={`/customers/${cust.key}`}
                      className="p-2 rounded-xl border border-border hover:bg-muted text-muted-foreground hover:text-primary transition-colors"
                      title="View 360° Profile & Photos"
                    >
                      <UserIcon className="w-4 h-4" />
                    </Link>

                    {/* Location Audit History button */}
                    <button
                      onClick={() => handleOpenHistory(cust)}
                      className="p-2 rounded-xl border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                      title="View GPS check-in audit history"
                    >
                      <History className="w-4 h-4" />
                    </button>

                    {/* Edit Profile button */}
                    <button
                      onClick={() => handleOpenEdit(cust)}
                      className="p-2 rounded-xl border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                      title="Edit locality, contact, or notes"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>

                    {/* Link to Tally Ledger (Admin only, unmapped customers only) */}
                    {isAdmin && !cust.ledger_id && (
                      <button
                        onClick={() => handleOpenLinkLedger(cust)}
                        className="p-2 rounded-xl border border-primary/40 bg-primary/10 hover:bg-primary/20 text-primary transition-colors flex items-center gap-1 text-xs font-semibold"
                        title="Admin Only: Link this shop to a Tally Ledger"
                      >
                        <Link2 className="w-4 h-4" />
                        <span className="hidden sm:inline">Link</span>
                      </button>
                    )}

                    {/* Delete Wrong Tagging (Only for unmapped leads) */}
                    {!cust.ledger_id && (
                      <button
                        onClick={() => setCustomerToDelete(cust)}
                        className="p-2 rounded-xl border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 transition-colors flex items-center justify-center"
                        title="Delete wrongly tagged customer lead"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ─── MODAL 1: Location Audit History ─── */}
      {showHistoryModal && selectedCustomer && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-primary" />
                  <h3 className="font-bold text-lg">GPS Check-in Audit History</h3>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">{selectedCustomer.name}</p>
              </div>
              <button
                onClick={() => setShowHistoryModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Master Shop Coordinates */}
            <div className="bg-muted/40 p-3.5 rounded-xl border border-border text-xs flex items-center justify-between">
              <div>
                <span className="font-semibold text-foreground">Established Shop Location:</span>
                <p className="text-muted-foreground mt-0.5">
                  {selectedCustomer.latitude && selectedCustomer.longitude
                    ? `📍 Lat: ${selectedCustomer.latitude}, Lon: ${selectedCustomer.longitude}`
                    : '⚠️ No established coordinates yet'}
                </p>
              </div>
              {selectedCustomer.latitude && (
                <a
                  href={`https://www.google.com/maps/search/?api=1&query=${selectedCustomer.latitude},${selectedCustomer.longitude}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-2.5 py-1 rounded-lg bg-background border border-border text-primary font-semibold hover:underline flex items-center gap-1"
                >
                  <MapPin className="w-3 h-3" />
                  <span>View Pin</span>
                </a>
              )}
            </div>

            {/* Timeline Logs List */}
            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {loadingHistory ? (
                <div className="py-12 flex flex-col items-center justify-center text-muted-foreground gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                  <span className="text-xs">Loading historical GPS check-ins...</span>
                </div>
              ) : historyLogs.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground text-xs">
                  No check-ins or location events recorded for this customer yet.
                </div>
              ) : (
                historyLogs.map((log) => (
                  <div
                    key={log.id}
                    className="p-3.5 rounded-xl border border-border bg-background space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-foreground">{log.salesperson}</span>
                        <span className="text-[10px] text-muted-foreground">
                          {log.created_at ? new Date(log.created_at).toLocaleString() : ''}
                        </span>
                      </div>

                      {log.verification_status === 'VERIFIED_ON_SITE' ? (
                        <span className="px-2 py-0.5 rounded-md font-bold text-[10px] bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                          Verified (≤75m)
                        </span>
                      ) : log.verification_status === 'NEARBY' ? (
                        <span className="px-2 py-0.5 rounded-md font-bold text-[10px] bg-amber-500/10 text-amber-600 border border-amber-500/20">
                          Nearby (75-250m)
                        </span>
                      ) : log.verification_status === 'MISMATCH_FAR' ? (
                        <span className="px-2 py-0.5 rounded-md font-bold text-[10px] bg-rose-500/10 text-rose-600 border border-rose-500/20">
                          Mismatch (&gt;250m away)
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-md font-medium text-[10px] bg-muted text-muted-foreground">
                          {log.verification_status}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-muted-foreground pt-1 border-t border-border/50">
                      <div>
                        <span>Check-in Distance from Shop: </span>
                        <strong className="text-foreground font-semibold">
                          {log.distance_from_base_meters !== null
                            ? log.distance_from_base_meters >= 1000
                              ? `${(log.distance_from_base_meters / 1000).toFixed(2)} km`
                              : `${Math.round(log.distance_from_base_meters)} meters`
                            : 'N/A'}
                        </strong>
                      </div>

                      <a
                        href={log.maps_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline font-medium flex items-center gap-1"
                      >
                        <span>Maps Coordinates</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>

                    {log.notes && (
                      <p className="text-[11px] text-muted-foreground italic bg-muted/40 p-2 rounded-lg">
                        {log.notes}
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="pt-2 border-t border-border flex justify-end">
              <button
                onClick={() => setShowHistoryModal(false)}
                className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL 2: Add New Customer (Field Profile Only) ─── */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <h3 className="font-bold text-lg">Add New Field Customer</h3>
                <p className="text-xs text-muted-foreground">
                  Saved purely in Portal database • Zero changes to Tally accounting.
                </p>
              </div>
              <button
                onClick={() => setShowAddModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateCustomer} className="space-y-3.5 text-xs">
              <div>
                <label className="font-semibold block mb-1">
                  Shop Name <span className="text-destructive">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={addForm.name}
                  onChange={(e) => setAddForm({ ...addForm, name: e.target.value })}
                  placeholder="e.g. Aggarwal Crockeries & Plastic"
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Contact Person</label>
                  <input
                    type="text"
                    value={addForm.contact_person}
                    onChange={(e) => setAddForm({ ...addForm, contact_person: e.target.value })}
                    placeholder="Owner / Manager name"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">Shop Type</label>
                  <select
                    value={addForm.shop_type}
                    onChange={(e) => setAddForm({ ...addForm, shop_type: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="Retailer">Retailer</option>
                    <option value="Wholesaler">Wholesaler</option>
                    <option value="Distributor">Distributor</option>
                    <option value="Online">Online / D2C</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Phone / Mobile</label>
                  <input
                    type="text"
                    value={addForm.phone}
                    onChange={(e) => setAddForm({ ...addForm, phone: e.target.value })}
                    placeholder="10-digit mobile"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">WhatsApp Number</label>
                  <input
                    type="text"
                    value={addForm.whatsapp_number}
                    onChange={(e) => setAddForm({ ...addForm, whatsapp_number: e.target.value })}
                    placeholder="Same as mobile if blank"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold block mb-1">Street Address</label>
                <input
                  type="text"
                  value={addForm.address}
                  onChange={(e) => setAddForm({ ...addForm, address: e.target.value })}
                  placeholder="Shop No., Market building, Road"
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Locality / Market Area</label>
                  <input
                    type="text"
                    list="global-localities-list"
                    value={addForm.locality}
                    onChange={(e) => setAddForm({ ...addForm, locality: e.target.value })}
                    placeholder="e.g. Sadar Bazaar, Chandni Chowk"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">City</label>
                  <input
                    type="text"
                    list="global-cities-list"
                    value={addForm.city}
                    onChange={(e) => setAddForm({ ...addForm, city: e.target.value })}
                    placeholder="e.g. Delhi, Gurgaon"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Route / Sales Beat</label>
                  <input
                    type="text"
                    list="global-routes-list"
                    value={addForm.route_name}
                    onChange={(e) => setAddForm({ ...addForm, route_name: e.target.value })}
                    placeholder="e.g. Monday Route, Beat 1"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">Priority</label>
                  <select
                    value={addForm.priority}
                    onChange={(e) => setAddForm({ ...addForm, priority: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="high">High Priority</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              {/* GPS Coordinates Capture */}
              <div className="bg-muted/40 p-3 rounded-xl border border-border space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-foreground">GPS Location Coordinates</span>
                  <button
                    type="button"
                    onClick={() => {
                      if (!navigator.geolocation) return alert('No geolocation support')
                      navigator.geolocation.getCurrentPosition((pos) => {
                        setAddForm((prev) => ({
                          ...prev,
                          latitude: pos.coords.latitude.toFixed(6),
                          longitude: pos.coords.longitude.toFixed(6),
                        }))
                      })
                    }}
                    className="flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
                  >
                    <Compass className="w-3.5 h-3.5" />
                    <span>Auto-Capture Device GPS</span>
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={addForm.latitude}
                    onChange={(e) => setAddForm({ ...addForm, latitude: e.target.value })}
                    placeholder="Latitude (e.g. 28.6505)"
                    className="w-full px-2.5 py-1.5 rounded-lg bg-background border border-border text-xs"
                  />
                  <input
                    type="text"
                    value={addForm.longitude}
                    onChange={(e) => setAddForm({ ...addForm, longitude: e.target.value })}
                    placeholder="Longitude (e.g. 77.2145)"
                    className="w-full px-2.5 py-1.5 rounded-lg bg-background border border-border text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold block mb-1">Internal Notes</label>
                <textarea
                  rows={2}
                  value={addForm.notes}
                  onChange={(e) => setAddForm({ ...addForm, notes: e.target.value })}
                  placeholder="Order preferences, key contacts, shop timings..."
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="pt-3 border-t border-border flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/90 flex items-center gap-2"
                >
                  {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Save Customer</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL 3: Edit Customer Details ─── */}
      {showEditModal && selectedCustomer && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <h3 className="font-bold text-lg">Edit Customer Details</h3>
                <p className="text-xs text-muted-foreground">{selectedCustomer.name}</p>
              </div>
              <button
                onClick={() => setShowEditModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Unmapped Customer Link Alert (Admin Only) */}
            {isAdmin && !selectedCustomer.ledger_id && (
              <div className="p-3 rounded-xl bg-primary/10 border border-primary/25 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="p-1.5 rounded-lg bg-primary/20 text-primary flex-shrink-0">
                    <Link2 className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="font-bold text-foreground text-xs">Unmapped Field Profile</div>
                    <div className="text-[11px] text-muted-foreground truncate">
                      Not linked to any Tally ledger yet.
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setShowEditModal(false)
                    handleOpenLinkLedger(selectedCustomer)
                  }}
                  className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground font-semibold text-xs hover:bg-primary/90 flex items-center gap-1 flex-shrink-0 shadow-sm"
                >
                  <Link2 className="w-3.5 h-3.5" />
                  <span>Link to Tally</span>
                </button>
              </div>
            )}

            <form onSubmit={handleSaveProfile} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Contact Person</label>
                  <input
                    type="text"
                    value={editForm.contact_person}
                    onChange={(e) => setEditForm({ ...editForm, contact_person: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">Shop Type</label>
                  <select
                    value={editForm.shop_type}
                    onChange={(e) => setEditForm({ ...editForm, shop_type: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="Retailer">Retailer</option>
                    <option value="Wholesaler">Wholesaler</option>
                    <option value="Distributor">Distributor</option>
                    <option value="Online">Online / D2C</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Phone / Mobile</label>
                  <input
                    type="text"
                    value={editForm.phone}
                    onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">WhatsApp Number</label>
                  <input
                    type="text"
                    value={editForm.whatsapp_number}
                    onChange={(e) => setEditForm({ ...editForm, whatsapp_number: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold block mb-1">Address</label>
                <input
                  type="text"
                  value={editForm.address}
                  onChange={(e) => setEditForm({ ...editForm, address: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Locality</label>
                  <input
                    type="text"
                    list="global-localities-list"
                    value={editForm.locality}
                    onChange={(e) => setEditForm({ ...editForm, locality: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">City</label>
                  <input
                    type="text"
                    list="global-cities-list"
                    value={editForm.city}
                    onChange={(e) => setEditForm({ ...editForm, city: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Route / Sales Beat</label>
                  <input
                    type="text"
                    list="global-routes-list"
                    value={editForm.route_name}
                    onChange={(e) => setEditForm({ ...editForm, route_name: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">Priority</label>
                  <select
                    value={editForm.priority}
                    onChange={(e) => setEditForm({ ...editForm, priority: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="high">High Priority</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-semibold block mb-1">Internal Sales Notes</label>
                <textarea
                  rows={3}
                  value={editForm.notes}
                  onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="pt-3 border-t border-border flex items-center justify-between gap-2">
                {!selectedCustomer.ledger_id ? (
                  <button
                    type="button"
                    onClick={() => {
                      const toDel = selectedCustomer
                      setShowEditModal(false)
                      setCustomerToDelete(toDel)
                    }}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 font-semibold text-xs transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Delete Lead</span>
                  </button>
                ) : <div />}

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowEditModal(false)}
                    className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-5 py-2 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/90 flex items-center gap-2"
                  >
                    {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    <span>Save Changes</span>
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL 4: Tag Master GPS Coordinates ─── */}
      {showTagModal && selectedCustomer && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Compass className="w-5 h-5 text-primary" />
                <div>
                  <h3 className="font-bold text-lg">Tag Shop GPS Location</h3>
                  <p className="text-xs text-muted-foreground">{selectedCustomer.name}</p>
                </div>
              </div>
              <button
                onClick={() => setShowTagModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveTagLocation} className="space-y-4 text-xs">
              <div className="p-3 bg-primary/5 border border-primary/20 rounded-xl space-y-2">
                <p className="text-xs font-medium text-foreground">
                  This sets the master reference GPS coordinates for this shop. All future check-ins will be verified against this point.
                </p>
                <button
                  type="button"
                  onClick={handleCaptureTagLocation}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 transition-all shadow-sm"
                >
                  <MapPin className="w-4 h-4" />
                  <span>Use My Current Device Location</span>
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Latitude</label>
                  <input
                    type="number"
                    step="any"
                    required
                    value={tagForm.latitude}
                    onChange={(e) => setTagForm({ ...tagForm, latitude: e.target.value })}
                    placeholder="28.650523"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">Longitude</label>
                  <input
                    type="number"
                    step="any"
                    required
                    value={tagForm.longitude}
                    onChange={(e) => setTagForm({ ...tagForm, longitude: e.target.value })}
                    placeholder="77.214589"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold block mb-1">Reason / Note</label>
                <input
                  type="text"
                  value={tagForm.reason}
                  onChange={(e) => setTagForm({ ...tagForm, reason: e.target.value })}
                  placeholder="e.g. Calibrated on-site by salesperson"
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="pt-3 border-t border-border flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowTagModal(false)}
                  className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/90 flex items-center gap-2"
                >
                  {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Save Location</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL 5: Link Field Customer to Tally Ledger (Admin Only) ─── */}
      {showLinkModal && selectedCustomer && isAdmin && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col animate-in fade-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <Link2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg leading-tight">Link to Tally Ledger</h3>
                  <p className="text-xs text-muted-foreground">Admin Operation • Maps field profile to Tally debtor</p>
                </div>
              </div>
              <button
                onClick={() => setShowLinkModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Target Field Customer Summary */}
            <div className="p-3.5 rounded-xl bg-muted/50 border border-border space-y-1.5">
              <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                Field Customer Profile (To be linked)
              </div>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-bold text-sm text-foreground">{selectedCustomer.name}</div>
                  <div className="text-xs text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5">
                    {selectedCustomer.contact_person && (
                      <span>Attn: <b className="text-foreground">{selectedCustomer.contact_person}</b></span>
                    )}
                    {(selectedCustomer.mobile || selectedCustomer.phone) && (
                      <span>📞 {selectedCustomer.mobile || selectedCustomer.phone}</span>
                    )}
                    {selectedCustomer.locality && (
                      <span>📍 {selectedCustomer.locality}{selectedCustomer.city ? `, ${selectedCustomer.city}` : ''}</span>
                    )}
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-amber-500/10 text-amber-600 border border-amber-500/20 flex-shrink-0">
                  Unmapped Profile
                </span>
              </div>
            </div>

            {/* Search Input for Tally Debtors */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold block text-foreground">
                Select Matching Tally Sundry Debtor
              </label>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={ledgerSearch}
                  onChange={(e) => {
                    setLedgerSearch(e.target.value)
                    fetchUnlinkedLedgers(e.target.value)
                  }}
                  placeholder="Search unlinked Tally debtor by name, address, or mobile..."
                  className="w-full pl-9 pr-8 py-2 rounded-xl bg-background border border-border text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                />
                {ledgerSearch && (
                  <button
                    type="button"
                    onClick={() => {
                      setLedgerSearch('')
                      fetchUnlinkedLedgers('')
                    }}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>

            {/* Unlinked Ledgers List */}
            <div className="flex-1 overflow-y-auto space-y-2 max-h-64 pr-1">
              {loadingUnlinkedLedgers ? (
                <div className="py-10 text-center text-muted-foreground flex flex-col items-center gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                  <span className="text-xs">Fetching unlinked Tally Debtors...</span>
                </div>
              ) : unlinkedLedgers.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground border border-dashed border-border rounded-xl">
                  <Building className="w-7 h-7 mx-auto opacity-40 mb-1" />
                  <p className="text-xs font-medium">No unlinked Tally ledgers found</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    All Sundry Debtors are already mapped, or no ledger matches your search.
                  </p>
                </div>
              ) : (
                unlinkedLedgers.map((l) => {
                  const isSelected = selectedLedgerId === l.ledger_id
                  return (
                    <div
                      key={l.ledger_id}
                      onClick={() => setSelectedLedgerId(l.ledger_id)}
                      className={cn(
                        'p-3 rounded-xl border text-xs cursor-pointer transition-all flex items-start justify-between gap-3',
                        isSelected
                          ? 'border-primary bg-primary/10 shadow-sm ring-1 ring-primary'
                          : 'border-border bg-card hover:bg-muted/50 hover:border-primary/40'
                      )}
                    >
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-foreground text-sm truncate">{l.name}</span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-muted text-muted-foreground font-mono">
                            #{l.ledger_id}
                          </span>
                        </div>
                        {l.address && (
                          <div className="text-[11px] text-muted-foreground line-clamp-1">
                            {l.address}
                          </div>
                        )}
                        <div className="flex flex-wrap items-center gap-x-2 text-[10px] text-muted-foreground">
                          {l.mobile && <span>📱 {l.mobile}</span>}
                          {l.state && <span>📍 {l.state}</span>}
                          {l.pincode && <span>📮 {l.pincode}</span>}
                        </div>
                      </div>

                      <div className="pt-0.5">
                        <input
                          type="radio"
                          name="selected_ledger"
                          checked={isSelected}
                          onChange={() => setSelectedLedgerId(l.ledger_id)}
                          className="w-4 h-4 text-primary focus:ring-primary cursor-pointer"
                        />
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            {/* Safety Notice */}
            <div className="p-2.5 rounded-lg bg-muted/40 text-[11px] text-muted-foreground flex items-center gap-2 border border-border">
              <Info className="w-4 h-4 text-primary flex-shrink-0" />
              <span>
                Linking securely attaches visit history & GPS logs to this Tally debtor in the Portal. Zero modifications will be made to Tally accounting.
              </span>
            </div>

            {/* Modal Actions */}
            <div className="pt-3 border-t border-border flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowLinkModal(false)}
                className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-semibold text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmLinkLedger}
                disabled={!selectedLedgerId || linkingLedger}
                className="px-5 py-2 rounded-xl bg-primary text-primary-foreground font-semibold text-xs hover:bg-primary/90 flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {linkingLedger && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <Link2 className="w-3.5 h-3.5" />
                <span>Confirm Link to Tally</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL 6: Delete Wrong Tagging Modal ─── */}
      {customerToDelete && !customerToDelete.ledger_id && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-600 mx-auto">
              <Trash2 className="w-6 h-6" />
            </div>

            <div className="text-center space-y-2">
              <h3 className="text-lg font-bold text-foreground">
                Delete Wrong Tagging?
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Are you sure you want to delete <span className="font-semibold text-foreground">"{customerToDelete.name}"</span>?
                This customer was tagged in the field and has no Tally ledger mapping.
              </p>
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-left text-xs text-rose-600 space-y-1">
                <p className="font-semibold">⚠️ What will be removed:</p>
                <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                  <li>Customer profile and contact details</li>
                  <li>All uploaded shop & owner photos from storage</li>
                  <li>All GPS check-in logs and visit history</li>
                </ul>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setCustomerToDelete(null)}
                disabled={deletingCustomer}
                className="px-4 py-2 rounded-xl border border-border hover:bg-muted text-xs font-semibold text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteCustomer}
                disabled={deletingCustomer}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-colors disabled:opacity-50"
              >
                {deletingCustomer ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    <span>Yes, Delete Lead</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL 7: Customer Health Score Breakdown ─── */}
      {activeHealthCustomer && activeHealthCustomer.health_score && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-start justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-violet-500/10 text-violet-600">
                  <HeartPulse className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-lg text-foreground flex items-center gap-2">
                    <span>Customer Health Score</span>
                    <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-violet-500/10 text-violet-600 border border-violet-500/20">
                      {activeHealthCustomer.health_score.score}/100
                    </span>
                  </h3>
                  <p className="text-xs text-muted-foreground">{activeHealthCustomer.name}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActiveHealthCustomer(null)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Score Overview Banner */}
            <div className="p-4 rounded-xl bg-muted/40 border border-border flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Health Rating</span>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-3xl font-black text-foreground">{activeHealthCustomer.health_score.score}</span>
                  <div className="text-xs">
                    <div className="font-bold text-foreground">Grade {activeHealthCustomer.health_score.grade}</div>
                    <div className={cn(
                      'font-semibold',
                      activeHealthCustomer.health_score.status === 'Healthy' ? 'text-emerald-600' :
                      activeHealthCustomer.health_score.status === 'Fair' ? 'text-amber-600' : 'text-rose-600'
                    )}>
                      {activeHealthCustomer.health_score.status}
                    </div>
                  </div>
                </div>
              </div>
              <div className="text-right">
                <span className="text-xs text-muted-foreground">Visit Recency</span>
                <div className="mt-1">
                  {renderRecencyBadge(activeHealthCustomer)}
                </div>
              </div>
            </div>

            {/* 4-Factor Breakdown */}
            <div className="space-y-3 text-xs">
              <h4 className="font-bold text-foreground uppercase tracking-wider text-[11px]">
                Score Factors (100 pts max)
              </h4>

              {/* Factor 1: Order Recency (35 pts) */}
              <div className="p-3 rounded-xl border border-border bg-background space-y-1.5">
                <div className="flex justify-between items-center font-medium">
                  <span className="text-foreground">Order Recency</span>
                  <span className="font-bold text-foreground">
                    {activeHealthCustomer.health_score.breakdown.order_recency_score} / 35 pts
                  </span>
                </div>
                <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-primary h-2 rounded-full transition-all"
                    style={{ width: `${(activeHealthCustomer.health_score.breakdown.order_recency_score / 35) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground">Based on latest sales voucher activity from Tally</span>
              </div>

              {/* Factor 2: Visit Cadence (25 pts) */}
              <div className="p-3 rounded-xl border border-border bg-background space-y-1.5">
                <div className="flex justify-between items-center font-medium">
                  <span className="text-foreground">Visit Cadence</span>
                  <span className="font-bold text-foreground">
                    {activeHealthCustomer.health_score.breakdown.visit_cadence_score} / 25 pts
                  </span>
                </div>
                <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-2 rounded-full transition-all"
                    style={{ width: `${(activeHealthCustomer.health_score.breakdown.visit_cadence_score / 25) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground">Based on days since last field visit check-in</span>
              </div>

              {/* Factor 3: Transaction Depth (25 pts) */}
              <div className="p-3 rounded-xl border border-border bg-background space-y-1.5">
                <div className="flex justify-between items-center font-medium">
                  <span className="text-foreground">Transaction Depth</span>
                  <span className="font-bold text-foreground">
                    {activeHealthCustomer.health_score.breakdown.txn_depth_score} / 25 pts
                  </span>
                </div>
                <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-blue-500 h-2 rounded-full transition-all"
                    style={{ width: `${(activeHealthCustomer.health_score.breakdown.txn_depth_score / 25) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground">Historical voucher frequency and buying consistency</span>
              </div>

              {/* Factor 4: Profile & GPS Verification (15 pts) */}
              <div className="p-3 rounded-xl border border-border bg-background space-y-1.5">
                <div className="flex justify-between items-center font-medium">
                  <span className="text-foreground">Profile & GPS Verification</span>
                  <span className="font-bold text-foreground">
                    {activeHealthCustomer.health_score.breakdown.profile_verification_score} / 15 pts
                  </span>
                </div>
                <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-amber-500 h-2 rounded-full transition-all"
                    style={{ width: `${(activeHealthCustomer.health_score.breakdown.profile_verification_score / 15) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted-foreground">Verified coordinates and complete contact information</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-border">
              <Link
                href={`/customers/${activeHealthCustomer.key}`}
                className="text-xs text-primary font-semibold hover:underline flex items-center gap-1"
              >
                <span>View 360° Profile</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
              <button
                type="button"
                onClick={() => setActiveHealthCustomer(null)}
                className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground text-xs font-semibold transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Global Datalists for Form Autocomplete */}
      <datalist id="global-localities-list">
        {localitiesList.map(loc => (
          <option key={loc.name} value={loc.name} />
        ))}
      </datalist>
      <datalist id="global-cities-list">
        {citiesList.map(city => (
          <option key={city.name} value={city.name} />
        ))}
      </datalist>
      <datalist id="global-routes-list">
        {routesList.map(r => (
          <option key={r} value={r} />
        ))}
      </datalist>
    </div>
  )
}
