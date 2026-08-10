'use client'

import React, { useState, useEffect } from 'react'
import { Plus, Edit2, Trash2, Info } from 'lucide-react'
import VoucherTypeFormModal from '@/components/VoucherTypeFormModal'
import { API_BASE, authHeaders } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'

export default function VoucherTypesPage() {
  const { token } = useAuth()
  const [voucherTypes, setVoucherTypes] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [voucherTypeToEdit, setVoucherTypeToEdit] = useState<any | null>(null)

  const fetchVoucherTypes = async () => {
    try {
      const res = await fetch(`${API_BASE}/voucher-type`, {
        headers: authHeaders(token)
      })
      if (!res.ok) throw new Error('Failed to fetch voucher types')
      const data = await res.json()
      setVoucherTypes(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (token) fetchVoucherTypes()
  }, [token])

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this voucher type?')) return
    try {
      const res = await fetch(`${API_BASE}/voucher-type/${id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to delete voucher type')
      }
      fetchVoucherTypes()
    } catch (e: any) {
      alert(e.message)
    }
  }

  const openCreateModal = () => {
    setVoucherTypeToEdit(null)
    setIsModalOpen(true)
  }

  const openEditModal = (vt: any) => {
    setVoucherTypeToEdit(vt)
    setIsModalOpen(true)
  }

  if (loading) return <div className="p-6">Loading voucher types...</div>

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">Voucher Types</h1>
          <p className="text-sm text-gray-500 mt-2">Manage Accounting and Inventory Voucher Types</p>
        </div>
        <button
          onClick={openCreateModal}
          className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background bg-blue-600 text-white hover:bg-blue-700 h-10 py-2 px-4 shadow-sm"
        >
          <Plus className="w-4 h-4 mr-2" />
          Create Voucher Type
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-md text-sm border border-red-200">
          {error}
        </div>
      )}

      {/* Info Banner */}
      <div className="bg-blue-50/50 border border-blue-100 rounded-lg p-4 flex gap-3 text-sm text-blue-800">
        <Info className="w-5 h-5 text-blue-500 shrink-0" />
        <div>
          <p className="font-semibold mb-1">About Voucher Types</p>
          <p className="text-blue-700/80">
            Voucher Types define the nature of transactions (e.g., Sales, Purchase, Payment). You can configure automatic numbering, prefixes, and duplicates prevention. Note: System-defined voucher types cannot be deleted or renamed.
          </p>
        </div>
      </div>

      {/* Data Table */}
      <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-50/50 text-gray-500 font-medium border-b">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Parent Type</th>
              <th className="px-4 py-3">Abbreviation</th>
              <th className="px-4 py-3">Numbering</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {voucherTypes.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  No voucher types found.
                </td>
              </tr>
            ) : (
              voucherTypes.map((vt) => (
                <tr key={vt.voucher_type_id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {vt.name}
                    {vt.is_system_defined && <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">System</span>}
                    {!vt.is_active && <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">Inactive</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{vt.parent_type || '-'}</td>
                  <td className="px-4 py-3 text-gray-600">{vt.abbreviation || '-'}</td>
                  <td className="px-4 py-3 text-gray-600">{vt.numbering_method}</td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button
                      onClick={() => openEditModal(vt)}
                      className="text-blue-600 hover:text-blue-800 p-1 rounded-md hover:bg-blue-50 transition-colors"
                      title="Edit Voucher Type"
                    >
                      <Edit2 className="w-4 h-4 inline" />
                    </button>
                    {!vt.is_system_defined && (
                      <button
                        onClick={() => handleDelete(vt.voucher_type_id)}
                        className="text-red-600 hover:text-red-800 p-1 rounded-md hover:bg-red-50 transition-colors"
                        title="Delete Voucher Type"
                      >
                        <Trash2 className="w-4 h-4 inline" />
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <VoucherTypeFormModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={fetchVoucherTypes}
        voucherTypeToEdit={voucherTypeToEdit}
        systemTypes={voucherTypes.map(v => v.name)}
      />
    </div>
  )
}
