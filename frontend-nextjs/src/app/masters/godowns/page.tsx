'use client'

import { confirmInCompany } from '@/lib/current-company'
import React, { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders, cn } from '@/lib/utils'
import { Plus, Edit2, Trash2, X, ChevronRight, ChevronDown, MapPin, Building2 } from 'lucide-react'

type Godown = {
  godown_id: number
  name: string
  address: string | null
  parent_id: number | null
  is_active: boolean
  contact_person: string | null
  phone: string | null
}

type TreeNode = Godown & {
  children: TreeNode[]
}

export default function GodownsPage() {
  const { user, token, can } = useAuth()
  const router = useRouter()
  
  const [godowns, setGodowns] = useState<Godown[]>([])
  const [loading, setLoading] = useState(true)

  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set())

  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  
  const [godownId, setGodownId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [parentId, setParentId] = useState<number | ''>('')
  const [isActive, setIsActive] = useState(true)
  const [contactPerson, setContactPerson] = useState('')
  const [phone, setPhone] = useState('')

  const fetchGodowns = async () => {
    try {
      const res = await fetch(`${API_BASE}/inventory/godowns`, { headers: authHeaders(token) })
      const data = await res.json()
      setGodowns(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!can('godowns', 'read')) { router.replace('/'); return }
    fetchGodowns()
  }, [user, can, router])

  const tree = useMemo(() => {
    const map = new Map<number, TreeNode>()
    const roots: TreeNode[] = []

    godowns.forEach(g => {
      map.set(g.godown_id, { ...g, children: [] })
    })

    godowns.forEach(g => {
      if (g.parent_id && map.has(g.parent_id)) {
        map.get(g.parent_id)!.children.push(map.get(g.godown_id)!)
      } else {
        roots.push(map.get(g.godown_id)!)
      }
    })

    return roots
  }, [godowns])

  const toggleExpand = (id: number) => {
    const next = new Set(expandedNodes)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setExpandedNodes(next)
  }

  const openCreate = (prefillParentId?: number) => {
    setIsEditing(false)
    setGodownId(null)
    setName('')
    setAddress('')
    setParentId(prefillParentId || '')
    setIsActive(true)
    setContactPerson('')
    setPhone('')
    setIsPanelOpen(true)
  }

  const openEdit = (g: Godown) => {
    setIsEditing(true)
    setGodownId(g.godown_id)
    setName(g.name)
    setAddress(g.address || '')
    setParentId(g.parent_id || '')
    setIsActive(g.is_active)
    setContactPerson(g.contact_person || '')
    setPhone(g.phone || '')
    setIsPanelOpen(true)
  }

  const closePanel = () => {
    setIsPanelOpen(false)
    setGodownId(null)
    setIsEditing(false)
  }

  const handleDelete = async (id: number) => {
    if (!confirmInCompany('Are you sure you want to delete this godown? Inventory could be affected.')) return
    try {
      await fetch(`${API_BASE}/inventory/godowns/${id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      fetchGodowns()
      if (godownId === id) closePanel()
    } catch (e) {
      console.error(e)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name) return alert("Name is required")

    const payload = {
      name,
      address,
      parent_id: parentId === '' ? null : Number(parentId),
      is_active: isActive,
      contact_person: contactPerson,
      phone
    }

    const url = isEditing ? `${API_BASE}/inventory/godowns/${godownId}` : `${API_BASE}/inventory/godowns`
    const method = isEditing ? 'PUT' : 'POST'

    try {
      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const d = await res.json()
        alert(d.detail || "Error saving godown")
        return
      }
      closePanel()
      fetchGodowns()
    } catch (e) {
      console.error(e)
    }
  }

  const renderTree = (nodes: TreeNode[], depth = 0) => {
    return nodes.map(node => {
      const isExpanded = expandedNodes.has(node.godown_id)
      const hasChildren = node.children.length > 0
      const isSelected = isPanelOpen && godownId === node.godown_id

      return (
        <div key={node.godown_id} className="relative">
          <div 
            className={cn(
              "flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl transition-all cursor-pointer group select-none",
              isSelected
                ? "bg-primary/10 text-primary border border-primary/30 shadow-xs"
                : "hover:bg-muted/60 text-foreground border border-transparent"
            )}
            onClick={() => {
              if (hasChildren) toggleExpand(node.godown_id)
              else openEdit(node)
            }}
          >
            <div className="flex items-center gap-2.5 min-w-0 flex-1">
              {/* Selected indicator pill */}
              {isSelected && (
                <span className="w-1.5 h-4 rounded-full bg-primary shrink-0 -ml-1" />
              )}

              {/* Chevron or spacer */}
              <div className="w-5 h-5 flex items-center justify-center shrink-0">
                {hasChildren ? (
                  <button 
                    type="button"
                    onClick={(e) => { 
                      e.stopPropagation()
                      toggleExpand(node.godown_id) 
                    }}
                    className="w-5 h-5 flex items-center justify-center rounded-md hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-all cursor-pointer"
                  >
                    <ChevronRight className={cn("h-3.5 w-3.5 transition-transform duration-200", isExpanded && "rotate-90")} />
                  </button>
                ) : (
                  <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/25" />
                )}
              </div>
              
              <Building2 className={cn("h-4 w-4 shrink-0", isSelected ? "text-primary" : isExpanded ? "text-primary/80" : "text-muted-foreground")} />
              
              <div className="flex flex-col min-w-0">
                <div className="flex items-center gap-2">
                  <span className={cn(
                    "text-sm tracking-tight truncate",
                    !node.is_active && "text-muted-foreground",
                    isSelected ? "font-bold text-foreground" : "font-semibold"
                  )}>
                    {node.name}
                  </span>

                  {!node.is_active && (
                    <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border shrink-0">
                      Inactive
                    </span>
                  )}
                </div>

                {node.address && depth === 0 && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5 truncate">
                    <MapPin className="h-3 w-3 shrink-0" /> {node.address}
                  </span>
                )}
              </div>

              {isSelected && (
                <span className="text-[9px] font-extrabold uppercase tracking-wider px-1.5 py-0.5 rounded bg-primary/20 text-primary border border-primary/30 shrink-0 ml-auto mr-1">
                  Editing
                </span>
              )}
            </div>

            <div 
              className={cn(
                "flex items-center gap-1 shrink-0 transition-opacity",
                isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100 focus-within:opacity-100"
              )}
              onClick={(e) => e.stopPropagation()}
            >
              {can('godowns', 'create') && (
                <button 
                  type="button" 
                  onClick={() => openCreate(node.godown_id)} 
                  title="Add child godown"
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors cursor-pointer"
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              )}
              {can('godowns', 'update') && (
                <button 
                  type="button" 
                  onClick={() => openEdit(node)} 
                  title="Edit godown"
                  className={cn(
                    "p-1.5 rounded-lg transition-colors cursor-pointer",
                    isSelected 
                      ? "text-primary bg-primary/15 font-bold" 
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  )}
                >
                  <Edit2 className="h-3.5 w-3.5" />
                </button>
              )}
              {can('godowns', 'delete') && (
                <button 
                  type="button" 
                  onClick={() => handleDelete(node.godown_id)} 
                  title="Delete godown"
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {isExpanded && hasChildren && (
            <div className="ml-5 pl-3 border-l-2 border-border/50 space-y-1 mt-1">
              {renderTree(node.children, depth + 1)}
            </div>
          )}
        </div>
      )
    })
  }

  return (
    <div className="h-[calc(100vh-64px)] flex overflow-hidden">
      <div className={`flex-1 flex flex-col p-6 overflow-y-auto transition-all ${isPanelOpen ? 'mr-[400px]' : ''}`}>
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Godowns / Locations</h1>
            <p className="text-sm text-muted-foreground mt-1">Manage warehouses, stores, and hierarchical storage locations.</p>
          </div>
          {can('godowns', 'create') && (
            <button 
              onClick={() => openCreate()}
              className="bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-4 w-4" /> Create Godown
            </button>
          )}
        </div>

        {loading ? (
          <div className="flex justify-center p-8"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>
        ) : (
          <div className="bg-card border border-border rounded-xl shadow-sm p-4 min-h-[500px]">
            {godowns.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground flex flex-col items-center">
                <Building2 className="h-12 w-12 text-muted mb-4" />
                <p>No godowns found.</p>
                {can('godowns', 'create') && (
                  <button onClick={() => openCreate()} className="text-primary hover:underline mt-2">Create your first godown</button>
                )}
              </div>
            ) : (
              <div className="space-y-1">
                {renderTree(tree)}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Mobile backdrop overlay */}
      {isPanelOpen && (
        <div 
          className="fixed inset-0 bg-black/40 backdrop-blur-xs z-30 lg:hidden"
          onClick={closePanel}
        />
      )}

      <div className={`fixed top-[64px] right-0 bottom-0 w-[400px] max-w-[90vw] bg-card border-l border-border shadow-2xl transition-transform duration-300 transform flex flex-col z-40 ${isPanelOpen ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <h2 className="text-lg font-bold">{isEditing ? 'Edit Godown' : 'Create Godown'}</h2>
          <button type="button" onClick={closePanel} className="p-2 hover:bg-muted rounded-full transition-colors"><X className="h-5 w-5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <form id="godown-form" onSubmit={handleSave} className="space-y-5">
            <div>
              <label className="text-sm font-semibold mb-1.5 block">Godown Name <span className="text-destructive">*</span></label>
              <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Main Warehouse, Rack 1" className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" required />
            </div>

            <div>
              <label className="text-sm font-semibold mb-1.5 block">Under Godown (Parent)</label>
              <select value={parentId} onChange={e => setParentId(e.target.value ? Number(e.target.value) : '')} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none">
                <option value="">Primary (Top Level / Root)</option>
                {godowns.filter(g => g.godown_id !== godownId).map(g => (
                  <option key={g.godown_id} value={g.godown_id}>{g.name}</option>
                ))}
              </select>
              <p className="text-[11px] text-muted-foreground mt-1">
                In Tally, <span className="font-semibold text-foreground">Primary</span> is the top level (no parent godown).
              </p>
            </div>

            <div>
              <label className="text-sm font-semibold mb-1.5 block">Address</label>
              <textarea 
                value={address} 
                onChange={e => setAddress(e.target.value)} 
                rows={3} 
                placeholder="Physical address of the location"
                className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none resize-none" 
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-semibold mb-1.5 block">Contact Person</label>
                <input type="text" value={contactPerson} onChange={e => setContactPerson(e.target.value)} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
              </div>
              <div>
                <label className="text-sm font-semibold mb-1.5 block">Phone Number</label>
                <input type="text" value={phone} onChange={e => setPhone(e.target.value)} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" />
              </div>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <input 
                type="checkbox" 
                id="gdn_is_active" 
                checked={isActive} 
                onChange={e => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <label htmlFor="gdn_is_active" className="text-sm font-medium">Godown is Active</label>
            </div>
          </form>
        </div>

        <div className="p-4 border-t border-border bg-muted/10 flex justify-end gap-3">
          <button type="button" onClick={closePanel} className="px-4 py-2 rounded-lg font-medium text-sm hover:bg-muted transition-colors">Cancel</button>
          <button type="submit" form="godown-form" className="bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors">Save Godown</button>
        </div>
      </div>
    </div>
  )
}
