'use client'

import React, { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Plus, Trash2 } from 'lucide-react'
import { API_BASE, authHeaders } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'

export default function CostCentreClassFormModal({ isOpen, onClose, onSuccess, initialData, categories, centres }: any) {
  const { token } = useAuth()
  const [name, setName] = useState('')
  const [allocations, setAllocations] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (initialData) {
      setName(initialData.name)
      setAllocations(initialData.allocations.map((a: any) => ({
        id: a.allocation_id || Math.random(),
        category_id: String(a.category_id),
        cost_centre_id: String(a.cost_centre_id),
        percentage: String(a.percentage)
      })))
    } else {
      setName('')
      setAllocations([{ id: Math.random(), category_id: '', cost_centre_id: '', percentage: '' }])
    }
  }, [initialData])

  const handleAddRow = () => {
    setAllocations([...allocations, { id: Math.random(), category_id: '', cost_centre_id: '', percentage: '' }])
  }

  const handleRemoveRow = (index: number) => {
    setAllocations(allocations.filter((_, i) => i !== index))
  }

  const handleAllocationChange = (index: number, field: string, value: string) => {
    const newAlloc = [...allocations]
    newAlloc[index][field] = value
    
    if (field === 'category_id') {
      newAlloc[index].cost_centre_id = '' // Reset centre if category changes
    }
    
    setAllocations(newAlloc)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    // Validate
    if (!name.trim()) {
      setError('Name is required')
      setLoading(false)
      return
    }

    // Validate sums
    const sums: Record<string, number> = {}
    const validAllocations = []
    
    for (const alloc of allocations) {
      if (!alloc.category_id || !alloc.cost_centre_id || !alloc.percentage) {
        setError('Please fill out all fields in all allocation rows.')
        setLoading(false)
        return
      }
      const pct = parseFloat(alloc.percentage)
      sums[alloc.category_id] = (sums[alloc.category_id] || 0) + pct
      validAllocations.push({
        category_id: parseInt(alloc.category_id),
        cost_centre_id: parseInt(alloc.cost_centre_id),
        percentage: pct
      })
    }

    for (const [catId, sum] of Object.entries(sums)) {
      if (sum > 100) {
        const catName = categories.find((c: any) => c.category_id.toString() === catId)?.name || 'Unknown Category'
        setError(`Total percentage for ${catName} exceeds 100%.`)
        setLoading(false)
        return
      }
    }

    const payload = {
      name,
      allocations: validAllocations
    }

    try {
      const url = initialData 
        ? `${API_BASE}/masters/cost-centre-classes/${initialData.class_id}`
        : `${API_BASE}/masters/cost-centre-classes`
      
      const res = await fetch(url, {
        method: initialData ? 'PUT' : 'POST',
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })

      if (res.ok) {
        onSuccess()
      } else {
        const data = await res.json()
        setError(data.detail || 'Something went wrong')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[700px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 bg-clip-text text-transparent">
            {initialData ? 'Edit Cost Centre Class' : 'Create Cost Centre Class'}
          </DialogTitle>
        </DialogHeader>

        {error && (
          <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm border border-red-100">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6 mt-4">
          <div className="space-y-2">
            <Label htmlFor="name" className="text-gray-700">Class Name <span className="text-red-500">*</span></Label>
            <Input 
              id="name"
              placeholder="e.g. Primary Class"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="border-gray-200 focus:border-blue-500 focus:ring-blue-500 transition-all"
            />
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <Label className="text-gray-700 text-lg">Allocations</Label>
              <Button type="button" variant="outline" size="sm" onClick={handleAddRow} className="gap-2">
                <Plus size={16} /> Add Row
              </Button>
            </div>
            
            <div className="space-y-3">
              {allocations.map((alloc, index) => {
                const filteredCentres = centres.filter((c: any) => String(c.category_id) === alloc.category_id)
                return (
                  <div key={alloc.id} className="flex items-start gap-3 bg-gray-50 p-3 rounded-xl border border-gray-100">
                    <div className="flex-1 space-y-2">
                      <Label className="text-xs text-gray-500">Cost Category</Label>
                      <Select 
                        value={alloc.category_id} 
                        onValueChange={(val) => handleAllocationChange(index, 'category_id', val)}
                      >
                        <SelectTrigger className="bg-white">
                          <SelectValue placeholder="Select Category" />
                        </SelectTrigger>
                        <SelectContent>
                          {categories.map((cat: any) => (
                            <SelectItem key={cat.category_id} value={String(cat.category_id)}>
                              {cat.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex-1 space-y-2">
                      <Label className="text-xs text-gray-500">Cost Centre</Label>
                      <Select 
                        value={alloc.cost_centre_id} 
                        onValueChange={(val) => handleAllocationChange(index, 'cost_centre_id', val)}
                        disabled={!alloc.category_id}
                      >
                        <SelectTrigger className="bg-white">
                          <SelectValue placeholder={alloc.category_id ? "Select Centre" : "Select Category First"} />
                        </SelectTrigger>
                        <SelectContent>
                          {filteredCentres.map((cc: any) => (
                            <SelectItem key={cc.cost_centre_id} value={String(cc.cost_centre_id)}>
                              {cc.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="w-24 space-y-2">
                      <Label className="text-xs text-gray-500">Percentage</Label>
                      <div className="relative">
                        <Input
                          type="number"
                          min="0.01"
                          max="100"
                          step="0.01"
                          value={alloc.percentage}
                          onChange={(e) => handleAllocationChange(index, 'percentage', e.target.value)}
                          className="bg-white pr-6"
                        />
                        <span className="absolute right-3 top-2 text-gray-400 text-sm">%</span>
                      </div>
                    </div>

                    <div className="pt-7">
                      <button
                        type="button"
                        onClick={() => handleRemoveRow(index)}
                        disabled={allocations.length === 1}
                        className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <Trash2 size={20} />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
            
            <p className="text-xs text-gray-500">
              Note: The total percentage for any Cost Category cannot exceed 100%. If less than 100%, the remainder is unallocated.
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-100">
            <Button type="button" variant="outline" onClick={onClose} disabled={loading} className="px-6 rounded-lg">
              Cancel
            </Button>
            <Button type="submit" disabled={loading} className="px-6 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-all shadow-md">
              {loading ? 'Saving...' : (initialData ? 'Update Class' : 'Create Class')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
