'use client'

import { Suspense, useEffect, useRef } from 'react'
import { useSearchParams } from 'next/navigation'

/*
 * Deep links (from notifications) carry the screen state in the query: ?tab=, ?status=, ?order=, ... Pages
 * render <LinkParams onChange={...} /> to apply them on arrival and whenever the query changes while the
 * page is already open (a second notification for the same screen used to do nothing).
 */

export function LinkParams({ onChange }: { onChange: (params: URLSearchParams) => void }) {
  return (
    <Suspense fallback={null}>
      <Listener onChange={onChange} />
    </Suspense>
  )
}

function Listener({ onChange }: { onChange: (params: URLSearchParams) => void }) {
  const params = useSearchParams()
  const query = params.toString()
  const latest = useRef(onChange)

  useEffect(() => {
    latest.current = onChange
  })

  useEffect(() => {
    latest.current(new URLSearchParams(query))
  }, [query])

  return null
}

/** Positive integer from a query value, or null. */
export function idParam(value: string | null): number | null {
  const n = Number(value)
  return Number.isInteger(n) && n > 0 ? n : null
}

/** Ring shown on the record a notification pointed at. */
export const LINKED_RECORD = 'ring-2 ring-primary ring-offset-2 ring-offset-background'

/**
 * Scrolls the linked record into view once it's on screen. Mark the record with data-link-target={key};
 * when a page renders it twice (table on desktop, cards on phones) the visible copy is used.
 */
export function useScrollToLinked(key: string | null, ready: unknown) {
  useEffect(() => {
    if (!key) return
    const matches = document.querySelectorAll<HTMLElement>(`[data-link-target="${CSS.escape(key)}"]`)
    const visible = Array.from(matches).find(el => el.offsetParent !== null)
    visible?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [key, ready])
}
