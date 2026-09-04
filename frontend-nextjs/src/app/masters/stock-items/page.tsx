'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'
import { Plus, Edit2, Trash2, X, Info, Search, FileText, Tag, Banknote, MapPin, Package, Settings, ChevronRight, Wrench } from 'lucide-react'
import { useReorderableColumns, DraggableTh, ResetColumnsButton } from '@/components/ui/reorderable-columns'

export default function StockItemsPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const [uoms, setUoms] = useState<any[]>([])
  const [groups, setGroups] = useState<any[]>([])
  const [categories, setCategories] = useState<any[]>([])
  const [godowns, setGodowns] = useState<any[]>([])

  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  
  // Tabs for Progressive Disclosure
  const [activeTab, setActiveTab] = useState<'basic' | 'pricing' | 'tax' | 'tracking' | 'opening' | 'aliases' | 'bom'>('basic')
  
  // Form State
  const [itemId, setItemId] = useState<number | null>(null)
  
  // Basic Info
  const [name, setName] = useState('')
  const [groupId, setGroupId] = useState<number | ''>('')
  const [categoryId, setCategoryId] = useState<number | ''>('')
  const [unitId, setUnitId] = useState<number | ''>('')
  const [altUnitId, setAltUnitId] = useState<number | ''>('')
  const [altUnitConversion, setAltUnitConversion] = useState<string>('')
  const [description, setDescription] = useState('')
  const [isActive, setIsActive] = useState(true)
  
  // Pricing
  const [stdCost, setStdCost] = useState('')
  const [stdSelling, setStdSelling] = useState('')
  
  // Tax
  const [hsnCode, setHsnCode] = useState('')
  const [gstRate, setGstRate] = useState('')
  
  // Tracking
  const [trackingType, setTrackingType] = useState('None')
  const [reorderLevel, setReorderLevel] = useState('')
  const [minOrderQty, setMinOrderQty] = useState('')
  const [shelfLife, setShelfLife] = useState('')
  
  // Opening Balance (Simple for now: one total, or we can do list per godown. Let's do list per godown)
  const [openingBalances, setOpeningBalances] = useState<any[]>([])
  
  // Aliases
  const [aliases, setAliases] = useState<any[]>([])
  const [newAlias, setNewAlias] = useState('')
  
  // BOMs
  const [boms, setBoms] = useState<any[]>([])

  // Reorderable column hook
  const stockItemCols = useReorderableColumns({
    tableKey: 'master_stock_items',
    defaultColumns: ['name', 'group_name', 'uom', 'hsn_code', 'closing_balance', 'actions'],
  })

  const fetchDependencies = async () => {
    try {
      const [rItems, rUoms, rGroups, rCats, rGodowns] = await Promise.all([
        fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/inventory/uoms`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/inventory/groups`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/inventory/categories`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/inventory/godowns`, { headers: authHeaders(token) })
      ])
      
      setItems(Array.isArray(await rItems.json()) ? await rItems.json() : [])
      setUoms(Array.isArray(await rUoms.json()) ? await rUoms.json() : [])
      setGroups(Array.isArray(await rGroups.json()) ? await rGroups.json() : [])
      setCategories(Array.isArray(await rCats.json()) ? await rCats.json() : [])
      setGodowns(Array.isArray(await rGodowns.json()) ? await rGodowns.json() : [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const fetchItemsOnly = async () => {
    try {
      const res = await fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) })
      setItems(Array.isArray(await res.json()) ? await res.json() : [])
    } catch(e) { console.error(e) }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.isAdmin) { router.replace('/'); return }
    fetchDependencies()
  }, [user, permissions, router])

  const openCreate = () => {
    setIsEditing(false)
    setItemId(null)
    setActiveTab('basic')
    
    setName('')
    setGroupId('')
    setCategoryId('')
    setUnitId('')
    setAltUnitId('')
    setAltUnitConversion('')
    setDescription('')
    setIsActive(true)
    
    setStdCost('')
    setStdSelling('')
    setHsnCode('')
    setGstRate('')
    
    setTrackingType('None')
    setReorderLevel('')
    setMinOrderQty('')
    setShelfLife('')
    
    setOpeningBalances([])
    setAliases([])
    setNewAlias('')
    setBoms([])
    
    setIsPanelOpen(true)
  }

  const openEdit = async (itemRes: any) => {
    setIsEditing(true)
    setActiveTab('basic')
    
    // Fetch full item details including aliases and opening balances
    try {
      const res = await fetch(`${API_BASE}/inventory/items/${itemRes.stock_item_id}`, { headers: authHeaders(token) })
      const i = await res.json()
      
      setItemId(i.stock_item_id)
      setName(i.name || '')
      setGroupId(i.stock_group_id || '')
      setCategoryId(i.stock_category_id || '')
      setUnitId(i.unit_id || '')
      setAltUnitId(i.alt_unit_id || '')
      setAltUnitConversion(i.alt_unit_conversion ? i.alt_unit_conversion.toString() : '')
      setDescription(i.description || '')
      setIsActive(i.is_active ?? true)
      
      setStdCost(i.standard_cost_price ? i.standard_cost_price.toString() : '')
      setStdSelling(i.standard_selling_price ? i.standard_selling_price.toString() : '')
      
      setHsnCode(i.hsn_code || '')
      setGstRate(i.gst_rate_percent ? i.gst_rate_percent.toString() : '')
      
      setTrackingType(i.tracking_type || 'None')
      setReorderLevel(i.reorder_level ? i.reorder_level.toString() : '')
      setMinOrderQty(i.minimum_order_qty ? i.minimum_order_qty.toString() : '')
      setShelfLife(i.shelf_life_days ? i.shelf_life_days.toString() : '')
      
      setOpeningBalances(i.opening_balances || [])
      setAliases(i.aliases || [])
      setNewAlias('')
      setBoms(i.boms || [])
      
      setIsPanelOpen(true)
    } catch (e) {
      console.error(e)
      alert("Error fetching item details")
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this stock item? All history will be lost.')) return
    try {
      await fetch(`${API_BASE}/inventory/items/${id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      fetchItemsOnly()
      if (itemId === id) setIsPanelOpen(false)
    } catch (e) {
      console.error(e)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !unitId) {
      alert("Name and Base Unit are required")
      setActiveTab('basic')
      return
    }

    const payload = {
      name,
      stock_group_id: groupId === '' ? null : Number(groupId),
      stock_category_id: categoryId === '' ? null : Number(categoryId),
      unit_id: Number(unitId),
      alt_unit_id: altUnitId === '' ? null : Number(altUnitId),
      alt_unit_conversion: altUnitConversion === '' ? null : Number(altUnitConversion),
      description: description || null,
      standard_cost_price: stdCost === '' ? null : Number(stdCost),
      standard_selling_price: stdSelling === '' ? null : Number(stdSelling),
      hsn_code: hsnCode || null,
      gst_rate_percent: gstRate === '' ? 0 : Number(gstRate),
      reorder_level: reorderLevel === '' ? 0 : Number(reorderLevel),
      minimum_order_qty: minOrderQty === '' ? 0 : Number(minOrderQty),
      tracking_type: trackingType,
      shelf_life_days: shelfLife === '' ? null : Number(shelfLife),
      is_active: isActive,
      aliases: aliases.map(a => ({ alias: a.alias, alias_type: a.alias_type || 'name' })),
      price_lists: [],
      price_level_rates: [], // For future update via Price List Manager
      boms: boms.map(b => ({
        bom_name: b.bom_name,
        unit_of_manufacture: Number(b.unit_of_manufacture || 1),
        is_active: b.is_active ?? true,
        components: (b.components || []).map((c: any) => ({
          component_item_id: Number(c.component_item_id),
          godown_id: c.godown_id ? Number(c.godown_id) : null,
          quantity: Number(c.quantity || 0),
          component_type: c.component_type || 'Component'
        }))
      })),
      opening_balances: openingBalances.map(ob => ({
        godown_id: ob.godown_id === '' ? null : Number(ob.godown_id),
        batch_name: ob.batch_name || null,
        quantity: Number(ob.quantity || 0),
        rate: Number(ob.rate || 0),
        amount: Number(ob.quantity || 0) * Number(ob.rate || 0)
      }))
    }
    
    // Auto-calculate aggregate opening qty/rate
    let totalQty = 0
    let totalAmt = 0
    payload.opening_balances.forEach(ob => {
      totalQty += ob.quantity
      totalAmt += ob.amount
    })
    
    // @ts-ignore
    payload.opening_qty = totalQty
    // @ts-ignore
    payload.opening_rate = totalQty > 0 ? totalAmt / totalQty : 0

    const url = isEditing ? `${API_BASE}/inventory/items/${itemId}` : `${API_BASE}/inventory/items`
    const method = isEditing ? 'PUT' : 'POST'

    try {
      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const d = await res.json()
        alert(d.detail || "Error saving item")
        return
      }
      setIsPanelOpen(false)
      fetchItemsOnly()
    } catch (e) {
      console.error(e)
    }
  }

  // Helpers for nested states
  const addAlias = () => {
    if (!newAlias) return
    setAliases([...aliases, { alias: newAlias, alias_type: 'name' }])
    setNewAlias('')
  }
  
  const addOpeningBalance = () => {
    setOpeningBalances([...openingBalances, { godown_id: '', batch_name: '', quantity: '', rate: '' }])
  }
  
  const addBom = () => {
    setBoms([...boms, { bom_name: 'New BOM', unit_of_manufacture: 1, is_active: true, components: [] }])
  }
  
  const addBomComponent = (bomIndex: number) => {
    const newBoms = [...boms]
    newBoms[bomIndex].components.push({ component_item_id: '', godown_id: '', quantity: '', component_type: 'Component' })
    setBoms(newBoms)
  }

  const tabs = [
    { id: 'basic', label: 'Basic Info', icon: <FileText className="h-4 w-4" /> },
    { id: 'pricing', label: 'Pricing', icon: <Banknote className="h-4 w-4" /> },
    { id: 'tax', label: 'GST & Tax', icon: <Tag className="h-4 w-4" /> },
    { id: 'tracking', label: 'Stock Tracking', icon: <Settings className="h-4 w-4" /> },
    { id: 'bom', label: 'Bill of Materials', icon: <Wrench className="h-4 w-4" /> },
    { id: 'opening', label: 'Opening Stock', icon: <MapPin className="h-4 w-4" /> },
    { id: 'aliases', label: 'Aliases / Codes', icon: <Package className="h-4 w-4" /> },
  ]

  return (
    <div className="h-[calc(100vh-64px)] flex overflow-hidden">
      <div className={`flex-1 flex flex-col p-6 overflow-y-auto transition-all ${isPanelOpen ? 'mr-[700px]' : ''}`}>
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Stock Items</h1>
            <p className="text-sm text-muted-foreground mt-1">Manage your inventory products, raw materials, and services.</p>
          </div>
          <div className="flex items-center gap-3">
            <ResetColumnsButton {...stockItemCols} />
            <button 
              onClick={openCreate}
              className="bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 hover:bg-primary/90 transition-colors shadow-sm"
            >
              <Plus className="h-4 w-4" /> Create Item
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center p-8"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>
        ) : (
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
            {(() => {
              const stockItemColDefs: Record<string, { label: string; align?: 'left' | 'center' | 'right' }> = {
                name: { label: 'Item Name', align: 'left' },
                group_name: { label: 'Group', align: 'left' },
                uom: { label: 'UOM', align: 'left' },
                hsn_code: { label: 'HSN', align: 'left' },
                closing_balance: { label: 'Closing Qty', align: 'right' },
                actions: { label: 'Actions', align: 'right' },
              }

              return (
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="bg-muted/50 border-b border-border">
                      {stockItemCols.columns.map((colId) => {
                        const def = stockItemColDefs[colId]
                        if (!def) return null
                        return (
                          <DraggableTh
                            key={colId}
                            id={colId}
                            label={def.label}
                            align={def.align}
                            reorderProps={stockItemCols}
                            className="px-4 py-3 font-semibold text-muted-foreground"
                          />
                        )
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {items.length === 0 ? (
                      <tr>
                        <td colSpan={stockItemCols.columns.length} className="px-4 py-8 text-center text-muted-foreground">No stock items found.</td>
                      </tr>
                    ) : (
                      items.map(item => (
                        <tr key={item.stock_item_id} className="border-b border-border last:border-0 hover:bg-muted/20 transition-colors">
                          {stockItemCols.columns.map((colId) => {
                            switch (colId) {
                              case 'name':
                                return (
                                  <td key="name" className="px-4 py-3 align-middle">
                                    <div className="flex items-center gap-2">
                                      <span className={`font-semibold ${!item.is_active && 'line-through text-muted-foreground'}`}>{item.name}</span>
                                    </div>
                                  </td>
                                )
                              case 'group_name':
                                return (
                                  <td key="group_name" className="px-4 py-3 align-middle text-muted-foreground">
                                    {item.group_name || 'Primary'}
                                  </td>
                                )
                              case 'uom':
                                return (
                                  <td key="uom" className="px-4 py-3 align-middle text-muted-foreground">
                                    {item.uom || '—'}
                                  </td>
                                )
                              case 'hsn_code':
                                return (
                                  <td key="hsn_code" className="px-4 py-3 align-middle text-muted-foreground">
                                    {item.hsn_code || '—'}
                                  </td>
                                )
                              case 'closing_balance':
                                return (
                                  <td key="closing_balance" className="px-4 py-3 align-middle text-right font-medium">
                                    {item.closing_balance}
                                  </td>
                                )
                              case 'actions':
                                return (
                                  <td key="actions" className="px-4 py-3 align-middle text-right space-x-2">
                                    <button onClick={() => openEdit(item)} className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"><Edit2 className="h-4 w-4" /></button>
                                    <button onClick={() => handleDelete(item.stock_item_id)} className="p-1.5 text-muted-foreground hover:text-destructive transition-colors"><Trash2 className="h-4 w-4" /></button>
                                  </td>
                                )
                              default:
                                return null
                            }
                          })}
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )
            })()}
          </div>
        )}
      </div>

      {/* Large Slide-over Form with Progressive Disclosure */}
      <div className={`fixed top-[64px] right-0 bottom-0 w-[700px] bg-card border-l border-border shadow-2xl transition-transform duration-300 transform flex flex-col z-40 ${isPanelOpen ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div>
            <h2 className="text-xl font-bold">{isEditing ? 'Edit Stock Item' : 'Create Stock Item'}</h2>
            <p className="text-xs text-muted-foreground mt-0.5">{name || 'New Item'}</p>
          </div>
          <button onClick={() => setIsPanelOpen(false)} className="p-2 hover:bg-muted rounded-full transition-colors"><X className="h-5 w-5" /></button>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Vertical Tabs */}
          <div className="w-[200px] border-r border-border bg-muted/10 overflow-y-auto py-4 flex flex-col gap-1 px-3">
            {tabs.map(tab => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left ${activeTab === tab.id ? 'bg-primary text-primary-foreground shadow' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Form Content */}
          <div className="flex-1 overflow-y-auto p-6 bg-background">
            <form id="item-form" onSubmit={handleSave} className="space-y-6">
              
              {/* BASIC INFO */}
              <div className={activeTab === 'basic' ? 'block animate-in fade-in zoom-in-95 duration-200' : 'hidden'}>
                <h3 className="text-lg font-semibold mb-4 border-b border-border pb-2">Basic Information</h3>
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-semibold mb-1.5 block">Item Name <span className="text-destructive">*</span></label>
                    <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. iPhone 14 Pro, Cement Bag" className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" required />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-semibold mb-1.5 block">Under Group</label>
                      <select value={groupId} onChange={e => setGroupId(e.target.value ? Number(e.target.value) : '')} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none">
                        <option value="">Primary</option>
                        {groups.filter(g => (g.name || '').trim().toLowerCase() !== 'primary').map(g => <option key={g.stock_group_id} value={g.stock_group_id}>{g.name.trim()}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-sm font-semibold mb-1.5 block">Category</label>
                      <select value={categoryId} onChange={e => setCategoryId(e.target.value ? Number(e.target.value) : '')} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none">
                        <option value="">Not Applicable</option>
                        {categories.map(c => <option key={c.stock_category_id} value={c.stock_category_id}>{c.name}</option>)}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-semibold mb-1.5 block">Base Unit <span className="text-destructive">*</span></label>
                      <select value={unitId} onChange={e => setUnitId(e.target.value ? Number(e.target.value) : '')} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" required>
                        <option value="" disabled>Select Unit...</option>
                        {uoms.filter(u => (u.symbol || '').trim().toLowerCase() !== 'not applicable').map(u => <option key={u.unit_id} value={u.unit_id}>{u.symbol} {u.original_name ? `(${u.original_name})` : ''}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-sm font-semibold mb-1.5 block">Alternate Unit</label>
                      <select value={altUnitId} onChange={e => setAltUnitId(e.target.value ? Number(e.target.value) : '')} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none">
                        <option value="">Not Applicable</option>
                        {uoms.filter(u => (u.symbol || '').trim().toLowerCase() !== 'not applicable').map(u => <option key={u.unit_id} value={u.unit_id}>{u.symbol} {u.original_name ? `(${u.original_name})` : ''}</option>)}
                      </select>
                    </div>
                  </div>

                  {altUnitId && (
                    <div className="bg-muted/30 p-3 rounded-lg border border-border">
                      <label className="text-xs font-semibold uppercase text-muted-foreground mb-2 block">Where</label>
                      <div className="flex items-center gap-3">
                        <input type="number" min="0.0001" step="any" value={altUnitConversion} onChange={e => setAltUnitConversion(e.target.value)} placeholder="e.g. 10" className="w-24 bg-background border border-input rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
                        <span className="text-sm font-medium">{uoms.find(u => u.unit_id === Number(altUnitId))?.symbol || 'Alt Unit'} = 1 {uoms.find(u => u.unit_id === Number(unitId))?.symbol || 'Base Unit'}</span>
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="text-sm font-semibold mb-1.5 block">Description</label>
                    <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} placeholder="Detailed product description..." className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none resize-none" />
                  </div>
                  
                  <div className="flex items-center gap-3 pt-2">
                    <input type="checkbox" id="item_is_active" checked={isActive} onChange={e => setIsActive(e.target.checked)} className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary" />
                    <label htmlFor="item_is_active" className="text-sm font-medium">Item is Active</label>
                  </div>
                </div>
              </div>

              {/* PRICING */}
              <div className={activeTab === 'pricing' ? 'block animate-in fade-in zoom-in-95 duration-200' : 'hidden'}>
                <h3 className="text-lg font-semibold mb-4 border-b border-border pb-2">Standard Pricing</h3>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <label className="text-sm font-semibold mb-1.5 block">Standard Cost</label>
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">₹</span>
                        <input type="number" step="any" min="0" value={stdCost} onChange={e => setStdCost(e.target.value)} placeholder="0.00" className="w-full bg-background border border-input rounded-lg pl-7 pr-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-semibold mb-1.5 block">Standard Selling Price</label>
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">₹</span>
                        <input type="number" step="any" min="0" value={stdSelling} onChange={e => setStdSelling(e.target.value)} placeholder="0.00" className="w-full bg-background border border-input rounded-lg pl-7 pr-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
                      </div>
                    </div>
                  </div>
                  
                  <div className="mt-8 bg-blue-50/50 p-4 rounded-xl border border-blue-100 flex gap-3 text-blue-800 text-sm">
                    <Info className="h-5 w-5 shrink-0 mt-0.5" />
                    <p>Advanced date-effective price lists (Multiple Price Levels) are supported by the backend model and will be manageable in a future UI phase.</p>
                  </div>
                </div>
              </div>

              {/* TAX */}
              <div className={activeTab === 'tax' ? 'block animate-in fade-in zoom-in-95 duration-200' : 'hidden'}>
                <h3 className="text-lg font-semibold mb-4 border-b border-border pb-2">GST & HSN/SAC Details</h3>
                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-semibold mb-1.5 block">HSN / SAC Code</label>
                    <input type="text" maxLength={10} value={hsnCode} onChange={e => setHsnCode(e.target.value.replace(/[^0-9]/g, ''))} placeholder="e.g. 84713010" className="w-full max-w-sm bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
                    <p className="text-xs text-muted-foreground mt-1">4, 6, or 8 digit numeric code.</p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-semibold mb-1.5 block">GST Rate (%)</label>
                    <div className="relative max-w-sm">
                      <input type="number" step="0.01" min="0" max="100" value={gstRate} onChange={e => setGstRate(e.target.value)} placeholder="e.g. 18.00" className="w-full bg-background border border-input rounded-lg pr-8 pl-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">%</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* TRACKING */}
              <div className={activeTab === 'tracking' ? 'block animate-in fade-in zoom-in-95 duration-200' : 'hidden'}>
                <h3 className="text-lg font-semibold mb-4 border-b border-border pb-2">Inventory Tracking & Behaviors</h3>
                <div className="space-y-5">
                  <div>
                    <label className="text-sm font-semibold mb-1.5 block">Maintain in Batches or Serials?</label>
                    <select value={trackingType} onChange={e => setTrackingType(e.target.value)} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none">
                      <option value="None">None (Simple Quantity)</option>
                      <option value="Batch">Maintain in Batches / Lots</option>
                      <option value="Serial">Maintain Serial Numbers</option>
                    </select>
                  </div>
                  
                  {trackingType === 'Batch' && (
                    <div className="bg-muted/30 p-4 rounded-lg border border-border">
                      <label className="text-sm font-semibold mb-1.5 block">Shelf Life (Days)</label>
                      <input type="number" min="1" value={shelfLife} onChange={e => setShelfLife(e.target.value)} placeholder="e.g. 365" className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none mb-1" />
                      <p className="text-xs text-muted-foreground">Used to calculate expiry date from manufacture date.</p>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-semibold mb-1.5 block">Reorder Level</label>
                      <input type="number" step="any" min="0" value={reorderLevel} onChange={e => setReorderLevel(e.target.value)} placeholder="0" className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
                    </div>
                    <div>
                      <label className="text-sm font-semibold mb-1.5 block">Minimum Order Qty</label>
                      <input type="number" step="any" min="0" value={minOrderQty} onChange={e => setMinOrderQty(e.target.value)} placeholder="0" className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
                    </div>
                  </div>
                </div>
              </div>

              {/* OPENING STOCK */}
              <div className={activeTab === 'opening' ? 'block animate-in fade-in zoom-in-95 duration-200' : 'hidden'}>
                <div className="flex justify-between items-center mb-4 border-b border-border pb-2">
                  <h3 className="text-lg font-semibold">Opening Balances</h3>
                  <button type="button" onClick={addOpeningBalance} className="text-primary text-sm font-semibold hover:underline flex items-center gap-1"><Plus className="h-4 w-4" /> Add Row</button>
                </div>
                
                {openingBalances.length === 0 ? (
                  <div className="text-center py-8 bg-muted/20 rounded-lg border border-dashed border-border">
                    <p className="text-sm text-muted-foreground mb-3">No opening stock defined.</p>
                    <button type="button" onClick={addOpeningBalance} className="bg-primary text-primary-foreground px-3 py-1.5 rounded-lg text-sm font-medium">Add Opening Stock</button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="grid grid-cols-12 gap-2 px-2 text-xs font-semibold text-muted-foreground uppercase">
                      <div className="col-span-4">Godown</div>
                      <div className="col-span-3">Qty</div>
                      <div className="col-span-4">Rate</div>
                      <div className="col-span-1"></div>
                    </div>
                    {openingBalances.map((ob, idx) => (
                      <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                        <div className="col-span-4">
                          <select 
                            value={ob.godown_id} 
                            onChange={e => { const newBals = [...openingBalances]; newBals[idx].godown_id = e.target.value; setOpeningBalances(newBals) }}
                            className="w-full bg-background border border-input rounded-md px-2 py-1.5 text-sm"
                          >
                            <option value="">Main Location</option>
                            {godowns.map(g => <option key={g.godown_id} value={g.godown_id}>{g.name}</option>)}
                          </select>
                        </div>
                        <div className="col-span-3">
                          <input 
                            type="number" step="any" min="0" placeholder="Qty" value={ob.quantity}
                            onChange={e => { const newBals = [...openingBalances]; newBals[idx].quantity = e.target.value; setOpeningBalances(newBals) }}
                            className="w-full bg-background border border-input rounded-md px-2 py-1.5 text-sm"
                          />
                        </div>
                        <div className="col-span-4 relative">
                          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground text-xs">₹</span>
                          <input 
                            type="number" step="any" min="0" placeholder="Rate" value={ob.rate}
                            onChange={e => { const newBals = [...openingBalances]; newBals[idx].rate = e.target.value; setOpeningBalances(newBals) }}
                            className="w-full bg-background border border-input rounded-md pl-6 pr-2 py-1.5 text-sm"
                          />
                        </div>
                        <div className="col-span-1 flex justify-center">
                          <button type="button" onClick={() => setOpeningBalances(openingBalances.filter((_, i) => i !== idx))} className="text-muted-foreground hover:text-destructive"><Trash2 className="h-4 w-4" /></button>
                        </div>
                      </div>
                    ))}
                    <div className="bg-muted/50 p-3 rounded-lg flex justify-between items-center text-sm font-semibold mt-4">
                      <span>Total Value:</span>
                      <span>₹ {openingBalances.reduce((acc, curr) => acc + (Number(curr.quantity || 0) * Number(curr.rate || 0)), 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* ALIASES */}
              <div className={activeTab === 'aliases' ? 'block animate-in fade-in zoom-in-95 duration-200' : 'hidden'}>
                <h3 className="text-lg font-semibold mb-4 border-b border-border pb-2">Aliases & Part Numbers</h3>
                <div className="space-y-4">
                  <div className="flex gap-2">
                    <input 
                      type="text" 
                      value={newAlias} 
                      onChange={e => setNewAlias(e.target.value)} 
                      onKeyDown={e => { if(e.key === 'Enter') { e.preventDefault(); addAlias() } }}
                      placeholder="Type an alias and press enter or click add..." 
                      className="flex-1 bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" 
                    />
                    <button type="button" onClick={addAlias} className="bg-secondary text-secondary-foreground px-4 rounded-lg text-sm font-medium hover:bg-secondary/80">Add</button>
                  </div>

                  {aliases.length > 0 && (
                    <div className="bg-muted/20 border border-border rounded-lg divide-y divide-border">
                      {aliases.map((a, idx) => (
                        <div key={idx} className="flex justify-between items-center px-4 py-2.5">
                          <span className="text-sm font-medium">{a.alias}</span>
                          <button type="button" onClick={() => setAliases(aliases.filter((_, i) => i !== idx))} className="text-muted-foreground hover:text-destructive p-1"><X className="h-4 w-4" /></button>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  <p className="text-xs text-muted-foreground mt-2">Useful for alternative names, product codes, or barcodes during billing.</p>
                </div>
              </div>

              {/* BOM */}
              <div className={activeTab === 'bom' ? 'block animate-in fade-in zoom-in-95 duration-200' : 'hidden'}>
                <div className="flex justify-between items-center mb-4 border-b border-border pb-2">
                  <h3 className="text-lg font-semibold">Bill of Materials (BOM)</h3>
                  <button type="button" onClick={addBom} className="text-primary text-sm font-semibold hover:underline flex items-center gap-1"><Plus className="h-4 w-4" /> Add BOM</button>
                </div>
                
                {boms.length === 0 ? (
                  <div className="text-center py-8 bg-muted/20 rounded-lg border border-dashed border-border">
                    <p className="text-sm text-muted-foreground mb-3">No Bill of Materials defined for this item.</p>
                    <button type="button" onClick={addBom} className="bg-primary text-primary-foreground px-3 py-1.5 rounded-lg text-sm font-medium">Create BOM</button>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {boms.map((bom, bIdx) => (
                      <div key={bIdx} className="bg-muted/10 border border-border rounded-xl p-4 shadow-sm relative">
                        <button type="button" onClick={() => setBoms(boms.filter((_, i) => i !== bIdx))} className="absolute top-3 right-3 text-muted-foreground hover:text-destructive"><Trash2 className="h-4 w-4" /></button>
                        
                        <div className="grid grid-cols-2 gap-4 mb-4 pr-6">
                          <div>
                            <label className="text-xs font-semibold mb-1 block uppercase text-muted-foreground">BOM Name</label>
                            <input type="text" value={bom.bom_name} onChange={e => { const nb = [...boms]; nb[bIdx].bom_name = e.target.value; setBoms(nb) }} className="w-full bg-background border border-input rounded-md px-3 py-1.5 text-sm" placeholder="e.g. Standard Formula" />
                          </div>
                          <div>
                            <label className="text-xs font-semibold mb-1 block uppercase text-muted-foreground">Unit of Manufacture</label>
                            <div className="flex items-center gap-2">
                              <input type="number" min="1" step="any" value={bom.unit_of_manufacture} onChange={e => { const nb = [...boms]; nb[bIdx].unit_of_manufacture = e.target.value; setBoms(nb) }} className="w-24 bg-background border border-input rounded-md px-3 py-1.5 text-sm" />
                              <span className="text-sm">{uoms.find(u => u.unit_id === Number(unitId))?.symbol || 'Unit'}</span>
                            </div>
                          </div>
                        </div>

                        <div className="mt-4 border-t border-border pt-4">
                          <div className="flex justify-between items-center mb-2">
                            <h4 className="text-sm font-semibold">Components</h4>
                            <button type="button" onClick={() => addBomComponent(bIdx)} className="text-primary text-xs font-semibold hover:underline flex items-center gap-1"><Plus className="h-3 w-3" /> Add Item</button>
                          </div>
                          
                          {bom.components.length === 0 ? (
                            <div className="text-xs text-muted-foreground italic py-2">No components added yet.</div>
                          ) : (
                            <div className="space-y-2 mt-2">
                              {bom.components.map((comp: any, cIdx: number) => (
                                <div key={cIdx} className="flex gap-2 items-center">
                                  <div className="flex-1">
                                    <select value={comp.component_item_id} onChange={e => { const nb = [...boms]; nb[bIdx].components[cIdx].component_item_id = e.target.value; setBoms(nb) }} className="w-full bg-background border border-input rounded-md px-2 py-1.5 text-sm">
                                      <option value="" disabled>Select Item...</option>
                                      {items.filter(i => i.stock_item_id !== itemId).map(i => <option key={i.stock_item_id} value={i.stock_item_id}>{i.name}</option>)}
                                    </select>
                                  </div>
                                  <div className="w-24">
                                    <input type="number" min="0.001" step="any" placeholder="Qty" value={comp.quantity} onChange={e => { const nb = [...boms]; nb[bIdx].components[cIdx].quantity = e.target.value; setBoms(nb) }} className="w-full bg-background border border-input rounded-md px-2 py-1.5 text-sm" />
                                  </div>
                                  <div className="w-28">
                                    <select value={comp.component_type} onChange={e => { const nb = [...boms]; nb[bIdx].components[cIdx].component_type = e.target.value; setBoms(nb) }} className="w-full bg-background border border-input rounded-md px-2 py-1.5 text-sm">
                                      <option value="Component">Component</option>
                                      <option value="Scrap">Scrap</option>
                                      <option value="By-Product">By-Product</option>
                                    </select>
                                  </div>
                                  <button type="button" onClick={() => { const nb = [...boms]; nb[bIdx].components.splice(cIdx, 1); setBoms(nb) }} className="text-muted-foreground hover:text-destructive p-1"><X className="h-4 w-4" /></button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </form>
          </div>
        </div>

        <div className="p-4 border-t border-border bg-muted/10 flex justify-end gap-3 z-10">
          <button type="button" onClick={() => setIsPanelOpen(false)} className="px-5 py-2.5 rounded-lg font-semibold text-sm hover:bg-muted transition-colors border border-transparent hover:border-border">Cancel</button>
          <button type="submit" form="item-form" className="bg-primary text-primary-foreground px-5 py-2.5 rounded-lg font-semibold text-sm hover:bg-primary/90 transition-colors shadow">Save Stock Item</button>
        </div>
      </div>
    </div>
  )
}
