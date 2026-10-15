'use client'

import React, { useState } from 'react'
import { rupees } from '@/lib/report-insights'

interface DailyPoint {
  date: string
  sales: number
  cumulative: number
  target_cumulative: number
}

interface TargetSparklineProps {
  daily: DailyPoint[]
}

export function TargetSparkline({ daily }: TargetSparklineProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  if (!daily || daily.length <= 1) return null

  const width = 300
  const height = 70
  const paddingY = 8

  // Calculate scales
  const maxVal = Math.max(
    ...daily.map(d => Math.max(d.cumulative || 0, d.target_cumulative || 0, 1))
  )

  const getY = (val: number) => {
    const ratio = Math.min(1, Math.max(0, val / maxVal))
    return height - paddingY - ratio * (height - 2 * paddingY)
  }

  const getX = (index: number) => {
    return (index / (daily.length - 1)) * width
  }

  // Construct SVG paths
  const cumulativePoints = daily.map((d, i) => `${getX(i).toFixed(1)},${getY(d.cumulative).toFixed(1)}`)
  const targetPoints = daily.map((d, i) => `${getX(i).toFixed(1)},${getY(d.target_cumulative).toFixed(1)}`)

  const cumulativePath = `M ${cumulativePoints.join(' L ')}`
  const targetPath = `M ${targetPoints.join(' L ')}`

  // Area under cumulative line
  const firstX = getX(0).toFixed(1)
  const lastX = getX(daily.length - 1).toFixed(1)
  const bottomY = (height - 2).toFixed(1)
  const areaPath = `${cumulativePath} L ${lastX},${bottomY} L ${firstX},${bottomY} Z`

  const activePoint = hoverIndex !== null ? daily[hoverIndex] : null

  return (
    <div className="relative mt-3 h-20 w-full select-none" aria-hidden="true">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-full overflow-visible"
        preserveAspectRatio="none"
        onMouseLeave={() => setHoverIndex(null)}
        onTouchEnd={() => setHoverIndex(null)}
        onMouseMove={e => {
          const rect = e.currentTarget.getBoundingClientRect()
          const x = e.clientX - rect.left
          const ratio = Math.max(0, Math.min(1, x / rect.width))
          const idx = Math.round(ratio * (daily.length - 1))
          setHoverIndex(idx)
        }}
        onTouchMove={e => {
          if (e.touches.length > 0) {
            const rect = e.currentTarget.getBoundingClientRect()
            const x = e.touches[0].clientX - rect.left
            const ratio = Math.max(0, Math.min(1, x / rect.width))
            const idx = Math.round(ratio * (daily.length - 1))
            setHoverIndex(idx)
          }
        }}
      >
        <defs>
          <linearGradient id="sparkline-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-primary, #10b981)" stopOpacity="0.25" />
            <stop offset="100%" stopColor="var(--color-primary, #10b981)" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Shaded Area */}
        <path d={areaPath} fill="url(#sparkline-fill)" />

        {/* Target Pace (dashed gray line) */}
        <path
          d={targetPath}
          fill="none"
          stroke="#94a3b8"
          strokeWidth="1.5"
          strokeDasharray="4 4"
        />

        {/* Actual Sales Cumulative (primary green solid line) */}
        <path
          d={cumulativePath}
          fill="none"
          stroke="var(--color-primary, #10b981)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Hover vertical crosshair & dots */}
        {hoverIndex !== null && (
          <g>
            <line
              x1={getX(hoverIndex)}
              y1="4"
              x2={getX(hoverIndex)}
              y2={height - 2}
              stroke="#64748b"
              strokeWidth="1"
              strokeDasharray="2 2"
            />
            {activePoint && (
              <>
                <circle
                  cx={getX(hoverIndex)}
                  cy={getY(activePoint.target_cumulative)}
                  r="3"
                  fill="#94a3b8"
                />
                <circle
                  cx={getX(hoverIndex)}
                  cy={getY(activePoint.cumulative)}
                  r="3.5"
                  fill="var(--color-primary, #10b981)"
                />
              </>
            )}
          </g>
        )}
      </svg>

      {/* Floating tooltip */}
      {activePoint && hoverIndex !== null && (
        <div
          className="pointer-events-none absolute -top-8 bg-popover/95 border border-border text-foreground px-2 py-0.5 rounded-md text-[11px] shadow-md whitespace-nowrap transform -translate-x-1/2 backdrop-blur-sm"
          style={{
            left: `${((hoverIndex / (daily.length - 1)) * 100).toFixed(1)}%`,
          }}
        >
          <span className="font-medium text-primary">{rupees(activePoint.cumulative)}</span>
          <span className="text-muted-foreground ml-1">/ {rupees(activePoint.target_cumulative)}</span>
        </div>
      )}
    </div>
  )
}
