'use client'

import React, { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { API_BASE, authHeaders } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'

export type CostCentreFormData = {
  cost_centre_id?: number
  name: string
  alias?: string
  category_id: number
  parent_id?: number
}

type CostCentreFormModalProps = {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  initialData?: CostCentreFormData | null
  categories: any[]
  centres: any[]
}

export default function CostCentreFormModal({ isOpen, onClose, onSuccess, initialData, categories, centres }: CostCentreFormModalProps) {
  const { token } = useAuth()

  const [formData, setFormData] = useState<CostCentreFormData>({
    name: '',
    alias: '',
    category_id: categories.length > 0 ? categories[0].category_id : 0,
    parent_id: undefined
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (initialData) {
      setFormData(initialData)
    } else {
      setFormData({
        name: '',
        alias: '',
        category_id: categories.length > 0 ? categories[0].category_id : 0,
        parent_id: undefined
      })
    }
    setError('')
  }, [initialData, isOpen, categories])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const url = formData.cost_centre_id
        ? `${API_BASE}/masters/cost-centres/${formData.cost_centre_id}`
        : `${API_BASE}/masters/cost-centres`
      const method = formData.cost_centre_id ? 'PUT' : 'POST'

      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(formData)
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to save Cost Centre')
      }

      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{formData.cost_centre_id ? 'Cost Centre Alteration' : 'Cost Centre Creation'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 py-4">
          {error && <div className="text-destructive text-sm font-medium">{error}</div>}

          <div className="grid grid-cols-4 items-center gap-4">
            <label className="text-right font-semibold text-sm">Category</label>
            <div className="col-span-3">
              <select
                value={String(formData.category_id)}
                onChange={(e) => setFormData({ ...formData, category_id: parseInt(e.target.value) })}
                className="flex h-10 w-full rounded-md border border-input px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 bg-yellow-100/50 focus:bg-yellow-100 transition-colors"
              >
                {categories.map((c) => (
                  <option key={c.category_id} value={String(c.category_id)}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <label className="text-right font-semibold text-sm">Name</label>
            <div className="col-span-3">
              <input
                required
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="flex h-10 w-full rounded-md border border-input px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 bg-yellow-100/50 focus:bg-yellow-100 transition-colors"
                autoFocus
              />
            </div>
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <label className="text-right text-muted-foreground text-sm">(Alias)</label>
            <div className="col-span-3">
              <input
                type="text"
                value={formData.alias || ''}
                onChange={(e) => setFormData({ ...formData, alias: e.target.value })}
                className="flex h-10 w-full rounded-md border border-input px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 bg-yellow-100/50 focus:bg-yellow-100 transition-colors"
              />
            </div>
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <label className="text-right font-semibold text-sm">Under</label>
            <div className="col-span-3">
              <select
                value={formData.parent_id ? String(formData.parent_id) : 'primary'}
                onChange={(e) => setFormData({ ...formData, parent_id: e.target.value === 'primary' ? undefined : parseInt(e.target.value) })}
                className="flex h-10 w-full rounded-md border border-input px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 bg-yellow-100/50 focus:bg-yellow-100 transition-colors"
              >
                <option value="primary">Primary</option>
                {centres.filter(c => c.cost_centre_id !== formData.cost_centre_id).map((c) => (
                  <option key={c.cost_centre_id} value={String(c.cost_centre_id)}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <DialogFooter className="mt-6">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
