'use client'

import { useState } from 'react'
import { X, Save, Loader2, Info } from 'lucide-react'
import { API_BASE, authHeaders } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'

interface Props {
  onClose: () => void
  onSuccess: () => void
  editingCategory?: any
}

export default function CostCategoryFormModal({ onClose, onSuccess, editingCategory }: Props) {
  const { token } = useAuth()
  const [formData, setFormData] = useState({
    name: editingCategory?.name || '',
    alias: editingCategory?.alias || '',
    allocate_revenue: editingCategory?.allocate_revenue ?? true,
    allocate_non_revenue: editingCategory?.allocate_non_revenue ?? false,
    is_active: editingCategory?.is_active ?? true,
  })

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const isEdit = !!editingCategory
      const url = isEdit
        ? `${API_BASE}/masters/cost-categories/${editingCategory.category_id}`
        : `${API_BASE}/masters/cost-categories`
        
      const method = isEdit ? 'PUT' : 'POST'

      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(formData)
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to save Cost Category')
      }

      onSuccess()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-card border border-border w-full max-w-xl rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        
        {/* Header (Tally Style) */}
        <div className="flex items-center justify-between p-4 bg-[#84D4DE] text-black rounded-t-2xl border-b border-border">
          <div>
            <h2 className="text-sm font-bold">Cost Category Alteration</h2>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-black/10 rounded transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 text-foreground bg-[#DDE9F2]">
          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 text-red-600 rounded-lg text-sm font-medium flex items-center gap-2">
              <Info className="w-4 h-4" />
              {error}
            </div>
          )}

          <form id="cost-category-form" onSubmit={handleSubmit} className="space-y-6">
            
            <div className="grid grid-cols-[150px_1fr] items-center gap-4">
              <label className="text-sm text-gray-600 font-semibold text-right">Name</label>
              <input
                type="text"
                required
                className="w-full bg-[#FFF5C6] border border-gray-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 px-2 py-1 text-sm font-semibold text-black"
                value={formData.name}
                onChange={e => setFormData({ ...formData, name: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-[150px_1fr] items-center gap-4">
              <label className="text-sm text-gray-500 italic text-right">(alias)</label>
              <input
                type="text"
                className="w-full bg-white border border-gray-300 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 px-2 py-1 text-sm text-black"
                value={formData.alias}
                onChange={e => setFormData({ ...formData, alias: e.target.value })}
              />
            </div>

            <div className="h-px bg-gray-300 my-4" />

            <div className="grid grid-cols-[1fr_100px] items-center gap-4">
              <label className="text-sm text-gray-600 font-semibold">Allocate Revenue Items</label>
              <select
                className="w-full bg-white border border-gray-300 focus:outline-none focus:border-blue-500 px-2 py-1 text-sm font-semibold text-black appearance-none text-right"
                value={formData.allocate_revenue ? 'Yes' : 'No'}
                onChange={e => setFormData({ ...formData, allocate_revenue: e.target.value === 'Yes' })}
              >
                <option value="Yes">Yes</option>
                <option value="No">No</option>
              </select>
            </div>

            <div className="grid grid-cols-[1fr_100px] items-center gap-4">
              <label className="text-sm text-gray-600 font-semibold">Allocate Non-revenue items</label>
              <select
                className="w-full bg-white border border-gray-300 focus:outline-none focus:border-blue-500 px-2 py-1 text-sm font-semibold text-black appearance-none text-right"
                value={formData.allocate_non_revenue ? 'Yes' : 'No'}
                onChange={e => setFormData({ ...formData, allocate_non_revenue: e.target.value === 'Yes' })}
              >
                <option value="Yes">Yes</option>
                <option value="No">No</option>
              </select>
            </div>

          </form>
        </div>

        <div className="p-4 border-t border-border bg-card flex justify-end gap-3 rounded-b-2xl">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-semibold text-muted-foreground hover:bg-muted rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="cost-category-form"
            disabled={loading}
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save
          </button>
        </div>
      </div>
    </div>
  )
}
