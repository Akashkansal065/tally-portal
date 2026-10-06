'use client'

import { useState } from 'react'
import { Loader2, Mail } from 'lucide-react'
import { toast } from 'sonner'
import type jsPDF from 'jspdf'
import { BottomSheet } from '@/components/ui/bottom-sheet'
import { emailDocument } from '@/lib/reminders'

export interface EmailPdfRequest {
  ledgerId: number
  to: string
  subject: string
  message: string
  /** "Invoice S-101": shown in the customer's reminder history */
  reference: string
  filename: string
  makePdf: () => Promise<jsPDF>
}

/** Email an invoice or statement PDF to the customer through Gmail (needs the Email switch in Admin → Integrations). */
export function EmailPdfSheet({ request, token, onClose }: { request: EmailPdfRequest | null; token: string; onClose: () => void }) {
  return (
    <BottomSheet
      open={request !== null}
      onOpenChange={open => { if (!open) onClose() }}
      title={`Email ${request?.reference ?? ''}`}
      description="Sent from the business Gmail account with the PDF attached. It's saved in the customer's reminder history."
    >
      {request && <EmailPdfForm key={request.reference} request={request} token={token} onDone={onClose} />}
    </BottomSheet>
  )
}

function EmailPdfForm({ request, token, onDone }: { request: EmailPdfRequest; token: string; onDone: () => void }) {
  const [to, setTo] = useState(request.to)
  const [subject, setSubject] = useState(request.subject)
  const [message, setMessage] = useState(request.message)
  const [sending, setSending] = useState(false)
  const field = 'w-full rounded-xl border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30'

  const send = async () => {
    setSending(true)
    try {
      const doc = await request.makePdf()
      const log = await emailDocument(token, {
        ledgerId: request.ledgerId, to: to.trim(), subject: subject.trim(), message, reference: request.reference,
        pdf: doc.output('blob'), filename: request.filename,
      })
      if (log.status === 'sent') {
        toast.success(`Emailed to ${log.recipient}`)
        onDone()
      } else if (log.status === 'dry_run') {
        toast.success('Dry run: logged, not sent')
        onDone()
      } else {
        toast.error(log.detail || 'Not sent')
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not send the email')
    } finally {
      setSending(false)
    }
  }

  return (
    <form className="space-y-3" onSubmit={e => { e.preventDefault(); send() }}>
      <label className="block text-sm">
        <span className="mb-1 block font-semibold">To</span>
        <input type="email" required value={to} onChange={e => setTo(e.target.value)} placeholder="customer@example.com" className={`${field} h-10`} />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block font-semibold">Subject</span>
        <input required maxLength={200} value={subject} onChange={e => setSubject(e.target.value)} className={`${field} h-10`} />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block font-semibold">Message</span>
        <textarea rows={5} maxLength={5000} value={message} onChange={e => setMessage(e.target.value)} className={field} />
      </label>
      <p className="text-xs text-muted-foreground">Attached: {request.filename}</p>
      <button type="submit" disabled={sending || !to.trim() || !subject.trim()}
        className="flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-bold text-primary-foreground disabled:opacity-50 cursor-pointer">
        {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />} Send email
      </button>
    </form>
  )
}
