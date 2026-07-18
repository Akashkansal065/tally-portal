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
  Package
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface CartItem {
  cartItemId: string
  stock_item_id: number
  name: string
  qty: number
  price: number
  has_gst: boolean
}

type Ledger = { ledger_id: number; name: string; is_customer?: boolean }
type StockItem = { item_id: number; name: string; closing_rate: number; parent?: string }

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
  const [showShopDropdown, setShowShopDropdown] = useState(false)
  const shopDropdownRef = useRef<HTMLDivElement>(null)

  // Step 2: Add Items
  const [productQuery, setProductQuery] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<StockItem | null>(null)
  const [qty, setQty] = useState<number>(1)
  const [price, setPrice] = useState<number>(0)
  const [hasGst, setHasGst] = useState(true)
  const [cart, setCart] = useState<CartItem[]>([])
  const [showProductDropdown, setShowProductDropdown] = useState(false)
  const productDropdownRef = useRef<HTMLDivElement>(null)

  // Narration
  const [narration, setNarration] = useState('')

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    
    // Fetch cache
    fetch(`${API_BASE}/ledgers`, { headers: authHeaders(token) })
      .then(r => r.json())
      .then(data => {
        const customers = Array.isArray(data) ? data.filter((l: any) => l.is_customer) : []
        setCachedShops(customers)
      })

    fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) })
      .then(r => r.json())
      .then(data => {
        setCachedProducts(Array.isArray(data) ? data : [])
      })
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

  // Filtered Shops
  const filteredShops = useMemo(() => {
    if (shopQuery.trim().length < 2) return []
    return cachedShops.filter(s =>
      s.name.toLowerCase().includes(shopQuery.toLowerCase())
    ).slice(0, 15)
  }, [shopQuery, cachedShops])

  // Filtered Products
  const filteredProducts = useMemo(() => {
    if (productQuery.trim().length < 2) return []
    const lowerQuery = productQuery.toLowerCase()
    return cachedProducts.filter(p => {
      const mapping = p.name ? getProductDetails(p.name, p.parent || '') : null
      const brandStr = mapping?.brand?.toLowerCase() || ''
      const subtitleStr = mapping?.subtitle?.toLowerCase() || ''
      return p.name.toLowerCase().includes(lowerQuery) || 
             brandStr.includes(lowerQuery) || 
             subtitleStr.includes(lowerQuery)
    }).slice(0, 15)
  }, [productQuery, cachedProducts])

  // Handle Add Item to Cart
  const handleAddItem = () => {
    if (!selectedProduct) return
    if (qty <= 0) return

    const newItem: CartItem = {
      cartItemId: Math.random().toString(36).substring(2, 9),
      stock_item_id: selectedProduct.item_id,
      name: selectedProduct.name,
      qty,
      price,
      has_gst: hasGst,
    }

    setCart([...cart, newItem])
    setProductQuery('')
    setSelectedProduct(null)
    setQty(1)
    setPrice(0)
    setHasGst(true)
  }

  const handleRemoveItem = (cartItemId: string) => {
    setCart(cart.filter(item => item.cartItemId !== cartItemId))
  }

  // Calculate Cart Subtotals
  const totals = useMemo(() => {
    let subtotal = 0
    let tax = 0
    cart.forEach(item => {
      const amt = item.qty * item.price
      subtotal += amt
      if (item.has_gst) {
        tax += amt * 0.18
      }
    })
    return {
      subtotal,
      tax,
      total: subtotal + tax
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
        items: cart.map(item => ({
          stock_item_id: item.stock_item_id,
          qty: item.qty,
          price: item.price,
          has_gst: item.has_gst
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
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-extrabold text-foreground">Create Order</h1>
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
                    setIsCustomShop(!isCustomShop)
                    setSelectedShop(null)
                    setShopQuery('')
                    setCustomShopName('')
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
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Shop Name</label>
                  <input
                    type="text"
                    placeholder="Enter customer shop name..."
                    value={customShopName}
                    onChange={e => setCustomShopName(e.target.value)}
                    className="w-full px-3 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
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
                        <span className="font-bold text-foreground block truncate">{toTitleCase(item.name)}</span>
                        <span className="text-[10px] text-muted-foreground mt-0.5 block">
                          {item.qty} Qty @ {formatCurrency(item.price)}/ea {item.has_gst && <span className="text-green-600 font-bold ml-1">+18% GST</span>}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="font-black text-emerald-600 dark:text-emerald-400 font-mono">
                          {formatCurrency(item.qty * item.price * (item.has_gst ? 1.18 : 1.0))}
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
                <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Select stock item</label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Type product name to search..."
                    value={productQuery}
                    onChange={e => {
                      setProductQuery(e.target.value)
                      setShowProductDropdown(true)
                      if (selectedProduct) setSelectedProduct(null)
                    }}
                    onFocus={() => setShowProductDropdown(true)}
                    className="w-full pl-9 pr-3 py-2.5 bg-muted/40 border border-border rounded-xl text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>

                {showProductDropdown && productQuery.trim().length >= 2 && (
                  <div className="absolute z-50 w-full mt-1 bg-popover border border-border rounded-xl shadow-lg max-h-56 overflow-y-auto divide-y divide-border/50">
                    {filteredProducts.length === 0 ? (
                      <p className="p-3 text-xs text-muted-foreground text-center">No products found</p>
                    ) : (
                      filteredProducts.map(product => {
                        const mapping = product.name ? getProductDetails(product.name, product.parent || '') : null
                        return (
                          <button
                            key={product.item_id}
                            type="button"
                            onClick={() => {
                              setSelectedProduct(product)
                              setProductQuery(toTitleCase(product.name))
                              setPrice(product.closing_rate || 0)
                              setShowProductDropdown(false)
                            }}
                            className="w-full text-left p-3 hover:bg-muted text-xs text-foreground flex flex-col gap-0.5"
                          >
                            <span className="font-semibold">{toTitleCase(product.name)}</span>
                            {mapping && (
                              <span className="text-[10px] text-muted-foreground font-medium">
                                {mapping.brand} • {mapping.subtitle}
                              </span>
                            )}
                          </button>
                        )
                      })
                    )}
                  </div>
                )}

                {selectedProduct && (
                  <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 p-2.5 rounded-xl text-xs flex items-center gap-1.5 mt-2">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    <span>Product: <strong>{toTitleCase(selectedProduct.name)}</strong></span>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Quantity</label>
                  <input
                    type="number"
                    min="1"
                    value={qty || ''}
                    onChange={e => setQty(Number(e.target.value))}
                    className="w-full px-3 py-2 bg-muted/40 border border-border rounded-xl text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-wide">Rate (₹/ea)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={price || ''}
                    onChange={e => setPrice(Number(e.target.value))}
                    className="w-full px-3 py-2 bg-muted/40 border border-border rounded-xl text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between border-t border-border/40 pt-3">
                <div>
                  <h4 className="text-xs font-bold text-foreground">Include 18% GST</h4>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Calculates simple 18% IGST/CGST split</p>
                </div>
                <button
                  type="button"
                  onClick={() => setHasGst(!hasGst)}
                  className={cn(
                    'w-9 h-5 rounded-full transition-all relative',
                    hasGst ? 'bg-emerald-500' : 'bg-muted border border-border'
                  )}
                >
                  <div className={cn('w-4 h-4 rounded-full bg-white shadow absolute top-[2px] transition-all', hasGst ? 'right-[2px]' : 'left-[2px]')} />
                </button>
              </div>

              <button
                type="button"
                disabled={!selectedProduct || qty <= 0}
                onClick={handleAddItem}
                className="w-full py-2.5 bg-emerald-500/10 hover:bg-emerald-500 text-emerald-600 hover:text-white font-bold rounded-xl text-xs transition-all border border-emerald-500/20 flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
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
              </div>

              <div className="border-t border-border pt-4">
                <span className="text-[9px] font-extrabold text-muted-foreground uppercase tracking-widest block mb-2.5">Order Items</span>
                <div className="space-y-2 max-h-56 overflow-y-auto no-scrollbar">
                  {cart.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-center text-xs">
                      <span className="text-muted-foreground truncate max-w-[200px]">{toTitleCase(item.name)}</span>
                      <span className="font-semibold shrink-0">{item.qty} × {formatCurrency(item.price)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Tax Breakdowns */}
              <div className="border-t border-border pt-3 space-y-1.5 text-xs text-muted-foreground">
                <div className="flex justify-between">
                  <span>Gross Subtotal</span>
                  <span>{formatCurrency(totals.subtotal)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Taxes (GST 18%)</span>
                  <span>{formatCurrency(totals.tax)}</span>
                </div>
              </div>

              {/* Grand Total */}
              <div className="border-t border-border pt-3 flex justify-between items-center bg-muted/10 p-4 rounded-xl border">
                <div>
                  <span className="text-xs font-bold text-foreground block">Grand Total</span>
                  <span className="text-[10px] text-muted-foreground block">(Inclusive of Taxes)</span>
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
