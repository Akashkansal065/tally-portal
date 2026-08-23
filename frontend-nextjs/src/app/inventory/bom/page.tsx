'use client'

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, formatCurrency } from '@/lib/utils'
import { 
  Factory, Plus, Search, Layers, RefreshCw, ChevronRight, 
  Trash2, Sparkles, CheckCircle2, Box, ArrowRight, ShieldCheck,
  AlertCircle, Loader2
} from 'lucide-react'
import { toast } from 'sonner'

export default function BillOfMaterialsPage() {
  const { user, token } = useAuth()
  const router = useRouter()

  const [stockItems, setStockItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedItem, setSelectedItem] = useState<any>(null)

  // Modals
  const [isNewBomOpen, setIsNewBomOpen] = useState(false)
  const [isMfgJournalOpen, setIsMfgJournalOpen] = useState(false)
  const [selectedBomForMfg, setSelectedBomForMfg] = useState<any>(null)
  const [mfgQty, setMfgQty] = useState('1')
  const [mfgNarration, setMfgNarration] = useState('')
  const [isProducing, setIsProducing] = useState(false)

  // New BOM Form State
  const [newBomTargetItemId, setNewBomTargetItemId] = useState<string>('')
  const [newBomName, setNewBomName] = useState('Standard Production Recipe')
  const [newBomOutputQty, setNewBomOutputQty] = useState('1')
  const [newBomComponents, setNewBomComponents] = useState<Array<{ component_item_id: string; quantity: string; scrap_percentage: string }>>([
    { component_item_id: '', quantity: '1', scrap_percentage: '0' }
  ])
  const [isSavingBom, setIsSavingBom] = useState(false)

  const fetchItems = async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/inventory/items`, { headers: authHeaders(token) })
      if (res.ok) {
        const data = await res.json()
        const items = Array.isArray(data) ? data : (data.items || [])
        setStockItems(items)
        if (items.length > 0 && !selectedItem) {
          const withBom = items.find((i: any) => i.boms && i.boms.length > 0)
          setSelectedItem(withBom || items[0])
        }
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchItems()
  }, [token])

  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return stockItems
    const q = searchQuery.toLowerCase()
    return stockItems.filter(i => (i.name || '').toLowerCase().includes(q))
  }, [stockItems, searchQuery])

  const handleSaveNewBom = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newBomTargetItemId || !token) {
      toast.error('Please select a finished stock item')
      return
    }
    const validComps = newBomComponents.filter(c => c.component_item_id && parseFloat(c.quantity) > 0)
    if (validComps.length === 0) {
      toast.error('Please add at least one valid raw material component')
      return
    }

    setIsSavingBom(true)
    try {
      const targetItem = stockItems.find(i => String(i.stock_item_id) === String(newBomTargetItemId))
      const existingBoms = (targetItem?.boms || []).map((b: any) => ({
        bom_name: b.bom_name,
        unit_of_manufacture: parseFloat(b.unit_of_manufacture || '1'),
        is_active: b.is_active,
        components: (b.components || []).map((c: any) => ({
          component_item_id: c.component_item_id,
          quantity: parseFloat(c.quantity),
          component_type: c.component_type || 'Component',
          godown_id: c.godown_id || null
        }))
      }))

      const newBomPayload = {
        bom_name: newBomName.trim(),
        unit_of_manufacture: parseFloat(newBomOutputQty || '1'),
        is_active: true,
        components: validComps.map(c => ({
          component_item_id: parseInt(c.component_item_id),
          quantity: parseFloat(c.quantity),
          component_type: 'Component',
          godown_id: null
        }))
      }

      const res = await fetch(`${API_BASE}/inventory/items/${newBomTargetItemId}`, {
        method: 'PUT',
        headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...targetItem,
          boms: [...existingBoms, newBomPayload]
        })
      })

      if (res.ok) {
        toast.success('BOM Recipe saved successfully!')
        setIsNewBomOpen(false)
        fetchItems()
      } else {
        const err = await res.json()
        toast.error(err.detail || 'Failed to save BOM recipe')
      }
    } catch (err: any) {
      toast.error(err.message || 'Error saving BOM')
    } finally {
      setIsSavingBom(false)
    }
  }

  const handleRunMfgJournal = async () => {
    if (!selectedItem || !selectedBomForMfg || !token) return
    const qty = parseFloat(mfgQty)
    if (isNaN(qty) || qty <= 0) {
      toast.error('Please enter a valid production quantity')
      return
    }

    setIsProducing(true)
    try {
      const res = await fetch(`${API_BASE}/inventory/manufacturing-journal`, {
        method: 'POST',
        headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stock_item_id: selectedItem.stock_item_id,
          bom_id: selectedBomForMfg.bom_id,
          quantity_to_produce: qty,
          narration: mfgNarration.trim() || undefined
        })
      })

      if (res.ok) {
        const data = await res.json()
        toast.success(`Manufacturing Stock Journal ${data.voucher_number} created successfully!`)
        setIsMfgJournalOpen(false)
        router.push(`/vouchers/${data.voucher_id}`)
      } else {
        const err = await res.json()
        toast.error(err.detail || 'Failed to execute manufacturing journal')
      }
    } catch (err: any) {
      toast.error(err.message || 'Error running manufacturing journal')
    } finally {
      setIsProducing(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-r from-slate-900 to-indigo-950 text-white shadow-xl">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-white/10 rounded-xl backdrop-blur-sm">
            <Factory className="w-6 h-6 text-indigo-300" />
          </div>
          <div>
            <h1 className="text-lg font-black tracking-tight">Bill of Materials (BOM) & Manufacturing</h1>
            <p className="text-xs text-indigo-200 mt-0.5">
              Define multi-component recipes & auto-execute Manufacturing Stock Journals in Tally Prime 7.0 format.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setNewBomTargetItemId(selectedItem?.stock_item_id ? String(selectedItem.stock_item_id) : '')
              setIsNewBomOpen(true)
            }}
            className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-extrabold rounded-xl shadow flex items-center gap-1.5 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" /> Create BOM Recipe
          </button>
        </div>
      </div>

      {/* Main Grid: Left Items Selector & Right BOM Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Left Column: Stock Items List */}
        <div className="md:col-span-4 space-y-3 bg-card border border-border rounded-2xl p-4 shadow-sm">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search finished goods..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs bg-muted/40 border border-border rounded-xl focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="space-y-1.5 max-h-[600px] overflow-y-auto pr-1">
            {loading ? (
              <div className="py-12 flex justify-center text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin" />
              </div>
            ) : filteredItems.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-8">No stock items found.</p>
            ) : (
              filteredItems.map(item => {
                const isSelected = selectedItem?.stock_item_id === item.stock_item_id
                const hasBom = item.boms && item.boms.length > 0
                return (
                  <div
                    key={item.stock_item_id}
                    onClick={() => setSelectedItem(item)}
                    className={`p-3 rounded-xl border text-xs cursor-pointer transition-all flex items-center justify-between ${
                      isSelected
                        ? 'bg-indigo-500/10 border-indigo-500/40 text-indigo-700 dark:text-indigo-300 font-bold'
                        : 'bg-background hover:bg-muted/50 border-border text-foreground'
                    }`}
                  >
                    <div className="space-y-0.5 truncate pr-2">
                      <p className="truncate">{item.name}</p>
                      <p className="text-[10px] text-muted-foreground font-normal">
                        UOM: {item.unit?.symbol || 'PCS'} • Group: {item.group?.name || 'All'}
                      </p>
                    </div>
                    {hasBom ? (
                      <span className="px-2 py-0.5 text-[9px] font-black rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 shrink-0">
                        {item.boms.length} BOM
                      </span>
                    ) : (
                      <span className="text-[10px] text-muted-foreground shrink-0">No Recipe</span>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Right Column: BOM Recipes & Manufacturing Simulator */}
        <div className="md:col-span-8 space-y-4">
          {selectedItem ? (
            <div className="bg-card border border-border rounded-2xl p-5 shadow-sm space-y-5">
              {/* Item Overview Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-4">
                <div>
                  <h2 className="text-base font-black text-foreground">{selectedItem.name}</h2>
                  <p className="text-xs text-muted-foreground">
                    Standard Cost: ₹{selectedItem.standard_cost_price || '0.00'} • Standard Selling: ₹{selectedItem.standard_selling_price || '0.00'}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-muted-foreground">
                    Active Recipes: <strong>{selectedItem.boms?.length || 0}</strong>
                  </span>
                </div>
              </div>

              {/* BOM Recipes List */}
              {(!selectedItem.boms || selectedItem.boms.length === 0) ? (
                <div className="py-16 text-center space-y-3">
                  <Layers className="w-10 h-10 text-muted-foreground mx-auto opacity-40" />
                  <p className="text-xs text-muted-foreground">No Bill of Materials (BOM) configured for this item.</p>
                  <button
                    type="button"
                    onClick={() => {
                      setNewBomTargetItemId(String(selectedItem.stock_item_id))
                      setIsNewBomOpen(true)
                    }}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl inline-flex items-center gap-1.5 cursor-pointer shadow-sm"
                  >
                    <Plus className="w-3.5 h-3.5" /> Define First BOM Recipe
                  </button>
                </div>
              ) : (
                <div className="space-y-6">
                  {selectedItem.boms.map((bom: any) => {
                    const totalRawCost = (bom.components || []).reduce((acc: number, comp: any) => {
                      const itemPrice = comp.component_item?.standard_cost_price || comp.component_item?.opening_rate || 10
                      return acc + (parseFloat(comp.quantity || '0') * parseFloat(itemPrice))
                    }, 0)

                    return (
                      <div key={bom.bom_id} className="rounded-xl border border-border bg-muted/20 overflow-hidden shadow-xs">
                        {/* BOM Title Bar */}
                        <div className="p-4 border-b border-border flex items-center justify-between bg-muted/40">
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="font-extrabold text-sm text-foreground">{bom.bom_name}</h3>
                              <span className="px-2 py-0.5 text-[9px] font-black rounded-full bg-indigo-500/10 text-indigo-600 border border-indigo-500/20">
                                Output: {bom.unit_of_manufacture} {selectedItem.unit?.symbol || 'PCS'}
                              </span>
                            </div>
                            <p className="text-[11px] text-muted-foreground mt-0.5">
                              Estimated Raw Material Batch Cost: <strong>₹{totalRawCost.toFixed(2)}</strong>
                            </p>
                          </div>

                          <button
                            type="button"
                            onClick={() => {
                              setSelectedBomForMfg(bom)
                              setMfgQty(String(bom.unit_of_manufacture || 1))
                              setIsMfgJournalOpen(true)
                            }}
                            className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-extrabold rounded-xl shadow-xs flex items-center gap-1.5 cursor-pointer transition-all"
                          >
                            <Factory className="w-3.5 h-3.5" /> Run Manufacturing
                          </button>
                        </div>

                        {/* Raw Material Components Table */}
                        <div className="p-3 overflow-x-auto">
                          <table className="w-full text-xs text-left">
                            <thead>
                              <tr className="border-b border-border text-[10px] uppercase font-bold text-muted-foreground">
                                <th className="py-2 px-2">Raw Material Component</th>
                                <th className="py-2 px-2 text-right">Required Qty</th>
                                <th className="py-2 px-2 text-right">Standard Rate</th>
                                <th className="py-2 px-2 text-right">Est. Cost</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border/60 font-medium">
                              {(bom.components || []).map((c: any) => {
                                const rate = c.component_item?.standard_cost_price || c.component_item?.opening_rate || 10
                                const cost = parseFloat(c.quantity || '0') * parseFloat(rate)
                                return (
                                  <tr key={c.id || c.component_item_id} className="hover:bg-muted/30">
                                    <td className="py-2 px-2 font-bold text-foreground">
                                      {c.component_item?.name || `Item #${c.component_item_id}`}
                                    </td>
                                    <td className="py-2 px-2 text-right font-mono">
                                      {c.quantity} {c.component_item?.unit?.symbol || 'PCS'}
                                    </td>
                                    <td className="py-2 px-2 text-right text-muted-foreground">
                                      ₹{parseFloat(rate).toFixed(2)}
                                    </td>
                                    <td className="py-2 px-2 text-right font-bold text-foreground">
                                      ₹{cost.toFixed(2)}
                                    </td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-card border border-border rounded-2xl p-12 text-center text-muted-foreground">
              Select an item on the left to view and configure its Bill of Materials recipe.
            </div>
          )}
        </div>
      </div>

      {/* MODAL 1: Create New BOM Recipe */}
      {isNewBomOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-xl w-full border border-border shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-4 border-b border-border flex items-center justify-between bg-muted/30">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-600">
                  <Factory className="w-4 h-4" />
                </div>
                <h3 className="font-extrabold text-sm text-foreground">Create Bill of Materials (BOM)</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsNewBomOpen(false)}
                className="text-muted-foreground hover:text-foreground text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveNewBom} className="p-4 space-y-4 overflow-y-auto flex-1 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">Finished Stock Item</label>
                  <select
                    value={newBomTargetItemId}
                    onChange={e => setNewBomTargetItemId(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-border rounded-xl bg-background text-foreground font-semibold focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="">Select Finished Item...</option>
                    {stockItems.map(i => (
                      <option key={i.stock_item_id} value={i.stock_item_id}>{i.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-foreground mb-1">BOM Recipe Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Standard Recipe / Model A"
                    value={newBomName}
                    onChange={e => setNewBomName(e.target.value)}
                    className="w-full px-3 py-2 border border-border rounded-xl bg-background text-foreground font-semibold focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-foreground mb-1">Batch Output Quantity</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={newBomOutputQty}
                  onChange={e => setNewBomOutputQty(e.target.value)}
                  className="w-40 px-3 py-2 border border-border rounded-xl bg-background text-foreground font-bold focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Components List */}
              <div className="space-y-2 border-t border-border pt-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-extrabold text-foreground">Raw Material Components</span>
                  <button
                    type="button"
                    onClick={() => {
                      setNewBomComponents([
                        ...newBomComponents,
                        { component_item_id: '', quantity: '1', scrap_percentage: '0' }
                      ])
                    }}
                    className="px-2.5 py-1 bg-muted hover:bg-muted/80 text-foreground font-bold rounded-lg flex items-center gap-1 cursor-pointer"
                  >
                    <Plus className="w-3 h-3" /> Add Component
                  </button>
                </div>

                {newBomComponents.map((comp, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <select
                      value={comp.component_item_id}
                      onChange={e => {
                        const next = [...newBomComponents]
                        next[idx].component_item_id = e.target.value
                        setNewBomComponents(next)
                      }}
                      className="flex-1 px-2.5 py-1.5 border border-border rounded-lg bg-background text-foreground font-semibold"
                    >
                      <option value="">Select Raw Material...</option>
                      {stockItems.map(i => (
                        <option key={i.stock_item_id} value={i.stock_item_id}>{i.name}</option>
                      ))}
                    </select>

                    <input
                      type="number"
                      step="0.01"
                      placeholder="Qty"
                      value={comp.quantity}
                      onChange={e => {
                        const next = [...newBomComponents]
                        next[idx].quantity = e.target.value
                        setNewBomComponents(next)
                      }}
                      className="w-24 px-2 py-1.5 border border-border rounded-lg bg-background text-foreground font-bold text-right"
                    />

                    <button
                      type="button"
                      onClick={() => {
                        setNewBomComponents(newBomComponents.filter((_, i) => i !== idx))
                      }}
                      className="p-1.5 text-muted-foreground hover:text-rose-500 rounded-lg cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>

              <div className="p-3 border-t border-border flex justify-end gap-2 pt-4">
                <button
                  type="button"
                  onClick={() => setIsNewBomOpen(false)}
                  className="px-4 py-2 border border-border rounded-xl font-bold hover:bg-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingBom}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-extrabold rounded-xl shadow flex items-center gap-1.5 disabled:opacity-50"
                >
                  {isSavingBom ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                  Save BOM Recipe
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Execute Manufacturing Stock Journal */}
      {isMfgJournalOpen && selectedBomForMfg && selectedItem && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 rounded-2xl max-w-lg w-full border border-border shadow-2xl overflow-hidden flex flex-col">
            <div className="p-4 border-b border-border flex items-center justify-between bg-emerald-500/10">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-600">
                  <Factory className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-extrabold text-sm text-foreground">Run Manufacturing Journal</h3>
                  <p className="text-[10px] text-muted-foreground">Consumes components & produces {selectedItem.name}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsMfgJournalOpen(false)}
                className="text-muted-foreground hover:text-foreground font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-4 space-y-4 text-xs">
              <div>
                <label className="block text-xs font-bold text-foreground mb-1">Production Output Quantity</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.01"
                    value={mfgQty}
                    onChange={e => setMfgQty(e.target.value)}
                    className="w-36 px-3 py-2 border border-border rounded-xl bg-background text-foreground font-bold text-base focus:ring-1 focus:ring-emerald-500"
                  />
                  <span className="text-xs font-bold text-muted-foreground">{selectedItem.unit?.symbol || 'PCS'}</span>
                </div>
              </div>

              {/* Calculated Component Requirements */}
              <div className="p-3 bg-muted/40 rounded-xl border border-border space-y-2">
                <p className="text-[11px] font-extrabold text-foreground uppercase tracking-wider">
                  Required Raw Material Consumptions:
                </p>
                {(() => {
                  const scale = (parseFloat(mfgQty) || 1) / (parseFloat(selectedBomForMfg.unit_of_manufacture) || 1)
                  return (selectedBomForMfg.components || []).map((c: any) => {
                    const reqQty = parseFloat(c.quantity || '0') * scale
                    return (
                      <div key={c.id || c.component_item_id} className="flex items-center justify-between text-xs">
                        <span>{c.component_item?.name || `Item #${c.component_item_id}`}</span>
                        <span className="font-mono font-bold text-foreground">
                          {reqQty.toFixed(2)} {c.component_item?.unit?.symbol || 'PCS'}
                        </span>
                      </div>
                    )
                  })
                })()}
              </div>

              <div>
                <label className="block text-xs font-bold text-foreground mb-1">Voucher Narration</label>
                <input
                  type="text"
                  placeholder="e.g. Batch #MFG-01 produced on Main Floor"
                  value={mfgNarration}
                  onChange={e => setMfgNarration(e.target.value)}
                  className="w-full px-3 py-2 border border-border rounded-xl bg-background text-foreground font-medium"
                />
              </div>

              <div className="p-3 border-t border-border flex justify-end gap-2 pt-4">
                <button
                  type="button"
                  onClick={() => setIsMfgJournalOpen(false)}
                  className="px-4 py-2 border border-border rounded-xl font-bold hover:bg-muted cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleRunMfgJournal}
                  disabled={isProducing}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold rounded-xl shadow flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  {isProducing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Factory className="w-3.5 h-3.5" />}
                  Execute Manufacturing
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
