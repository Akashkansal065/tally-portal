'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'
import { Plus, X, Search, Save, Calendar, Filter } from 'lucide-react'

export default function PriceListManagerPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  
  const [loading, setLoading] = useState(true)
  const [groups, setGroups] = useState<any[]>([])
  const [levels, setLevels] = useState<any[]>([])
  const [items, setItems] = useState<any[]>([])
  
  // Selection State
  const [selectedGroup, setSelectedGroup] = useState<string>('')
  const [selectedLevel, setSelectedLevel] = useState<string>('')
  const [effectiveDate, setEffectiveDate] = useState<string>(new Date().toISOString().split('T')[0])
  
  // Grid State: map of item_id -> array of rate tiers
  const [gridData, setGridData] = useState<Record<number, any[]>>({})

  const fetchDependencies = async () => {
    try {
      const [rGroups, rLevels, rItems] = await Promise.all([
        fetch(`${API_BASE}/inventory/groups`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/inventory/price-levels`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) })
      ])
      
      setGroups(Array.isArray(await rGroups.json()) ? await rGroups.json() : [])
      setLevels(Array.isArray(await rLevels.json()) ? await rLevels.json() : [])
      
      const itemsData = await rItems.json()
      setItems(Array.isArray(itemsData) ? itemsData : [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.isAdmin) { router.replace('/'); return }
    fetchDependencies()
  }, [user, permissions, router])

  // Filter items based on group selection
  const displayItems = selectedGroup === '' ? items : items.filter(i => i.stock_group_id === Number(selectedGroup))

  // Initialize grid when group or items change
  useEffect(() => {
    const newGrid: Record<number, any[]> = {}
    displayItems.forEach(item => {
      // Find if we already have rates for this item in the selected level and date
      // For this UI, we will just initialize empty if not loaded, 
      // but if we wanted to edit existing, we'd pull from item.price_level_rates filtering by selectedLevel & date.
      const existingRates = (item.price_level_rates || []).filter((r: any) => 
        r.price_level_id === Number(selectedLevel) && r.effective_from === effectiveDate
      )
      
      if (existingRates.length > 0) {
        newGrid[item.stock_item_id] = existingRates.map((r: any) => ({ ...r }))
      } else {
        newGrid[item.stock_item_id] = [{ qty_from: '', qty_to: '', rate: '', discount_percent: '' }]
      }
    })
    setGridData(newGrid)
  }, [selectedGroup, selectedLevel, effectiveDate, items])

  const addTier = (itemId: number) => {
    const arr = [...(gridData[itemId] || [])]
    arr.push({ qty_from: '', qty_to: '', rate: '', discount_percent: '' })
    setGridData({ ...gridData, [itemId]: arr })
  }

  const removeTier = (itemId: number, idx: number) => {
    const arr = [...(gridData[itemId] || [])]
    if (arr.length > 1) {
      arr.splice(idx, 1)
      setGridData({ ...gridData, [itemId]: arr })
    } else {
      // clear it instead of removing last row
      arr[0] = { qty_from: '', qty_to: '', rate: '', discount_percent: '' }
      setGridData({ ...gridData, [itemId]: arr })
    }
  }

  const updateTier = (itemId: number, idx: number, field: string, val: string) => {
    const arr = [...(gridData[itemId] || [])]
    arr[idx][field] = val
    setGridData({ ...gridData, [itemId]: arr })
  }

  const handleSave = async () => {
    if (!selectedLevel) return alert("Please select a Price Level.")
    if (!effectiveDate) return alert("Please select an Effective Date.")

    // Flatten gridData into bulk rates payload
    const rates: any[] = []
    
    Object.keys(gridData).forEach(itemIdStr => {
      const itemId = Number(itemIdStr)
      const tiers = gridData[itemId]
      
      tiers.forEach(t => {
        if (t.rate !== '') {
          rates.push({
            stock_item_id: itemId,
            qty_from: t.qty_from === '' ? null : Number(t.qty_from),
            qty_to: t.qty_to === '' ? null : Number(t.qty_to),
            rate: Number(t.rate),
            discount_percent: t.discount_percent === '' ? 0 : Number(t.discount_percent)
          })
        }
      })
    })

    if (rates.length === 0) {
      return alert("No rates entered. Please enter at least one rate.")
    }

    try {
      const res = await fetch(`${API_BASE}/inventory/price-levels/${selectedLevel}/rates`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          stock_group_id: selectedGroup === '' ? null : Number(selectedGroup),
          effective_from: effectiveDate,
          rates
        })
      })
      if (!res.ok) throw new Error(await res.text())
      
      alert("Price List saved successfully!")
      // Refetch items to get updated rates
      fetchDependencies()
    } catch (e: any) {
      console.error(e)
      alert("Error saving: " + e.message)
    }
  }

  if (loading) {
    return <div className="h-full flex items-center justify-center"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>
  }

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col p-6 overflow-hidden">
      <div className="flex justify-between items-center mb-6 shrink-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Price List Manager</h1>
          <p className="text-sm text-muted-foreground mt-1">Bulk manage date-effective item rates for specific price levels.</p>
        </div>
        <button 
          onClick={handleSave}
          className="bg-primary text-primary-foreground px-5 py-2.5 rounded-lg font-medium text-sm flex items-center gap-2 hover:bg-primary/90 transition-colors shadow-sm"
        >
          <Save className="h-4 w-4" /> Save Price List
        </button>
      </div>

      <div className="bg-card border border-border rounded-xl shadow-sm mb-6 shrink-0 p-4 flex items-end gap-6">
        <div className="flex-1">
          <label className="text-xs font-semibold mb-1.5 block uppercase text-muted-foreground">Stock Group</label>
          <select value={selectedGroup} onChange={e => setSelectedGroup(e.target.value)} className="w-full bg-background border border-input rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary focus:outline-none">
            <option value="">All Items</option>
            {groups.map(g => <option key={g.stock_group_id} value={g.stock_group_id}>{g.name}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <label className="text-xs font-semibold mb-1.5 block uppercase text-muted-foreground">Price Level <span className="text-destructive">*</span></label>
          <select value={selectedLevel} onChange={e => setSelectedLevel(e.target.value)} className="w-full bg-background border border-input rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary focus:outline-none border-primary/30">
            <option value="" disabled>Select Price Level...</option>
            {levels.map(l => <option key={l.price_level_id} value={l.price_level_id}>{l.name}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <label className="text-xs font-semibold mb-1.5 block uppercase text-muted-foreground">Applicable From <span className="text-destructive">*</span></label>
          <input type="date" value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} className="w-full bg-background border border-input rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
        </div>
      </div>

      <div className="bg-card border border-border rounded-xl shadow-sm flex-1 overflow-hidden flex flex-col relative">
        {/* Header */}
        <div className="grid grid-cols-12 gap-4 bg-muted/50 border-b border-border px-6 py-3 font-semibold text-sm text-muted-foreground">
          <div className="col-span-3">Item Name</div>
          <div className="col-span-2 text-right">Cost Price</div>
          <div className="col-span-7">
            <div className="grid grid-cols-12 gap-2 text-xs">
              <div className="col-span-3 text-right">Qty From</div>
              <div className="col-span-3 text-right">Qty To</div>
              <div className="col-span-3 text-right">Rate</div>
              <div className="col-span-2 text-right">Disc %</div>
              <div className="col-span-1"></div>
            </div>
          </div>
        </div>

        {/* Body */}
        {!selectedLevel ? (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8 text-center bg-muted/10">
            <Filter className="h-10 w-10 mb-3 opacity-20" />
            <p className="font-medium text-lg text-foreground mb-1">Select a Price Level</p>
            <p className="text-sm">You must select a Price Level to view and edit rates.</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {displayItems.length === 0 ? (
              <div className="text-center py-10 text-muted-foreground">No items found in the selected group.</div>
            ) : (
              displayItems.map((item) => {
                const tiers = gridData[item.stock_item_id] || []
                
                return (
                  <div key={item.stock_item_id} className="grid grid-cols-12 gap-4 items-start border-b border-border/50 pb-4 last:border-0">
                    <div className="col-span-3">
                      <div className="font-semibold text-sm">{item.name}</div>
                      <div className="text-xs text-muted-foreground">{item.uom || 'No UOM'}</div>
                    </div>
                    <div className="col-span-2 text-right text-sm text-muted-foreground">
                      {item.standard_cost_price ? `₹ ${item.standard_cost_price}` : '—'}
                    </div>
                    <div className="col-span-7 space-y-2">
                      {tiers.map((t, idx) => (
                        <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                          <div className="col-span-3">
                            <input 
                              type="number" step="any" min="0" placeholder="0" 
                              value={t.qty_from} onChange={e => updateTier(item.stock_item_id, idx, 'qty_from', e.target.value)}
                              className="w-full bg-background border border-input rounded-md px-2 py-1.5 text-sm text-right focus:ring-1 focus:ring-primary focus:outline-none" 
                            />
                          </div>
                          <div className="col-span-3">
                            <input 
                              type="number" step="any" min="0" placeholder="Less than" 
                              value={t.qty_to} onChange={e => updateTier(item.stock_item_id, idx, 'qty_to', e.target.value)}
                              className="w-full bg-background border border-input rounded-md px-2 py-1.5 text-sm text-right focus:ring-1 focus:ring-primary focus:outline-none" 
                            />
                          </div>
                          <div className="col-span-3 relative">
                            <span className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground text-xs">₹</span>
                            <input 
                              type="number" step="any" min="0" placeholder="0.00" 
                              value={t.rate} onChange={e => updateTier(item.stock_item_id, idx, 'rate', e.target.value)}
                              className="w-full bg-background border border-input rounded-md pl-6 pr-2 py-1.5 text-sm text-right focus:ring-1 focus:ring-primary focus:outline-none" 
                            />
                          </div>
                          <div className="col-span-2 relative">
                            <input 
                              type="number" step="any" min="0" max="100" placeholder="0" 
                              value={t.discount_percent} onChange={e => updateTier(item.stock_item_id, idx, 'discount_percent', e.target.value)}
                              className="w-full bg-background border border-input rounded-md px-2 py-1.5 text-sm text-right focus:ring-1 focus:ring-primary focus:outline-none" 
                            />
                            <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground text-xs">%</span>
                          </div>
                          <div className="col-span-1 flex justify-end gap-1">
                            {idx === tiers.length - 1 && (
                              <button onClick={() => addTier(item.stock_item_id)} className="text-primary hover:bg-primary/10 p-1 rounded transition-colors"><Plus className="h-4 w-4" /></button>
                            )}
                            {(tiers.length > 1 || t.rate !== '') && (
                              <button onClick={() => removeTier(item.stock_item_id, idx)} className="text-destructive hover:bg-destructive/10 p-1 rounded transition-colors"><X className="h-4 w-4" /></button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        )}
      </div>
    </div>
  )
}
