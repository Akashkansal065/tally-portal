'use client'

import React, { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE, authHeaders } from '@/lib/utils'
import { Plus, Edit2, Trash2, X, ChevronRight, ChevronDown, Folder, FolderOpen } from 'lucide-react'

type StockCategory = {
  stock_category_id: number
  name: string
  parent_id: number | null
  is_active: boolean
}

type TreeNode = StockCategory & {
  children: TreeNode[]
}

export default function StockCategoriesPage() {
  const { user, token, permissions } = useAuth()
  const router = useRouter()
  
  const [categories, setCategories] = useState<StockCategory[]>([])
  const [loading, setLoading] = useState(true)

  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set())

  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [parentId, setParentId] = useState<number | ''>('')
  const [isActive, setIsActive] = useState(true)

  const fetchCategories = async () => {
    try {
      const res = await fetch(`${API_BASE}/inventory/categories`, { headers: authHeaders(token) })
      const data = await res.json()
      setCategories(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user) { router.replace('/login'); return }
    if (!permissions.isAdmin) { router.replace('/'); return }
    fetchCategories()
  }, [user, permissions, router])

  const tree = useMemo(() => {
    const map = new Map<number, TreeNode>()
    const roots: TreeNode[] = []

    categories.forEach(c => {
      map.set(c.stock_category_id, { ...c, children: [] })
    })

    categories.forEach(c => {
      if (c.parent_id && map.has(c.parent_id)) {
        map.get(c.parent_id)!.children.push(map.get(c.stock_category_id)!)
      } else {
        roots.push(map.get(c.stock_category_id)!)
      }
    })

    return roots
  }, [categories])

  const toggleExpand = (id: number) => {
    const next = new Set(expandedNodes)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setExpandedNodes(next)
  }

  const openCreate = (prefillParentId?: number) => {
    setIsEditing(false)
    setCategoryId(null)
    setName('')
    setParentId(prefillParentId || '')
    setIsActive(true)
    setIsPanelOpen(true)
  }

  const openEdit = (c: StockCategory) => {
    setIsEditing(true)
    setCategoryId(c.stock_category_id)
    setName(c.name)
    setParentId(c.parent_id || '')
    setIsActive(c.is_active)
    setIsPanelOpen(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this category?')) return
    try {
      await fetch(`${API_BASE}/inventory/categories/${id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      fetchCategories()
      if (categoryId === id) setIsPanelOpen(false)
    } catch (e) {
      console.error(e)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name) return alert("Name is required")

    const payload = {
      name,
      parent_id: parentId === '' ? null : Number(parentId),
      is_active: isActive
    }

    const url = isEditing ? `${API_BASE}/inventory/categories/${categoryId}` : `${API_BASE}/inventory/categories`
    const method = isEditing ? 'PUT' : 'POST'

    try {
      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })
      if (!res.ok) {
        const d = await res.json()
        alert(d.detail || "Error saving category")
        return
      }
      setIsPanelOpen(false)
      fetchCategories()
    } catch (e) {
      console.error(e)
    }
  }

  const renderTree = (nodes: TreeNode[], depth = 0) => {
    return nodes.map(node => {
      const isExpanded = expandedNodes.has(node.stock_category_id)
      const hasChildren = node.children.length > 0

      return (
        <div key={node.stock_category_id}>
          <div 
            className={`flex items-center group hover:bg-muted/30 p-2 rounded-lg transition-colors border-l-2 ${categoryId === node.stock_category_id ? 'border-primary bg-primary/5' : 'border-transparent'}`}
            style={{ paddingLeft: `${depth * 1.5 + 0.5}rem` }}
          >
            <div className="flex items-center gap-2 flex-1 cursor-pointer" onClick={() => hasChildren ? toggleExpand(node.stock_category_id) : openEdit(node)}>
              <button 
                onClick={(e) => { e.stopPropagation(); toggleExpand(node.stock_category_id) }}
                className={`p-1 rounded hover:bg-muted text-muted-foreground ${!hasChildren && 'invisible'}`}
              >
                {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              
              {isExpanded ? <FolderOpen className="h-4 w-4 text-primary" /> : <Folder className="h-4 w-4 text-muted-foreground" />}
              
              <span className={`text-sm font-medium ${!node.is_active && 'line-through text-muted-foreground'}`}>
                {node.name}
              </span>
            </div>

            <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
              <button onClick={() => openCreate(node.stock_category_id)} className="p-1.5 text-muted-foreground hover:text-primary transition-colors"><Plus className="h-4 w-4" /></button>
              <button onClick={() => openEdit(node)} className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"><Edit2 className="h-4 w-4" /></button>
              <button onClick={() => handleDelete(node.stock_category_id)} className="p-1.5 text-muted-foreground hover:text-destructive transition-colors"><Trash2 className="h-4 w-4" /></button>
            </div>
          </div>

          {isExpanded && hasChildren && (
            <div className="mt-1">
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
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Stock Categories</h1>
            <p className="text-sm text-muted-foreground mt-1">Parallel classification for your inventory items.</p>
          </div>
          <button 
            onClick={() => openCreate()}
            className="bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium text-sm flex items-center gap-2 hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" /> Create Category
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center p-8"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" /></div>
        ) : (
          <div className="bg-card border border-border rounded-xl shadow-sm p-4 min-h-[500px]">
            {categories.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground flex flex-col items-center">
                <Folder className="h-12 w-12 text-muted mb-4" />
                <p>No stock categories found.</p>
                <button onClick={() => openCreate()} className="text-primary hover:underline mt-2">Create your first category</button>
              </div>
            ) : (
              <div className="space-y-1">
                {renderTree(tree)}
              </div>
            )}
          </div>
        )}
      </div>

      <div className={`fixed top-[64px] right-0 bottom-0 w-[400px] bg-card border-l border-border shadow-2xl transition-transform duration-300 transform flex flex-col ${isPanelOpen ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <h2 className="text-lg font-bold">{isEditing ? 'Edit Category' : 'Create Category'}</h2>
          <button onClick={() => setIsPanelOpen(false)} className="p-2 hover:bg-muted rounded-full transition-colors"><X className="h-5 w-5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <form id="category-form" onSubmit={handleSave} className="space-y-5">
            <div>
              <label className="text-sm font-semibold mb-1.5 block">Category Name <span className="text-destructive">*</span></label>
              <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Branded, Unbranded" className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none" required />
            </div>

            <div>
              <label className="text-sm font-semibold mb-1.5 block">Under Category</label>
              <select value={parentId} onChange={e => setParentId(e.target.value)} className="w-full bg-background border border-input rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none">
                <option value="">Primary (Root)</option>
                {categories.filter(c => c.stock_category_id !== categoryId).map(c => (
                  <option key={c.stock_category_id} value={c.stock_category_id}>{c.name}</option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <input 
                type="checkbox" 
                id="cat_is_active" 
                checked={isActive} 
                onChange={e => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <label htmlFor="cat_is_active" className="text-sm font-medium">Category is Active</label>
            </div>
          </form>
        </div>

        <div className="p-4 border-t border-border bg-muted/10 flex justify-end gap-3">
          <button type="button" onClick={() => setIsPanelOpen(false)} className="px-4 py-2 rounded-lg font-medium text-sm hover:bg-muted transition-colors">Cancel</button>
          <button type="submit" form="category-form" className="bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium text-sm hover:bg-primary/90 transition-colors">Save Category</button>
        </div>
      </div>
    </div>
  )
}
