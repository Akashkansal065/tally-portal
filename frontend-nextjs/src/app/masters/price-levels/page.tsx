'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'
import { Plus, Edit2, Trash2, X, Tag } from 'lucide-react'

type PriceLevel = {
  price_level_id: number
  name: string
  is_active: boolean
}

export default function PriceLevelsPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  
  const [levels, setLevels] = useState<PriceLevel[]>([])
  const [loading, setLoading] = useState(true)

  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [levelId, setLevelId] = useState<number | null>(null)
  
  const [name, setName] = useState('')
  const [isActive, setIsActive] = useState(true)

  const fetchLevels = async () => {
    try {
      const res = await fetch(`${API_BASE}/inventory/price-levels`, { headers: authHeaders(token) })
      const data = await res.json()
      setLevels(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.isAdmin) { router.replace('/'); return }
    fetchLevels()
  }, [user, permissions, router])

  const openCreate = () => {
    setIsEditing(false)
    setLevelId(null)
    setName('')
    setIsActive(true)
    setIsPanelOpen(true)
  }

  const openEdit = (l: PriceLevel) => {
    setIsEditing(true)
    setLevelId(l.price_level_id)
    setName(l.name)
    setIsActive(l.is_active)
    setIsPanelOpen(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this price level? Any associated rates will be lost.')) return
    try {
      await fetch(`${API_BASE}/inventory/price-levels/${id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      fetchLevels()
      if (levelId === id) setIsPanelOpen(false)
    } catch (e) {
      console.error(e)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name) return alert("Name is required")

    const payload = { name, is_active: isActive }

    const url = isEditing ? `${API_BASE}/inventory/price-levels/${levelId}` : `${API_BASE}/inventory/price-levels`
    const method = isEditing ? 'PUT' : 'POST'

    try {
      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const d = await res.json()
        alert(d.detail || "Error saving price level")
        return
      }
      setIsPanelOpen(false)
      fetchLevels()
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="h-[calc(100vh-64px)] flex overflow-hidden">
      <div className={`flex-1 flex flex-col p-6 overflow-y-auto transition-all ${isPanelOpen ? 'mr-[400px]' : ''}`}>
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Price Levels</h1>
            <p className="text-sm text-muted-foreground mt-1">Manage tiers for pricing (e.g., Wholesale, Retail, Corporate).</p>
          </div>
          <button 
            onClick={openCreate}
            className="bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" /> Create Price Level
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center p-8"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>
        ) : (
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden min-h-[500px]">
            {levels.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground flex flex-col items-center">
                <Tag className="h-12 w-12 text-muted mb-4" />
                <p>No price levels found.</p>
                <button onClick={openCreate} className="text-primary hover:underline mt-2">Create your first price level</button>
              </div>
            ) : (
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="bg-muted/50 border-b border-border">
                    <th className="px-4 py-3 font-semibold text-muted-foreground">Price Level Name</th>
                    <th className="px-4 py-3 font-semibold text-muted-foreground w-32">Status</th>
                    <th className="px-4 py-3 font-semibold text-muted-foreground text-right w-32">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {levels.map(l => (
                    <tr key={l.price_level_id} className="border-b border-border last:border-0 hover:bg-muted/20 transition-colors">
                      <td className={`px-4 py-3 font-medium ${!l.is_active && 'text-muted-foreground line-through'}`}>{l.name}</td>
                      <td className="px-4 py-3">
                        {l.is_active ? 
                          <span className="bg-green-100 text-green-700 px-2.5 py-0.5 rounded-full text-xs font-semibold">Active</span> : 
                          <span className="bg-red-100 text-red-700 px-2.5 py-0.5 rounded-full text-xs font-semibold">Inactive</span>
                        }
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        <button onClick={() => openEdit(l)} className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"><Edit2 className="h-4 w-4" /></button>
                        <button onClick={() => handleDelete(l.price_level_id)} className="p-1.5 text-muted-foreground hover:text-destructive transition-colors"><Trash2 className="h-4 w-4" /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      <div className={`fixed top-[64px] right-0 bottom-0 w-[400px] bg-card border-l border-border shadow-2xl transition-transform duration-300 transform flex flex-col ${isPanelOpen ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <h2 className="text-lg font-bold">{isEditing ? 'Edit Price Level' : 'Create Price Level'}</h2>
          <button onClick={() => setIsPanelOpen(false)} className="p-2 hover:bg-muted rounded-full transition-colors"><X className="h-5 w-5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <form id="price-level-form" onSubmit={handleSave} className="space-y-5">
            <div>
              <label className="text-sm font-semibold mb-1.5 block">Price Level Name <span className="text-destructive">*</span></label>
              <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Wholesale, Export" className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" required />
            </div>

            <div className="flex items-center gap-3 pt-2">
              <input 
                type="checkbox" 
                id="pl_active" 
                checked={isActive} 
                onChange={e => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <label htmlFor="pl_active" className="text-sm font-medium">Active</label>
            </div>
          </form>
        </div>

        <div className="p-4 border-t border-border bg-muted/10 flex justify-end gap-3">
          <button type="button" onClick={() => setIsPanelOpen(false)} className="px-4 py-2 rounded-lg font-medium text-sm hover:bg-muted transition-colors">Cancel</button>
          <button type="submit" form="price-level-form" className="bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors">Save Level</button>
        </div>
      </div>
    </div>
  )
}
