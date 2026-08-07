'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { API_BASE } from '@/lib/utils'

export default function CompanyFeaturesPage({ params }: { params: { id: string } }) {
  const router = useRouter()
  const companyId = params.id
  
  const [features, setFeatures] = useState({
    maintain_accounts: 'Yes',
    enable_bill_wise: 'Yes',
    enable_cost_centres: 'No',
    enable_interest: 'No',
    
    maintain_inventory: 'Yes',
    integrate_accounts_inventory: 'Yes',
    enable_multiple_price: 'No',
    enable_batches: 'No',
    
    enable_gst: 'Yes',
    enable_tds: 'No',
    enable_tcs: 'No',
    
    enable_browser_access: 'Yes'
  })
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (name: string, value: string) => {
    setFeatures(prev => ({ ...prev, [name]: value }))
  }
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    
    try {
      const token = localStorage.getItem('token')
      const res = await fetch(`${API_BASE}/companies/${companyId}/features`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          features: {
            maintain_accounts: features.maintain_accounts === 'Yes',
            enable_bill_wise: features.enable_bill_wise === 'Yes',
            enable_cost_centres: features.enable_cost_centres === 'Yes',
            enable_interest: features.enable_interest === 'Yes',
            
            maintain_inventory: features.maintain_inventory === 'Yes',
            integrate_accounts_inventory: features.integrate_accounts_inventory === 'Yes',
            enable_multiple_price: features.enable_multiple_price === 'Yes',
            enable_batches: features.enable_batches === 'Yes',
            
            enable_gst: features.enable_gst === 'Yes',
            enable_tds: features.enable_tds === 'Yes',
            enable_tcs: features.enable_tcs === 'Yes',
            
            enable_browser_access: features.enable_browser_access === 'Yes'
          }
        }),
      })
      
      if (!res.ok) {
        throw new Error('Failed to save features')
      }
      
      router.push('/') // Navigate to dashboard after setup
      
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Helper component for Yes/No selects
  const YesNoSelect = ({ label, name }: { label: string, name: keyof typeof features }) => (
    <div className="flex justify-between py-1">
      <span className="text-gray-800">{label}</span>
      <div className="flex items-center">
        <span className="px-2">:</span>
        <select 
          value={features[name]} 
          onChange={(e) => handleChange(name, e.target.value)}
          className={`w-16 border px-1 focus:outline-none focus:border-black focus:ring-1 focus:ring-black ${features[name] === 'Yes' ? 'bg-[#FBFEE9] border-black' : 'border-transparent bg-transparent hover:border-gray-400'}`}
        >
          <option>Yes</option>
          <option>No</option>
        </select>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-[#D0D4CD] flex items-center justify-center py-8">
      <div className="bg-white border-2 border-blue-900 shadow-xl w-full max-w-4xl font-sans text-sm">
        <div className="bg-[#6B9FCE] text-white py-1 px-4 font-bold border-b-2 border-blue-900 flex justify-between">
          <span>Company Features / Alteration</span>
        </div>

        <form onSubmit={handleSubmit} className="p-4">
          <div className="text-center mb-6">
            <div className="inline-block border-2 border-blue-900 p-2 font-bold text-blue-900">
              <div>Company created successfully.</div>
              <div className="font-normal italic">(Enable the features as per your business needs.)</div>
            </div>
          </div>
          
          {error && <div className="text-red-600 bg-red-100 p-2 mb-4 font-bold border border-red-400">{error}</div>}

          <div className="grid grid-cols-2 gap-12 px-8">
            {/* Left Column */}
            <div className="space-y-6">
              <div>
                <div className="font-bold border-b border-gray-300 pb-1 mb-2">Accounting</div>
                <YesNoSelect label="Maintain Accounts" name="maintain_accounts" />
                <div className="pl-4">
                  <YesNoSelect label="Enable Bill-wise entry" name="enable_bill_wise" />
                  <YesNoSelect label="Enable Cost Centres" name="enable_cost_centres" />
                  <YesNoSelect label="Enable Interest Calculation" name="enable_interest" />
                </div>
              </div>

              <div>
                <div className="font-bold border-b border-gray-300 pb-1 mb-2">Inventory</div>
                <YesNoSelect label="Maintain Inventory" name="maintain_inventory" />
                <div className="pl-4">
                  <YesNoSelect label="Integrate Accounts with Inventory" name="integrate_accounts_inventory" />
                  <YesNoSelect label="Enable multiple Price Levels" name="enable_multiple_price" />
                  <YesNoSelect label="Enable Batches" name="enable_batches" />
                </div>
              </div>
            </div>

            {/* Right Column */}
            <div className="space-y-6">
              <div>
                <div className="font-bold border-b border-gray-300 pb-1 mb-2">Taxation</div>
                <YesNoSelect label="Enable Goods and Services Tax (GST)" name="enable_gst" />
                <YesNoSelect label="Enable Tax Deducted at Source (TDS)" name="enable_tds" />
                <YesNoSelect label="Enable Tax Collected at Source (TCS)" name="enable_tcs" />
              </div>

              <div>
                <div className="font-bold border-b border-gray-300 pb-1 mb-2">Online Access</div>
                <YesNoSelect label="Enable Browser Access for Reports" name="enable_browser_access" />
              </div>
            </div>
          </div>

          <div className="mt-8 flex justify-end">
            <div className="border-2 border-gray-400 bg-gray-100 p-2">
              <div className="text-center mb-2 font-bold">Accept ?</div>
              <div className="flex space-x-2">
                <button type="submit" disabled={loading} className="px-4 py-1 hover:bg-black hover:text-white border border-transparent focus:border-black font-semibold">
                  Yes
                </button>
                <button type="button" onClick={() => router.push('/')} disabled={loading} className="px-4 py-1 hover:bg-black hover:text-white border border-transparent focus:border-black font-semibold">
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
