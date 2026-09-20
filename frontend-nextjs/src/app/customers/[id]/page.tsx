'use client'

import { useState, useEffect, useMemo, useRef, Suspense } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { usePeriod } from '@/context/PeriodContext'
import { API_BASE, authHeaders, cn } from '@/lib/utils'
import Cropper from 'react-easy-crop'
import { getCroppedImg } from '@/lib/cropImage'
import LedgerDetailsClient from '@/app/ledgers/[id]/ledger-details-client'
import {
  Users,
  MapPin,
  Navigation,
  Phone,
  MessageCircle,
  Search,
  Plus,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Clock,
  Building,
  CheckCircle2,
  X,
  Compass,
  History,
  Edit2,
  Tag,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Info,
  Link2,
  Camera,
  Image as ImageIcon,
  Trash2,
  User as UserIcon,
  Store,
  QrCode,
  CreditCard,
  Maximize2,
  Calendar,
  Sparkles,
  Copy,
  Check,
  UserPlus,
  Crown,
  Mail,
  Receipt,
  FileText,
  IndianRupee,
  Share2,
  ShoppingCart,
  ArrowDownRight,
  ArrowUpRight
} from 'lucide-react'

export interface FinancialSummary {
  closing_balance: number
  raw_balance: number
  balance_type: 'Dr' | 'Cr'
  opening_balance: number
  opening_type: string
  total_billed_debit: number
  total_collected_credit: number
}

export interface RecentVoucherItem {
  id: number
  date: string | null
  voucher_type: string
  voucher_number: string
  amount: number
  type: 'Dr' | 'Cr'
  narration: string
  running_balance?: number
  running_type?: string
}

export interface RecentOrderItem {
  id: number
  created_at: string | null
  status: string
  total_items: number
  total_amount: number
  comments: string | null
}

export interface RecentPaymentItem {
  id: number
  created_at: string | null
  amount: number
  payment_mode: string
  status: string
  notes: string | null
}

interface OwnerItem {
  id: number | null
  name: string
  designation: string
  phone: string
  whatsapp_number: string
  email: string
  photo_url: string | null
  imagekit_file_id?: string | null
  is_primary: boolean
  notes: string
  created_at: string | null
}

interface CustomerPhotoItem {
  id: number
  photo_type: string
  imagekit_url: string
  imagekit_thumbnail_url: string
  imagekit_file_path: string | null
  caption: string | null
  latitude: number | null
  longitude: number | null
  is_primary: boolean
  uploaded_by_name: string
  created_at: string | null
}

interface VisitItem {
  id: number
  salesperson: string
  comments: string | null
  latitude: number | null
  longitude: number | null
  photo_url: string | null
  status: string
  created_at: string | null
}

interface CustomerDetail {
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
  visit_frequency: string
  notes: string
  customer_photo_url: string | null
  shop_photo_url: string | null
  latitude: number | null
  longitude: number | null
  has_location: boolean
  location_verified: boolean
  location_verified_at: string | null
  maps_url: string
  latest_verification_status: string
  latest_checkin_distance: number | null
  latest_checkin_at: string | null
  days_since_last_visit?: number | null
  visit_recency_category?: string
  visit_recency_label?: string
  health_score?: {
    score: number
    grade: string
    status_label: string
    color: string
    breakdown?: {
      visit_score: number
      visit_label: string
      order_score: number
      order_label: string
      volume_score: number
      volume_label: string
      profile_score: number
      total: number
    }
  }
  photos: CustomerPhotoItem[]
  owners: OwnerItem[]
  visits: VisitItem[]
  financial_summary?: FinancialSummary | null
  recent_vouchers?: RecentVoucherItem[]
  recent_orders?: RecentOrderItem[]
  recent_payments?: RecentPaymentItem[]
  tally_details?: {
    ledger_id: number
    name: string
    group_id: number | null
    state: string | null
    pincode: string | null
  } | null
}

