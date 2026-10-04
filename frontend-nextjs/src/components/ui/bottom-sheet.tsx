'use client'

import { useRef, useState, type ReactNode } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

/*
 * A sheet that slides up from the bottom on phones and shows as a centred dialog on wider screens.
 * Built on Radix Dialog, so focus stays inside, Escape and the backdrop close it, and screen readers
 * announce it. On phones it can also be swiped down to close from its handle or title.
 */

const CLOSE_DISTANCE_PX = 90

interface BottomSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  /** One line under the title; also used as the accessible description */
  description?: ReactNode
  /** Extra controls next to the close button (e.g. "Reset") */
  headerAction?: ReactNode
  /** Pinned below the scrolling content, in the thumb zone (e.g. the sheet's main button) */
  footer?: ReactNode
  children: ReactNode
  className?: string
}

export function BottomSheet({
  open,
  onOpenChange,
  title,
  description,
  headerAction,
  footer,
  children,
  className,
}: BottomSheetProps) {
  const [dragY, setDragY] = useState(0)
  const startY = useRef<number | null>(null)

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.pointerType === 'mouse') return
    startY.current = e.clientY
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (startY.current === null) return
    setDragY(Math.max(0, e.clientY - startY.current))
  }
  const onPointerEnd = () => {
    if (startY.current === null) return
    startY.current = null
    if (dragY > CLOSE_DISTANCE_PX) onOpenChange(false)
    setDragY(0)
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
        <DialogPrimitive.Content
          {...(description ? {} : { 'aria-describedby': undefined })}
          style={dragY ? { transform: `translateY(${dragY}px)`, transition: 'none' } : undefined}
          className={cn(
            'fixed z-50 flex flex-col bg-card text-foreground shadow-2xl outline-none',
            // Phones: anchored to the bottom, up to 90% of the screen
            'inset-x-0 bottom-0 max-h-[90dvh] rounded-t-3xl border-t border-border',
            'data-[state=open]:animate-in data-[state=open]:slide-in-from-bottom data-[state=closed]:animate-out data-[state=closed]:slide-out-to-bottom duration-200',
            // Wider screens: a centred dialog
            'md:inset-x-auto md:bottom-auto md:left-1/2 md:top-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:w-full md:max-w-lg md:max-h-[85vh] md:rounded-3xl md:border',
            'md:data-[state=open]:slide-in-from-bottom-0 md:data-[state=open]:zoom-in-95 md:data-[state=closed]:slide-out-to-bottom-0',
            className,
          )}
        >
          <div
            className="shrink-0 touch-none select-none"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerEnd}
            onPointerCancel={onPointerEnd}
          >
            <div className="flex justify-center pt-2.5 pb-1 md:hidden" aria-hidden="true">
              <span className="h-1.5 w-10 rounded-full bg-muted-foreground/30" />
            </div>
            <div className="flex items-start gap-2 px-5 pt-2 pb-3 md:pt-5">
              <div className="min-w-0 flex-1">
                <DialogPrimitive.Title className="text-lg font-bold leading-tight text-balance">{title}</DialogPrimitive.Title>
                {description && (
                  <DialogPrimitive.Description className="mt-0.5 text-sm text-muted-foreground">{description}</DialogPrimitive.Description>
                )}
              </div>
              {headerAction}
              <DialogPrimitive.Close
                className="-mr-2 -mt-1 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </DialogPrimitive.Close>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-4">{children}</div>

          {footer && (
            <div
              className="shrink-0 border-t border-border px-5 pt-3"
              style={{ paddingBottom: 'calc(0.75rem + env(safe-area-inset-bottom, 0px))' }}
            >
              {footer}
            </div>
          )}
          {!footer && <div className="shrink-0" style={{ height: 'env(safe-area-inset-bottom, 0px)' }} />}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
