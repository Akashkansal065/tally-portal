'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency, toTitleCase } from '@/lib/utils'
import { getProductDetails } from '@/lib/kgoc-mapping'
import { 
  ArrowLeft, 
  Search, 
  Store, 
  CheckCircle2, 
  Plus, 
  Trash2, 
  ShoppingCart, 
  ChevronRight, 
  ChevronLeft,
  Package,
  AlertCircle,
  Sparkles,
  FileText
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface CartItem {
  cartItemId: string
  stock_item_id?: number | null
  custom_item_name?: string
  name: string
  company_name?: string
  qty: number
  price: number
  is_bill_required: boolean
  is_custom?: boolean
}

type Ledger = { ledger_id: number; name: string; is_customer?: boolean }
type StockItem = {
  item_id: number
  name: string
  closing_rate: number
  group_name?: string
  company_name?: string
  parent?: string
  part_number?: string
  hsn_code?: string
  uom?: string
}

const getCompanySuffix = (item: { group_name?: string; company_name?: string; parent?: string } | null | undefined): string => {
  if (!item) return ''
  const cName = (item.company_name || item.group_name || item.parent || '').trim()
  if (!cName || cName.toLowerCase() === 'all' || cName.toLowerCase() === 'primary' || cName.toLowerCase() === 'others') {
    return ''
  }
  return cName
}

const formatProductNameWithCompany = (name: string, company?: string): string => {
  const c = (company || '').trim()
  const titleName = toTitleCase(name)
  if (!c || c.toLowerCase() === 'all' || c.toLowerCase() === 'primary' || c.toLowerCase() === 'others') {
    return titleName
  }
  if (titleName.toLowerCase().includes(c.toLowerCase())) {
    return titleName
  }
  return `${titleName} (${c})`
}

export default function NewOrderPage() {
  const { user, token } = useAuth()
  const router = useRouter()
  
  // Wizards steps: 1 = Customer select, 2 = Add items, 3 = Summary & checkout
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Cache data
  const [cachedShops, setCachedShops] = useState<Ledger[]>([])
  const [cachedProducts, setCachedProducts] = useState<StockItem[]>([])

  // Step 1: Customer Selection
  const [isCustomShop, setIsCustomShop] = useState(false)
  const [shopQuery, setShopQuery] = useState('')
  const [selectedShop, setSelectedShop] = useState<Ledger | null>(null)
  const [customShopName, setCustomShopName] = useState('')
  const [customShopHasGst, setCustomShopHasGst] = useState(false)
  const [customShopGstin, setCustomShopGstin] = useState('')
  const [showShopDropdown, setShowShopDropdown] = useState(false)
  const shopDropdownRef = useRef<HTMLDivElement>(null)

  // Step 2: Add Items
  const [productQuery, setProductQuery] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<StockItem | null>(null)
  const [isCustomProduct, setIsCustomProduct] = useState(false)
  const [customProductName, setCustomProductName] = useState('')
  const [qty, setQty] = useState<number>(1)
  const [price, setPrice] = useState<number | ''>('')
  const [isBillRequired, setIsBillRequired] = useState(true)
  const [cart, setCart] = useState<CartItem[]>([])
  const [showProductDropdown, setShowProductDropdown] = useState(false)
  const productDropdownRef = useRef<HTMLDivElement>(null)
  const [itemErrors, setItemErrors] = useState<{ product?: string; qty?: string; price?: string }>({})

  // Narration
  const [narration, setNarration] = useState('')

  // Fetch initial ledgers & stock items cache
  useEffect(() => {
    if (!user) { router.replace('/login'); return }

    Promise.all([
      fetch(`${API_BASE}/ledgers`, { headers: authHeaders(token) }).then(r => r.json()),
      fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) }).then(r => r.json())
    ])
      .then(([ledgersData, stocksData]) => {
        const customers = Array.isArray(ledgersData) ? ledgersData.filter((l: any) => l.is_customer) : []
        setCachedShops(customers)
        setCachedProducts(Array.isArray(stocksData) ? stocksData : [])
      })
      .catch(err => console.error('Failed to load initial cache:', err))
      .finally(() => setLoading(false))
  }, [user, token, router])

  // Handle clicking outside dropdowns
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (shopDropdownRef.current && !shopDropdownRef.current.contains(event.target as Node)) {
        setShowShopDropdown(false)
      }
      if (productDropdownRef.current && !productDropdownRef.current.contains(event.target as Node)) {
        setShowProductDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Filtered Shops & Products
  const filteredShops = useMemo(() => {
    if (shopQuery.trim().length < 1) return []
    const q = shopQuery.toLowerCase().trim()
    return cachedShops.filter(s =>
      s.name.toLowerCase().includes(q)
    ).slice(0, 15)
  }, [shopQuery, cachedShops])

  const filteredProducts = useMemo(() => {
    if (productQuery.trim().length < 1) return []
    const q = productQuery.toLowerCase().trim()
    return cachedProducts.filter(p => {
      const company = getCompanySuffix(p)
      const mapping = p.name ? getProductDetails(p.name, company || p.parent || '') : null
      const brandStr = mapping?.brand?.toLowerCase() || ''
      const subtitleStr = mapping?.subtitle?.toLowerCase() || ''
      const parentStr = p.parent?.toLowerCase() || ''
      const groupStr = company.toLowerCase()
      const nameStr = p.name ? p.name.toLowerCase() : ''
      const partStr = p.part_number ? p.part_number.toLowerCase() : ''
      const hsnStr = p.hsn_code ? p.hsn_code.toLowerCase() : ''

      return nameStr.includes(q) || 
             brandStr.includes(q) || 
             subtitleStr.includes(q) || 
             parentStr.includes(q) || 
             groupStr.includes(q) ||
             partStr.includes(q) ||
             hsnStr.includes(q)
    }).slice(0, 30)
  }, [productQuery, cachedProducts])

  // Handle Add Item to Cart with field validation
  const handleAddItem = () => {
    const errs: { product?: string; qty?: string; price?: string } = {}

    let itemNameToAdd = ''
    let isCustom = false
    let stockItemId: number | null = null
    let company: string | undefined = undefined

    if (selectedProduct) {
      itemNameToAdd = selectedProduct.name
      stockItemId = selectedProduct.item_id
      company = getCompanySuffix(selectedProduct)
    } else if (isCustomProduct && customProductName.trim()) {
      itemNameToAdd = customProductName.trim()
      isCustom = true
    } else if (productQuery.trim()) {
      itemNameToAdd = productQuery.trim()
      isCustom = true
    } else {
      errs.product = 'Please search or enter a stock item name'
    }

    if (!qty || qty <= 0) {
      errs.qty = 'Quantity must be at least 1'
    }
    if (price === '' || Number(price) <= 0) {
      errs.price = 'Please enter a valid rate'
    }

    if (!itemNameToAdd || !qty || qty <= 0 || price === '' || Number(price) <= 0) {
      setItemErrors(errs)
      return
    }

    setItemErrors({})
    const newItem: CartItem = {
      cartItemId: Math.random().toString(36).substring(2, 9),
      stock_item_id: stockItemId,
      custom_item_name: isCustom ? itemNameToAdd : undefined,
      name: itemNameToAdd,
      company_name: company,
      qty,
      price: Number(price),
      is_bill_required: isBillRequired,
      is_custom: isCustom,
    }

    setCart([...cart, newItem])
    setProductQuery('')
    setSelectedProduct(null)
    setIsCustomProduct(false)
    setCustomProductName('')
    setQty(1)
    setPrice('')
    setIsBillRequired(true)
  }

  const handleRemoveItem = (cartItemId: string) => {
    setCart(cart.filter(item => item.cartItemId !== cartItemId))
  }

  // Calculate Cart Subtotals
  const totals = useMemo(() => {
    let subtotal = 0
    cart.forEach(item => {
      subtotal += item.qty * item.price
    })
    return {
      subtotal,
      total: subtotal
    }
  }, [cart])

  // Submit Order to backend API
  const handleSubmitOrder = async () => {
    if (submitting) return
    if (cart.length === 0) return

    const shopName = isCustomShop ? customShopName.trim() : selectedShop?.name
    if (!shopName) return

    setSubmitting(true)
    try {
      const payload = {
        ledger_id: isCustomShop ? null : selectedShop?.ledger_id,
        custom_customer_name: isCustomShop ? customShopName.trim() : null,
        custom_customer_gstin: isCustomShop && customShopHasGst && customShopGstin.trim() ? customShopGstin.trim().toUpperCase() : null,
        items: cart.map(item => ({
          stock_item_id: item.stock_item_id || null,
          custom_item_name: item.is_custom ? item.name : (item.custom_item_name || null),
          qty: item.qty,
          price: item.price,
          is_bill_required: item.is_bill_required
        }))
      }

      const res = await fetch(`${API_BASE}/temporders`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to submit order')
      }

      router.push('/temporders')
    } catch (err: any) {
      alert(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-background font-sans">
      {/* Main Container */}
      <div className="flex-1 overflow-y-auto px-4 py-5 max-w-xl mx-auto w-full space-y-4">
        {/* Header with Back Button */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              if (typeof window !== 'undefined' && window.history.length > 1) {
                router.back()
              } else {
                router.push('/temporders')
              }
            }}
            className="p-2 rounded-xl bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-colors cursor-pointer border border-border shrink-0"
            title="Back to Orders"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-xl font-extrabold text-foreground">Create Order</h1>
            <p className="text-[11px] text-muted-foreground mt-0.5">Place a new temporary order for customer</p>
          </div>
        </div>
        {/* Step Indicators */}
        <div className="flex items-center justify-between bg-card border border-border/80 rounded-2xl p-4 shadow-sm text-sm">
          <div>
            <h2 className="font-extrabold text-sm text-foreground">Step {step} of 3</h2>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {step === 1 && 'Select customer outlet details'}
              {step === 2 && 'Add stock items & rates'}
              {step === 3 && 'narration & complete order'}
            </p>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 px-2 py-0.5 rounded">
            {step === 1 && 'Shop Selection'}
            {step === 2 && 'Products'}
            {step === 3 && 'Save Order'}
          </span>
        </div>

        {/* STEP 1: CHOOSE SHOP */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="bg-card border border-border rounded-2xl p-4 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-bold text-sm text-foreground">Manual / New Shop Mode</h3>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Toggle this if customer is unregistered in Tally</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    const next = !isCustomShop
                    setIsCustomShop(next)
                    setSelectedShop(null)
                    setShopQuery('')
                    setCustomShopName('')
                    setCustomShopHasGst(false)
                    setCustomShopGstin('')
                  }}
                  className={cn(
                    'w-9 h-5 rounded-full transition-all relative',
                    isCustomShop ? 'bg-emerald-500' : 'bg-muted border border-border'
                  )}
                >
                  <div className={cn('w-4 h-4 rounded-full bg-white shadow absolute top-[2px] transition-all', isCustomShop ? 'right-[2px]' : 'left-[2px]')} />
                </button>
              </div>

              {isCustomShop ? (
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Shop / Customer Name</label>
                    <input
                      type="text"
                      placeholder="Enter customer shop name..."
                      value={customShopName}
                      onChange={e => setCustomShopName(e.target.value)}
                      className="w-full px-3 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>

                  {/* GST Option for Unregistered Customer */}
                  <div className="space-y-2 border-t border-border/40 pt-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <label className="text-xs font-bold text-foreground flex items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5 text-emerald-500" /> GST Option
                        </label>
                        <p className="text-[10px] text-muted-foreground">Does this new customer have a GSTIN?</p>
                      </div>
                      <span className={cn(
                        "text-[10px] font-bold px-2 py-0.5 rounded-full border transition-all",
                        customShopHasGst 
                          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" 
                          : "bg-muted text-muted-foreground border-border"
                      )}>
                        {customShopHasGst ? 'Has GSTIN' : 'Unregistered'}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setCustomShopHasGst(false)
                          setCustomShopGstin('')
                        }}
                        className={cn(
                          "py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.98]",
                          !customShopHasGst
                            ? "bg-emerald-500 text-white border-emerald-500 shadow-sm shadow-emerald-500/20"
                            : "bg-muted/40 border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                        )}
                      >
                        <CheckCircle2 className={cn("h-3.5 w-3.5", !customShopHasGst ? "text-white" : "opacity-0")} />
                        Unregistered (No GST)
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setCustomShopHasGst(true)
                          setIsBillRequired(true)
                        }}
                        className={cn(
                          "py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.98]",
                          customShopHasGst
                            ? "bg-emerald-500 text-white border-emerald-500 shadow-sm shadow-emerald-500/20"
                            : "bg-muted/40 border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                        )}
                      >
                        <CheckCircle2 className={cn("h-3.5 w-3.5", customShopHasGst ? "text-white" : "opacity-0")} />
                        Registered (Has GSTIN)
                      </button>
                    </div>

                    {customShopHasGst && (
                      <div className="space-y-1.5 pt-1 animate-in fade-in slide-in-from-top-1 duration-200">
                        <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">
                          Customer GSTIN (15 Digits)
                        </label>
                        <input
                          type="text"
                          maxLength={15}
                          placeholder="e.g. 07AAAAA0000A1Z5"
                          value={customShopGstin}
                          onChange={e => setCustomShopGstin(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))}
                          className="w-full px-3 py-2 bg-muted/40 border border-border rounded-xl text-xs font-mono font-bold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 tracking-wider placeholder:font-normal placeholder:tracking-normal uppercase"
                        />
                        {customShopGstin.trim().length > 0 && (
                          <div className="flex items-center gap-1.5 text-[11px] mt-1 font-semibold">
                            {customShopGstin.length === 15 && /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/.test(customShopGstin) ? (
                              <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                                <CheckCircle2 className="h-3.5 w-3.5" /> Valid 15-digit GSTIN Format
                              </span>
                            ) : customShopGstin.length === 15 ? (
                              <span className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
                                <AlertCircle className="h-3.5 w-3.5" /> Check format (expected: 2 digits + 10-char PAN + entity + Z + check digit)
                              </span>
                            ) : (
                              <span className="text-muted-foreground">
                                {15 - customShopGstin.length} more character{15 - customShopGstin.length > 1 ? 's' : ''} required
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-1.5 relative" ref={shopDropdownRef}>
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Search Registered Customer</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder="Type customer name to search..."
                      value={shopQuery}
                      onChange={e => {
                        setShopQuery(e.target.value)
                        setShowShopDropdown(true)
                        if (selectedShop) setSelectedShop(null)
                      }}
                      onFocus={() => setShowShopDropdown(true)}
                      className="w-full pl-9 pr-3 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
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
                    <div className="bg-green-500/10 border border-green-500/20 text-green-600 dark:text-green-400 p-3 rounded-xl text-xs flex items-center gap-2 mt-2">
                      <CheckCircle2 className="h-4 w-4 shrink-0" />
                      <span>Outlet selected: <strong>{toTitleCase(selectedShop.name)}</strong></span>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  if (typeof window !== 'undefined' && window.history.length > 1) {
                    router.back()
                  } else {
                    router.push('/temporders')
                  }
                }}
                className="w-1/3 py-3 border border-border bg-card hover:bg-muted text-muted-foreground hover:text-foreground font-bold rounded-xl text-sm transition-all text-center flex items-center justify-center gap-1 cursor-pointer"
              >
                <ArrowLeft className="h-4 w-4" /> Cancel
              </button>
              <button
                type="button"
                disabled={isCustomShop ? !customShopName.trim() : !selectedShop}
                onClick={() => setStep(2)}
                className="flex-1 py-3 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white font-bold rounded-xl text-sm transition-all active:scale-[0.98] shadow-md shadow-emerald-500/10 text-center flex items-center justify-center gap-1.5 cursor-pointer"
              >
                Next Step <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: PRODUCTS SELECTION */}
        {step === 2 && (
          <div className="space-y-4">
            {/* Cart Items List */}
            {cart.length > 0 && (
              <div className="bg-card border border-border rounded-2xl p-4 shadow-sm space-y-3">
                <h4 className="font-bold text-xs uppercase text-muted-foreground tracking-wider mb-2">Cart Sub-Items ({cart.length})</h4>
                <div className="space-y-2 max-h-60 overflow-y-auto no-scrollbar">
                  {cart.map((item, idx) => (
                    <div key={item.cartItemId} className="flex justify-between items-center gap-4 text-xs bg-muted/20 border border-border/40 p-3 rounded-xl">
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-bold text-foreground block truncate">
                            {formatProductNameWithCompany(item.name, item.company_name)}
                          </span>
                          {item.is_custom && (
                            <span className="px-1.5 py-0.2 text-[8px] font-extrabold uppercase tracking-wider bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 rounded">
                              Custom
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] text-muted-foreground mt-0.5 block">
                          {item.qty} Qty @ {formatCurrency(item.price)}/ea •{' '}
                          {item.is_bill_required ? (
                            <span className="text-emerald-600 dark:text-emerald-400 font-bold">With Bill</span>
                          ) : (
                            <span className="text-muted-foreground font-medium">Without Bill</span>
                          )}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="font-black text-emerald-600 dark:text-emerald-400 font-mono">
                          {formatCurrency(item.qty * item.price)}
                        </span>
                        <button type="button" onClick={() => handleRemoveItem(item.cartItemId)} className="text-destructive hover:bg-destructive/10 p-1.5 rounded-lg transition-colors cursor-pointer">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Product Picker */}
            <div className="bg-card border border-border rounded-2xl p-4 shadow-sm space-y-4">
              <div className="space-y-1.5 relative" ref={productDropdownRef}>
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">
                    Select or enter stock item
                  </label>
                  {isCustomProduct && (
                    <span className="text-[10px] font-extrabold uppercase tracking-wider bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded">
                      Custom Unlisted Item
                    </span>
                  )}
                </div>

                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Type product name to search or enter custom item..."
                    value={productQuery}
                    onChange={e => {
                      const val = e.target.value
                      setProductQuery(val)
                      setShowProductDropdown(true)
                      if (selectedProduct) setSelectedProduct(null)
                      if (isCustomProduct) setCustomProductName(val)
                      if (itemErrors.product) setItemErrors(prev => ({ ...prev, product: undefined }))
                    }}
                    onFocus={() => setShowProductDropdown(true)}
                    className={cn(
                      "w-full pl-9 pr-3 py-2.5 bg-muted/40 border rounded-xl text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all",
                      itemErrors.product ? "border-rose-500 ring-2 ring-rose-500/20 bg-rose-500/5" : "border-border"
                    )}
                  />
                </div>

                {itemErrors.product && (
                  <p className="text-[11px] font-bold text-rose-500 flex items-center gap-1 mt-1">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {itemErrors.product}
                  </p>
                )}

                {showProductDropdown && productQuery.trim().length >= 1 && (
                  <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-xl shadow-lg max-h-60 overflow-y-auto divide-y divide-border/50">
                    {filteredProducts.length === 0 ? (
                      <div className="p-3.5 text-center space-y-2.5">
                        <p className="text-xs text-muted-foreground font-medium">No matching products found in Tally.</p>
                        <button
                          type="button"
                          onClick={() => {
                            setIsCustomProduct(true)
                            setCustomProductName(productQuery.trim())
                            setSelectedProduct(null)
                            setShowProductDropdown(false)
                            setItemErrors(prev => ({ ...prev, product: undefined }))
                          }}
                          className="w-full py-2.5 px-3 bg-emerald-500 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold transition-all shadow-sm flex items-center justify-center gap-1.5 cursor-pointer"
                        >
                          <Plus className="h-4 w-4" />
                          <span>Add &ldquo;{productQuery.trim()}&rdquo; as Custom / Unlisted Item</span>
                        </button>
                      </div>
                    ) : (
                      <>
                        {filteredProducts.map(product => {
                          const company = getCompanySuffix(product)
                          const mapping = product.name ? getProductDetails(product.name, company || product.parent || '') : null
                          const displayTitle = formatProductNameWithCompany(product.name, company)
                          return (
                            <button
                              key={product.item_id}
                              type="button"
                              onClick={() => {
                                setSelectedProduct(product)
                                setIsCustomProduct(false)
                                setCustomProductName('')
                                setProductQuery(displayTitle)
                                setPrice('')
                                setShowProductDropdown(false)
                                setItemErrors(prev => ({ ...prev, product: undefined }))
                              }}
                              className="w-full text-left p-3 hover:bg-muted text-xs text-foreground flex flex-col gap-0.5 cursor-pointer"
                            >
                              <span className="font-semibold">{displayTitle}</span>
                              {company ? (
                                <span className="text-[10px] text-muted-foreground font-medium flex items-center gap-1.5">
                                  <span className="inline-block px-1.5 py-0.5 rounded bg-muted text-foreground/80 font-semibold">{company}</span>
                                  {product.uom && <span>• {product.uom}</span>}
                                  {mapping?.subtitle && mapping.subtitle !== product.name && <span>• {mapping.subtitle}</span>}
                                </span>
                              ) : mapping && (
                                <span className="text-[10px] text-muted-foreground font-medium">
                                  {mapping.brand} • {mapping.subtitle}
                                </span>
                              )}
                            </button>
                          )
                        })}

                        <div className="p-2 bg-muted/30 border-t border-border/60">
                          <button
                            type="button"
                            onClick={() => {
                              setIsCustomProduct(true)
                              setCustomProductName(productQuery.trim())
                              setSelectedProduct(null)
                              setShowProductDropdown(false)
                              setItemErrors(prev => ({ ...prev, product: undefined }))
                            }}
                            className="w-full py-1.5 px-2.5 text-left text-xs font-bold text-primary hover:bg-muted rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
                          >
                            <Plus className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                            <span className="truncate">Not in list? Add &ldquo;{productQuery.trim()}&rdquo; as custom item</span>
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {selectedProduct ? (
                  <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 p-2.5 rounded-xl text-xs flex items-center justify-between gap-1.5 mt-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">Product: <strong>{formatProductNameWithCompany(selectedProduct.name, getCompanySuffix(selectedProduct))}</strong></span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedProduct(null)
                        setProductQuery('')
                      }}
                      className="text-xs text-muted-foreground hover:text-foreground font-semibold underline shrink-0 cursor-pointer"
                    >
                      Clear
                    </button>
                  </div>
                ) : isCustomProduct && customProductName ? (
                  <div className="bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 p-2.5 rounded-xl text-xs flex items-center justify-between gap-1.5 mt-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <Sparkles className="h-3.5 w-3.5 shrink-0 text-amber-500" />
                      <span className="truncate">Custom Item: <strong>{customProductName}</strong></span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setIsCustomProduct(false)
                        setCustomProductName('')
                        setProductQuery('')
                      }}
                      className="text-xs text-muted-foreground hover:text-foreground font-semibold underline shrink-0 cursor-pointer"
                    >
                      Clear
                    </button>
                  </div>
                ) : null}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Quantity</label>
                  <input
                    type="number"
                    min="1"
                    value={qty || ''}
                    onChange={e => {
                      setQty(Number(e.target.value))
                      if (itemErrors.qty) setItemErrors(prev => ({ ...prev, qty: undefined }))
                    }}
                    className={cn(
                      "w-full px-3 py-2 bg-muted/40 border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all",
                      itemErrors.qty ? "border-rose-500 ring-2 ring-rose-500/20 bg-rose-500/5" : "border-border"
                    )}
                  />
                  {itemErrors.qty && (
                    <p className="text-[11px] font-bold text-rose-500 flex items-center gap-1 mt-1">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {itemErrors.qty}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Rate (₹/ea)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="Enter Rate..."
                    value={price}
                    onChange={e => {
                      setPrice(e.target.value === '' ? '' : Number(e.target.value))
                      if (itemErrors.price) setItemErrors(prev => ({ ...prev, price: undefined }))
                    }}
                    className={cn(
                      "w-full px-3 py-2 bg-muted/40 border rounded-xl text-sm font-semibold text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 transition-all",
                      itemErrors.price ? "border-rose-500 ring-2 ring-rose-500/20 bg-rose-500/5" : "border-border"
                    )}
                  />
                  {itemErrors.price && (
                    <p className="text-[11px] font-bold text-rose-500 flex items-center gap-1 mt-1">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {itemErrors.price}
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-2 border-t border-border/40 pt-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">
                    Billing Type
                  </label>
                  <span className={cn(
                    "text-[10px] font-bold px-2 py-0.5 rounded-full border transition-all",
                    isBillRequired 
                      ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" 
                      : "bg-muted text-muted-foreground border-border"
                  )}>
                    {isBillRequired ? 'With Bill' : 'Without Bill'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setIsBillRequired(true)}
                    className={cn(
                      "py-2.5 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.98]",
                      isBillRequired
                        ? "bg-emerald-500 text-white border-emerald-500 shadow-sm shadow-emerald-500/20"
                        : "bg-muted/40 border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                  >
                    <CheckCircle2 className={cn("h-3.5 w-3.5", isBillRequired ? "text-white" : "opacity-0")} />
                    With Bill
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsBillRequired(false)}
                    className={cn(
                      "py-2.5 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.98]",
                      !isBillRequired
                        ? "bg-emerald-500 text-white border-emerald-500 shadow-sm shadow-emerald-500/20"
                        : "bg-muted/40 border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                  >
                    <CheckCircle2 className={cn("h-3.5 w-3.5", !isBillRequired ? "text-white" : "opacity-0")} />
                    Without Bill
                  </button>
                </div>
              </div>

              <button
                type="button"
                onClick={handleAddItem}
                className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl text-xs transition-all shadow-md shadow-emerald-500/10 flex items-center justify-center gap-1.5 cursor-pointer active:scale-[0.98]"
              >
                <Plus className="h-4 w-4" /> Add Item
              </button>
            </div>

            <div className="flex gap-2.5">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="flex-1 py-3 bg-muted hover:bg-muted/80 text-foreground font-bold rounded-xl text-sm transition-all text-center flex items-center justify-center gap-1 cursor-pointer"
              >
                <ChevronLeft className="h-4 w-4" /> Back
              </button>
              <button
                type="button"
                disabled={cart.length === 0}
                onClick={() => setStep(3)}
                className="flex-1 py-3 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white font-bold rounded-xl text-sm transition-all text-center flex items-center justify-center gap-1.5 cursor-pointer shadow-md shadow-emerald-500/10"
              >
                Summary <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: SUMMARY & SUBMIT */}
        {step === 3 && (
          <div className="space-y-4">
            <div className="bg-card border border-border rounded-2xl p-5 shadow-sm space-y-4">
              <div>
                <span className="text-[9px] font-extrabold text-muted-foreground uppercase tracking-widest block">Customer</span>
                <span className="font-extrabold text-base text-foreground mt-0.5 block">{isCustomShop ? customShopName : selectedShop?.name}</span>
                {isCustomShop ? (
                  <div className="flex items-center gap-1.5 mt-1">
                    {customShopHasGst && customShopGstin.trim() ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[11px] font-mono font-bold">
                        GSTIN: {customShopGstin.trim().toUpperCase()}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-muted text-muted-foreground border border-border text-[10px] font-semibold">
                        Unregistered Consumer (No GST)
                      </span>
                    )}
                  </div>
                ) : null}
              </div>

              <div className="border-t border-border pt-4">
                <span className="text-[9px] font-extrabold text-muted-foreground uppercase tracking-widest block mb-2.5">Order Items</span>
                <div className="space-y-2 max-h-56 overflow-y-auto no-scrollbar">
                  {cart.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-center text-xs">
                      <div className="min-w-0 pr-2">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-foreground font-medium truncate block">
                            {formatProductNameWithCompany(item.name, item.company_name)}
                          </span>
                          {item.is_custom && (
                            <span className="px-1.5 py-0.2 text-[8px] font-extrabold uppercase tracking-wider bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 rounded">
                              Custom
                            </span>
                          )}
                        </div>
                        <span className="text-[10px]">
                          {item.is_bill_required ? (
                            <span className="text-emerald-600 dark:text-emerald-400 font-semibold">With Bill</span>
                          ) : (
                            <span className="text-muted-foreground font-medium">Without Bill</span>
                          )}
                        </span>
                      </div>
                      <span className="font-semibold shrink-0">{item.qty} × {formatCurrency(item.price)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Grand Total */}
              <div className="border-t border-border pt-3 flex justify-between items-center bg-muted/10 p-4 rounded-xl border">
                <div>
                  <span className="text-xs font-bold text-foreground block">Grand Total</span>
                  <span className="text-[10px] text-muted-foreground block">{cart.length} item{cart.length > 1 ? 's' : ''}</span>
                </div>
                <span className="text-lg font-black text-emerald-600 dark:text-emerald-400 font-mono">{formatCurrency(totals.total)}</span>
              </div>

              {/* Narration */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Narration / Notes</label>
                <textarea
                  placeholder="Enter order notes, delivery details..."
                  value={narration}
                  onChange={e => setNarration(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 bg-muted/40 border border-border rounded-xl text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none font-medium"
                />
              </div>
            </div>

            <div className="flex gap-2.5">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="py-3 px-5 bg-muted hover:bg-muted/80 text-foreground font-bold rounded-xl text-sm transition-all text-center flex items-center justify-center cursor-pointer"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleSubmitOrder}
                className="flex-1 py-3 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white font-bold rounded-xl text-sm transition-all text-center flex items-center justify-center gap-1.5 cursor-pointer shadow-md shadow-emerald-500/10"
              >
                {submitting && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin shrink-0" />}
                Confirm & Submit Order
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
