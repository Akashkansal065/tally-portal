"use client"

import * as React from "react"
import { useState, useEffect, useRef, useCallback } from "react"
import { GripVertical, RotateCcw, ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

export interface UseReorderableColumnsOptions<TKey extends string> {
  tableKey: string
  defaultColumns: TKey[]
}

export function useReorderableColumns<TKey extends string>({
  tableKey,
  defaultColumns,
}: UseReorderableColumnsOptions<TKey>) {
  const [columns, setColumns] = useState<TKey[]>(defaultColumns)
  const [draggedCol, setDraggedCol] = useState<TKey | null>(null)
  const [dragOverCol, setDragOverCol] = useState<TKey | null>(null)
  const [dropPosition, setDropPosition] = useState<'left' | 'right'>('left')
  
  const hasDraggedRef = useRef(false)
  const touchStartPosRef = useRef<{ x: number; y: number } | null>(null)
  const touchHoldTimerRef = useRef<any>(null)
  const isTouchDraggingRef = useRef(false)
  const touchCurrentOverColRef = useRef<TKey | null>(null)
  const touchCurrentDropPosRef = useRef<'left' | 'right'>('left')

  // Load saved column order on mount (hydration-safe)
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`mytally_cols_${tableKey}`)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed)) {
          const validSaved = parsed.filter(id => defaultColumns.includes(id as TKey)) as TKey[]
          const missing = defaultColumns.filter(id => !validSaved.includes(id))
          if (validSaved.length > 0) {
            setColumns([...validSaved, ...missing])
          }
        }
      }
    } catch (e) {
      // ignore storage errors
    }
  }, [tableKey])

  // Save new column order
  const saveOrder = useCallback((newCols: TKey[]) => {
    try {
      localStorage.setItem(`mytally_cols_${tableKey}`, JSON.stringify(newCols))
    } catch (e) {}
  }, [tableKey])

  // Move column from source to target
  const moveColumn = useCallback((sourceId: TKey, targetId: TKey, pos: 'left' | 'right' = 'left') => {
    if (sourceId === targetId) return
    setColumns(prev => {
      const copy = [...prev]
      const sourceIdx = copy.indexOf(sourceId)
      const targetIdx = copy.indexOf(targetId)
      if (sourceIdx === -1 || targetIdx === -1) return prev

      copy.splice(sourceIdx, 1)
      const newTargetIdx = copy.indexOf(targetId)
      const insertIdx = pos === 'right' ? newTargetIdx + 1 : newTargetIdx
      copy.splice(insertIdx, 0, sourceId)
      saveOrder(copy)
      return copy
    })
  }, [saveOrder])

  // Move one slot left
  const moveLeft = useCallback((colId: TKey) => {
    setColumns(prev => {
      const idx = prev.indexOf(colId)
      if (idx <= 0) return prev
      const copy = [...prev]
      const temp = copy[idx - 1]
      copy[idx - 1] = copy[idx]
      copy[idx] = temp
      saveOrder(copy)
      return copy
    })
  }, [saveOrder])

  // Move one slot right
  const moveRight = useCallback((colId: TKey) => {
    setColumns(prev => {
      const idx = prev.indexOf(colId)
      if (idx === -1 || idx >= prev.length - 1) return prev
      const copy = [...prev]
      const temp = copy[idx + 1]
      copy[idx + 1] = copy[idx]
      copy[idx] = temp
      saveOrder(copy)
      return copy
    })
  }, [saveOrder])

  // Reset to default
  const resetColumns = useCallback(() => {
    setColumns(defaultColumns)
    try {
      localStorage.removeItem(`mytally_cols_${tableKey}`)
    } catch (e) {}
  }, [tableKey, defaultColumns])

  const isCustomized = columns.some((col, idx) => col !== defaultColumns[idx])

  const getHeaderProps = useCallback((colId: TKey) => ({
    draggable: true,
    'data-col-id': colId,
    onDragStart: (e: React.DragEvent) => {
      hasDraggedRef.current = true
      setDraggedCol(colId)
      e.dataTransfer.effectAllowed = 'move'
      e.dataTransfer.setData('text/plain', colId)
    },
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault()
      e.dataTransfer.dropEffect = 'move'
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
      const isRight = (e.clientX - rect.left) > rect.width / 2
      setDragOverCol(colId)
      setDropPosition(isRight ? 'right' : 'left')
    },
    onDragEnter: (e: React.DragEvent) => {
      e.preventDefault()
    },
    onDrop: (e: React.DragEvent) => {
      e.preventDefault()
      const source = (e.dataTransfer.getData('text/plain') as TKey) || draggedCol
      if (source && source !== colId) {
        moveColumn(source, colId, dropPosition)
      }
      setDraggedCol(null)
      setDragOverCol(null)
      setTimeout(() => {
        hasDraggedRef.current = false
      }, 80)
    },
    onDragEnd: () => {
      setDraggedCol(null)
      setDragOverCol(null)
      setTimeout(() => {
        hasDraggedRef.current = false
      }, 80)
    },
    // Touch events for mobile click-and-hold
    onTouchStart: (e: React.TouchEvent) => {
      const touch = e.touches[0]
      touchStartPosRef.current = { x: touch.clientX, y: touch.clientY }
      isTouchDraggingRef.current = false
      touchHoldTimerRef.current = setTimeout(() => {
        isTouchDraggingRef.current = true
        hasDraggedRef.current = true
        setDraggedCol(colId)
        if (typeof navigator !== 'undefined' && navigator.vibrate) {
          navigator.vibrate(35)
        }
      }, 200)
    },
    onTouchMove: (e: React.TouchEvent) => {
      const touch = e.touches[0]
      if (!isTouchDraggingRef.current) {
        if (touchStartPosRef.current) {
          const dx = Math.abs(touch.clientX - touchStartPosRef.current.x)
          const dy = Math.abs(touch.clientY - touchStartPosRef.current.y)
          if (dx > 8 || dy > 8) {
            clearTimeout(touchHoldTimerRef.current)
          }
        }
        return
      }

      if (e.cancelable) {
        e.preventDefault()
      }
      const el = document.elementFromPoint(touch.clientX, touch.clientY)
      const targetTh = el?.closest('th[data-col-id]') as HTMLElement | null
      if (targetTh) {
        const targetId = targetTh.getAttribute('data-col-id') as TKey
        if (targetId) {
          const rect = targetTh.getBoundingClientRect()
          const isRight = (touch.clientX - rect.left) > rect.width / 2
          touchCurrentOverColRef.current = targetId
          touchCurrentDropPosRef.current = isRight ? 'right' : 'left'
          setDragOverCol(targetId)
          setDropPosition(isRight ? 'right' : 'left')
        }
      }
    },
    onTouchEnd: () => {
      clearTimeout(touchHoldTimerRef.current)
      if (isTouchDraggingRef.current) {
        const targetId = touchCurrentOverColRef.current
        const dropPos = touchCurrentDropPosRef.current
        if (colId && targetId && colId !== targetId) {
          moveColumn(colId, targetId, dropPos)
        }
        setDraggedCol(null)
        setDragOverCol(null)
        isTouchDraggingRef.current = false
        touchCurrentOverColRef.current = null
        setTimeout(() => {
          hasDraggedRef.current = false
        }, 80)
      }
    },
  }), [draggedCol, dropPosition, moveColumn])

  return {
    columns,
    draggedCol,
    dragOverCol,
    dropPosition,
    hasDraggedRef,
    moveColumn,
    moveLeft,
    moveRight,
    resetColumns,
    isCustomized,
    getHeaderProps,
  }
}

