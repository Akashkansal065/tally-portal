'use client'

import { useState, useEffect } from 'react'
import { Plus, Edit2, Trash2, Info } from 'lucide-react'
import CostCategoryFormModal from '@/components/CostCategoryFormModal'

export default function CostCategoriesPage() {
  const [categories, setCategories] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingCategory, setEditingCategory] = useState<any>(null)

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

  const authHeaders = () => {
    const token = localStorage.getItem('mytally_token') || localStorage.getItem('token')
    const activeCompanyId = localStorage.getItem('active_company_id')
    return {
      'Authorization': `Bearer ${token}`,
      'X-Company-ID': activeCompanyId || '',
      'Content-Type': 'application/json'
    }
  }

  const fetchCategories = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/masters/cost-categories`, { headers: authHeaders() })
      if (res.ok) {
        const data = await res.json()
        setCategories(Array.isArray(data) ? data : [])
      } else {
        throw new Error('Failed to fetch Cost Categories')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCategories()
  }, [])

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this Cost Category?')) return
    try {
      const res = await fetch(`${API_BASE}/masters/cost-categories/${id}`, {
        method: 'DELETE',
        headers: authHeaders()
      })
      if (res.ok) {
        fetchCategories()
      } else {
        const data = await res.json()
        alert(data.detail || 'Failed to delete')
      }
    } catch (err: any) {
      alert(err.message)
    }
  }

  return (
    <div className="flex flex-col h-full bg-background text-foreground">
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="max-w-6xl mx-auto space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div className="max-w-2xl">
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-foreground">List of Cost Categories</h1>
              <p className="text-sm text-muted-foreground mt-1 mb-3">
                Manage your primary cost tracking dimensions.
              </p>
              <div className="bg-blue-50/50 border border-blue-100 rounded-lg p-3 text-sm text-blue-800 flex gap-3">
                <Info className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold mb-1">What is a Cost Category?</p>
                  <p>
                    Cost Categories allow you to allocate the same transaction amount to multiple distinct dimensions in parallel (e.g., Projects, Departments, Regions). They act as the main buckets that hold individual Cost Centres. Use them to analyze your business from different perspectives simultaneously.
                  </p>
                </div>
              </div>
            </div>
            <button
              onClick={() => { setEditingCategory(null); setIsModalOpen(true) }}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg shadow-sm font-semibold transition-colors flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Create
            </button>
          </div>

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-600 rounded-lg text-sm font-medium">
              {error}
            </div>
          )}

          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
            {loading ? (
              <div className="p-8 text-center text-muted-foreground animate-pulse">Loading Cost Categories...</div>
            ) : categories.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">No Cost Categories found.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-muted-foreground font-semibold border-b border-border">
                    <tr>
                      <th className="px-6 py-3">Name (Alias)</th>
                      <th className="px-6 py-3">Allocate Revenue Items</th>
                      <th className="px-6 py-3">Allocate Non-revenue Items</th>
                      <th className="px-6 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {categories.map((cat) => (
                      <tr key={cat.category_id} className="hover:bg-muted/30 transition-colors group">
                        <td className="px-6 py-4">
                          <div className="font-semibold text-foreground">{cat.name}</div>
                          {cat.alias && <div className="text-xs text-muted-foreground italic">{cat.alias}</div>}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${cat.allocate_revenue ? 'bg-emerald-500/10 text-emerald-600' : 'bg-muted text-muted-foreground'}`}>
                            {cat.allocate_revenue ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                           <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${cat.allocate_non_revenue ? 'bg-emerald-500/10 text-emerald-600' : 'bg-muted text-muted-foreground'}`}>
                            {cat.allocate_non_revenue ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={() => { setEditingCategory(cat); setIsModalOpen(true) }}
                              className="p-1.5 bg-primary/10 text-primary hover:bg-primary/20 rounded-md transition-colors"
                              title="Edit Cost Category"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDelete(cat.category_id)}
                              className="p-1.5 bg-destructive/10 text-destructive hover:bg-destructive/20 rounded-md transition-colors"
                              title="Delete Cost Category"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {isModalOpen && (
        <CostCategoryFormModal
          onClose={() => setIsModalOpen(false)}
          onSuccess={() => { setIsModalOpen(false); fetchCategories(); }}
          editingCategory={editingCategory}
        />
      )}
    </div>
  )
}
