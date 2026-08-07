export const GST_REGISTRATION_TYPES = [
  'Regular',
  'Composition',
  'Unregistered/Consumer',
  'Government entity / TDS',
  'Regular - SEZ',
  'Regular-Deemed Exporter',
  'Regular-Exports (EOU)',
  'e-Commerce Operator',
  'Input Service Distributor',
  'Embassy/UN Body',
  'Non-Resident Taxpayer',
  'Unknown',
] as const

export type GSTRegistrationType = typeof GST_REGISTRATION_TYPES[number]

/**
 * Returns whether GSTIN is required for a given registration type
 */
export const isGSTINRequired = (type?: string): boolean => {
  if (!type) return false
  return [
    'Regular',
    'Composition',
    'Government entity / TDS',
    'Regular - SEZ',
    'Regular-Deemed Exporter',
    'Regular-Exports (EOU)',
    'e-Commerce Operator',
    'Input Service Distributor',
    'Embassy/UN Body',
    'Non-Resident Taxpayer'
  ].includes(type)
}
