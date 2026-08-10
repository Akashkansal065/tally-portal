'use client'

import { useState, useEffect } from 'react'
import { Plus, Edit2, Trash2 } from 'lucide-react'
import CostCentreFormModal from '@/components/CostCentreFormModal'
import { API_BASE, authHeaders } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { ChevronRight, ChevronDown, CheckCircle2, AlertCircle, Info } from 'lucide-react'

export default function CostCentresPage() {
  const { user, token } = useAuth()
  const [centresTree, setCentresTree] = useState<any[]>([])
  const [flatCentres, setFlatCentres] = useState<any[]>([])
  const [categories, setCategories] = useState<any[]>([])
  
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set())

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editData, setEditData] = useState<any>(null)

  useEffect(() => {
    if (user && token) {
      fetchData()
    }
  }, [user, token])

  const fetchData = async () => {
    setLoading(true)
    setError('')
    try {
      const [ccRes, flatRes, catRes] = await Promise.all([
        fetch(`${API_BASE}/masters/cost-centres/tree`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/masters/cost-centres`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/masters/cost-categories`, { headers: authHeaders(token) })
      ])

      if (ccRes.ok && flatRes.ok && catRes.ok) {
        setCentresTree(await ccRes.json())
        setFlatCentres(await flatRes.json())
        setCategories(await catRes.json())
      } else {
        throw new Error('Failed to fetch data')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this Cost Centre?')) return

    try {
      const res = await fetch(`${API_BASE}/masters/cost-centres/${id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      if (res.ok) {
        fetchData()
      } else {
        const data = await res.json()
        alert(data.detail || 'Failed to delete')
      }
    } catch (err) {
      console.error(err)
      alert('An error occurred while deleting')
    }
  }

  const toggleNode = (id: number) => {
    const newExpanded = new Set(expandedNodes)
    if (newExpanded.has(id)) {
      newExpanded.delete(id)
    } else {
      newExpanded.add(id)
    }
    setExpandedNodes(newExpanded)
  }

  const renderTree = (nodes: any[], depth = 0) => {
    return nodes.map((node) => {
      const hasChildren = node.children && node.children.length > 0
      const isExpanded = expandedNodes.has(node.cost_centre_id)

      return (
        <div key={node.cost_centre_id}>
          <div
            className={`group flex items-center justify-between py-2 px-3 hover:bg-muted/50 rounded-md transition-colors ${
              depth === 0 ? 'border-b last:border-0' : ''
            }`}
            style={{ paddingLeft: `${depth * 1.5 + 0.75}rem` }}
          >
            <div className="flex items-center gap-2 flex-1">
              {hasChildren ? (
                <button
                  onClick={() => toggleNode(node.cost_centre_id)}
                  className="p-1 hover:bg-muted rounded-md transition-colors"
                >
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  )}
                </button>
              ) : (
                <div className="w-6" /> // spacer
              )}
              
              <div className="flex flex-col">
                <span className="font-medium text-foreground">{node.name}</span>
                {node.alias && (
                  <span className="text-xs text-muted-foreground italic">Alias: {node.alias}</span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-xs px-2 py-1 bg-secondary rounded-full text-secondary-foreground">
                {node.category_name}
              </span>

              {node.is_active ? (
                <CheckCircle2 className="w-4 h-4 text-green-500" />
              ) : (
                <AlertCircle className="w-4 h-4 text-red-500" />
              )}
              
              <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-primary"
                  onClick={() => {
                    setEditData(node)
                    setIsModalOpen(true)
                  }}
                >
                  <Edit2 className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-destructive"
                  onClick={() => handleDelete(node.cost_centre_id)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
          {hasChildren && isExpanded && (
            <div className="animate-in slide-in-from-top-1 fade-in duration-200">
              {renderTree(node.children, depth + 1)}
            </div>
          )}
        </div>
      )
    })
  }

  return (
    <div className="flex flex-col h-full bg-background text-foreground">
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="max-w-6xl mx-auto space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div className="max-w-2xl">
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-foreground">List of Cost Centres</h1>
              <p className="text-sm text-muted-foreground mt-1 mb-3">
                Manage your cost and profit centers in a hierarchical tree view.
              </p>
              <div className="bg-emerald-50/50 border border-emerald-100 rounded-lg p-3 text-sm text-emerald-800 flex gap-3">
                <Info className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold mb-1">What is a Cost Centre?</p>
                  <p>
                    Cost Centres are the sub-units of a Cost Category. They represent the actual entities you want to track income or expenses against (e.g., specific Marketing Campaigns, Employees, or Vehicles). You can nest them hierarchically to create detailed parent-child relationships for granular profit analysis.
                  </p>
                </div>
              </div>
            </div>
            <Button
              onClick={() => {
                setEditData(null)
                setIsModalOpen(true)
              }}
              className="bg-[#008f68] hover:bg-[#007656] text-white whitespace-nowrap"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create
            </Button>
          </div>

          {error && (
            <div className="p-4 bg-destructive/10 text-destructive rounded-lg border border-destructive/20 text-sm font-medium">
              {error}
            </div>
          )}

          <div className="bg-card border shadow-sm rounded-xl overflow-hidden">
            {loading ? (
              <div className="p-8 text-center text-muted-foreground animate-pulse">Loading Cost Centres...</div>
            ) : centresTree.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">No Cost Centres found.</div>
            ) : (
              <div className="divide-y divide-border">
                {renderTree(centresTree)}
              </div>
            )}
          </div>
        </div>
      </div>

      {isModalOpen && (
        <CostCentreFormModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSuccess={fetchData}
          initialData={editData}
          categories={categories}
          centres={flatCentres}
        />
      )}
    </div>
  )
}
