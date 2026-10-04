'use client'

import { useCallback, useSyncExternalStore } from 'react'
import { ChevronDown, SlidersHorizontal, X } from 'lucide-react'
import { cn } from '@/lib/utils'

/*
 * Lets a page minimise its filter controls so the list below gets the screen.
 *
 *   const filters = useCollapsibleFilters('stocks-group')
 *   <FiltersToggle state={filters} active={['In Stock', 'Profitable']} />
 *   <div id={filters.panelId} hidden={filters.collapsed}>...filter controls...</div>
 *   <ActiveFiltersSummary state={filters} active={[...]} onReset={...} />
 *
 * The choice is remembered per page in this browser. Until someone picks, filters start minimised on
 * phones, tablets and narrow windows, and open on desktop-width screens. The panel uses `hidden`, so its controls keep their values.
 */

const STORAGE_PREFIX = 'mytally_filters_collapsed_'
// Below Tailwind's lg breakpoint the filters stack into several rows, so they start minimised there
const COMPACT_QUERY = '(max-width: 1023px)'
const listeners = new Set<() => void>()
// Choices made during this visit. They also keep the toggle working where localStorage throws (private mode).
const chosen = new Map<string, boolean>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  // Until someone picks, the default follows the screen size (e.g. a tablet rotating)
  const compact = window.matchMedia(COMPACT_QUERY)
  compact.addEventListener('change', listener)
  return () => {
    listeners.delete(listener)
    compact.removeEventListener('change', listener)
  }
}

function readCollapsed(id: string): boolean {
  const choice = chosen.get(id)
  if (choice !== undefined) return choice
  try {
    const saved = localStorage.getItem(STORAGE_PREFIX + id)
    if (saved === '1') return true
    if (saved === '0') return false
  } catch {
    // Storage blocked: fall back to the screen-size default
  }
  return window.matchMedia(COMPACT_QUERY).matches
}

export interface CollapsibleFiltersState {
  collapsed: boolean
  toggle: () => void
  panelId: string
}

export function useCollapsibleFilters(id: string): CollapsibleFiltersState {
  const collapsed = useSyncExternalStore(
    subscribe,
    () => readCollapsed(id),
    () => false, // server render: open, then the browser applies the saved choice
  )
  const toggle = useCallback(() => {
    const next = !readCollapsed(id)
    chosen.set(id, next)
    try {
      localStorage.setItem(STORAGE_PREFIX + id, next ? '1' : '0')
    } catch {
      // Not remembered after a reload, but works for this visit
    }
    listeners.forEach((listener) => listener())
  }, [id])
  return { collapsed, toggle, panelId: `filters-panel-${id}` }
}

/** The Filters button: shows how many settings are not at their defaults, and opens or minimises the panel. */
export function FiltersToggle({
  state,
  active,
  controls,
  className,
}: {
  state: CollapsibleFiltersState
  active: string[]
  /** Space-separated ids when the button hides more than one panel */
  controls?: string
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={state.toggle}
      aria-expanded={!state.collapsed}
      aria-controls={controls ?? state.panelId}
      title={state.collapsed ? 'Show filters' : 'Hide filters'}
      className={cn(
        'shrink-0 inline-flex items-center gap-1.5 h-9 px-3 rounded-lg border text-xs font-bold transition-colors cursor-pointer select-none',
        active.length > 0
          ? 'border-primary/40 bg-primary/10 text-primary hover:bg-primary/15'
          : 'border-border bg-card text-foreground hover:bg-muted/60',
        className,
      )}
    >
      <SlidersHorizontal className="w-3.5 h-3.5" aria-hidden="true" />
      <span>Filters</span>
      {active.length > 0 && (
        <span className="min-w-4 h-4 px-1 rounded-full bg-primary text-primary-foreground text-[10px] leading-4 text-center tabular-nums">
          {active.length}
        </span>
      )}
      <ChevronDown
        className={cn('w-3.5 h-3.5 transition-transform motion-reduce:transition-none', !state.collapsed && 'rotate-180')}
        aria-hidden="true"
      />
    </button>
  )
}

/** One line naming the active filters while the panel is minimised, so nothing applied is out of sight. */
export function ActiveFiltersSummary({
  state,
  active,
  onReset,
  className,
}: {
  state: CollapsibleFiltersState
  active: string[]
  onReset?: () => void
  className?: string
}) {
  if (!state.collapsed || active.length === 0) return null
  return (
    <div className={cn('flex items-center gap-2 text-[11px] text-muted-foreground min-w-0', className)}>
      <span className="truncate min-w-0">
        <span className="font-bold text-foreground">Filtered:</span> {active.join(' · ')}
      </span>
      {onReset && (
        <button
          type="button"
          onClick={onReset}
          className="shrink-0 inline-flex items-center gap-0.5 font-bold text-primary hover:underline cursor-pointer"
        >
          <X className="w-3 h-3" aria-hidden="true" />
          Reset
        </button>
      )}
    </div>
  )
}

/** Removable chips for the filters in use, for screens whose filters live in a sheet (phones). */
export function FilterChips({
  items,
  onClearAll,
  className,
}: {
  items: { key: string; label: string; onRemove: () => void }[]
  onClearAll: () => void
  className?: string
}) {
  if (items.length === 0) return null
  return (
    <div className={cn('flex items-center gap-2 overflow-x-auto scrollbar-none', className)}>
      {items.map(item => (
        <button
          key={item.key}
          type="button"
          onClick={item.onRemove}
          aria-label={`Remove filter: ${item.label}`}
          className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 pl-3 pr-2 text-sm font-semibold text-primary cursor-pointer"
        >
          {item.label}
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      ))}
      {items.length > 1 && (
        <button
          type="button"
          onClick={onClearAll}
          className="inline-flex h-9 shrink-0 items-center px-2 text-sm font-semibold text-muted-foreground hover:text-foreground cursor-pointer"
        >
          Clear all
        </button>
      )}
    </div>
  )
}
