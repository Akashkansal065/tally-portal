'use client'

import { useState, useEffect } from 'react'
import { Plus, Edit2, Trash2, Info } from 'lucide-react'
import CostCentreClassFormModal from '@/components/CostCentreClassFormModal'
import { API_BASE, authHeaders } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'

export default function CostCentreClassesPage() {
  const { token, permissions } = useAuth()
  const [classes, setClasses] = useState<any[]>([])
  const [categories, setCategories] = useState<any[]>([])
  const [centres, setCentres] = useState<any[]>([])
  
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingData, setEditingData] = useState<any>(null)
  
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchData = async () => {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      const [clsRes, catRes, ccRes] = await Promise.all([
        fetch(`${API_BASE}/masters/cost-centre-classes`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/masters/cost-categories`, { headers: authHeaders(token) }),
        fetch(`${API_BASE}/masters/cost-centres`, { headers: authHeaders(token) })
      ])

      if (clsRes.ok && catRes.ok && ccRes.ok) {
        setClasses(await clsRes.json())
        setCategories(await catRes.json())
        setCentres(await ccRes.json())
      } else {
        throw new Error('Failed to fetch data')
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [token])

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this Cost Centre Class?')) return

    try {
      const res = await fetch(`${API_BASE}/masters/cost-centre-classes/${id}`, {
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

  const handleEdit = (cls: any) => {
    setEditingData(cls)
    setIsModalOpen(true)
  }

  if (!permissions.isAdmin) {
    return <div className="p-6 text-red-500">You do not have permission to access this page.</div>
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 bg-clip-text text-transparent">
            Cost Centre Classes
          </h1>
          <p className="text-gray-500 mt-2">
            Configure automated percentage-based allocations for your Cost Centres.
          </p>
        </div>
        <button
          onClick={() => { setEditingData(null); setIsModalOpen(true) }}
          className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-all shadow-md hover:shadow-lg font-medium"
        >
          <Plus size={20} />
          Create Class
        </button>
      </div>
      
      {/* Informational Banner */}
      <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg flex items-start gap-3">
        <Info className="text-blue-500 shrink-0 mt-0.5" size={20} />
        <div>
          <h3 className="font-semibold text-blue-800">What is a Cost Centre Class?</h3>
          <p className="text-blue-700 text-sm mt-1">
            A Cost Centre Class allows you to automate cost allocations. Instead of manually splitting a transaction across multiple cost centres during data entry, you select a "Class", and the system automatically distributes the amount based on the percentages you define here!
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center p-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      ) : error ? (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg border border-red-200">
          {error}
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-gray-600 text-sm font-semibold uppercase tracking-wider">
                <th className="p-4">Name</th>
                <th className="p-4">Allocations Summary</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {classes.length === 0 ? (
                <tr>
                  <td colSpan={3} className="p-8 text-center text-gray-500">
                    No Cost Centre Classes found.
                  </td>
                </tr>
              ) : (
                classes.map(cls => (
                  <tr key={cls.class_id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="p-4 font-medium text-gray-900">{cls.name}</td>
                    <td className="p-4 text-sm text-gray-600">
                      {cls.allocations.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {cls.allocations.slice(0, 3).map((a: any) => (
                            <span key={a.allocation_id} className="bg-gray-100 px-2 py-1 rounded text-xs font-medium text-gray-700 border border-gray-200">
                              {a.cost_centre_name} ({Number(a.percentage).toFixed(0)}%)
                            </span>
                          ))}
                          {cls.allocations.length > 3 && (
                            <span className="bg-gray-100 px-2 py-1 rounded text-xs font-medium text-gray-700 border border-gray-200">
                              +{cls.allocations.length - 3} more
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-400 italic">No allocations defined</span>
                      )}
                    </td>
                    <td className="p-4 text-right">
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => handleEdit(cls)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title="Edit"
                        >
                          <Edit2 size={18} />
                        </button>
                        <button
                          onClick={() => handleDelete(cls.class_id)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Delete"
                        >
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {isModalOpen && (
        <CostCentreClassFormModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSuccess={() => {
            setIsModalOpen(false)
            fetchData()
          }}
          initialData={editingData}
          categories={categories}
          centres={centres}
        />
      )}
    </div>
  )
}
