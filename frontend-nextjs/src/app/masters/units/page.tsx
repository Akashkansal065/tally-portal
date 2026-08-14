'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'
import { Plus, Edit2, Trash2, X, Info } from 'lucide-react'

type UOM = {
  unit_id: number
  name: string
  symbol: string
  original_name: string | null
  decimal_places: number
  is_simple_unit: boolean
  base_unit_id: number | null
  additional_unit_id: number | null
  conversion_factor: number | null
}

export default function UnitsOfMeasurePage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  const [uoms, setUoms] = useState<UOM[]>([])
  const [loading, setLoading] = useState(true)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  
  // Form State
  const [unitId, setUnitId] = useState<number | null>(null)
  const [isSimple, setIsSimple] = useState(true)
  const [symbol, setSymbol] = useState('')
  const [originalName, setOriginalName] = useState('')
  const [decimalPlaces, setDecimalPlaces] = useState<number>(2)
  const [baseUnitId, setBaseUnitId] = useState<number | ''>('')
  const [additionalUnitId, setAdditionalUnitId] = useState<number | ''>('')
  const [conversionFactor, setConversionFactor] = useState<string>('')

  const fetchUoms = async () => {
    try {
      const res = await fetch(`${API_BASE}/inventory/uoms`, { headers: authHeaders(token) })
      const data = await res.json()
      setUoms(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.isAdmin) { router.replace('/'); return }
    fetchUoms()
  }, [user, permissions, router])

  const openCreateModal = () => {
    setIsEditing(false)
    setUnitId(null)
    setIsSimple(true)
    setSymbol('')
    setOriginalName('')
    setDecimalPlaces(2)
    setBaseUnitId('')
    setAdditionalUnitId('')
    setConversionFactor('')
    setIsModalOpen(true)
  }

  const openEditModal = (uom: UOM) => {
    setIsEditing(true)
    setUnitId(uom.unit_id)
    setIsSimple(uom.is_simple_unit)
    setSymbol(uom.symbol || '')
    setOriginalName(uom.original_name || '')
    setDecimalPlaces(uom.decimal_places || 2)
    setBaseUnitId(uom.base_unit_id || '')
    setAdditionalUnitId(uom.additional_unit_id || '')
    setConversionFactor(uom.conversion_factor ? uom.conversion_factor.toString() : '')
    setIsModalOpen(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this UOM?')) return
    try {
      await fetch(`${API_BASE}/inventory/uoms/${id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      fetchUoms()
    } catch (e) {
      console.error(e)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    
    const payload: any = {
      is_simple_unit: isSimple,
    }

    if (isSimple) {
      if (!symbol) return alert("Symbol is required")
      payload.symbol = symbol
      payload.original_name = originalName
      payload.decimal_places = decimalPlaces
    } else {
      if (!baseUnitId || !additionalUnitId || !conversionFactor) return alert("Base Unit, Additional Unit, and Conversion Factor are required")
      if (baseUnitId === additionalUnitId) return alert("Base Unit and Additional Unit cannot be the same")
      payload.base_unit_id = Number(baseUnitId)
      payload.additional_unit_id = Number(additionalUnitId)
      payload.conversion_factor = Number(conversionFactor)
      payload.decimal_places = 0
    }

    const url = isEditing ? `${API_BASE}/inventory/uoms/${unitId}` : `${API_BASE}/inventory/uoms`
    const method = isEditing ? 'PUT' : 'POST'

    try {
      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const d = await res.json()
        alert(d.detail || "Error saving UOM")
        return
      }
      setIsModalOpen(false)
      fetchUoms()
    } catch (e) {
      console.error(e)
    }
  }

  const simpleUoms = uoms.filter(u => u.is_simple_unit)
  
  // Live Preview
  let compoundPreview = ""
  if (!isSimple && baseUnitId && additionalUnitId && conversionFactor) {
    const base = simpleUoms.find(u => u.unit_id === Number(baseUnitId))?.symbol || 'Base'
    const add = simpleUoms.find(u => u.unit_id === Number(additionalUnitId))?.symbol || 'Add'
    compoundPreview = `1 ${add} = ${conversionFactor} ${base}`
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Units of Measure</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage simple and compound units for inventory tracking.</p>
        </div>
        <button 
          onClick={openCreateModal}
          className="bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" /> Create UOM
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center p-8"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>
      ) : (
        <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="bg-muted/50 border-b border-border">
                <th className="px-4 py-3 font-semibold text-muted-foreground">Type</th>
                <th className="px-4 py-3 font-semibold text-muted-foreground">Symbol / Name</th>
                <th className="px-4 py-3 font-semibold text-muted-foreground">Formal Name</th>
                <th className="px-4 py-3 font-semibold text-muted-foreground">Conversion</th>
                <th className="px-4 py-3 font-semibold text-muted-foreground text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {uoms.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">No units of measure found.</td>
                </tr>
              ) : (
                uoms.map(uom => (
                  <tr key={uom.unit_id} className="border-b border-border last:border-0 hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-3 align-middle">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${uom.is_simple_unit ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                        {uom.is_simple_unit ? 'Simple' : 'Compound'}
                      </span>
                    </td>
                    <td className="px-4 py-3 align-middle font-semibold">{uom.symbol || uom.name}</td>
                    <td className="px-4 py-3 align-middle text-muted-foreground">{uom.original_name || '—'}</td>
                    <td className="px-4 py-3 align-middle text-muted-foreground">
                      {!uom.is_simple_unit && uom.conversion_factor ? (
                        <>1 {uoms.find(u => u.unit_id === uom.additional_unit_id)?.symbol} = {uom.conversion_factor} {uoms.find(u => u.unit_id === uom.base_unit_id)?.symbol}</>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 align-middle text-right space-x-2">
                      <button onClick={() => openEditModal(uom)} className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"><Edit2 className="h-4 w-4" /></button>
                      <button onClick={() => handleDelete(uom.unit_id)} className="p-1.5 text-muted-foreground hover:text-destructive transition-colors"><Trash2 className="h-4 w-4" /></button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-in fade-in duration-200">
          <div className="bg-card w-full max-w-lg rounded-2xl shadow-xl flex flex-col border border-border">
            <div className="px-6 py-4 border-b border-border flex items-center justify-between">
              <h2 className="text-xl font-bold">{isEditing ? 'Edit Unit of Measure' : 'Create Unit of Measure'}</h2>
              <button onClick={() => setIsModalOpen(false)} className="p-2 hover:bg-muted rounded-full transition-colors"><X className="h-5 w-5" /></button>
            </div>

            <form onSubmit={handleSave} className="p-6 space-y-5">
              
              {/* Toggle Simple/Compound */}
              <div className="flex gap-4 p-1 bg-muted rounded-lg">
                <button type="button" onClick={() => setIsSimple(true)} className={`flex-1 py-2 text-sm font-semibold rounded-md transition-all ${isSimple ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'}`}>Simple Unit</button>
                <button type="button" onClick={() => setIsSimple(false)} className={`flex-1 py-2 text-sm font-semibold rounded-md transition-all ${!isSimple ? 'bg-background shadow text-foreground' : 'text-muted-foreground hover:text-foreground'}`}>Compound Unit</button>
              </div>

              {isSimple ? (
                <>
                  <div>
                    <label className="text-sm font-semibold mb-1.5 block">Symbol <span className="text-destructive">*</span></label>
                    <input type="text" value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="e.g. Pcs, Kgs, Box" className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" required />
                  </div>
                  <div>
                    <label className="text-sm font-semibold mb-1.5 block">Formal Name</label>
                    <input type="text" value={originalName} onChange={e => setOriginalName(e.target.value)} placeholder="e.g. Pieces, Kilograms" className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
                  </div>
                  <div>
                    <label className="text-sm font-semibold mb-1.5 block">Number of Decimal Places</label>
                    <input type="number" min="0" max="4" value={decimalPlaces} onChange={e => setDecimalPlaces(Number(e.target.value))} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
                  </div>
                </>
              ) : (
                <>
                  <div className="bg-blue-50/50 p-3 rounded-lg flex gap-2 items-start text-sm text-blue-800 mb-2 border border-blue-100">
                    <Info className="h-4 w-4 mt-0.5 shrink-0" />
                    <p>A compound unit relates two simple units. Ensure you have created the simple units first (e.g. "Box" and "Pcs").</p>
                  </div>
                  
                  <div className="grid grid-cols-12 gap-3 items-end">
                    <div className="col-span-5">
                      <label className="text-xs font-semibold uppercase text-muted-foreground mb-1 block">First Unit (Larger)</label>
                      <select value={additionalUnitId} onChange={e => setAdditionalUnitId(e.target.value ? Number(e.target.value) : '')} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" required>
                        <option value="" disabled>Select...</option>
                        {simpleUoms.map(u => <option key={u.unit_id} value={u.unit_id}>{u.symbol}</option>)}
                      </select>
                    </div>
                    <div className="col-span-2 text-center pb-2 font-medium text-muted-foreground">of</div>
                    <div className="col-span-5">
                      <label className="text-xs font-semibold uppercase text-muted-foreground mb-1 block">Conversion Factor</label>
                      <input type="number" min="0.0001" step="any" value={conversionFactor} onChange={e => setConversionFactor(e.target.value)} placeholder="e.g. 10" className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" required />
                    </div>
                  </div>
                  
                  <div>
                    <label className="text-xs font-semibold uppercase text-muted-foreground mb-1 block">Second Unit (Base/Smaller)</label>
                    <select value={baseUnitId} onChange={e => setBaseUnitId(e.target.value ? Number(e.target.value) : '')} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" required>
                      <option value="" disabled>Select...</option>
                      {simpleUoms.map(u => <option key={u.unit_id} value={u.unit_id}>{u.symbol}</option>)}
                    </select>
                  </div>

                  {compoundPreview && (
                    <div className="mt-4 p-4 bg-muted/30 rounded-lg border border-border flex flex-col items-center justify-center">
                      <span className="text-xs font-semibold text-muted-foreground uppercase mb-1">Generated Name</span>
                      <span className="text-lg font-bold text-primary">{compoundPreview}</span>
                    </div>
                  )}
                </>
              )}

              <div className="flex justify-end gap-3 pt-4 border-t border-border mt-6">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 rounded-lg font-medium text-sm hover:bg-muted transition-colors">Cancel</button>
                <button type="submit" className="bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors">Save Unit</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