export interface DraggableThProps<TKey extends string> {
  id?: TKey
  colId?: TKey
  label?: React.ReactNode
  reorderProps?: {
    columns: TKey[]
    getHeaderProps: (colId: TKey) => any
    draggedCol: TKey | null
    dragOverCol: TKey | null
    dropPosition: 'left' | 'right'
    hasDraggedRef: React.RefObject<boolean>
    moveLeft: (colId: TKey) => void
    moveRight: (colId: TKey) => void
  }
  columns?: TKey[]
  getHeaderProps?: (colId: TKey) => any
  draggedCol?: TKey | null
  dragOverCol?: TKey | null
  dropPosition?: 'left' | 'right'
  hasDraggedRef?: React.RefObject<boolean>
  moveLeft?: (colId: TKey) => void
  moveRight?: (colId: TKey) => void
  onClick?: (e: React.MouseEvent) => void
  className?: string
  align?: 'left' | 'right' | 'center'
  minWidth?: string
  sticky?: boolean
  children?: React.ReactNode
  title?: string
}

export function DraggableTh<TKey extends string>(props: DraggableThProps<TKey>) {
  const colId = (props.id || props.colId) as TKey
  const columns = props.columns || props.reorderProps?.columns || []
  const getHeaderProps = props.getHeaderProps || props.reorderProps?.getHeaderProps || (() => ({}))
  const draggedCol = props.draggedCol !== undefined ? props.draggedCol : (props.reorderProps?.draggedCol ?? null)
  const dragOverCol = props.dragOverCol !== undefined ? props.dragOverCol : (props.reorderProps?.dragOverCol ?? null)
  const dropPosition = props.dropPosition || props.reorderProps?.dropPosition || 'left'
  const hasDraggedRef = props.hasDraggedRef || props.reorderProps?.hasDraggedRef || { current: false }
  const moveLeft = props.moveLeft || props.reorderProps?.moveLeft || (() => {})
  const moveRight = props.moveRight || props.reorderProps?.moveRight || (() => {})
  const children = props.children ?? props.label
  const { onClick, className, align = 'left', minWidth, sticky, title } = props

  const isDragging = draggedCol === colId
  const isOver = dragOverCol === colId && !isDragging
  const headerProps = getHeaderProps(colId)
  const colIndex = columns.indexOf(colId)
  const canMoveLeft = colIndex > 0
  const canMoveRight = colIndex !== -1 && colIndex < columns.length - 1

  const handleClick = (e: React.MouseEvent) => {
    if (hasDraggedRef.current) return
    if (onClick) onClick(e)
  }

  return (
    <th
      {...headerProps}
      style={minWidth ? { minWidth } : undefined}
      title={title || "Click & hold to move column left/right • Click to sort"}
      onClick={handleClick}
      className={cn(
        "relative select-none transition-all py-2.5 px-2 text-xs font-bold group/th touch-manipulation",
        "cursor-grab active:cursor-grabbing",
        align === 'right' ? "text-right" : align === 'center' ? "text-center" : "text-left",
        isDragging && "opacity-40 bg-primary/20 scale-[0.98] ring-1 ring-primary",
        isOver && dropPosition === 'left' && "before:absolute before:left-0 before:top-0 before:bottom-0 before:w-1.5 before:bg-primary before:z-30 bg-primary/10",
        isOver && dropPosition === 'right' && "after:absolute after:right-0 after:top-0 after:bottom-0 after:w-1.5 after:bg-primary after:z-30 bg-primary/10",
        sticky && "sticky left-0 bg-muted/95 z-20 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)]",
        className
      )}
    >
      <div
        className={cn(
          "inline-flex items-center gap-1.5 w-full",
          align === 'right' ? "justify-end" : align === 'center' ? "justify-center" : "justify-start"
        )}
      >
        {/* Subtle Grip Icon */}
        <span
          className="opacity-30 group-hover/th:opacity-100 text-muted-foreground hover:text-primary transition-opacity shrink-0 cursor-grab active:cursor-grabbing"
          title="Click and hold to drag column left or right"
        >
          <GripVertical className="h-3 w-3" />
        </span>

        {/* Content */}
        <div className="flex-1 truncate">{children}</div>

        {/* Quick Left / Right Nudge Arrows on Hover / Focus */}
        <div
          className="hidden group-hover/th:flex items-center gap-0.5 shrink-0 opacity-80 hover:opacity-100 transition-opacity ml-1"
          onClick={e => e.stopPropagation()}
        >
          {canMoveLeft && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                moveLeft(colId)
              }}
              title="Move column left"
              className="p-0.5 rounded hover:bg-background/80 hover:text-primary text-muted-foreground transition-colors cursor-pointer"
            >
              <ChevronLeft className="h-3 w-3" />
            </button>
          )}
          {canMoveRight && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                moveRight(colId)
              }}
              title="Move column right"
              className="p-0.5 rounded hover:bg-background/80 hover:text-primary text-muted-foreground transition-colors cursor-pointer"
            >
              <ChevronRight className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
    </th>
  )
}

export interface ResetColumnsButtonProps {
  isCustomized: boolean
  onReset?: () => void
  resetColumns?: () => void
  label?: string
  className?: string
}

export function ResetColumnsButton({
  isCustomized,
  onReset,
  resetColumns,
  label = "Reset Columns",
  className,
}: ResetColumnsButtonProps) {
  if (!isCustomized) return null
  const handleReset = onReset || resetColumns

  return (
    <button
      type="button"
      onClick={handleReset}
      title="Restore columns to original order"
      className={cn(
        "inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-lg",
        "bg-amber-500/10 text-amber-700 dark:text-amber-400 hover:bg-amber-500/20",
        "border border-amber-500/30 transition-all cursor-pointer shadow-xs",
        className
      )}
    >
      <RotateCcw className="h-3 w-3" />
      <span>{label}</span>
    </button>
  )
}
