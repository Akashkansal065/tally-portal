'use client'

import React, { useState, useEffect } from 'react'
import { Plus, Edit2, Trash2, Info } from 'lucide-react'
import CurrencyFormModal from '@/components/CurrencyFormModal'
import { API_BASE, authHeaders } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'

export default function CurrenciesPage() {
  const { token, user } = useAuth()
  const [currencies, setCurrencies] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [currencyToEdit, setCurrencyToEdit] = useState<any | null>(null)

  const fetchCurrencies = async () => {
    try {
      const res = await fetch(`${API_BASE}/currency`, {
        headers: authHeaders(token)
      })
      if (!res.ok) throw new Error('Failed to fetch currencies')
      const data = await res.json()
      setCurrencies(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (token) fetchCurrencies()
  }, [token])

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this currency?')) return
    try {
      const res = await fetch(`${API_BASE}/currency/${id}`, {
        method: 'DELETE',
        headers: authHeaders(token)
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to delete currency')
      }
      fetchCurrencies()
    } catch (e: any) {
      alert(e.message)
    }
  }

  const openCreateModal = () => {
    setCurrencyToEdit(null)
    setIsModalOpen(true)
  }

  const openEditModal = (currency: any) => {
    setCurrencyToEdit(currency)
    setIsModalOpen(true)
  }

  if (loading) return <div className="p-6">Loading currencies...</div>

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">Currencies</h1>
          <p className="text-sm text-gray-500 mt-2">Manage Foreign Currencies and Exchange Rates</p>
        </div>
        <button
          onClick={openCreateModal}
          className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background bg-blue-600 text-white hover:bg-blue-700 h-10 py-2 px-4 shadow-sm"
        >
          <Plus className="w-4 h-4 mr-2" />
          Create Currency
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
          <p className="font-semibold mb-1">About Currency Master</p>
          <p className="text-blue-700/80">
            Currencies allow you to record transactions in foreign denominations. You can set formatting options (like suffixes and spacing) and specify Exchange Rates (Standard, Selling, and Buying) for different dates. Note: The Base Currency is set during Company Creation and cannot be deleted.
          </p>
        </div>
      </div>

      {/* Data Table */}
      <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-50/50 text-gray-500 font-medium border-b">
            <tr>
              <th className="px-4 py-3">Symbol</th>
              <th className="px-4 py-3">Formal Name</th>
              <th className="px-4 py-3">ISO Code</th>
              <th className="px-4 py-3 text-center">Decimals</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {currencies.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  No currencies found. Click "Create Currency" to add one.
                </td>
              </tr>
            ) : (
              currencies.map((curr) => (
                <tr key={curr.currency_id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {curr.symbol}
                    {curr.is_base_currency && <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">Base</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{curr.formal_name || '-'}</td>
                  <td className="px-4 py-3 text-gray-600">{curr.code}</td>
                  <td className="px-4 py-3 text-center text-gray-600">{curr.decimal_places}</td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button
                      onClick={() => openEditModal(curr)}
                      className="text-blue-600 hover:text-blue-800 p-1 rounded-md hover:bg-blue-50 transition-colors"
                      title="Edit Currency"
                    >
                      <Edit2 className="w-4 h-4 inline" />
                    </button>
                    {!curr.is_base_currency && (
                      <button
                        onClick={() => handleDelete(curr.currency_id)}
                        className="text-red-600 hover:text-red-800 p-1 rounded-md hover:bg-red-50 transition-colors"
                        title="Delete Currency"
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

      <CurrencyFormModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={fetchCurrencies}
        currencyToEdit={currencyToEdit}
      />
    </div>
  )
}
