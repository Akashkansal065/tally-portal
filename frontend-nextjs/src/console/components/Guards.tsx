'use client'

/**
 * Guards.tsx – Declarative UI authorization guards for Operator Console.
 *
 * Implements Plan Section 5.1 & Phase 3:
 *   • <Can permission="..."> – Conditional rendering based on effective operator permissions
 *   • <CanRank minRank={...} targetRank={...}> – Conditional rendering based on hierarchy rank
 *   • <CanSuperAdmin> – Convenience guard for super_admin rank (>= 1000)
 */

import React from 'react'
import { useConsoleAuth } from '../context/ConsoleAuthContext'

interface CanProps {
  permission?: string
  anyOf?: string[]
  allOf?: string[]
  fallback?: React.ReactNode
  children: React.ReactNode
}

/**
 * <Can> renders children only if the logged-in operator holds the required permission(s).
 * Super-administrators (max_rank >= 1000) automatically satisfy all permission checks.
 */
export function Can({ permission, anyOf, allOf, fallback = null, children }: CanProps) {
  const { operator, permissions, hasPermission } = useConsoleAuth()

  if (!operator) return <>{fallback}</>

  // Super admin bypasses permission checks
  if ((operator.max_rank ?? 0) >= 1000) {
    return <>{children}</>
  }

  if (permission && !hasPermission(permission)) {
    return <>{fallback}</>
  }

  if (anyOf && anyOf.length > 0) {
    const hasAny = anyOf.some(p => permissions.has(p))
    if (!hasAny) return <>{fallback}</>
  }

  if (allOf && allOf.length > 0) {
    const hasAll = allOf.every(p => permissions.has(p))
    if (!hasAll) return <>{fallback}</>
  }

  return <>{children}</>
}

interface CanRankProps {
  /** Minimum rank required by caller to view/interact with this action */
  minRank?: number
  /** Rank of target role or operator: caller must have rank STRICTLY GREATER than targetRank */
  targetRank?: number
  fallback?: React.ReactNode
  children: React.ReactNode
}

/**
 * <CanRank> enforces hierarchy rules:
 *   1. Caller must meet `minRank` if specified.
 *   2. Caller must have rank > `targetRank` (cannot modify peers or superiors).
 */
export function CanRank({ minRank, targetRank, fallback = null, children }: CanRankProps) {
  const { operator } = useConsoleAuth()

  if (!operator) return <>{fallback}</>

  const operatorRank = operator.max_rank ?? 0

  if (minRank !== undefined && operatorRank < minRank) {
    return <>{fallback}</>
  }

  if (targetRank !== undefined && operatorRank <= targetRank) {
    return <>{fallback}</>
  }

  return <>{children}</>
}

export function CanSuperAdmin({ fallback = null, children }: { fallback?: React.ReactNode; children: React.ReactNode }) {
  const { operator } = useConsoleAuth()
  if (!operator || (operator.max_rank ?? 0) < 1000) {
    return <>{fallback}</>
  }
  return <>{children}</>
}