function CustomerProfileContent() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, token, permissions, can, isLoading } = useAuth()
  const targetId = (params?.id as string) || ''

  const isAdmin = Boolean(
    permissions?.isAdmin ||
    user?.role?.toLowerCase() === 'admin' ||
    user?.role?.toLowerCase() === 'superadmin' ||
    user?.role?.toLowerCase() === 'owner'
  )

  const canViewStore = Boolean(isAdmin || permissions?.showCustomers || can?.('customers', 'read'))
  const canViewStatement = Boolean(isAdmin || permissions?.showSalesLedgers || permissions?.showLedger || can?.('ledger_customer', 'read') || can?.('ledgers', 'read'))
  const canViewOrders = Boolean(isAdmin || permissions?.showOrders || can?.('orders', 'read'))
  const canViewVisits = Boolean(isAdmin || permissions?.showCheckIn || can?.('visits', 'read'))
  const canDelete = Boolean(isAdmin || can?.('customers', 'delete'))
  const canUpdate = Boolean(isAdmin || can?.('customers', 'update'))

  const allowedTabs = useMemo(() => {
    const list: ('overview' | 'statement' | 'orders' | 'visits')[] = []
    if (canViewStore) list.push('overview')
    if (canViewStatement) list.push('statement')
    if (canViewOrders) list.push('orders')
    if (canViewVisits) list.push('visits')
    return list
  }, [canViewStore, canViewStatement, canViewOrders, canViewVisits])

  const [customer, setCustomer] = useState<CustomerDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [copiedField, setCopiedField] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  // 360° View Main Tabs: overview | statement | orders | visits
  const [mainTab, setMainTab] = useState<'overview' | 'statement' | 'orders' | 'visits'>(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search)
      const tabParam = urlParams.get('tab')
      if (tabParam === 'statement' || tabParam === 'orders' || tabParam === 'visits' || tabParam === 'overview') {
        return tabParam
      }
      try {
        const savedTab = sessionStorage.getItem(`customer_tab_${targetId}`)
        if (savedTab === 'statement' || savedTab === 'orders' || savedTab === 'visits' || savedTab === 'overview') {
          return savedTab
        }
      } catch {}
    }
    return 'overview'
  })

  // Synchronize tab helper to keep state, sessionStorage, and URL query params in sync
  const handleTabChange = (tab: 'overview' | 'statement' | 'orders' | 'visits') => {
    setMainTab(tab)
    if (typeof window !== 'undefined') {
      if (targetId) {
        try {
          sessionStorage.setItem(`customer_tab_${targetId}`, tab)
        } catch {}
      }
      const url = new URL(window.location.href)
      if (tab === 'overview') {
        url.searchParams.delete('tab')
      } else {
        url.searchParams.set('tab', tab)
      }
      window.history.replaceState(null, '', url.toString())
    }
  }

  // Synchronize mainTab when URL searchParams changes (e.g. browser back/forward)
  useEffect(() => {
    const tabFromUrl = searchParams.get('tab') as 'overview' | 'statement' | 'orders' | 'visits' | null
    if (tabFromUrl && ['overview', 'statement', 'orders', 'visits'].includes(tabFromUrl)) {
      if (tabFromUrl !== mainTab) {
        setMainTab(tabFromUrl)
        if (targetId) {
          try {
            sessionStorage.setItem(`customer_tab_${targetId}`, tabFromUrl)
          } catch {}
        }
      }
    } else if (!tabFromUrl && typeof window !== 'undefined' && targetId) {
      try {
        const savedTab = sessionStorage.getItem(`customer_tab_${targetId}`) as 'overview' | 'statement' | 'orders' | 'visits' | null
        if (savedTab && ['statement', 'orders', 'visits', 'overview'].includes(savedTab)) {
          if (mainTab !== savedTab) {
            setMainTab(savedTab)
            const url = new URL(window.location.href)
            if (savedTab === 'overview') {
              url.searchParams.delete('tab')
            } else {
              url.searchParams.set('tab', savedTab)
            }
            window.history.replaceState(null, '', url.toString())
          }
          return
        }
      } catch {}
      if (mainTab !== 'overview') {
        setMainTab('overview')
      }
    }
  }, [searchParams, targetId, mainTab])

  // Safety fallback if active tab is restricted (guarded so it doesn't prematurely fire while auth loads)
  useEffect(() => {
    if (isLoading || !user) return
    if (allowedTabs.length > 0 && !allowedTabs.includes(mainTab)) {
      handleTabChange(allowedTabs[0])
    }
  }, [mainTab, allowedTabs, isLoading, user])

  // WhatsApp Statement Sharing Handler
  const handleShareStatement = () => {
    if (!customer || !canViewStatement) return
    const phone = (customer.whatsapp_number || customer.mobile || customer.phone || '').replace(/\D/g, '')
    const bal = Math.abs(customer.financial_summary?.closing_balance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })
    const balType = customer.financial_summary?.balance_type || 'Dr'
    const billed = (customer.financial_summary?.total_billed_debit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })
    const collected = (customer.financial_summary?.total_collected_credit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })

    let text = `*Account Statement — Sneh Distributors*\n`
    text += `Customer: *${customer.name}*\n`
    if (customer.ledger_id) text += `Ledger Account: #${customer.ledger_id}\n`
    text += `━━━━━━━━━━━━━━━━━━━━━\n`
    text += `*Outstanding Balance:* ₹${bal} (${balType})\n`
    text += `Total Billed: ₹${billed}\n`
    text += `Total Paid: ₹${collected}\n`
    text += `━━━━━━━━━━━━━━━━━━━━━\n`

    if (customer.recent_vouchers && customer.recent_vouchers.length > 0) {
      text += `*Recent Transactions:*\n`
      customer.recent_vouchers.slice(0, 3).forEach((v) => {
        text += `• ${v.date ? new Date(v.date).toLocaleDateString('en-IN') : 'Recent'}: ${v.voucher_type} (${v.voucher_number}) — ₹${v.amount.toLocaleString('en-IN')} (${v.type})\n`
      })
      text += `━━━━━━━━━━━━━━━━━━━━━\n`
    }

    text += `Please arrange payment at your earliest convenience.\nThank you for your business!`

    const url = `https://wa.me/91${phone}?text=${encodeURIComponent(text)}`
    window.open(url, '_blank')
  }

  // Gallery Filter State
  const [photoFilter, setPhotoFilter] = useState<string>('all')
  const [lightboxPhoto, setLightboxPhoto] = useState<CustomerPhotoItem | null>(null)

  // Upload Photo Modal State
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploadType, setUploadType] = useState<string>('shop_front')
  const [uploadCaption, setUploadCaption] = useState<string>('')
  const [uploadBase64, setUploadBase64] = useState<string>('')
  const [uploadCoords, setUploadCoords] = useState<{ lat: number; lon: number } | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const cameraInputRef = useRef<HTMLInputElement>(null)

  // Crop State
  const [crop, setCrop] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<any>(null)
  const [isCropping, setIsCropping] = useState(false)

  // Edit Modal State
  const [showEditModal, setShowEditModal] = useState(false)
  const [filterOptions, setFilterOptions] = useState<{ localities: any[], cities: any[], routes: string[] } | null>(null)

  useEffect(() => {
    if (showEditModal && !filterOptions && token) {
      fetch(`${API_BASE}/customers/localities`, { headers: authHeaders(token) })
        .then(res => res.ok ? res.json() : null)
        .then(data => { if (data) setFilterOptions(data) })
        .catch(err => console.error('Failed to load filter options', err))
    }
  }, [showEditModal, filterOptions, token])

  // Full Ledger Statement State
  const { startDate, endDate } = usePeriod()
  const [ledgerInfo, setLedgerInfo] = useState<any>(null)
  const [transactions, setTransactions] = useState<any[]>([])
  const [loadingLedger, setLoadingLedger] = useState(false)

  // Fetch full ledger statement when on statement tab
  useEffect(() => {
    if (mainTab === 'statement' && canViewStatement && customer?.ledger_id && token) {
      setLoadingLedger(true)
      let url = `${API_BASE}/ledgers/${customer.ledger_id}/statement`
      const q: string[] = []
      if (startDate) q.push(`from_date=${startDate}`)
      if (endDate) q.push(`to_date=${endDate}`)
      if (q.length > 0) url += `?${q.join('&')}`

      fetch(url, { headers: authHeaders(token) })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && data.success) {
            setLedgerInfo(data.ledgerInfo)
            setTransactions(data.transactions)
          }
        })
        .catch(console.error)
        .finally(() => setLoadingLedger(false))
    }
  }, [mainTab, canViewStatement, customer?.ledger_id, token, startDate, endDate])

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
    visit_frequency: 'weekly',
    notes: '',
  })
  const [savingEdit, setSavingEdit] = useState(false)

  // Tag Location Modal State
  const [showTagModal, setShowTagModal] = useState(false)
  const [tagForm, setTagForm] = useState({ latitude: '', longitude: '', reason: '' })
  const [savingLocation, setSavingLocation] = useState(false)

  // Link to Ledger Modal State (Admin Only)
  const [showLinkModal, setShowLinkModal] = useState(false)
  const [unlinkedLedgers, setUnlinkedLedgers] = useState<{
    ledger_id: number
    name: string
    address: string
    mobile: string
    state: string
    pincode: string
  }[]>([])
  const [loadingUnlinked, setLoadingUnlinked] = useState(false)
  const [selectedLedgerId, setSelectedLedgerId] = useState<number | null>(null)
  const [ledgerSearch, setLedgerSearch] = useState('')
  const [linkingLedger, setLinkingLedger] = useState(false)

  // Delete Wrong Tagging Modal State
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // Multi-Owner States
  const [showAddOwnerModal, setShowAddOwnerModal] = useState(false)
  const [editingOwner, setEditingOwner] = useState<OwnerItem | null>(null)
  const [ownerForm, setOwnerForm] = useState({
    name: '',
    designation: 'Partner / Co-Owner',
    phone: '',
    whatsapp_number: '',
    email: '',
    notes: '',
    is_primary: false,
  })
  const [savingOwner, setSavingOwner] = useState(false)
  const [ownerToDelete, setOwnerToDelete] = useState<OwnerItem | null>(null)
  const [deletingOwner, setDeletingOwner] = useState(false)
  const [ownerForPhoto, setOwnerForPhoto] = useState<OwnerItem | null>(null)
  const [uploadingOwnerPhoto, setUploadingOwnerPhoto] = useState(false)
  const [ownerPhotoPreview, setOwnerPhotoPreview] = useState<string | null>(null)
  const [ownerCameraActive, setOwnerCameraActive] = useState(false)
  const ownerVideoRef = useRef<HTMLVideoElement | null>(null)

  // Fetch Customer Profile
  const fetchCustomer = async (isRefresh = false) => {
    if (!token || !targetId) return
    if (isRefresh) setRefreshing(true)
    else setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/customers/${targetId}`, {
        headers: authHeaders(token),
      })
      if (res.ok) {
        const data = await res.json()
        setCustomer(data)
        setEditForm({
          contact_person: data.contact_person || '',
          phone: data.phone || '',
          whatsapp_number: data.whatsapp_number || data.mobile || '',
          address: data.address || '',
          locality: data.locality || '',
          city: data.city || '',
          state: data.state || '',
          pincode: data.pincode || '',
          route_name: data.route_name || '',
          shop_type: data.shop_type || 'Retailer',
          tags: data.tags ? data.tags.join(', ') : '',
          priority: data.priority || 'medium',
          visit_frequency: data.visit_frequency || 'weekly',
          notes: data.notes || '',
        })
      } else if (res.status === 404) {
        alert('Customer not found')
        router.push('/customers')
      }
    } catch (e) {
      console.error('Failed to load customer', e)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchCustomer()
  }, [targetId, token])

  // Copy to clipboard helper
  const copyToClipboard = (text: string, fieldName: string) => {
    if (!text) return
    navigator.clipboard.writeText(text)
    setCopiedField(fieldName)
    setTimeout(() => setCopiedField(null), 2000)
  }

  // Handle Photo Selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.size > 10 * 1024 * 1024) {
      alert('Photo is too large (maximum 10MB). Please select a smaller photo.')
      return
    }

    const reader = new FileReader()
    reader.onload = (event) => {
      const rawBase64 = event.target?.result as string
      // Compress high-res mobile camera images to max 1800px for fast, reliable upload
      const img = new Image()
      img.onload = () => {
        const MAX_DIM = 1800
        let width = img.width
        let height = img.height
        if (width > MAX_DIM || height > MAX_DIM) {
          if (width > height) {
            height = Math.round((height * MAX_DIM) / width)
            width = MAX_DIM
          } else {
            width = Math.round((width * MAX_DIM) / height)
            height = MAX_DIM
          }
        }
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.drawImage(img, 0, 0, width, height)
          setUploadBase64(canvas.toDataURL('image/jpeg', 0.85))
        } else {
          setUploadBase64(rawBase64)
        }
        setIsCropping(true)
      }
      img.onerror = () => {
        setUploadBase64(rawBase64)
        setIsCropping(true)
      }
      img.src = rawBase64
    }
    reader.readAsDataURL(file)

    // Capture device coordinates automatically
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setUploadCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude })
        },
        (err) => console.log('GPS not available during photo selection', err),
        { enableHighAccuracy: true, timeout: 8000 }
      )
    }
  }

  // Submit Photo Upload
  const handleUploadPhoto = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uploadBase64) {
      alert('Please select or capture a photo first.')
      return
    }

    setUploading(true)
    try {
      const payload = {
        photo_base64: uploadBase64,
        photo_type: uploadType,
        caption: uploadCaption.trim() || null,
        latitude: uploadCoords?.lat || null,
        longitude: uploadCoords?.lon || null,
        is_primary: uploadType === 'customer_owner' || uploadType === 'shop_front',
      }

      const res = await fetch(`${API_BASE}/customers/${targetId}/photos`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (res.ok) {
        const data = await res.json()
        setShowUploadModal(false)
        setUploadBase64('')
        setUploadCaption('')
        setUploadCoords(null)
        setActionSuccess(data.message || 'Photo uploaded successfully to ImageKit!')
        setTimeout(() => setActionSuccess(null), 4000)
        fetchCustomer(true)
      } else {
        const err = await res.json().catch(() => null)
        alert(err?.detail || 'Failed to upload photo to ImageKit')
      }
    } catch (err) {
      alert('Error uploading photo')
    } finally {
      setUploading(false)
    }
  }

  // Delete Photo
  const handleDeletePhoto = async (photoId: number) => {
    if (!canDelete) {
      alert('You do not have permission to delete customer photos.')
      return
    }
    if (!confirm('Are you sure you want to permanently delete this photo from ImageKit storage?')) {
      return
    }

    try {
      const res = await fetch(`${API_BASE}/customers/${targetId}/photos/${photoId}`, {
        method: 'DELETE',
        headers: authHeaders(token),
      })
      if (res.ok) {
        setActionSuccess('Photo deleted successfully from ImageKit.')
        setTimeout(() => setActionSuccess(null), 3500)
        fetchCustomer(true)
        if (lightboxPhoto?.id === photoId) {
          setLightboxPhoto(null)
        }
      } else {
        alert('Failed to delete photo')
      }
    } catch (e) {
      alert('Error deleting photo')
    }
  }

  // Save Profile Edits
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setSavingEdit(true)
    try {
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
        fetchCustomer(true)
      } else {
        alert('Failed to update details')
      }
    } catch (e) {
      alert('Error saving customer profile')
    } finally {
      setSavingEdit(false)
    }
  }

  // Save Location Tag
  const handleSaveLocation = async (e: React.FormEvent) => {
    e.preventDefault()
    const lat = parseFloat(tagForm.latitude)
    const lon = parseFloat(tagForm.longitude)
    if (isNaN(lat) || isNaN(lon)) {
      alert('Please enter valid numeric latitude and longitude coordinates')
      return
    }

    setSavingLocation(true)
    try {
      const res = await fetch(`${API_BASE}/customers/${targetId}/tag-location`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ latitude: lat, longitude: lon, reason: tagForm.reason || 'Calibrated on-site' }),
      })
      if (res.ok) {
        setShowTagModal(false)
        setActionSuccess('Master shop location tagged and verified!')
        setTimeout(() => setActionSuccess(null), 3500)
        fetchCustomer(true)
      } else {
        alert('Failed to tag shop location')
      }
    } catch (e) {
      alert('Error saving location')
    } finally {
      setSavingLocation(false)
    }
  }

  // Open Link to Ledger Modal (Admin Only)
  const handleOpenLinkModal = async () => {
    setShowLinkModal(true)
    setSelectedLedgerId(null)
    setLedgerSearch('')
    setLoadingUnlinked(true)
    try {
      const res = await fetch(`${API_BASE}/customers/unlinked-ledgers`, {
        headers: authHeaders(token),
      })
      if (res.ok) {
        const data = await res.json()
        setUnlinkedLedgers(data.unlinked_ledgers || [])
      }
    } catch (e) {
      console.error('Failed to load unlinked ledgers', e)
    } finally {
      setLoadingUnlinked(false)
    }
  }

  // Confirm Link to Ledger
  const handleConfirmLink = async () => {
    if (!selectedLedgerId) return
    setLinkingLedger(true)
    try {
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
        setActionSuccess(data.message || 'Successfully linked to Tally ledger!')
        setTimeout(() => setActionSuccess(null), 4000)
        fetchCustomer(true)
      } else {
        const err = await res.json().catch(() => null)
        alert(err?.detail || 'Failed to link ledger')
      }
    } catch (e) {
      alert('Error linking ledger')
    } finally {
      setLinkingLedger(false)
    }
  }

  // Delete unmapped customer lead (wrong tagging)
  const handleDeleteCustomer = async () => {
    if (!canDelete) {
      alert('You do not have permission to delete customer leads.')
      return
    }
    if (!token || !targetId || customer?.ledger_id) return

    setDeleting(true)
    try {
      const res = await fetch(`${API_BASE}/customers/${targetId}`, {
        method: 'DELETE',
        headers: authHeaders(token),
      })

      if (res.ok) {
        setActionSuccess('Customer lead deleted successfully.')
        setShowDeleteModal(false)
        setTimeout(() => {
          router.push('/customers')
        }, 1200)
      } else {
        const err = await res.json().catch(() => null)
        alert(err?.detail || 'Failed to delete customer lead')
        setDeleting(false)
        setShowDeleteModal(false)
      }
    } catch (e) {
      console.error('Delete error', e)
      alert('Network error while deleting customer')
      setDeleting(false)
      setShowDeleteModal(false)
    }
  }

  // ─── Multi-Owner Actions ───
  const handleOpenAddOwner = () => {
    setOwnerForm({
      name: '',
      designation: 'Partner / Co-Owner',
      phone: '',
      whatsapp_number: '',
      email: '',
      notes: '',
      is_primary: (customer?.owners?.length || 0) === 0,
    })
    setEditingOwner(null)
    setShowAddOwnerModal(true)
  }

  const handleOpenEditOwner = (owner: OwnerItem) => {
    setOwnerForm({
      name: owner.name,
      designation: owner.designation || 'Owner / Partner',
      phone: owner.phone || '',
      whatsapp_number: owner.whatsapp_number || '',
      email: owner.email || '',
      notes: owner.notes || '',
      is_primary: owner.is_primary,
    })
    setEditingOwner(owner)
    setShowAddOwnerModal(true)
  }

  const handleSaveOwner = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token || !targetId) return

    setSavingOwner(true)
    try {
      if (editingOwner && editingOwner.id) {
        // Update existing owner
        const res = await fetch(`${API_BASE}/customers/${targetId}/owners/${editingOwner.id}`, {
          method: 'PUT',
          headers: {
            ...authHeaders(token),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(ownerForm),
        })

        if (res.ok) {
          setActionSuccess(`Owner "${ownerForm.name}" updated successfully!`)
          setShowAddOwnerModal(false)
          setEditingOwner(null)
          setTimeout(() => setActionSuccess(null), 3500)
          fetchCustomer(true)
        } else {
          const err = await res.json().catch(() => null)
          alert(err?.detail || 'Failed to update owner')
        }
      } else {
        // Create new owner
        const res = await fetch(`${API_BASE}/customers/${targetId}/owners`, {
          method: 'POST',
          headers: {
            ...authHeaders(token),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(ownerForm),
        })

        if (res.ok) {
          setActionSuccess(`Owner "${ownerForm.name}" added successfully!`)
          setShowAddOwnerModal(false)
          setTimeout(() => setActionSuccess(null), 3500)
          fetchCustomer(true)
        } else {
          const err = await res.json().catch(() => null)
          alert(err?.detail || 'Failed to add owner')
        }
      }
    } catch (err) {
      alert('Error saving owner details')
    } finally {
      setSavingOwner(false)
    }
  }

  const handleSetPrimaryOwner = async (owner: OwnerItem) => {
    if (!token || !targetId || !owner.id || owner.is_primary) return

    try {
      const res = await fetch(`${API_BASE}/customers/${targetId}/owners/${owner.id}`, {
        method: 'PUT',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ is_primary: true }),
      })

      if (res.ok) {
        setActionSuccess(`"${owner.name}" is now marked as Primary Owner!`)
        setTimeout(() => setActionSuccess(null), 3500)
        fetchCustomer(true)
      } else {
        const err = await res.json().catch(() => null)
        alert(err?.detail || 'Failed to set primary owner')
      }
    } catch (err) {
      alert('Error setting primary owner')
    }
  }

  const handleDeleteOwner = async () => {
    if (!canDelete) {
      alert('You do not have permission to delete owners.')
      return
    }
    if (!token || !targetId || !ownerToDelete || !ownerToDelete.id) return

    setDeletingOwner(true)
    try {
      const res = await fetch(`${API_BASE}/customers/${targetId}/owners/${ownerToDelete.id}`, {
        method: 'DELETE',
        headers: authHeaders(token),
      })

      if (res.ok) {
        setActionSuccess(`Owner "${ownerToDelete.name}" removed successfully.`)
        setOwnerToDelete(null)
        setTimeout(() => setActionSuccess(null), 3500)
        fetchCustomer(true)
      } else {
        const err = await res.json().catch(() => null)
        alert(err?.detail || 'Failed to delete owner')
      }
    } catch (err) {
      alert('Error deleting owner')
    } finally {
      setDeletingOwner(false)
    }
  }

  const handleUploadOwnerPhoto = async () => {
    if (!token || !targetId || !ownerForPhoto || !ownerForPhoto.id || !ownerPhotoPreview) return

    setUploadingOwnerPhoto(true)
    try {
      const res = await fetch(`${API_BASE}/customers/${targetId}/owners/${ownerForPhoto.id}/photo`, {
        method: 'POST',
        headers: {
          ...authHeaders(token),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          photo_base64: ownerPhotoPreview,
          caption: `Portrait: ${ownerForPhoto.name} (${ownerForPhoto.designation})`
        }),
      })

      if (res.ok) {
        setActionSuccess(`Photo for "${ownerForPhoto.name}" uploaded successfully!`)
        setOwnerForPhoto(null)
        setOwnerPhotoPreview(null)
        if (ownerCameraActive) {
          stopOwnerCamera()
        }
        setTimeout(() => setActionSuccess(null), 3500)
        fetchCustomer(true)
      } else {
        const err = await res.json().catch(() => null)
        alert(err?.detail || 'Failed to upload photo for owner')
      }
    } catch (err) {
      alert('Error uploading owner photo')
    } finally {
      setUploadingOwnerPhoto(false)
    }
  }

  const startOwnerCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 720 }, height: { ideal: 720 } },
      })
      if (ownerVideoRef.current) {
        ownerVideoRef.current.srcObject = stream
        ownerVideoRef.current.play()
      }
      setOwnerCameraActive(true)
    } catch (err) {
      alert('Could not access camera. Please allow camera permissions.')
    }
  }

  const stopOwnerCamera = () => {
    if (ownerVideoRef.current && ownerVideoRef.current.srcObject) {
      const stream = ownerVideoRef.current.srcObject as MediaStream
      stream.getTracks().forEach((t) => t.stop())
      ownerVideoRef.current.srcObject = null
    }
    setOwnerCameraActive(false)
  }

  const captureOwnerPhoto = () => {
    if (!ownerVideoRef.current) return
    const canvas = document.createElement('canvas')
    canvas.width = ownerVideoRef.current.videoWidth || 640
    canvas.height = ownerVideoRef.current.videoHeight || 640
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.drawImage(ownerVideoRef.current, 0, 0, canvas.width, canvas.height)
    const base64 = canvas.toDataURL('image/jpeg', 0.85)
    setOwnerPhotoPreview(base64)
    stopOwnerCamera()
  }

  // Comprehensive list of all photos for this customer (gallery photos + primary owner photo if not already included)
  const allCustomerPhotos = useMemo(() => {
    const list: CustomerPhotoItem[] = customer?.photos ? [...customer.photos] : []
    // If there is an owner photo that is not in customer.photos list, include it at the start
    if (customer?.customer_photo_url && !list.some(p => p.imagekit_url === customer.customer_photo_url)) {
      list.unshift({
        id: -999,
        photo_type: 'customer_owner',
        imagekit_url: customer.customer_photo_url,
        imagekit_thumbnail_url: customer.customer_photo_url,
        imagekit_file_path: null,
        caption: `Owner Portrait: ${customer.contact_person || customer.name}`,
        latitude: customer.latitude,
        longitude: customer.longitude,
        is_primary: true,
        uploaded_by_name: customer.contact_person || 'Owner',
        created_at: null,
      })
    }
    // Also include any owner/partner photos from customer.owners if not already in list
    if (customer?.owners) {
      for (const ow of customer.owners) {
        if (ow.photo_url && !list.some(p => p.imagekit_url === ow.photo_url)) {
          list.push({
            id: -(ow.id || 100),
            photo_type: 'customer_owner',
            imagekit_url: ow.photo_url,
            imagekit_thumbnail_url: ow.photo_url,
            imagekit_file_path: null,
            caption: `Partner Portrait: ${ow.name} (${ow.designation || 'Partner'})`,
            latitude: customer.latitude,
            longitude: customer.longitude,
            is_primary: ow.is_primary,
            uploaded_by_name: ow.name,
            created_at: ow.created_at,
          })
        }
      }
    }
    return list
  }, [customer?.photos, customer?.customer_photo_url, customer?.owners, customer?.name, customer?.contact_person, customer?.latitude, customer?.longitude])

  // Filtered Photos List for gallery tab view
  const filteredPhotos = useMemo(() => {
    if (photoFilter === 'all') return allCustomerPhotos
    return allCustomerPhotos.filter((p) => p.photo_type === photoFilter)
  }, [allCustomerPhotos, photoFilter])

  // Photos actively browsable in the lightbox
  const activeLightboxPhotos = useMemo(() => {
    if (filteredPhotos.some(p => p.id === lightboxPhoto?.id || p.imagekit_url === lightboxPhoto?.imagekit_url)) {
      return filteredPhotos
    }
    return allCustomerPhotos
  }, [filteredPhotos, allCustomerPhotos, lightboxPhoto])

  const currentLightboxIndex = useMemo(() => {
    if (!lightboxPhoto) return -1
    return activeLightboxPhotos.findIndex(p => p.id === lightboxPhoto.id || p.imagekit_url === lightboxPhoto.imagekit_url)
  }, [activeLightboxPhotos, lightboxPhoto])

  // Photo Navigation Handlers (supports looping)
  const handlePrevPhoto = (e?: React.MouseEvent) => {
    e?.stopPropagation()
    if (!lightboxPhoto || activeLightboxPhotos.length <= 1) return
    const idx = currentLightboxIndex
    if (idx > 0) {
      setLightboxPhoto(activeLightboxPhotos[idx - 1])
    } else {
      setLightboxPhoto(activeLightboxPhotos[activeLightboxPhotos.length - 1])
    }
  }

  const handleNextPhoto = (e?: React.MouseEvent) => {
    e?.stopPropagation()
    if (!lightboxPhoto || activeLightboxPhotos.length <= 1) return
    const idx = currentLightboxIndex
    if (idx !== -1 && idx < activeLightboxPhotos.length - 1) {
      setLightboxPhoto(activeLightboxPhotos[idx + 1])
    } else {
      setLightboxPhoto(activeLightboxPhotos[0])
    }
  }

  // Open lightbox starting from owner photo with all photos available to scroll
  const handleOpenOwnerPhoto = (targetUrl?: string) => {
    if (!customer) return
    setPhotoFilter('all')
    const urlToFind = targetUrl || customer.customer_photo_url

    if (urlToFind) {
      const match = allCustomerPhotos.find(p => p.imagekit_url === urlToFind)
      if (match) {
        setLightboxPhoto(match)
        return
      }
    }

    const ownerPhotoMatch = allCustomerPhotos.find(p => p.photo_type === 'customer_owner')
    if (ownerPhotoMatch) {
      setLightboxPhoto(ownerPhotoMatch)
      return
    }

    if (allCustomerPhotos.length > 0) {
      setLightboxPhoto(allCustomerPhotos[0])
    }
  }

  // Keyboard navigation for lightbox
  useEffect(() => {
    if (!lightboxPhoto) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') {
        handlePrevPhoto()
      } else if (e.key === 'ArrowRight') {
        handleNextPhoto()
      } else if (e.key === 'Escape') {
        setLightboxPhoto(null)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [lightboxPhoto, currentLightboxIndex, activeLightboxPhotos])

  const [touchStart, setTouchStart] = useState<number | null>(null)
  const [touchEnd, setTouchEnd] = useState<number | null>(null)

  const onTouchStart = (e: React.TouchEvent) => {
    setTouchEnd(null)
    setTouchStart(e.targetTouches[0].clientX)
  }

  const onTouchMove = (e: React.TouchEvent) => {
    setTouchEnd(e.targetTouches[0].clientX)
  }

  const onTouchEnd = () => {
    if (!touchStart || !touchEnd) return
    const distance = touchStart - touchEnd
    const minSwipeDistance = 50
    if (distance > minSwipeDistance) {
      handleNextPhoto()
    }
    if (distance < -minSwipeDistance) {
      handlePrevPhoto()
    }
  }

  // Photo Type Labels
  const photoTypeLabels: Record<string, { label: string; icon: any; color: string }> = {
    customer_owner: { label: 'Owner Portrait', icon: UserIcon, color: 'text-violet-500 bg-violet-500/10 border-violet-500/20' },
    shop_front: { label: 'Storefront', icon: Store, color: 'text-blue-500 bg-blue-500/10 border-blue-500/20' },
    shop_inside: { label: 'Inside Shop', icon: ImageIcon, color: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20' },
    shop_board: { label: 'Signboard', icon: Building, color: 'text-amber-500 bg-amber-500/10 border-amber-500/20' },
    visiting_card: { label: 'Visiting Card', icon: CreditCard, color: 'text-pink-500 bg-pink-500/10 border-pink-500/20' },
    qr_code: { label: 'UPI QR Code', icon: QrCode, color: 'text-cyan-500 bg-cyan-500/10 border-cyan-500/20' },
    visit_checkin: { label: 'Check-In Snap', icon: Clock, color: 'text-indigo-500 bg-indigo-500/10 border-indigo-500/20' },
    other: { label: 'Other', icon: ImageIcon, color: 'text-muted-foreground bg-muted border-border' },
  }

  // Verification Badge Helper
  const renderVerificationBadge = () => {
    if (!customer) return null
    const status = customer.latest_verification_status
    const dist = customer.latest_checkin_distance

    if (status === 'VERIFIED_ON_SITE') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/25">
          <ShieldCheck className="w-4 h-4" />
          Verified On-Site ({dist !== null ? `${Math.round(dist)}m` : '0m'})
        </span>
      )
    }
    if (status === 'NEARBY') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-amber-500/10 text-amber-600 border border-amber-500/25">
          <MapPin className="w-4 h-4" />
          Nearby ({dist !== null ? `${Math.round(dist)}m` : ''})
        </span>
      )
    }
    if (status === 'MISMATCH_FAR') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-rose-500/10 text-rose-600 border border-rose-500/25">
          <AlertTriangle className="w-4 h-4" />
          Location Discrepancy ({dist !== null ? (dist >= 1000 ? `${(dist / 1000).toFixed(1)}km` : `${Math.round(dist)}m`) : ''})
        </span>
      )
    }
    if (status === 'ESTABLISHED_BASE') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-blue-500/10 text-blue-600 border border-blue-500/25">
          <MapPin className="w-4 h-4" />
          Base Location Established
        </span>
      )
    }
    if (!customer.has_location) {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-semibold bg-muted text-muted-foreground border border-border">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
          Needs GPS Tag
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-semibold bg-muted text-muted-foreground border border-border">
        <Clock className="w-3.5 h-3.5" />
        No Check-in Log
      </span>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 text-foreground">
        <Loader2 className="w-10 h-10 animate-spin text-primary mb-3" />
        <p className="text-sm font-medium text-muted-foreground">Loading customer profile & media...</p>
      </div>
    )
  }

  if (!customer) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 text-foreground">
        <AlertTriangle className="w-12 h-12 text-amber-500 mb-3" />
        <h2 className="text-lg font-bold">Customer Not Found</h2>
        <Link href="/customers" className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-xl text-sm font-semibold">
          Return to Directory
        </Link>
      </div>
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

      {/* Top Breadcrumbs & Back Link */}
      <div className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link
              href="/customers"
              className="inline-flex items-center gap-1 hover:text-foreground font-semibold transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>Customer Directory</span>
            </Link>
            <span>/</span>
            <span className="text-foreground font-medium truncate max-w-[200px] sm:max-w-md">
              {customer.name}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchCustomer(true)}
              disabled={refreshing}
              className="p-1.5 rounded-lg border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              title="Refresh profile"
            >
              <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin text-primary')} />
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* ─── HERO HEADER CARD ─── */}
        <div className="bg-card border border-border rounded-3xl p-6 sm:p-8 shadow-sm relative overflow-hidden">
          {/* Subtle Top Accent Glow */}
          <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-primary via-indigo-500 to-purple-500" />

          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
            {/* Left: Customer Avatar + Name + Badges */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
              {/* Customer / Owner Portrait with 1-Tap Upload Overlay */}
              <div className="relative group flex-shrink-0">
                <div 
                  className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl overflow-hidden border-2 border-border shadow-md bg-muted flex items-center justify-center cursor-pointer relative hover:ring-2 hover:ring-primary/50 transition-all group"
                  onClick={() => handleOpenOwnerPhoto()}
                  title="Click to view and scroll all customer photos"
                >
                  {customer.customer_photo_url ? (
                    <>
                      <img
                        src={customer.customer_photo_url}
                        alt={customer.contact_person || customer.name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      <div className="absolute inset-0 bg-black/35 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center pointer-events-none text-white text-center p-1">
                        <Maximize2 className="w-5 h-5 mb-0.5" />
                        <span className="text-[10px] font-bold">View Photos</span>
                      </div>
                      {/* Photo Count badge showing total scrollable photos */}
                      {allCustomerPhotos.length > 1 && (
                        <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded-md bg-black/75 backdrop-blur-xs text-white text-[10px] font-extrabold flex items-center gap-1 shadow-sm pointer-events-none">
                          <ImageIcon className="w-2.5 h-2.5" />
                          <span>{allCustomerPhotos.length}</span>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="flex flex-col items-center justify-center text-muted-foreground p-2 text-center">
                      <UserIcon className="w-10 h-10 opacity-40 mb-1" />
                      <span className="text-[10px] font-semibold">No Photo</span>
                    </div>
                  )}
                </div>

                {/* Quick Camera Overlay / Edit Button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setUploadType('customer_owner')
                    setShowUploadModal(true)
                  }}
                  className="absolute -bottom-2 -right-2 bg-primary text-primary-foreground p-2 rounded-full shadow-lg border-2 border-background hover:bg-primary/90 transition-colors z-10"
                  title="Upload / Change Owner Photo"
                >
                  <Camera className="w-4 h-4" />
                </button>
              </div>

              {/* Shop Title & Badges */}
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-foreground">
                    {customer.name}
                  </h1>
                  {renderVerificationBadge()}
                </div>

                {customer.contact_person && (
                  <div className="text-sm text-muted-foreground flex items-center gap-1.5">
                    <span>Contact:</span>
                    <span className="font-bold text-foreground">{customer.contact_person}</span>
                  </div>
                )}

                {/* Category & Route Pills */}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="px-2.5 py-0.5 rounded-lg text-xs font-semibold bg-primary/10 text-primary border border-primary/20">
                    {customer.shop_type || 'Retailer'}
                  </span>
                  {customer.route_name && (
                    <span className="px-2.5 py-0.5 rounded-lg text-xs font-semibold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                      Beat: {customer.route_name}
                    </span>
                  )}
                  {customer.priority && customer.priority !== 'medium' && (
                    <span className={cn(
                      'px-2.5 py-0.5 rounded-lg text-xs font-bold uppercase tracking-wider border',
                      customer.priority === 'high' ? 'bg-rose-500/10 text-rose-600 border-rose-500/20' : 'bg-muted text-muted-foreground border-border'
                    )}>
                      {customer.priority} Priority
                    </span>
                  )}
                  {customer.ledger_id ? (
                    <span className="px-2.5 py-0.5 rounded-lg text-xs font-mono font-medium bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                      Tally #{customer.ledger_id}
                    </span>
                  ) : (
                    <span className="px-2.5 py-0.5 rounded-lg text-xs font-semibold bg-amber-500/10 text-amber-600 border border-amber-500/20">
                      Unmapped Field Lead
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Right: Quick Action Toolbar */}
            <div className="flex flex-wrap items-center gap-2.5 w-full lg:w-auto">
              {(customer.mobile || customer.phone) && (
                <a
                  href={`tel:${customer.mobile || customer.phone}`}
                  className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-sm transition-colors"
                  title="Call Customer"
                >
                  <Phone className="w-4 h-4" />
                  <span>Call</span>
                </a>
              )}

              {(customer.whatsapp_number || customer.mobile) && (
                <a
                  href={`https://wa.me/91${(customer.whatsapp_number || customer.mobile).replace(/\D/g, '')}?text=${encodeURIComponent(`Hello ${customer.name}, this is regarding your account/order.`)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-[#25D366] hover:bg-[#20bd5a] text-white font-bold text-xs shadow-sm transition-colors"
                  title="Open WhatsApp Chat"
                >
                  <MessageCircle className="w-4 h-4" />
                  <span>WhatsApp</span>
                </a>
              )}

              {/* Direct Check-In Action Button */}
              <Link
                href={`/check-in?${customer.ledger_id ? `ledger_id=${customer.ledger_id}` : `profile_id=${customer.profile_id}`}&name=${encodeURIComponent(customer.name || customer.tally_details?.name || '')}`}
                className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-sm transition-colors"
                title="Perform live check-in visit at this shop"
              >
                <MapPin className="w-4 h-4" />
                <span>Check In</span>
              </Link>

              <a
                href={customer.maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-xs shadow-sm transition-colors"
                title="Open Google Maps Navigation"
              >
                <Navigation className="w-4 h-4" />
                <span>Navigate</span>
                <ExternalLink className="w-3 h-3 opacity-70" />
              </a>

              <button
                onClick={() => {
                  setUploadType('shop_front')
                  setShowUploadModal(true)
                }}
                className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl border border-border bg-background hover:bg-muted text-foreground font-semibold text-xs transition-colors"
                title="Add Shop Photo to ImageKit"
              >
                <Camera className="w-4 h-4 text-primary" />
                <span>+ Photo</span>
              </button>

              <button
                onClick={() => {
                  setTagForm({
                    latitude: customer.latitude ? customer.latitude.toString() : '',
                    longitude: customer.longitude ? customer.longitude.toString() : '',
                    reason: 'Master shop location calibration',
                  })
                  setShowTagModal(true)
                }}
                className="p-2.5 rounded-xl border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                title="Tag / Calibrate GPS Location"
              >
                <MapPin className="w-4 h-4" />
              </button>

              <button
                onClick={() => setShowEditModal(true)}
                className="p-2.5 rounded-xl border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                title="Edit Customer Details"
              >
                <Edit2 className="w-4 h-4" />
              </button>

              {isAdmin && !customer.ledger_id && (
                <button
                  onClick={handleOpenLinkModal}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl border border-primary/40 bg-primary/10 hover:bg-primary/20 text-primary font-bold text-xs transition-colors"
                  title="Admin: Link to Tally Ledger"
                >
                  <Link2 className="w-4 h-4" />
                  <span>Link Ledger</span>
                </button>
              )}

              {/* Delete Wrong Tagging (ONLY if customer has NO ledger_id and user has delete permission) */}
              {canDelete && !customer.ledger_id && (
                <button
                  onClick={() => setShowDeleteModal(true)}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 font-bold text-xs transition-colors"
                  title="Delete wrongly tagged lead (Only available for leads with no Tally ledger)"
                >
                  <Trash2 className="w-4 h-4" />
                  <span className="hidden sm:inline">Delete Lead</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* ─── CUSTOMER HEALTH & VISIT RECENCY INTELLIGENCE BANNER ─── */}
        {customer.health_score && (
          <div className="bg-card border border-border rounded-3xl p-5 shadow-sm space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/60 pb-3">
              <div className="flex items-center gap-3">
                <div className={cn(
                  'w-12 h-12 rounded-2xl flex items-center justify-center font-black text-lg border shadow-sm',
                  customer.health_score.grade === 'HEALTHY'
                    ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/25'
                    : customer.health_score.grade === 'FAIR'
                    ? 'bg-amber-500/10 text-amber-600 border-amber-500/25'
                    : 'bg-rose-500/10 text-rose-600 border-rose-500/25'
                )}>
                  {customer.health_score.score}
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="font-extrabold text-base text-foreground">Customer Health Score</h2>
                    <span className={cn(
                      'px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider',
                      customer.health_score.grade === 'HEALTHY'
                        ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                        : customer.health_score.grade === 'FAIR'
                        ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
                        : 'bg-rose-500/15 text-rose-600 dark:text-rose-400'
                    )}>
                      {customer.health_score.status_label}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    100-point composite index based on visit cadence, order recency & transaction velocity
                  </p>
                </div>
              </div>

              {/* Days Since Last Visit Highlight */}
              <div className="flex items-center gap-2 self-start sm:self-auto bg-muted/50 px-3.5 py-2 rounded-2xl border border-border">
                <Clock className="w-4 h-4 text-primary" />
                <div className="text-xs">
                  <span className="text-muted-foreground">Last Visit: </span>
                  <strong className={cn(
                    customer.visit_recency_category === 'today' || customer.visit_recency_category === 'recent'
                      ? 'text-emerald-600 font-bold'
                      : customer.visit_recency_category === 'due_soon'
                      ? 'text-amber-600 font-bold'
                      : 'text-rose-600 font-bold'
                  )}>
                    {customer.visit_recency_label || 'Never Visited'}
                  </strong>
                  <span className="text-muted-foreground ml-1 font-medium">({customer.visit_frequency || 'weekly'} target)</span>
                </div>
              </div>
            </div>

            {/* Score Breakdown Factor Grid */}
            {customer.health_score.breakdown && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 text-xs">
                <div className="p-2.5 rounded-xl bg-muted/40 border border-border/50">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground text-[11px] font-medium">Visit Cadence</span>
                    <span className="font-mono font-bold text-foreground">{customer.health_score.breakdown.visit_score}/25</span>
                  </div>
                  <p className="text-[11px] font-semibold text-primary mt-1 truncate">{customer.health_score.breakdown.visit_label}</p>
                </div>

                <div className="p-2.5 rounded-xl bg-muted/40 border border-border/50">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground text-[11px] font-medium">Order Recency</span>
                    <span className="font-mono font-bold text-foreground">{customer.health_score.breakdown.order_score}/35</span>
                  </div>
                  <p className="text-[11px] font-semibold text-primary mt-1 truncate">{customer.health_score.breakdown.order_label}</p>
                </div>

                <div className="p-2.5 rounded-xl bg-muted/40 border border-border/50">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground text-[11px] font-medium">Txn Depth</span>
                    <span className="font-mono font-bold text-foreground">{customer.health_score.breakdown.volume_score}/25</span>
                  </div>
                  <p className="text-[11px] font-semibold text-primary mt-1 truncate">{customer.health_score.breakdown.volume_label}</p>
                </div>

                <div className="p-2.5 rounded-xl bg-muted/40 border border-border/50">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground text-[11px] font-medium">Profile Audit</span>
                    <span className="font-mono font-bold text-foreground">{customer.health_score.breakdown.profile_score}/15</span>
                  </div>
                  <p className="text-[11px] font-semibold text-primary mt-1 truncate">
                    {customer.location_verified ? 'GPS Verified' : 'Pending GPS'}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─── FINANCIAL 360° METRICS BAR ─── */}
        {canViewStatement && customer.financial_summary && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Outstanding Balance */}
            <div className="bg-card border border-border rounded-3xl p-5 shadow-sm relative overflow-hidden flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Outstanding Balance</span>
                <span className={cn(
                  'px-2 py-0.5 rounded-full text-[11px] font-extrabold uppercase',
                  customer.financial_summary.balance_type === 'Dr'
                    ? 'bg-rose-500/10 text-rose-600 border border-rose-500/20'
                    : 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20'
                )}>
                  {customer.financial_summary.balance_type}
                </span>
              </div>
              <div className="my-2">
                <div className="text-2xl sm:text-3xl font-black tracking-tight text-foreground flex items-baseline gap-1">
                  <span className="text-lg font-bold text-muted-foreground">₹</span>
                  <span>{Math.abs(customer.financial_summary.closing_balance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                </div>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  {customer.financial_summary.balance_type === 'Dr' ? 'Receivable from customer' : 'Advance / Credit balance'}
                </p>
              </div>
              <div className="pt-2 border-t border-border/60 flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleShareStatement}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-colors shadow-sm"
                  title="Send account statement via WhatsApp"
                >
                  <Share2 className="w-3.5 h-3.5" />
                  <span>Share Statement</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleTabChange('statement')}
                  className="inline-flex items-center justify-center p-1.5 rounded-xl border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  title="View Ledger Statement"
                >
                  <Receipt className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Total Billed (Sales Debit) */}
            <div className="bg-card border border-border rounded-3xl p-5 shadow-sm relative overflow-hidden flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Total Billed</span>
                <div className="p-1.5 rounded-xl bg-blue-500/10 text-blue-600">
                  <ArrowUpRight className="w-4 h-4" />
                </div>
              </div>
              <div className="my-2">
                <div className="text-2xl sm:text-3xl font-black tracking-tight text-foreground flex items-baseline gap-1">
                  <span className="text-lg font-bold text-muted-foreground">₹</span>
                  <span>{(customer.financial_summary.total_billed_debit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                </div>
                <p className="text-[11px] text-muted-foreground mt-0.5">Gross debits / sales invoices</p>
              </div>
              <div className="pt-2 border-t border-border/60 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>Opening: ₹{(customer.financial_summary.opening_balance || 0).toLocaleString('en-IN')} {customer.financial_summary.opening_type}</span>
              </div>
            </div>

            {/* Total Collected (Receipts Credit) */}
            <div className="bg-card border border-border rounded-3xl p-5 shadow-sm relative overflow-hidden flex flex-col justify-between">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Total Collected</span>
                <div className="p-1.5 rounded-xl bg-emerald-500/10 text-emerald-600">
                  <ArrowDownRight className="w-4 h-4" />
                </div>
              </div>
              <div className="my-2">
                <div className="text-2xl sm:text-3xl font-black tracking-tight text-emerald-600 dark:text-emerald-400 flex items-baseline gap-1">
                  <span className="text-lg font-bold text-muted-foreground">₹</span>
                  <span>{(customer.financial_summary.total_collected_credit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                </div>
                <p className="text-[11px] text-muted-foreground mt-0.5">Total payments cleared</p>
              </div>
              <div className="pt-2 border-t border-border/60 flex items-center justify-between text-[11px]">
                <span className="text-muted-foreground">Collection Ratio:</span>
                <span className="font-bold text-foreground">
                  {customer.financial_summary.total_billed_debit > 0
                    ? `${Math.min(100, Math.round((customer.financial_summary.total_collected_credit / customer.financial_summary.total_billed_debit) * 100))}%`
                    : '100%'}
                </span>
              </div>
            </div>

            {/* Commercial Desk / Quick Actions */}
            <div className="bg-gradient-to-br from-primary/5 via-card to-primary/10 border border-primary/20 rounded-3xl p-5 shadow-sm flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-primary uppercase tracking-wider">Commercial Desk</span>
                <h4 className="text-base font-extrabold text-foreground mt-1">Actions & Orders</h4>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Direct billing and order placement for this account.
                </p>
              </div>
              <div className="pt-3 flex flex-col gap-2">
                <Link
                  href={`/orders/new?customer_id=${customer.profile_id}${customer.ledger_id ? `&ledger_id=${customer.ledger_id}` : ''}`}
                  className="w-full inline-flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-bold shadow-sm transition-colors"
                >
                  <ShoppingCart className="w-3.5 h-3.5" />
                  <span>Create New Order</span>
                </Link>
                <Link
                  href={`/check-in?${customer.ledger_id ? `ledger_id=${customer.ledger_id}` : `profile_id=${customer.profile_id}`}&name=${encodeURIComponent(customer.name || customer.tally_details?.name || '')}`}
                  className="w-full inline-flex items-center justify-center gap-2 py-2 px-3 rounded-xl border border-border bg-background hover:bg-muted text-foreground text-xs font-bold transition-colors"
                >
                  <MapPin className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Check-In & Record Visit</span>
                </Link>
              </div>
            </div>
          </div>
        )}

        {(!canViewStatement || !customer.financial_summary) && (
          <div className="bg-gradient-to-br from-primary/5 via-card to-primary/10 border border-primary/20 rounded-3xl p-5 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <span className="text-xs font-bold text-primary uppercase tracking-wider">Commercial Desk</span>
              <h4 className="text-base font-extrabold text-foreground mt-1">Actions & Quick Access</h4>
              <p className="text-xs text-muted-foreground mt-0.5">
                Direct billing and visit check-in for this customer account.
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap w-full sm:w-auto">
              {canViewOrders && (
                <Link
                  href={`/orders/new?customer_id=${customer.profile_id}${customer.ledger_id ? `&ledger_id=${customer.ledger_id}` : ''}`}
                  className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-bold shadow-sm transition-colors"
                >
                  <ShoppingCart className="w-3.5 h-3.5" />
                  <span>Create New Order</span>
                </Link>
              )}
              {canViewVisits && (
                <Link
                  href={`/check-in?${customer.ledger_id ? `ledger_id=${customer.ledger_id}` : `profile_id=${customer.profile_id}`}&name=${encodeURIComponent(customer.name || customer.tally_details?.name || '')}`}
                  className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-border bg-background hover:bg-muted text-foreground text-xs font-bold transition-colors"
                >
                  <MapPin className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Check-In & Record Visit</span>
                </Link>
              )}
            </div>
          </div>
        )}

        {/* ─── 360° VIEW NAVIGATION TABS ─── */}
        {allowedTabs.length > 0 && (
          <div className="flex items-center gap-1 sm:gap-2 p-1 bg-muted/60 dark:bg-muted/30 sm:bg-transparent sm:p-0 rounded-2xl sm:rounded-none border sm:border-0 sm:border-b border-border/80 sm:border-border sm:pb-1 shadow-2xs sm:shadow-none overflow-x-auto">
            {/* Tab 1: Store & Partners */}
            {canViewStore && (
              <button
                type="button"
                onClick={() => handleTabChange('overview')}
                className={cn(
                  'flex-1 sm:flex-initial flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 px-2 py-2 sm:px-4 sm:py-2.5 rounded-xl sm:rounded-2xl font-bold text-[11px] sm:text-sm transition-all text-center min-w-0',
                  mainTab === 'overview'
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/40 sm:hover:bg-muted/60'
                )}
              >
                <Store className="w-4 h-4 shrink-0" />
                <span className="sm:hidden truncate">Store</span>
                <span className="hidden sm:inline whitespace-nowrap">Store & Partners</span>
              </button>
            )}

          {/* Tab 2: Ledger Statement */}
          {canViewStatement && (
            <button
              type="button"
              onClick={() => handleTabChange('statement')}
              className={cn(
                'flex-1 sm:flex-initial flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 px-2 py-2 sm:px-4 sm:py-2.5 rounded-xl sm:rounded-2xl font-bold text-[11px] sm:text-sm transition-all text-center min-w-0 relative',
                mainTab === 'statement'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground hover:bg-background/40 sm:hover:bg-muted/60'
              )}
            >
              <div className="flex items-center gap-1">
                <Receipt className="w-4 h-4 shrink-0" />
                {customer.recent_vouchers && customer.recent_vouchers.length > 0 && (
                  <span className={cn(
                    'sm:hidden px-1.5 py-0.2 rounded-full text-[9px] font-extrabold leading-tight',
                    mainTab === 'statement' ? 'bg-white/20 text-white' : 'bg-background text-foreground border border-border/70'
                  )}>
                    {customer.recent_vouchers.length}
                  </span>
                )}
              </div>
              <span className="sm:hidden truncate">Ledger</span>
              <span className="hidden sm:inline whitespace-nowrap">Ledger Statement</span>
              {customer.recent_vouchers && customer.recent_vouchers.length > 0 && (
                <span className={cn(
                  'hidden sm:inline-block px-2 py-0.5 rounded-full text-[10px] font-extrabold',
                  mainTab === 'statement' ? 'bg-white/20 text-white' : 'bg-muted text-foreground'
                )}>
                  {customer.recent_vouchers.length}
                </span>
              )}
            </button>
          )}

          {/* Tab 3: Order History */}
          {canViewOrders && (
            <button
              type="button"
              onClick={() => handleTabChange('orders')}
              className={cn(
                'flex-1 sm:flex-initial flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 px-2 py-2 sm:px-4 sm:py-2.5 rounded-xl sm:rounded-2xl font-bold text-[11px] sm:text-sm transition-all text-center min-w-0 relative',
                mainTab === 'orders'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground hover:bg-background/40 sm:hover:bg-muted/60'
              )}
            >
              <div className="flex items-center gap-1">
                <ShoppingCart className="w-4 h-4 shrink-0" />
                {customer.recent_orders && customer.recent_orders.length > 0 && (
                  <span className={cn(
                    'sm:hidden px-1.5 py-0.2 rounded-full text-[9px] font-extrabold leading-tight',
                    mainTab === 'orders' ? 'bg-white/20 text-white' : 'bg-background text-foreground border border-border/70'
                  )}>
                    {customer.recent_orders.length}
                  </span>
                )}
              </div>
              <span className="sm:hidden truncate">Orders</span>
              <span className="hidden sm:inline whitespace-nowrap">Order History</span>
              {customer.recent_orders && customer.recent_orders.length > 0 && (
                <span className={cn(
                  'hidden sm:inline-block px-2 py-0.5 rounded-full text-[10px] font-extrabold',
                  mainTab === 'orders' ? 'bg-white/20 text-white' : 'bg-muted text-foreground'
                )}>
                  {customer.recent_orders.length}
                </span>
              )}
            </button>
          )}

          {/* Tab 4: Field Visits */}
          {canViewVisits && (
            <button
              type="button"
              onClick={() => handleTabChange('visits')}
              className={cn(
                'flex-1 sm:flex-initial flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 px-2 py-2 sm:px-4 sm:py-2.5 rounded-xl sm:rounded-2xl font-bold text-[11px] sm:text-sm transition-all text-center min-w-0 relative',
                mainTab === 'visits'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground hover:bg-background/40 sm:hover:bg-muted/60'
              )}
            >
              <div className="flex items-center gap-1">
                <Clock className="w-4 h-4 shrink-0" />
                {customer.visits && customer.visits.length > 0 && (
                  <span className={cn(
                    'sm:hidden px-1.5 py-0.2 rounded-full text-[9px] font-extrabold leading-tight',
                    mainTab === 'visits' ? 'bg-white/20 text-white' : 'bg-background text-foreground border border-border/70'
                  )}>
                    {customer.visits.length}
                  </span>
                )}
              </div>
              <span className="sm:hidden truncate">Visits</span>
              <span className="hidden sm:inline whitespace-nowrap">Field Visits</span>
              {customer.visits && customer.visits.length > 0 && (
                <span className={cn(
                  'hidden sm:inline-block px-2 py-0.5 rounded-full text-[10px] font-extrabold',
                  mainTab === 'visits' ? 'bg-white/20 text-white' : 'bg-muted text-foreground'
                )}>
                  {customer.visits.length}
                </span>
              )}
            </button>
          )}
        </div>
        )}

        {/* ─── TAB 1: STORE & PARTNERS (OVERVIEW) ─── */}
        {mainTab === 'overview' && canViewStore && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* -------- LEFT COLUMN (Photos & Visits) -------- */}
          <div className="lg:col-span-7 space-y-6">
            {/* 📸 Photos Showcase Card */}
            <div className="bg-card border border-border rounded-3xl p-6 shadow-sm space-y-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-4">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-primary/10 text-primary">
                    <ImageIcon className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="font-bold text-lg leading-tight">Customer & Shop Photos</h2>
                    <p className="text-xs text-muted-foreground">
                      Stored in ImageKit under <code className="text-primary font-mono text-[11px]">/customers/{customer.ledger_id ? `ledger_${customer.ledger_id}` : `profile_${customer.profile_id}`}/</code>
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => {
                    setUploadType('shop_front')
                    setShowUploadModal(true)
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary text-primary-foreground font-semibold text-xs hover:bg-primary/90 transition-colors shadow-sm self-start sm:self-auto"
                >
                  <Plus className="w-4 h-4" />
                  <span>Upload Photo</span>
                </button>
              </div>

              {/* Photo Filter Tabs */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs font-semibold no-scrollbar">
                {[
                  { id: 'all', label: `All (${customer.photos.length})` },
                  { id: 'customer_owner', label: 'Owner Portrait' },
                  { id: 'shop_front', label: 'Storefront' },
                  { id: 'visit_checkin', label: 'Check-In Snaps' },
                  { id: 'shop_inside', label: 'Inside Shop' },
                  { id: 'shop_board', label: 'Signboard' },
                  { id: 'visiting_card', label: 'Visiting Card' },
                  { id: 'qr_code', label: 'UPI QR Code' },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setPhotoFilter(tab.id)}
                    className={cn(
                      'px-3 py-1.5 rounded-xl transition-all whitespace-nowrap',
                      photoFilter === tab.id
                        ? 'bg-primary text-primary-foreground shadow-sm'
                        : 'bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground'
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Photos Grid */}
              {filteredPhotos.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground border border-dashed border-border rounded-2xl space-y-2">
                  <Camera className="w-8 h-8 mx-auto opacity-40 mb-1" />
                  <p className="text-sm font-semibold">No photos in this category yet</p>
                  <p className="text-xs max-w-sm mx-auto text-muted-foreground">
                    Upload owner portraits, shop façade, interior shelves, visiting cards, or counter UPI QR codes.
                  </p>
                  <button
                    onClick={() => {
                      setUploadType(photoFilter !== 'all' ? photoFilter : 'shop_front')
                      setShowUploadModal(true)
                    }}
                    className="mt-2 inline-flex items-center gap-1 px-3 py-1.5 bg-muted hover:bg-muted/80 text-foreground text-xs font-semibold rounded-xl"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add First Photo</span>
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3.5">
                  {filteredPhotos.map((photo) => {
                    const badge = photoTypeLabels[photo.photo_type] || photoTypeLabels.other
                    const IconComponent = badge.icon
                    return (
                      <div
                        key={photo.id}
                        className="group relative rounded-2xl overflow-hidden border border-border bg-card shadow-sm hover:shadow-md transition-all flex flex-col justify-between"
                      >
                        {/* Image Frame */}
                        <div
                          onClick={() => setLightboxPhoto(photo)}
                          className="aspect-square bg-muted cursor-pointer overflow-hidden relative"
                        >
                          <img
                            src={photo.imagekit_thumbnail_url || photo.imagekit_url}
                            alt={photo.caption || photo.photo_type}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                            loading="lazy"
                          />

                          {/* Hover Lightbox Indicator */}
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white pointer-events-none">
                            <Maximize2 className="w-6 h-6" />
                          </div>

                          {/* Top Category Badge */}
                          <div className="absolute top-2 left-2 z-10 max-w-[70%]">
                            <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase backdrop-blur-md border shadow-sm truncate', badge.color)}>
                              <IconComponent className="w-2.5 h-2.5 shrink-0" />
                              <span className="truncate">{badge.label}</span>
                            </span>
                          </div>

                          {/* Primary Badge */}
                          {photo.is_primary && (
                            <div className="absolute top-2 right-2 z-10">
                              <span className="p-1 rounded-md bg-amber-500 text-white shadow-sm" title="Primary Display Photo">
                                <Sparkles className="w-3 h-3" />
                              </span>
                            </div>
                          )}

                          {/* Delete Button (Visible on Mobile) */}
                          {canDelete && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleDeletePhoto(photo.id)
                              }}
                              className="absolute bottom-2 right-2 z-20 p-1.5 rounded-lg bg-black/70 hover:bg-rose-600 text-white shadow-md backdrop-blur-sm transition-all opacity-90 hover:opacity-100 active:scale-95 flex items-center justify-center"
                              title="Delete photo"
                              aria-label="Delete photo"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>

                        {/* Bottom Info Bar */}
                        <div className="p-2.5 space-y-1 bg-card">
                          {photo.caption && (
                            <p className="text-xs font-semibold text-foreground line-clamp-1">
                              {photo.caption}
                            </p>
                          )}
                          <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                            <span className="truncate max-w-[90px]">{photo.uploaded_by_name}</span>
                            {photo.latitude && photo.longitude && (
                              <span className="inline-flex items-center gap-0.5 text-emerald-600 font-medium" title="Geotagged on-site">
                                <Compass className="w-3 h-3" />
                                <span>GPS</span>
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* 🕒 Past Visits & Check-In History */}
            <div className="bg-card border border-border rounded-3xl p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <History className="w-5 h-5 text-primary" />
                  <h3 className="font-bold text-base">Past Sales Visits & Check-Ins</h3>
                </div>
                <span className="text-xs text-muted-foreground">{customer.visits.length} recorded</span>
              </div>

              {customer.visits.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground border border-dashed border-border rounded-xl">
                  <Clock className="w-6 h-6 mx-auto opacity-40 mb-1" />
                  <p className="text-xs font-medium">No check-in visits recorded yet</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    Field check-ins logged via the check-in module will show up here.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {customer.visits.map((v) => (
                    <div
                      key={v.id}
                      className="p-3.5 rounded-2xl border border-border bg-muted/20 hover:bg-muted/40 transition-colors flex items-start justify-between gap-3 text-xs"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-foreground">{v.salesperson}</span>
                          <span className="text-[11px] text-muted-foreground">
                            {v.created_at ? new Date(v.created_at).toLocaleString() : ''}
                          </span>
                        </div>

                        {v.comments && (
                          <p className="text-muted-foreground text-xs">{v.comments}</p>
                        )}

                        {v.latitude && v.longitude && (
                          <div className="text-[10px] text-muted-foreground font-mono">
                            📍 {v.latitude.toFixed(5)}, {v.longitude.toFixed(5)}
                          </div>
                        )}
                      </div>

                      {v.photo_url && (
                        <div
                          onClick={() => setLightboxPhoto({
                            id: v.id,
                            photo_type: 'visit_checkin',
                            imagekit_url: v.photo_url!,
                            imagekit_thumbnail_url: v.photo_url!,
                            imagekit_file_path: null,
                            caption: `Visit by ${v.salesperson}`,
                            latitude: v.latitude,
                            longitude: v.longitude,
                            is_primary: false,
                            uploaded_by_name: v.salesperson,
                            created_at: v.created_at,
                          })}
                          className="w-14 h-14 rounded-xl overflow-hidden border border-border cursor-pointer flex-shrink-0"
                        >
                          <img src={v.photo_url} alt="Check-in snap" className="w-full h-full object-cover" />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* -------- RIGHT COLUMN (Info, Location, Tally) -------- */}
          <div className="lg:col-span-5 space-y-6">
            {/* 👥 Owners & Business Partners Card */}
            <div className="bg-card border border-border rounded-3xl p-6 shadow-sm space-y-4 relative overflow-hidden">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-violet-500/10 text-violet-600 dark:text-violet-400">
                    <Users className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold text-base">Owners & Partners</h3>
                      <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-muted text-muted-foreground">
                        {customer.owners?.length || 0}
                      </span>
                    </div>
                    <p className="text-[11px] text-muted-foreground">Multiple owners, partners & decision makers</p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleOpenAddOwner}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold text-xs transition-all shadow-sm"
                >
                  <UserPlus className="w-3.5 h-3.5" />
                  <span>+ Partner</span>
                </button>
              </div>

              {(!customer.owners || customer.owners.length === 0) ? (
                <div className="py-6 text-center border border-dashed border-border rounded-2xl p-4">
                  <Users className="w-8 h-8 mx-auto opacity-30 mb-1.5 text-muted-foreground" />
                  <p className="text-xs font-semibold text-foreground">No partners recorded yet</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5 max-w-xs mx-auto">
                    Record details of all shop owners, partners, and key decision makers here.
                  </p>
                  <button
                    type="button"
                    onClick={handleOpenAddOwner}
                    className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary text-primary-foreground font-semibold text-xs hover:bg-primary/90 transition-colors"
                  >
                    <UserPlus className="w-3.5 h-3.5" />
                    <span>Add First Owner</span>
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {customer.owners.map((owner, idx) => (
                    <div
                      key={owner.id || `owner-${idx}`}
                      className={cn(
                        'p-4 rounded-2xl border transition-all relative group',
                        owner.is_primary
                          ? 'border-violet-500/30 bg-violet-500/[0.03] shadow-sm'
                          : 'border-border bg-muted/20 hover:bg-muted/40'
                      )}
                    >
                      <div className="flex items-start gap-3.5">
                        {/* Owner Avatar with 1-Tap Camera */}
                        <div className="relative group/avatar flex-shrink-0">
                          <div 
                            className="w-13 h-13 sm:w-14 sm:h-14 rounded-2xl overflow-hidden border border-border bg-muted flex items-center justify-center shadow-sm cursor-pointer hover:ring-2 hover:ring-primary/40 transition-all"
                            onClick={() => owner.photo_url && handleOpenOwnerPhoto(owner.photo_url)}
                            title={owner.photo_url ? "Click to view and scroll all customer photos" : undefined}
                          >
                            {owner.photo_url ? (
                              <img src={owner.photo_url} alt={owner.name} className="w-full h-full object-cover" />
                            ) : (
                              <UserIcon className="w-7 h-7 text-muted-foreground/40" />
                            )}
                          </div>
                          {owner.id && (
                            <button
                              type="button"
                              onClick={() => {
                                setOwnerForPhoto(owner)
                                setOwnerPhotoPreview(null)
                              }}
                              className="absolute inset-0 bg-black/60 rounded-2xl opacity-0 group-hover/avatar:opacity-100 transition-opacity flex flex-col items-center justify-center text-white text-[10px] font-semibold gap-0.5"
                              title="Upload / Change Photo for this owner"
                            >
                              <Camera className="w-4 h-4 text-white" />
                              <span>Snap</span>
                            </button>
                          )}
                        </div>

                        {/* Owner Details */}
                        <div className="flex-1 min-w-0 space-y-1">
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <h4 className="font-bold text-sm text-foreground truncate">
                                {owner.name}
                              </h4>
                              {owner.is_primary && (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/10 text-amber-600 border border-amber-500/20 flex-shrink-0">
                                  <Crown className="w-3 h-3 text-amber-500" />
                                  <span>Primary</span>
                                </span>
                              )}
                            </div>

                            {/* Owner Row Actions */}
                            {owner.id && (
                              <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100 transition-opacity flex-shrink-0">
                                {!owner.is_primary && (
                                  <button
                                    type="button"
                                    onClick={() => handleSetPrimaryOwner(owner)}
                                    className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-amber-500 transition-colors"
                                    title="Make this owner Primary Contact"
                                  >
                                    <Crown className="w-3.5 h-3.5" />
                                  </button>
                                )}
                                <button
                                  type="button"
                                  onClick={() => handleOpenEditOwner(owner)}
                                  className="p-1 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                                  title="Edit owner details"
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                </button>
                                {canDelete && (
                                  <button
                                    type="button"
                                    onClick={() => setOwnerToDelete(owner)}
                                    className="p-1 rounded-lg hover:bg-rose-500/10 text-muted-foreground hover:text-rose-600 transition-colors"
                                    title="Remove this owner"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                )}
                              </div>
                            )}
                          </div>

                          <div className="flex items-center gap-2 flex-wrap text-xs">
                            <span className="text-[11px] font-semibold text-muted-foreground bg-muted px-2 py-0.5 rounded-md">
                              {owner.designation || 'Owner / Partner'}
                            </span>
                            {owner.email && (
                              <span className="text-[11px] text-muted-foreground truncate max-w-[160px]">
                                {owner.email}
                              </span>
                            )}
                          </div>

                          {owner.notes && (
                            <p className="text-[11px] text-muted-foreground italic line-clamp-1 pt-0.5">
                              "{owner.notes}"
                            </p>
                          )}

                          {/* Quick Contact Bar for this specific owner */}
                          <div className="flex items-center gap-2 pt-2">
                            {owner.phone ? (
                              <a
                                href={`tel:${owner.phone}`}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 text-xs font-semibold transition-colors"
                                title={`Call ${owner.name}`}
                              >
                                <Phone className="w-3 h-3" />
                                <span>{owner.phone}</span>
                              </a>
                            ) : (
                              <span className="text-[11px] text-muted-foreground italic">No phone saved</span>
                            )}

                            {owner.whatsapp_number && (
                              <a
                                href={`https://wa.me/91${owner.whatsapp_number.replace(/\D/g, '')}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#25D366]/10 text-[#25D366] hover:bg-[#25D366]/20 text-xs font-semibold transition-colors"
                                title={`WhatsApp ${owner.name}`}
                              >
                                <MessageCircle className="w-3 h-3" />
                                <span>WhatsApp</span>
                              </a>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 📍 Contact & Address Card */}
            <div className="bg-card border border-border rounded-3xl p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <Building className="w-5 h-5 text-primary" />
                  <h3 className="font-bold text-base">Contact & Address</h3>
                </div>
                <button
                  onClick={() => setShowEditModal(true)}
                  className="text-xs text-primary font-semibold hover:underline flex items-center gap-1"
                >
                  <Edit2 className="w-3 h-3" />
                  <span>Edit</span>
                </button>
              </div>

              <div className="space-y-3 text-xs">
                {/* Contact Person */}
                <div>
                  <span className="text-muted-foreground block text-[11px]">Contact Person / Owner</span>
                  <span className="font-bold text-sm text-foreground">
                    {customer.contact_person || 'Not specified'}
                  </span>
                </div>

                {/* Phones */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-muted-foreground block text-[11px]">Primary Phone</span>
                    <div className="flex items-center gap-1 mt-0.5">
                      <span className="font-mono text-foreground font-semibold">
                        {customer.phone || customer.mobile || '—'}
                      </span>
                      {(customer.phone || customer.mobile) && (
                        <button
                          onClick={() => copyToClipboard(customer.phone || customer.mobile, 'phone')}
                          className="p-1 text-muted-foreground hover:text-foreground"
                          title="Copy phone"
                        >
                          {copiedField === 'phone' ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                        </button>
                      )}
                    </div>
                  </div>

                  <div>
                    <span className="text-muted-foreground block text-[11px]">WhatsApp</span>
                    <div className="flex items-center gap-1 mt-0.5">
                      <span className="font-mono text-foreground font-semibold">
                        {customer.whatsapp_number || customer.mobile || '—'}
                      </span>
                      {(customer.whatsapp_number || customer.mobile) && (
                        <button
                          onClick={() => copyToClipboard(customer.whatsapp_number || customer.mobile, 'wa')}
                          className="p-1 text-muted-foreground hover:text-foreground"
                          title="Copy WhatsApp"
                        >
                          {copiedField === 'wa' ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Email */}
                {customer.email && (
                  <div>
                    <span className="text-muted-foreground block text-[11px]">Email Address</span>
                    <span className="font-medium text-foreground">{customer.email}</span>
                  </div>
                )}

                {/* Address */}
                <div className="pt-2 border-t border-border">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground block text-[11px]">Shop Address</span>
                    {customer.address && (
                      <button
                        onClick={() => copyToClipboard(customer.address, 'addr')}
                        className="text-[10px] text-primary hover:underline flex items-center gap-0.5"
                      >
                        {copiedField === 'addr' ? 'Copied!' : 'Copy'}
                      </button>
                    )}
                  </div>
                  <p className="font-medium text-foreground mt-0.5 leading-relaxed">
                    {customer.address || 'Address not registered'}
                  </p>
                  <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground mt-1.5">
                    {customer.locality && <span className="bg-muted px-2 py-0.5 rounded-md">📍 {customer.locality}</span>}
                    {customer.city && <span className="bg-muted px-2 py-0.5 rounded-md">🏙️ {customer.city}</span>}
                    {customer.state && <span className="bg-muted px-2 py-0.5 rounded-md">{customer.state}</span>}
                    {customer.pincode && <span className="bg-muted px-2 py-0.5 rounded-md">📮 {customer.pincode}</span>}
                  </div>
                </div>

                {/* Frequency & Notes */}
                {(customer.visit_frequency || customer.notes) && (
                  <div className="pt-2 border-t border-border space-y-2">
                    {customer.visit_frequency && (
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground text-[11px]">Visit Schedule</span>
                        <span className="font-semibold text-foreground capitalize">{customer.visit_frequency}</span>
                      </div>
                    )}
                    {customer.notes && (
                      <div>
                        <span className="text-muted-foreground text-[11px] block">Field Notes / Instructions</span>
                        <p className="text-muted-foreground mt-0.5 italic">{customer.notes}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* 🧭 Master GPS & Verification Card */}
            <div className="bg-card border border-border rounded-3xl p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <MapPin className="w-5 h-5 text-primary" />
                  <h3 className="font-bold text-base">GPS Location & Audit</h3>
                </div>
                <button
                  onClick={() => {
                    setTagForm({
                      latitude: customer.latitude ? customer.latitude.toString() : '',
                      longitude: customer.longitude ? customer.longitude.toString() : '',
                      reason: 'Master shop location calibration',
                    })
                    setShowTagModal(true)
                  }}
                  className="text-xs text-primary font-semibold hover:underline flex items-center gap-1"
                >
                  <Compass className="w-3 h-3" />
                  <span>Calibrate</span>
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-muted-foreground block text-[11px]">Master Coordinates</span>
                  {customer.has_location ? (
                    <div className="flex items-center gap-2 mt-0.5 font-mono text-sm font-semibold text-foreground">
                      <span>{customer.latitude?.toFixed(6)}, {customer.longitude?.toFixed(6)}</span>
                      <button
                        onClick={() => copyToClipboard(`${customer.latitude},${customer.longitude}`, 'coords')}
                        className="p-1 text-muted-foreground hover:text-foreground"
                      >
                        {copiedField === 'coords' ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                      </button>
                    </div>
                  ) : (
                    <span className="text-amber-500 font-medium">GPS location not established yet</span>
                  )}
                </div>

                {customer.location_verified_at && (
                  <div className="text-[11px] text-muted-foreground">
                    Verified on: <b className="text-foreground">{new Date(customer.location_verified_at).toLocaleDateString()}</b>
                  </div>
                )}

                <a
                  href={customer.maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-primary-foreground font-bold text-xs hover:bg-primary/90 transition-colors shadow-sm"
                >
                  <Navigation className="w-4 h-4" />
                  <span>Open in Google Maps (Turn-by-Turn)</span>
                  <ExternalLink className="w-3 h-3 opacity-70" />
                </a>
              </div>
            </div>

            {/* 🔗 Tally Ledger Linkage Card */}
            <div className="bg-card border border-border rounded-3xl p-6 shadow-sm space-y-3">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <Building className="w-5 h-5 text-primary" />
                  <h3 className="font-bold text-base">Tally Ledger Linkage</h3>
                </div>
                {customer.ledger_id ? (
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                    Linked
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-amber-500/10 text-amber-600 border border-amber-500/20">
                    Unmapped
                  </span>
                )}
              </div>

              {customer.tally_details ? (
                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Ledger Name:</span>
                    <span className="font-bold text-foreground">{customer.tally_details.name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Ledger ID:</span>
                    <span className="font-mono text-foreground font-semibold">#{customer.tally_details.ledger_id}</span>
                  </div>
                  {customer.tally_details.state && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">State:</span>
                      <span className="text-foreground">{customer.tally_details.state}</span>
                    </div>
                  )}
                  <p className="text-[11px] text-muted-foreground pt-1 border-t border-border">
                    Linked to Tally Sundry Debtors. Accounting entries & vouchers remain strictly read-only and isolated.
                  </p>
                </div>
              ) : (
                <div className="space-y-2.5 text-xs">
                  <p className="text-muted-foreground">
                    This customer is currently a standalone field profile with zero Tally accounting association.
                  </p>
                  {isAdmin && (
                    <button
                      onClick={handleOpenLinkModal}
                      className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-primary/10 text-primary border border-primary/30 font-bold hover:bg-primary/20 transition-colors"
                    >
                      <Link2 className="w-4 h-4" />
                      <span>Link to Tally Sundry Debtor</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
        )}

        {/* ─── TAB 2: LEDGER STATEMENT ─── */}
        {mainTab === 'statement' && canViewStatement && (
          <div className="bg-card border border-border rounded-3xl p-6 sm:p-8 shadow-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-2xl bg-primary/10 text-primary">
                  <Receipt className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-extrabold text-foreground">Account Ledger Statement</h2>
                  <p className="text-xs text-muted-foreground">
                    Live ERP transactions, sales invoices, receipts, and running balance
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={handleShareStatement}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-sm transition-colors"
                >
                  <Share2 className="w-4 h-4" />
                  <span>Share on WhatsApp</span>
                </button>
                <button
                  type="button"
                  onClick={() => fetchCustomer(true)}
                  className="p-2 rounded-xl border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  title="Refresh statement"
                >
                  <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin text-primary')} />
                </button>
              </div>
            </div>

            {!customer.ledger_id ? (
              <div className="py-16 text-center border-2 border-dashed border-border rounded-2xl p-6">
                <Receipt className="w-12 h-12 mx-auto opacity-30 mb-2 text-muted-foreground" />
                <h3 className="font-bold text-base text-foreground">No Accounting Transactions Found</h3>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                  This customer has not been linked to a Tally ledger. Link to view financial statements.
                </p>
                {isAdmin && (
                  <button
                    type="button"
                    onClick={handleOpenLinkModal}
                    className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground font-semibold text-xs hover:bg-primary/90 transition-colors shadow-sm"
                  >
                    <Link2 className="w-4 h-4" />
                    <span>Link to Tally Ledger</span>
                  </button>
                )}
              </div>
            ) : loadingLedger ? (
              <div className="py-16 flex justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
              </div>
            ) : ledgerInfo ? (
              <div className="pt-2">
                <LedgerDetailsClient
                  ledgerInfo={ledgerInfo}
                  transactions={transactions}
                  customerPhone={customer.whatsapp_number || customer.mobile || customer.phone || ''}
                  customerName={customer.name}
                />
              </div>
            ) : (
              <div className="py-16 text-center text-muted-foreground">
                Failed to load ledger statement.
              </div>
            )}
          </div>
        )}

        {/* ─── TAB 3: ORDER HISTORY ─── */}
        {mainTab === 'orders' && canViewOrders && (
          <div className="bg-card border border-border rounded-3xl p-6 sm:p-8 shadow-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-2xl bg-indigo-500/10 text-indigo-600">
                  <ShoppingCart className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-extrabold text-foreground">Customer Orders History</h2>
                  <p className="text-xs text-muted-foreground">
                    Portal sales orders taken by field representatives
                  </p>
                </div>
              </div>

              <Link
                href={`/orders/new?customer_id=${customer.profile_id}${customer.ledger_id ? `&ledger_id=${customer.ledger_id}` : ''}`}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-xs shadow-sm transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>+ Create New Order</span>
              </Link>
            </div>

            {(!customer.recent_orders || customer.recent_orders.length === 0) ? (
              <div className="py-16 text-center border-2 border-dashed border-border rounded-2xl p-6">
                <ShoppingCart className="w-12 h-12 mx-auto opacity-30 mb-2 text-muted-foreground" />
                <h3 className="font-bold text-base text-foreground">No Portal Orders Placed Yet</h3>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                  Sales orders booked by field agents during shop visits will appear here with live sync status.
                </p>
                <Link
                  href={`/orders/new?customer_id=${customer.profile_id}${customer.ledger_id ? `&ledger_id=${customer.ledger_id}` : ''}`}
                  className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground font-semibold text-xs hover:bg-primary/90 transition-colors shadow-sm"
                >
                  <Plus className="w-4 h-4" />
                  <span>Place First Order</span>
                </Link>
              </div>
            ) : (
              <div className="border border-border rounded-2xl overflow-hidden shadow-xs">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-muted/60 border-b border-border text-muted-foreground font-bold uppercase tracking-wider text-[10px]">
                        <th className="p-3.5 pl-4">Order ID</th>
                        <th className="p-3.5">Date</th>
                        <th className="p-3.5">Status</th>
                        <th className="p-3.5 text-center">Items</th>
                        <th className="p-3.5 text-right pr-4">Total Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {customer.recent_orders.map((ord) => (
                        <tr key={ord.id} className="hover:bg-muted/40 transition-colors">
                          <td className="p-3.5 pl-4 font-mono font-bold text-primary">
                            #{ord.id}
                          </td>
                          <td className="p-3.5 text-muted-foreground whitespace-nowrap">
                            {ord.created_at ? new Date(ord.created_at).toLocaleDateString('en-IN', {
                              day: '2-digit',
                              month: 'short',
                              year: 'numeric',
                            }) : '—'}
                          </td>
                          <td className="p-3.5 whitespace-nowrap">
                            <span className={cn(
                              'px-2.5 py-0.5 rounded-full text-[11px] font-extrabold uppercase',
                              ord.status?.toLowerCase() === 'delivered'
                                ? 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20'
                                : ord.status?.toLowerCase() === 'confirmed'
                                ? 'bg-blue-500/10 text-blue-600 border border-blue-500/20'
                                : 'bg-amber-500/10 text-amber-600 border border-amber-500/20'
                            )}>
                              {ord.status || 'Pending'}
                            </span>
                          </td>
                          <td className="p-3.5 text-center font-bold text-foreground">
                            {ord.total_items} items
                          </td>
                          <td className="p-3.5 pr-4 text-right font-mono font-black text-foreground">
                            ₹{(ord.total_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ─── TAB 4: FIELD VISITS TIMELINE ─── */}
        {mainTab === 'visits' && canViewVisits && (
          <div className="bg-card border border-border rounded-3xl p-6 sm:p-8 shadow-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-2xl bg-emerald-500/10 text-emerald-600">
                  <Clock className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-extrabold text-foreground">Field Visit History & GPS Audit</h2>
                  <p className="text-xs text-muted-foreground">
                    Chronological audit trail of sales visits, geo-tagging, and shop verification
                  </p>
                </div>
              </div>

              <Link
                href={`/check-in?${customer.ledger_id ? `ledger_id=${customer.ledger_id}` : `profile_id=${customer.profile_id}`}&name=${encodeURIComponent(customer.name || customer.tally_details?.name || '')}`}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-sm transition-colors"
              >
                <MapPin className="w-4 h-4" />
                <span>+ Record New Visit</span>
              </Link>
            </div>

            {(!customer.visits || customer.visits.length === 0) ? (
              <div className="py-16 text-center border-2 border-dashed border-border rounded-2xl p-6">
                <MapPin className="w-12 h-12 mx-auto opacity-30 mb-2 text-muted-foreground" />
                <h3 className="font-bold text-base text-foreground">No Visit Logs Recorded</h3>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                  Every time a sales executive checks in at this customer location via GPS, the visit details will be recorded here.
                </p>
                <Link
                  href={`/check-in?${customer.ledger_id ? `ledger_id=${customer.ledger_id}` : `profile_id=${customer.profile_id}`}&name=${encodeURIComponent(customer.name || customer.tally_details?.name || '')}`}
                  className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground font-semibold text-xs hover:bg-primary/90 transition-colors shadow-sm"
                >
                  <MapPin className="w-4 h-4" />
                  <span>Check In Now</span>
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {customer.visits.map((v) => (
                  <div
                    key={v.id}
                    className="p-5 rounded-2xl border border-border bg-muted/20 hover:bg-muted/40 transition-colors space-y-3"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/60 pb-2.5">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">
                          {(v.salesperson || 'S')[0]}
                        </div>
                        <div>
                          <h4 className="font-bold text-sm text-foreground">{v.salesperson || 'Sales Representative'}</h4>
                          <span className="text-[11px] text-muted-foreground">
                            {v.created_at ? new Date(v.created_at).toLocaleString('en-IN', {
                              dateStyle: 'medium',
                              timeStyle: 'short',
                            }) : '—'}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                          {v.status || 'Verified Visit'}
                        </span>
                      </div>
                    </div>

                    {v.comments && (
                      <div className="p-3 rounded-xl bg-card border border-border/70 text-xs text-foreground">
                        <p>{v.comments}</p>
                      </div>
                    )}

                    {v.latitude && v.longitude && (
                      <div className="text-[11px] text-muted-foreground font-mono flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5 text-primary" />
                        <span>GPS: {v.latitude.toFixed(5)}, {v.longitude.toFixed(5)}</span>
                      </div>
                    )}

                    {v.photo_url && (
                      <div className="pt-2">
                        <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider block mb-2">
                          Visit Photo Snap
                        </span>
                        <img
                          src={v.photo_url}
                          alt="Visit snap"
                          className="w-20 h-20 rounded-xl object-cover border border-border cursor-pointer hover:scale-105 transition-transform"
                          onClick={() => setLightboxPhoto({
                            id: v.id,
                            photo_type: 'visit_checkin',
                            imagekit_url: v.photo_url!,
                            imagekit_thumbnail_url: v.photo_url!,
                            imagekit_file_path: null,
                            caption: `Visit by ${v.salesperson}`,
                            latitude: v.latitude,
                            longitude: v.longitude,
                            is_primary: false,
                            uploaded_by_name: v.salesperson,
                            created_at: v.created_at,
                          })}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Fallback if no tabs are allowed */}
        {allowedTabs.length === 0 && (
          <div className="bg-card border border-border rounded-3xl p-8 text-center space-y-4 shadow-sm my-6">
            <div className="w-12 h-12 rounded-2xl bg-destructive/10 text-destructive flex items-center justify-center mx-auto">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="font-black text-lg text-foreground">Access Restricted</h3>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                You do not have permission to view store details, ledger statements, orders, or visits for this customer.
              </p>
            </div>
            <Link
              href="/customers"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground font-bold text-xs hover:opacity-90 transition-opacity shadow-sm"
            >
              <ChevronLeft className="w-4 h-4" />
              Back to Customer Directory
            </Link>
          </div>
        )}
      </div>

      {/* ─── MODAL: Upload Customer / Shop Photo to ImageKit ─── */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <Camera className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg leading-tight">Upload Photo to ImageKit</h3>
                  <p className="text-xs text-muted-foreground">
                    Directory: /customers/{customer.ledger_id ? `ledger_${customer.ledger_id}` : `profile_${customer.profile_id}`}/
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowUploadModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUploadPhoto} className="space-y-4 text-xs">
              {/* Photo Type Selection */}
              <div>
                <label className="font-semibold block mb-1 text-foreground">Select Photo Category</label>
                <select
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary font-semibold text-xs"
                >
                  <option value="customer_owner">👤 Customer / Owner Portrait</option>
                  <option value="shop_front">🏪 Storefront / Exterior Façade</option>
                  <option value="shop_inside">📦 Inside Shop / Merchandising Shelves</option>
                  <option value="shop_board">🪧 Signboard / Printed Nameplate</option>
                  <option value="visiting_card">🪪 Visiting Card / Business Card</option>
                  <option value="qr_code">💳 Counter UPI / Payment QR Code</option>
                  <option value="other">📷 Other Supporting Photo</option>
                </select>
              </div>

              {/* Photo Picker or Camera Capture */}
              <div>
                <label className="font-semibold block mb-1.5 text-foreground">Capture or Choose Photo</label>

                {uploadBase64 ? (
                  isCropping ? (
                    <div className="rounded-2xl overflow-hidden border border-border bg-card flex flex-col shadow-sm">
                      <div className="relative w-full h-[220px] sm:h-[260px] bg-black overflow-hidden">
                        <Cropper
                          image={uploadBase64}
                          crop={crop}
                          zoom={zoom}
                          rotation={rotation}
                          aspect={uploadType === 'customer_owner' ? 1 : 4/3}
                          onCropChange={setCrop}
                          onRotationChange={setRotation}
                          onCropComplete={(croppedArea, croppedAreaPixels) => setCroppedAreaPixels(croppedAreaPixels)}
                          onZoomChange={setZoom}
                        />
                      </div>
                      <div className="w-full bg-card p-3.5 flex flex-col gap-2.5 border-t border-border">
                        <div className="flex items-center gap-3">
                           <span className="text-xs font-semibold whitespace-nowrap w-12 text-muted-foreground">Zoom</span>
                           <input
                             type="range"
                             value={zoom}
                             min={1}
                             max={3}
                             step={0.1}
                             aria-labelledby="Zoom"
                             onChange={(e) => setZoom(Number(e.target.value))}
                             className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                           />
                        </div>
                        <div className="flex items-center gap-3">
                           <span className="text-xs font-semibold whitespace-nowrap w-12 text-muted-foreground">Rotate</span>
                           <input
                             type="range"
                             value={rotation}
                             min={0}
                             max={360}
                             step={1}
                             aria-labelledby="Rotation"
                             onChange={(e) => setRotation(Number(e.target.value))}
                             className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                           />
                        </div>
                        <div className="flex items-center justify-between gap-3 pt-2 border-t border-border/60">
                          <button
                            type="button"
                            onClick={() => {
                              setUploadBase64('')
                              setIsCropping(false)
                            }}
                            className="flex-1 py-2 px-3 rounded-xl bg-muted hover:bg-muted/80 text-foreground text-xs font-bold transition-colors text-center"
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={async () => {
                              try {
                                const croppedImage = await getCroppedImg(uploadBase64, croppedAreaPixels, rotation)
                                setUploadBase64(croppedImage)
                                setIsCropping(false)
                              } catch (e) {
                                console.error(e)
                              }
                            }}
                            className="flex-1 py-2 px-3 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-bold shadow-sm transition-colors text-center"
                          >
                            Save Crop
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="relative rounded-2xl overflow-hidden border border-border aspect-video bg-muted flex items-center justify-center group">
                      <img src={uploadBase64} alt="Preview" className="w-full h-full object-contain" />
                      
                      <div className="absolute top-2 right-2 flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setIsCropping(true)}
                          className="p-1.5 rounded-xl bg-black/70 text-white hover:bg-black opacity-90 sm:opacity-0 group-hover:opacity-100 transition-opacity"
                          title="Crop Image"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                             setUploadBase64('')
                             setIsCropping(false)
                          }}
                          className="p-1.5 rounded-xl bg-black/70 text-white hover:bg-black"
                          title="Clear photo"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => cameraInputRef.current?.click()}
                      className="p-4 rounded-2xl border-2 border-dashed border-primary/40 hover:border-primary bg-primary/5 text-primary flex flex-col items-center justify-center gap-1.5 font-bold transition-all"
                    >
                      <Camera className="w-6 h-6" />
                      <span>Take Live Photo</span>
                      <span className="text-[10px] font-normal opacity-70">Camera capture</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="p-4 rounded-2xl border-2 border-dashed border-border hover:border-foreground/50 bg-muted/30 flex flex-col items-center justify-center gap-1.5 font-semibold text-foreground transition-all"
                    >
                      <ImageIcon className="w-6 h-6 text-muted-foreground" />
                      <span>Choose File</span>
                      <span className="text-[10px] text-muted-foreground font-normal">Gallery / device</span>
                    </button>

                    {/* Hidden Inputs */}
                    <input
                      ref={cameraInputRef}
                      type="file"
                      accept="image/*"
                      capture="environment"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                  </div>
                )}
              </div>

              {/* Caption */}
              <div>
                <label className="font-semibold block mb-1 text-foreground">Caption / Notes (Optional)</label>
                <input
                  type="text"
                  value={uploadCaption}
                  onChange={(e) => setUploadCaption(e.target.value)}
                  placeholder="e.g. Counter Standee QR Code or Main Market view"
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary text-xs"
                />
              </div>

              {/* Live Geotag indicator */}
              {uploadCoords && (
                <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 flex items-center gap-2 text-[11px]">
                  <Compass className="w-4 h-4 flex-shrink-0" />
                  <span>
                    GPS Geotag captured: <b>{uploadCoords.lat.toFixed(5)}, {uploadCoords.lon.toFixed(5)}</b>
                  </span>
                </div>
              )}

              <div className="pt-3 border-t border-border flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!uploadBase64 || uploading}
                  className="px-5 py-2 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/90 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {uploading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <Camera className="w-3.5 h-3.5" />
                  <span>Upload to ImageKit</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL: Full-Screen Photo Lightbox ─── */}
      {lightboxPhoto && (
        <div
          onClick={() => setLightboxPhoto(null)}
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative max-w-4xl w-full max-h-[92vh] flex flex-col items-center justify-center space-y-3"
          >
            {/* Top Lightbox Bar */}
            <div className="w-full flex items-center justify-between text-white text-xs px-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-sm">
                  {photoTypeLabels[lightboxPhoto.photo_type]?.label || lightboxPhoto.photo_type}
                </span>
                {activeLightboxPhotos.length > 1 && (
                  <span className="px-2 py-0.5 rounded-full bg-white/20 text-[11px] font-extrabold text-white">
                    {currentLightboxIndex !== -1 ? currentLightboxIndex + 1 : 1} of {activeLightboxPhotos.length}
                  </span>
                )}
                {lightboxPhoto.uploaded_by_name && (
                  <span className="opacity-75 hidden sm:inline">by {lightboxPhoto.uploaded_by_name}</span>
                )}
                {lightboxPhoto.created_at && (
                  <span className="opacity-60 text-[11px] hidden sm:inline">
                    • {new Date(lightboxPhoto.created_at).toLocaleDateString()}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                {canDelete && lightboxPhoto.id > 0 && (
                  <button
                    onClick={() => handleDeletePhoto(lightboxPhoto.id)}
                    className="p-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500 text-rose-300 hover:text-white transition-colors"
                    title="Delete Photo"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
                <a
                  href={lightboxPhoto.imagekit_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                  title="Open full resolution in new tab"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
                <button
                  onClick={() => setLightboxPhoto(null)}
                  className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                  title="Close viewer (Esc)"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Lightbox Image Container */}
            <div 
              className="relative w-full max-h-[70vh] flex items-center justify-center overflow-hidden rounded-2xl bg-black/50 border border-white/10 shadow-2xl group select-none"
              onTouchStart={onTouchStart}
              onTouchMove={onTouchMove}
              onTouchEnd={onTouchEnd}
            >
              <img
                src={lightboxPhoto.imagekit_url}
                alt={lightboxPhoto.caption || 'Photo'}
                className="max-h-[70vh] max-w-full object-contain rounded-2xl"
              />
              
              {/* Previous Button (Visible & Loopable) */}
              {activeLightboxPhotos.length > 1 && (
                <button
                  type="button"
                  onClick={handlePrevPhoto}
                  className="absolute left-2 md:left-4 p-2.5 md:p-3.5 rounded-full bg-black/60 hover:bg-black/90 text-white backdrop-blur-md transition-all shadow-xl flex items-center justify-center active:scale-90 z-20 border border-white/20"
                  title="Previous Photo (Left Arrow)"
                >
                  <ChevronLeft className="w-5 h-5 md:w-7 md:h-7" />
                </button>
              )}
              
              {/* Next Button (Visible & Loopable) */}
              {activeLightboxPhotos.length > 1 && (
                <button
                  type="button"
                  onClick={handleNextPhoto}
                  className="absolute right-2 md:right-4 p-2.5 md:p-3.5 rounded-full bg-black/60 hover:bg-black/90 text-white backdrop-blur-md transition-all shadow-xl flex items-center justify-center active:scale-90 z-20 border border-white/20"
                  title="Next Photo (Right Arrow)"
                >
                  <ChevronRight className="w-5 h-5 md:w-7 md:h-7" />
                </button>
              )}
            </div>

            {/* Caption & Metadata Footer */}
            {lightboxPhoto.caption && (
              <p className="text-white/90 text-xs sm:text-sm text-center px-4 font-medium">
                {lightboxPhoto.caption}
              </p>
            )}

            {/* Thumbnail Carousel Strip to Scroll & Jump Across All Photos */}
            {activeLightboxPhotos.length > 1 && (
              <div className="w-full flex flex-col items-center gap-1 pt-1">
                <div className="flex items-center gap-2 overflow-x-auto max-w-full px-4 py-1 no-scrollbar scroll-smooth">
                  {activeLightboxPhotos.map((p, pIdx) => {
                    const isActive = p.id === lightboxPhoto.id || p.imagekit_url === lightboxPhoto.imagekit_url
                    return (
                      <button
                        key={p.id ? `thumb-${p.id}` : `thumb-idx-${pIdx}`}
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          setLightboxPhoto(p)
                        }}
                        className={cn(
                          'relative w-12 h-12 sm:w-14 sm:h-14 rounded-xl overflow-hidden border-2 transition-all flex-shrink-0 cursor-pointer',
                          isActive
                            ? 'border-primary ring-2 ring-primary/60 scale-105 shadow-md opacity-100'
                            : 'border-white/25 opacity-50 hover:opacity-90 hover:scale-100'
                        )}
                        title={p.caption || photoTypeLabels[p.photo_type]?.label || `Photo ${pIdx + 1}`}
                      >
                        <img
                          src={p.imagekit_thumbnail_url || p.imagekit_url}
                          alt=""
                          className="w-full h-full object-cover"
                        />
                        {isActive && (
                          <div className="absolute inset-0 border-2 border-primary rounded-xl pointer-events-none" />
                        )}
                      </button>
                    )
                  })}
                </div>
                <span className="text-[10px] text-white/60 font-medium">
                  Swipe or tap thumbnail to scroll other photos ({activeLightboxPhotos.length} total)
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── MODAL: Edit Customer Details ─── */}
      {showEditModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <h3 className="font-bold text-lg">Edit Customer Details</h3>
                <p className="text-xs text-muted-foreground">{customer.name}</p>
              </div>
              <button
                onClick={() => setShowEditModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

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
                  <label className="font-semibold block mb-1">Phone Number</label>
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
                  <label className="font-semibold block mb-1">Locality / Area</label>
                  <input
                    type="text"
                    list="localities-list"
                    value={editForm.locality}
                    onChange={(e) => setEditForm({ ...editForm, locality: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  {filterOptions && (
                    <datalist id="localities-list">
                      {filterOptions.localities.map(loc => (
                        <option key={loc.name} value={loc.name} />
                      ))}
                    </datalist>
                  )}
                </div>
                <div>
                  <label className="font-semibold block mb-1">City</label>
                  <input
                    type="text"
                    list="cities-list"
                    value={editForm.city}
                    onChange={(e) => setEditForm({ ...editForm, city: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  {filterOptions && (
                    <datalist id="cities-list">
                      {filterOptions.cities.map(city => (
                        <option key={city.name} value={city.name} />
                      ))}
                    </datalist>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Sales Route / Beat</label>
                  <input
                    type="text"
                    list="routes-list"
                    value={editForm.route_name}
                    onChange={(e) => setEditForm({ ...editForm, route_name: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  {filterOptions && (
                    <datalist id="routes-list">
                      {filterOptions.routes.map(r => (
                        <option key={r} value={r} />
                      ))}
                    </datalist>
                  )}
                </div>
                <div>
                  <label className="font-semibold block mb-1">Visit Schedule</label>
                  <select
                    value={editForm.visit_frequency}
                    onChange={(e) => setEditForm({ ...editForm, visit_frequency: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="weekly">Weekly</option>
                    <option value="biweekly">Bi-weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-semibold block mb-1">Tags (Comma-separated)</label>
                <input
                  type="text"
                  value={editForm.tags}
                  onChange={(e) => setEditForm({ ...editForm, tags: e.target.value })}
                  placeholder="VIP, Key Account, Fast Payer"
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div>
                <label className="font-semibold block mb-1">Field Notes</label>
                <textarea
                  rows={2}
                  value={editForm.notes}
                  onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                  placeholder="Best time to visit, owner preferences, etc."
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="pt-3 border-t border-border flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingEdit}
                  className="px-5 py-2 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/90 flex items-center gap-2"
                >
                  {savingEdit && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Save Changes</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL: Tag Location ─── */}
      {showTagModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <MapPin className="w-5 h-5 text-primary" />
                <h3 className="font-bold text-lg">Calibrate Master GPS</h3>
              </div>
              <button
                onClick={() => setShowTagModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveLocation} className="space-y-3.5 text-xs">
              <button
                type="button"
                onClick={() => {
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
                    (err) => alert(`GPS Error: ${err.message}`),
                    { enableHighAccuracy: true, timeout: 10000 }
                  )
                }}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-primary/40 bg-primary/10 text-primary font-bold hover:bg-primary/20 transition-colors"
              >
                <Compass className="w-4 h-4" />
                <span>Use My Current Device GPS</span>
              </button>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Latitude</label>
                  <input
                    type="text"
                    value={tagForm.latitude}
                    onChange={(e) => setTagForm({ ...tagForm, latitude: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border font-mono"
                    required
                  />
                </div>
                <div>
                  <label className="font-semibold block mb-1">Longitude</label>
                  <input
                    type="text"
                    value={tagForm.longitude}
                    onChange={(e) => setTagForm({ ...tagForm, longitude: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border font-mono"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold block mb-1">Reason / Note</label>
                <input
                  type="text"
                  value={tagForm.reason}
                  onChange={(e) => setTagForm({ ...tagForm, reason: e.target.value })}
                  placeholder="e.g. Verified on-site at shop entrance"
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border"
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
                  disabled={savingLocation}
                  className="px-5 py-2 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/90 flex items-center gap-2"
                >
                  {savingLocation && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Save Coordinates</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL: Link to Tally Ledger (Admin Only) ─── */}
      {showLinkModal && isAdmin && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <Link2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg leading-tight">Link to Tally Ledger</h3>
                  <p className="text-xs text-muted-foreground">Admin Operation • Maps profile to Tally debtor</p>
                </div>
              </div>
              <button
                onClick={() => setShowLinkModal(false)}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-1.5">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={ledgerSearch}
                  onChange={(e) => setLedgerSearch(e.target.value)}
                  placeholder="Search unlinked Tally debtor by name or address..."
                  className="w-full pl-9 pr-8 py-2 rounded-xl bg-background border border-border text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 max-h-64 pr-1">
              {loadingUnlinked ? (
                <div className="py-10 text-center text-muted-foreground flex flex-col items-center gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                  <span className="text-xs">Fetching unlinked Tally Debtors...</span>
                </div>
              ) : unlinkedLedgers.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground border border-dashed border-border rounded-xl">
                  <p className="text-xs font-medium">No unlinked Tally ledgers available</p>
                </div>
              ) : (
                unlinkedLedgers
                  .filter((l) => !ledgerSearch || l.name.toLowerCase().includes(ledgerSearch.toLowerCase()) || l.address.toLowerCase().includes(ledgerSearch.toLowerCase()))
                  .map((l) => (
                    <div
                      key={l.ledger_id}
                      onClick={() => setSelectedLedgerId(l.ledger_id)}
                      className={cn(
                        'p-3 rounded-xl border text-xs cursor-pointer transition-all flex items-start justify-between gap-3',
                        selectedLedgerId === l.ledger_id
                          ? 'border-primary bg-primary/10 shadow-sm ring-1 ring-primary'
                          : 'border-border bg-card hover:bg-muted/50 hover:border-primary/40'
                      )}
                    >
                      <div className="space-y-0.5">
                        <div className="font-bold text-foreground">{l.name} <span className="font-mono text-[10px] text-muted-foreground">#{l.ledger_id}</span></div>
                        {l.address && <div className="text-[11px] text-muted-foreground line-clamp-1">{l.address}</div>}
                      </div>
                      <input
                        type="radio"
                        name="link_ledger_select"
                        checked={selectedLedgerId === l.ledger_id}
                        onChange={() => setSelectedLedgerId(l.ledger_id)}
                        className="w-4 h-4 text-primary"
                      />
                    </div>
                  ))
              )}
            </div>

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
                onClick={handleConfirmLink}
                disabled={!selectedLedgerId || linkingLedger}
                className="px-5 py-2 rounded-xl bg-primary text-primary-foreground font-semibold text-xs hover:bg-primary/90 flex items-center gap-1.5 disabled:opacity-50"
              >
                {linkingLedger && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <Link2 className="w-3.5 h-3.5" />
                <span>Confirm Link</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL 5: Delete Wrong Tagging Modal ─── */}
      {showDeleteModal && canDelete && !customer.ledger_id && (
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
                Are you sure you want to delete <span className="font-semibold text-foreground">"{customer.name}"</span>?
                This customer lead was tagged in the field and is not linked to any Tally ledger.
              </p>
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-left text-xs text-rose-600 space-y-1">
                <p className="font-semibold">⚠️ What will be removed:</p>
                <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                  <li>Customer profile and contact details</li>
                  <li>All uploaded shop and proprietor photos ({customer.photos?.length || 0} photos)</li>
                  <li>All GPS check-in logs and visit history</li>
                </ul>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
                disabled={deleting}
                className="px-4 py-2 rounded-xl border border-border hover:bg-muted text-xs font-semibold text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteCustomer}
                disabled={deleting}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-colors disabled:opacity-50"
              >
                {deleting ? (
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

      {/* ─── MODAL 6: Add / Edit Owner or Partner ─── */}
      {showAddOwnerModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200 max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-violet-500/10 text-violet-600">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-lg">
                    {editingOwner ? 'Edit Owner / Partner' : 'Add Owner / Partner'}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    Record partner or co-owner details for {customer.name}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowAddOwnerModal(false)
                  setEditingOwner(null)
                }}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveOwner} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">
                    Owner / Partner Name <span className="text-destructive">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={ownerForm.name}
                    onChange={(e) => setOwnerForm({ ...ownerForm, name: e.target.value })}
                    placeholder="e.g. Mukesh Aggarwal"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>

                <div>
                  <label className="font-semibold block mb-1">Designation / Role</label>
                  <input
                    type="text"
                    value={ownerForm.designation}
                    onChange={(e) => setOwnerForm({ ...ownerForm, designation: e.target.value })}
                    placeholder="e.g. Partner, Co-Owner, Manager"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold block mb-1">Phone Number</label>
                  <input
                    type="tel"
                    value={ownerForm.phone}
                    onChange={(e) => setOwnerForm({ ...ownerForm, phone: e.target.value })}
                    placeholder="10-digit mobile"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>

                <div>
                  <label className="font-semibold block mb-1">WhatsApp Number</label>
                  <input
                    type="tel"
                    value={ownerForm.whatsapp_number}
                    onChange={(e) => setOwnerForm({ ...ownerForm, whatsapp_number: e.target.value })}
                    placeholder="WhatsApp number"
                    className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold block mb-1">Email (Optional)</label>
                <input
                  type="email"
                  value={ownerForm.email}
                  onChange={(e) => setOwnerForm({ ...ownerForm, email: e.target.value })}
                  placeholder="partner@example.com"
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div>
                <label className="font-semibold block mb-1">Notes / Timing / Responsibilities</label>
                <textarea
                  rows={2}
                  value={ownerForm.notes}
                  onChange={(e) => setOwnerForm({ ...ownerForm, notes: e.target.value })}
                  placeholder="e.g. Available 4 PM - 9 PM, handles purchase orders, etc."
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="p-3 bg-muted/40 border border-border rounded-xl flex items-center gap-3">
                <input
                  type="checkbox"
                  id="markPrimary"
                  checked={ownerForm.is_primary}
                  onChange={(e) => setOwnerForm({ ...ownerForm, is_primary: e.target.checked })}
                  className="w-4 h-4 rounded text-primary focus:ring-primary cursor-pointer"
                />
                <label htmlFor="markPrimary" className="cursor-pointer text-xs space-y-0.5">
                  <span className="font-bold text-foreground block">Mark as Primary Contact Person</span>
                  <span className="text-[11px] text-muted-foreground block">
                    This owner will be featured as the main contact in the customer directory and order vouchers.
                  </span>
                </label>
              </div>

              <div className="pt-3 border-t border-border flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddOwnerModal(false)
                    setEditingOwner(null)
                  }}
                  className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingOwner}
                  className="px-5 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold flex items-center gap-2"
                >
                  {savingOwner && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{editingOwner ? 'Update Owner' : 'Save Owner'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── MODAL 7: Delete Owner Confirmation ─── */}
      {ownerToDelete && canDelete && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-600 mx-auto">
              <Trash2 className="w-6 h-6" />
            </div>

            <div className="text-center space-y-2">
              <h3 className="text-lg font-bold text-foreground">Remove Owner / Partner?</h3>
              <p className="text-xs text-muted-foreground">
                Are you sure you want to remove <span className="font-bold text-foreground">"{ownerToDelete.name}"</span> ({ownerToDelete.designation}) from this shop?
              </p>
              {ownerToDelete.is_primary && (
                <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-600 text-left">
                  ⚠️ This owner is currently marked as the <strong>Primary Contact</strong>. Another partner will automatically be promoted to primary.
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setOwnerToDelete(null)}
                disabled={deletingOwner}
                className="px-4 py-2 rounded-xl border border-border hover:bg-muted text-xs font-semibold text-foreground transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteOwner}
                disabled={deletingOwner}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold transition-colors disabled:opacity-50"
              >
                {deletingOwner ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Removing...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    <span>Yes, Remove Partner</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL 8: Upload / Snap Photo for Specific Owner ─── */}
      {ownerForPhoto && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Camera className="w-5 h-5 text-primary" />
                <div>
                  <h3 className="font-bold text-base">Owner Photo: {ownerForPhoto.name}</h3>
                  <p className="text-xs text-muted-foreground">{ownerForPhoto.designation}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  stopOwnerCamera()
                  setOwnerForPhoto(null)
                  setOwnerPhotoPreview(null)
                }}
                className="p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {/* Photo View / Camera View */}
              <div className="w-48 h-48 mx-auto rounded-3xl overflow-hidden border-2 border-border bg-black/10 flex items-center justify-center relative shadow-md">
                {ownerCameraActive ? (
                  <video
                    ref={ownerVideoRef}
                    autoPlay
                    playsInline
                    muted
                    className="w-full h-full object-cover"
                  />
                ) : ownerPhotoPreview ? (
                  <img
                    src={ownerPhotoPreview}
                    alt="Preview"
                    className="w-full h-full object-cover"
                  />
                ) : ownerForPhoto.photo_url ? (
                  <img
                    src={ownerForPhoto.photo_url}
                    alt={ownerForPhoto.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center text-muted-foreground text-center p-4">
                    <UserIcon className="w-12 h-12 opacity-30 mb-2" />
                    <span className="text-xs font-medium">No photo uploaded</span>
                  </div>
                )}
              </div>

              {/* Controls */}
              <div className="flex items-center justify-center gap-2">
                {ownerCameraActive ? (
                  <button
                    type="button"
                    onClick={captureOwnerPhoto}
                    className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs flex items-center gap-2 shadow-sm"
                  >
                    <Camera className="w-4 h-4" />
                    <span>Capture Photo</span>
                  </button>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={startOwnerCamera}
                      className="px-3.5 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-semibold text-xs flex items-center gap-2 border border-border"
                    >
                      <Camera className="w-4 h-4 text-primary" />
                      <span>Live Camera</span>
                    </button>

                    <label className="px-3.5 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-semibold text-xs flex items-center gap-2 border border-border cursor-pointer">
                      <ImageIcon className="w-4 h-4 text-primary" />
                      <span>Choose File</span>
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          if (!file) return
                          const reader = new FileReader()
                          reader.onload = () => {
                            setOwnerPhotoPreview(reader.result as string)
                          }
                          reader.readAsDataURL(file)
                        }}
                      />
                    </label>
                  </>
                )}
              </div>

              <div className="pt-3 border-t border-border flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    stopOwnerCamera()
                    setOwnerForPhoto(null)
                    setOwnerPhotoPreview(null)
                  }}
                  className="px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground font-semibold text-xs"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleUploadOwnerPhoto}
                  disabled={!ownerPhotoPreview || uploadingOwnerPhoto}
                  className="px-5 py-2 rounded-xl bg-primary text-primary-foreground font-bold text-xs hover:bg-primary/90 flex items-center gap-2 disabled:opacity-50"
                >
                  {uploadingOwnerPhoto && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Save to ImageKit</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function CustomerProfilePage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
            <span className="text-xs font-bold text-muted-foreground">Loading Customer Profile...</span>
          </div>
        </div>
      }
    >
      <CustomerProfileContent />
    </Suspense>
  )
}
