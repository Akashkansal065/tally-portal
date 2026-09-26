/**
 * Intelligent search utility for products, items, ledgers, and catalog records.
 * Supports:
 * - Substring and exact matches
 * - Space/punctuation insensitive matching (e.g. "tri ply" or "tri-ply" matches "Triply")
 * - Reverse space/punctuation matching (e.g. "honeycomb" matches "honey comb")
 * - Multi-token / out-of-order matches (e.g. "cooker tri ply" matches "Triply Aura Cooker")
 * - Number-boundary aware matching (e.g. "5" matches "5 Ltr", does not match "2.5 Ltr")
 * - Relevance scoring and sorting
 */

/**
 * Strips all non-alphanumeric characters and converts to lowercase.
 * e.g. "Tri-Ply 2.5 Ltr" -> "triply25ltr"
 */
export function collapseString(s: string | undefined | null): string {
  if (!s) return ''
  return String(s).toLowerCase().replace(/[^a-z0-9]/g, '')
}

/**
 * Checks if a target string (or array of fields) matches a user query string.
 */
export function matchesSearch(
  target: string | (string | undefined | null)[] | undefined | null,
  query: string | undefined | null
): boolean {
  if (!query) return true
  const qClean = query.trim().toLowerCase()
  if (!qClean) return true
  if (!target) return false

  const targetText = Array.isArray(target)
    ? target.filter(Boolean).join(' ')
    : String(target)
  const tLower = targetText.toLowerCase()

  // 1. Direct case-insensitive substring
  if (tLower.includes(qClean)) return true

  // 2. Full collapsed match (e.g. "tri ply" in "Triply", "honeycomb" in "honey comb")
  const qCol = collapseString(qClean)
  const tCol = collapseString(tLower)
  if (qCol && tCol.includes(qCol)) return true

  // 3. Multi-token match with adjacent token merging
  const qTokens = qClean.match(/\d+(?:\.\d+)?|[a-z]+/g) || []
  if (qTokens.length === 0) return false

  const tTokens = tLower.match(/\d+(?:\.\d+)?|[a-z]+/g) || []
  const tTokenSet = new Set(tTokens)

  function tokenMatches(tok: string): boolean {
    if (!tok) return false
    // Numeric tokens (e.g. "5", "2.5", "22")
    if (/\d/.test(tok)) {
      if (tTokenSet.has(tok)) return true
      const escaped = tok.replace(/\./g, '\\.')
      const regex = new RegExp(`(?<![\\d.])${escaped}(?![\\d.])`)
      return regex.test(tLower)
    }
    // Alphabetical tokens
    if (tTokenSet.has(tok)) return true
    for (const tt of tTokens) {
      if (tt.startsWith(tok) || (tok.length >= 3 && tt.includes(tok))) return true
    }
    return tCol.includes(tok)
  }

  let idx = 0
  while (idx < qTokens.length) {
    const tok = qTokens[idx]
    if (tokenMatches(tok)) {
      idx++
      continue
    }
    // Try merge with next token (e.g. "tri" + "ply" -> "triply")
    if (idx + 1 < qTokens.length) {
      const mergedPair = tok + qTokens[idx + 1]
      if (tokenMatches(mergedPair)) {
        idx += 2
        continue
      }
    }
    // Try merge with next 2 tokens (e.g. "non" + "stick" + "pan")
    if (idx + 2 < qTokens.length) {
      const mergedTriplet = tok + qTokens[idx + 1] + qTokens[idx + 2]
      if (tokenMatches(mergedTriplet)) {
        idx += 3
        continue
      }
    }
    return false
  }
  return true
}

/**
 * Returns a relevance score for ordering search results.
 * Higher score = more relevant match.
 */
export function getSearchScore(
  target: string | (string | undefined | null)[] | undefined | null,
  query: string | undefined | null
): number {
  if (!query) return 0
  const qClean = query.trim().toLowerCase()
  if (!qClean) return 0
  if (!target) return 0

  const targetText = Array.isArray(target)
    ? target.filter(Boolean).join(' ')
    : String(target)
  const tLower = targetText.toLowerCase()

  if (tLower === qClean) return 1000

  const qCol = collapseString(qClean)
  const tCol = collapseString(tLower)

  if (tCol === qCol) return 900
  if (tLower.startsWith(qClean)) return 800 - Math.min(tLower.length, 100)
  if (tCol.startsWith(qCol)) return 700 - Math.min(tCol.length, 100)
  if (tLower.includes(qClean)) return 600 - Math.min(tLower.length, 100)
  if (qCol && tCol.includes(qCol)) return 500 - Math.min(tCol.length, 100)
  if (matchesSearch(target, query)) return 400 - Math.min(tLower.length, 100)

  return 0
}

/**
 * Filters and sorts an array of items by search relevance.
 */
export function filterAndSortBySearch<T>(
  items: T[],
  query: string | undefined | null,
  getTarget: (item: T) => string | (string | undefined | null)[]
): T[] {
  if (!query || !query.trim()) return items

  const scored: { item: T; score: number }[] = []
  for (const item of items) {
    const target = getTarget(item)
    const score = getSearchScore(target, query)
    if (score > 0) {
      scored.push({ item, score })
    }
  }

  scored.sort((a, b) => b.score - a.score)
  return scored.map((s) => s.item)
}
