import React, { useState, useEffect, useMemo } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Plus, Trash2, Search, ChevronDown } from 'lucide-react'
import { API_BASE, authHeaders } from '@/lib/utils'
import { useAuth } from '@/context/AuthContext'

interface ExchangeRate {
  rate_date: string;
  standard_rate?: string | number;
  selling_rate?: string | number;
  buying_rate?: string | number;
  source: string;
}

interface Currency {
  currency_id?: number;
  code: string;
  symbol: string;
  formal_name: string;
  decimal_places: number;
  show_amount_in_millions: boolean;
  suffix_symbol_to_amount: boolean;
  add_space_between_amount_and_symbol: boolean;
  word_representing_amount_after_decimal: string;
  decimal_places_for_words: number;
  is_base_currency: boolean;
  rates: ExchangeRate[];
}

interface IsoCurrency {
  code: string;
  symbol: string;
  name: string;
  decimal_places: number;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  currencyToEdit?: Currency | null;
}

export default function CurrencyFormModal({ isOpen, onClose, onSuccess, currencyToEdit }: Props) {
  const { token } = useAuth()
  const [formData, setFormData] = useState<Currency>({
    code: '',
    symbol: '',
    formal_name: '',
    decimal_places: 2,
    show_amount_in_millions: false,
    suffix_symbol_to_amount: false,
    add_space_between_amount_and_symbol: true,
    word_representing_amount_after_decimal: 'paise',
    decimal_places_for_words: 2,
    is_base_currency: false,
    rates: []
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [isoList, setIsoList] = useState<IsoCurrency[]>([])
  const [showIsoPicker, setShowIsoPicker] = useState(false)
  const [isoSearch, setIsoSearch] = useState('')

  // Fetch ISO list once
  useEffect(() => {
    const fetchIsoList = async () => {
      try {
        const res = await fetch(`${API_BASE}/currency`, { headers: authHeaders(token) })
        if (res.ok) {
          const data = await res.json()
          setIsoList(data.map((c: any) => ({
            code: c.code,
            symbol: c.symbol,
            name: c.formal_name || c.code,
            decimal_places: c.decimal_places ?? 2,
          })))
        }
      } catch (e) { /* ignore */ }
    }
    fetchIsoList()
  }, [token])

  useEffect(() => {
    if (currencyToEdit) {
      setFormData({
        ...currencyToEdit,
        code: currencyToEdit.code ?? '',
        symbol: currencyToEdit.symbol ?? '',
        formal_name: currencyToEdit.formal_name ?? '',
        word_representing_amount_after_decimal: currencyToEdit.word_representing_amount_after_decimal ?? '',
        decimal_places: currencyToEdit.decimal_places ?? 2,
        decimal_places_for_words: currencyToEdit.decimal_places_for_words ?? 2,
        rates: currencyToEdit.rates ?? [],
      })
    } else {
      setFormData({
        code: '',
        symbol: '',
        formal_name: '',
        decimal_places: 2,
        show_amount_in_millions: false,
        suffix_symbol_to_amount: false,
        add_space_between_amount_and_symbol: true,
        word_representing_amount_after_decimal: 'paise',
        decimal_places_for_words: 2,
        is_base_currency: false,
        rates: []
      })
    }
    setError('')
    setShowIsoPicker(false)
    setIsoSearch('')
  }, [currencyToEdit, isOpen])

  const filteredIsoList = useMemo(() => {
    if (!isoSearch) return isoList
    const q = isoSearch.toLowerCase()
    return isoList.filter(c => 
      c.code.toLowerCase().includes(q) || 
      c.name.toLowerCase().includes(q) || 
      c.symbol.toLowerCase().includes(q)
    )
  }, [isoList, isoSearch])

  const selectIsoCurrency = (iso: IsoCurrency) => {
    setFormData(prev => ({
      ...prev,
      code: iso.code,
      symbol: iso.symbol,
      formal_name: iso.name,
      decimal_places: iso.decimal_places,
    }))
    setShowIsoPicker(false)
    setIsoSearch('')
  }

  const handleChange = (field: keyof Currency, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const addRate = () => {
    setFormData(prev => ({
      ...prev,
      rates: [...prev.rates, { rate_date: new Date().toISOString().split('T')[0], source: 'Manual' }]
    }))
  }

  const removeRate = (index: number) => {
    setFormData(prev => ({
      ...prev,
      rates: prev.rates.filter((_, i) => i !== index)
    }))
  }

  const updateRate = (index: number, field: keyof ExchangeRate, value: any) => {
    setFormData(prev => {
      const newRates = [...prev.rates]
      newRates[index] = { ...newRates[index], [field]: value || undefined }
      return { ...prev, rates: newRates }
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    
    // Clean up rates (convert empty strings to undefined to avoid API errors on Decimals)
    const payloadRates = formData.rates.map(r => ({
        rate_date: r.rate_date,
        standard_rate: r.standard_rate ? Number(r.standard_rate) : undefined,
        selling_rate: r.selling_rate ? Number(r.selling_rate) : undefined,
        buying_rate: r.buying_rate ? Number(r.buying_rate) : undefined,
        source: r.source
    })).filter(r => r.standard_rate || r.selling_rate || r.buying_rate);

    const payload = {
        ...formData,
        rates: payloadRates
    }

    try {
      const url = currencyToEdit ? `${API_BASE}/currency/${currencyToEdit.currency_id}` : `${API_BASE}/currency`
      const method = currencyToEdit ? 'PUT' : 'POST'
      const res = await fetch(url, {
        method,
        headers: authHeaders(token),
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to save currency')
      }

      onSuccess()
      onClose()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{currencyToEdit ? 'Alter Currency' : 'Currency Creation'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6 mt-4">
          {error && <div className="text-red-500 text-sm font-medium">{error}</div>}

          {/* ISO Currency Picker */}
          {!currencyToEdit && (
            <div className="relative">
              <Label className="mb-2 block">Select from ISO 4217 Currencies</Label>
              <button
                type="button"
                onClick={() => setShowIsoPicker(!showIsoPicker)}
                className="w-full flex items-center justify-between px-3 py-2 border rounded-md text-sm text-left hover:bg-gray-50 transition-colors"
              >
                <span className={formData.code ? 'text-gray-900' : 'text-gray-400'}>
                  {formData.code ? `${formData.symbol}  ${formData.formal_name} (${formData.code})` : 'Choose a currency to auto-fill fields...'}
                </span>
                <ChevronDown className="w-4 h-4 text-gray-400" />
              </button>
              {showIsoPicker && (
                <div className="absolute z-50 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-64 overflow-hidden">
                  <div className="sticky top-0 bg-white border-b p-2">
                    <div className="relative">
                      <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
                      <Input
                        autoFocus
                        placeholder="Search by name, code, or symbol..."
                        value={isoSearch}
                        onChange={e => setIsoSearch(e.target.value)}
                        className="pl-8"
                      />
                    </div>
                  </div>
                  <div className="overflow-y-auto max-h-48">
                    {filteredIsoList.length === 0 ? (
                      <div className="px-3 py-4 text-center text-sm text-gray-400">No currencies match your search.</div>
                    ) : (
                      filteredIsoList.map(iso => (
                        <button
                          key={iso.code}
                          type="button"
                          onClick={() => selectIsoCurrency(iso)}
                          className="w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-blue-50 transition-colors text-left"
                        >
                          <span className="w-8 text-lg">{iso.symbol}</span>
                          <span className="flex-1">{iso.name}</span>
                          <span className="text-xs font-mono text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">{iso.code}</span>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Symbol</Label>
              <Input required value={formData.symbol} onChange={e => handleChange('symbol', e.target.value)} placeholder="e.g. ₹" />
            </div>
            <div className="space-y-2">
              <Label>Formal Name</Label>
              <Input required value={formData.formal_name} onChange={e => handleChange('formal_name', e.target.value)} placeholder="e.g. Indian Rupee" />
            </div>
            <div className="space-y-2">
              <Label>ISO Currency Code</Label>
              <Input required value={formData.code} onChange={e => handleChange('code', e.target.value.toUpperCase())} placeholder="e.g. INR" maxLength={3} />
            </div>
            <div className="space-y-2">
              <Label>Number of decimal places</Label>
              <Input type="number" value={formData.decimal_places} onChange={e => handleChange('decimal_places', Number(e.target.value))} />
            </div>
            <div className="space-y-2">
              <Label>Word representing amount after decimal</Label>
              <Input value={formData.word_representing_amount_after_decimal} onChange={e => handleChange('word_representing_amount_after_decimal', e.target.value)} placeholder="e.g. paise" />
            </div>
            <div className="space-y-2">
              <Label>No. of decimal places for amount in words</Label>
              <Input type="number" value={formData.decimal_places_for_words} onChange={e => handleChange('decimal_places_for_words', Number(e.target.value))} />
            </div>
          </div>

          <div className="space-y-3 p-4 bg-gray-50 rounded-lg border border-gray-100">
            <div className="flex items-center space-x-2">
              <Checkbox id="millions" checked={formData.show_amount_in_millions} onCheckedChange={(c) => handleChange('show_amount_in_millions', c === true)} />
              <label htmlFor="millions" className="text-sm font-medium cursor-pointer">Show amount in millions</label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox id="suffix" checked={formData.suffix_symbol_to_amount} onCheckedChange={(c) => handleChange('suffix_symbol_to_amount', c === true)} />
              <label htmlFor="suffix" className="text-sm font-medium cursor-pointer">Suffix symbol to amount</label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox id="space" checked={formData.add_space_between_amount_and_symbol} onCheckedChange={(c) => handleChange('add_space_between_amount_and_symbol', c === true)} />
              <label htmlFor="space" className="text-sm font-medium cursor-pointer">Add space between amount and symbol</label>
            </div>
          </div>

          <div className="space-y-4 pt-4 border-t">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-semibold text-gray-700">Rates of Exchange</h3>
              <Button type="button" variant="outline" size="sm" onClick={addRate}>
                <Plus className="w-4 h-4 mr-2" /> Add Rate
              </Button>
            </div>

            {formData.rates.length > 0 ? (
              <div className="space-y-3">
                <div className="grid grid-cols-12 gap-2 text-xs font-semibold text-gray-500 uppercase px-1">
                  <div className="col-span-3">Date</div>
                  <div className="col-span-3">Standard Rate</div>
                  <div className="col-span-3">Selling Rate</div>
                  <div className="col-span-2">Buying Rate</div>
                  <div className="col-span-1"></div>
                </div>
                {formData.rates.map((rate, idx) => (
                  <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                    <div className="col-span-3">
                      <Input type="date" value={rate.rate_date} onChange={e => updateRate(idx, 'rate_date', e.target.value)} />
                    </div>
                    <div className="col-span-3">
                      <Input type="number" step="0.000001" value={rate.standard_rate ?? ''} onChange={e => updateRate(idx, 'standard_rate', e.target.value)} placeholder="0.00" />
                    </div>
                    <div className="col-span-3">
                      <Input type="number" step="0.000001" value={rate.selling_rate ?? ''} onChange={e => updateRate(idx, 'selling_rate', e.target.value)} placeholder="0.00" />
                    </div>
                    <div className="col-span-2">
                      <Input type="number" step="0.000001" value={rate.buying_rate ?? ''} onChange={e => updateRate(idx, 'buying_rate', e.target.value)} placeholder="0.00" />
                    </div>
                    <div className="col-span-1 flex justify-end">
                      <Button type="button" variant="ghost" size="sm" onClick={() => removeRate(idx)} className="text-red-500 hover:text-red-700 p-1">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500 italic text-center py-4 bg-gray-50 rounded-lg border border-dashed">
                No exchange rates defined. Click "Add Rate" to specify rates.
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" type="button" onClick={onClose} disabled={submitting}>Cancel</Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Saving...' : (currencyToEdit ? 'Update Currency' : 'Create Currency')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
