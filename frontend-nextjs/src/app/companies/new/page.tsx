'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { API_BASE } from '@/lib/utils'

export default function NewCompanyPage() {
  const { user, login } = useAuth()
  const router = useRouter()
  
  const [formData, setFormData] = useState({
    name: '',
    mailing_name: '',
    address_line1: '',
    address_line2: '',
    state: '',
    country: 'India',
    pincode: '',
    telephone: '',
    mobile: '',
    email: '',
    website: '',
    financial_year_start: '2026-04-01',
    books_begin_date: '2026-04-01',
    base_currency: 'INR',
    // User credentials if not logged in
    username: '',
    user_email: '',
    password: ''
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      // If user is logged in, use their token (they are an existing admin creating an extra company)
      if (user && typeof window !== 'undefined') {
        const token = localStorage.getItem('token')
        if (token) headers['Authorization'] = `Bearer ${token}`
      }

      const res = await fetch(`${API_BASE}/companies`, {
        method: 'POST',
        headers,
        body: JSON.stringify(formData),
      })
      
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to create company')
      }
      
      const newCompany = await res.json()
      
      if (!user) {
        // If not logged in, they just registered. We should log them in now.
        const loginRes = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: formData.user_email, password: formData.password }),
        })
        if (loginRes.ok) {
          const { access_token } = await loginRes.json()
          await login(access_token, formData.user_email)
        }
      }
      
      // Redirect to features F11 page
      router.push(`/companies/${newCompany.company_id}/features`)
      
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#D0D4CD] flex items-center justify-center py-8">
      <div className="bg-white border-2 border-blue-900 shadow-xl w-full max-w-4xl font-sans text-sm">
        {/* Tally-style header */}
        <div className="bg-[#6B9FCE] text-white py-1 px-4 font-bold border-b-2 border-blue-900">
          Company Creation
        </div>

        <form onSubmit={handleSubmit} className="p-4">
          {error && <div className="text-red-600 bg-red-100 p-2 mb-4 font-bold border border-red-400">{error}</div>}

          <div className="grid grid-cols-2 gap-x-8 gap-y-1">
            {/* Left Column */}
            <div className="space-y-1">
              <div className="flex">
                <span className="w-40 font-semibold text-gray-700">Company Data Path</span>
                <span className="px-1">:</span>
                <span className="font-mono text-gray-500">C:\Users\Public\Tally.ERP9\Data</span>
              </div>
              <div className="h-4 border-b border-gray-300 mb-2"></div>
              
              <div className="flex">
                <span className="w-40">Company Name</span>
                <span className="px-1">:</span>
                <input required name="name" value={formData.name} onChange={handleChange} className="flex-1 border border-gray-400 px-1 bg-[#FBFEE9] focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>
              <div className="flex">
                <span className="w-40">Mailing Name</span>
                <span className="px-1">:</span>
                <input name="mailing_name" value={formData.mailing_name} onChange={handleChange} className="flex-1 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>
              <div className="flex items-start">
                <span className="w-40 pt-1">Address</span>
                <span className="px-1 pt-1">:</span>
                <div className="flex-1 space-y-1">
                  <input name="address_line1" value={formData.address_line1} onChange={handleChange} className="w-full border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
                  <input name="address_line2" value={formData.address_line2} onChange={handleChange} className="w-full border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
                </div>
              </div>
              
              <div className="flex pt-4">
                <span className="w-40">State</span>
                <span className="px-1">:</span>
                <input name="state" value={formData.state} onChange={handleChange} className="flex-1 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>
              <div className="flex">
                <span className="w-40">Country</span>
                <span className="px-1">:</span>
                <input name="country" value={formData.country} onChange={handleChange} className="flex-1 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>
              <div className="flex">
                <span className="w-40">Pincode</span>
                <span className="px-1">:</span>
                <input name="pincode" value={formData.pincode} onChange={handleChange} className="flex-1 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>
              <div className="flex">
                <span className="w-40">Telephone</span>
                <span className="px-1">:</span>
                <input name="telephone" value={formData.telephone} onChange={handleChange} className="flex-1 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>
              <div className="flex">
                <span className="w-40">Mobile</span>
                <span className="px-1">:</span>
                <input name="mobile" value={formData.mobile} onChange={handleChange} className="flex-1 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>
              <div className="flex">
                <span className="w-40">E-mail</span>
                <span className="px-1">:</span>
                <input type="email" name="email" value={formData.email} onChange={handleChange} className="flex-1 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>
              <div className="flex">
                <span className="w-40">Website</span>
                <span className="px-1">:</span>
                <input name="website" value={formData.website} onChange={handleChange} className="flex-1 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>
            </div>

            {/* Right Column */}
            <div className="space-y-1 mt-6">
              <div className="flex">
                <span className="w-48">Financial year beginning from</span>
                <span className="px-1">:</span>
                <input type="date" required name="financial_year_start" value={formData.financial_year_start} onChange={handleChange} className="flex-1 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>
              <div className="flex">
                <span className="w-48">Books beginning from</span>
                <span className="px-1">:</span>
                <input type="date" required name="books_begin_date" value={formData.books_begin_date} onChange={handleChange} className="flex-1 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
              </div>

              {!user && (
                <div className="mt-8 border border-gray-300 p-3 bg-gray-50">
                  <div className="font-bold mb-2">Administrator Details</div>
                  <div className="flex mb-1">
                    <span className="w-40">Username</span>
                    <span className="px-1">:</span>
                    <input required name="username" value={formData.username} onChange={handleChange} className="flex-1 border border-gray-400 px-1 bg-[#FBFEE9] focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
                  </div>
                  <div className="flex mb-1">
                    <span className="w-40">Admin E-mail</span>
                    <span className="px-1">:</span>
                    <input type="email" required name="user_email" value={formData.user_email} onChange={handleChange} className="flex-1 border border-gray-400 px-1 bg-[#FBFEE9] focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
                  </div>
                  <div className="flex mb-1">
                    <span className="w-40">Password</span>
                    <span className="px-1">:</span>
                    <input type="password" required name="password" value={formData.password} onChange={handleChange} className="flex-1 border border-gray-400 px-1 bg-[#FBFEE9] focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
                  </div>
                </div>
              )}
            </div>
          </div>
          
          <div className="mt-8 pt-2 border-t border-gray-300">
            <div className="flex">
              <span className="w-40">Base Currency symbol</span>
              <span className="px-1">:</span>
              <input name="base_currency" value={formData.base_currency} onChange={handleChange} className="w-20 border border-gray-400 px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black" />
            </div>
            <div className="flex mt-1">
              <span className="w-40">Formal name</span>
              <span className="px-1">:</span>
              <span className="w-20 px-1">{formData.base_currency === 'INR' ? 'INR' : formData.base_currency}</span>
            </div>
          </div>

          <div className="mt-6 flex justify-end">
            <div className="border-2 border-gray-400 bg-gray-100 p-2">
              <div className="text-center mb-2 font-bold">Accept ?</div>
              <div className="flex space-x-2">
                <button type="submit" disabled={loading} className="px-4 py-1 hover:bg-black hover:text-white border border-transparent focus:border-black font-semibold">
                  Yes
                </button>
                <button type="button" onClick={() => router.back()} disabled={loading} className="px-4 py-1 hover:bg-black hover:text-white border border-transparent focus:border-black font-semibold">
                  No
                </button>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
