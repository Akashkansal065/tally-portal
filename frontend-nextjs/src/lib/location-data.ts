export type StateInfo = {
  code: string
  name: string
}

export const GST_STATE_MAP: Record<string, string> = {
  "01": "Jammu and Kashmir",
  "02": "Himachal Pradesh",
  "03": "Punjab",
  "04": "Chandigarh",
  "05": "Uttarakhand",
  "06": "Haryana",
  "07": "Delhi",
  "08": "Rajasthan",
  "09": "Uttar Pradesh",
  "10": "Bihar",
  "11": "Sikkim",
  "12": "Arunachal Pradesh",
  "13": "Nagaland",
  "14": "Manipur",
  "15": "Mizoram",
  "16": "Tripura",
  "17": "Meghalaya",
  "18": "Assam",
  "19": "West Bengal",
  "20": "Jharkhand",
  "21": "Odisha",
  "22": "Chhattisgarh",
  "23": "Madhya Pradesh",
  "24": "Gujarat",
  "26": "Dadra and Nagar Haveli and Daman and Diu",
  "27": "Maharashtra",
  "28": "Andhra Pradesh",
  "29": "Karnataka",
  "30": "Goa",
  "31": "Lakshadweep",
  "32": "Kerala",
  "33": "Tamil Nadu",
  "34": "Puducherry",
  "35": "Andaman and Nicobar Islands",
  "36": "Telangana",
  "37": "Andhra Pradesh",
  "38": "Ladakh",
  "97": "Other Territory"
}

export const INDIAN_STATES: string[] = [
  "Andaman and Nicobar Islands",
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chandigarh",
  "Chhattisgarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jammu and Kashmir",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Ladakh",
  "Lakshadweep",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Puducherry",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
  "Other Territory"
]

export const COUNTRY_LIST: string[] = [
  "India",
  "United States",
  "United Kingdom",
  "United Arab Emirates",
  "Singapore",
  "Australia",
  "Canada",
  "Germany",
  "Other"
]

/**
 * Extract 2-digit GST state code and PAN number from a 15-character GSTIN string
 */
/**
 * Extract the state name and PAN segment from a GSTIN.
 * Returns an empty object for values too short to contain a state code.
 */
export function parseGSTIN(gstin: string): { stateName?: string; panNumber?: string } {
  const clean = gstin.trim().toUpperCase()
  if (clean.length >= 2) {
    const code = clean.substring(0, 2)
    const stateName = GST_STATE_MAP[code]
    
    let panNumber: string | undefined = undefined
    if (clean.length >= 12) {
      panNumber = clean.substring(2, 12)
    }
    
    return { stateName, panNumber }
  }
  return {}
}

export const WEEKLY_OFF_DAYS: string[] = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
]

export const PROPOSED_PINCODE_CITIES: Record<string, { city: string; state?: string }> = {
  '250001': { city: 'Meerut', state: 'Uttar Pradesh' },
  '250002': { city: 'Meerut', state: 'Uttar Pradesh' },
  '250003': { city: 'Meerut', state: 'Uttar Pradesh' },
  '250004': { city: 'Meerut', state: 'Uttar Pradesh' },
  '250103': { city: 'Meerut', state: 'Uttar Pradesh' },
  '250104': { city: 'Meerut', state: 'Uttar Pradesh' },
  '250110': { city: 'Modipuram', state: 'Uttar Pradesh' },
  '250502': { city: 'Meerut', state: 'Uttar Pradesh' },
  '250401': { city: 'Mawana', state: 'Uttar Pradesh' },
  '250404': { city: 'Hastinapur', state: 'Uttar Pradesh' },
  '250342': { city: 'Sardhana', state: 'Uttar Pradesh' },
  '250611': { city: 'Baraut', state: 'Uttar Pradesh' },
  '250601': { city: 'Baghpat', state: 'Uttar Pradesh' },
  '245101': { city: 'Hapur', state: 'Uttar Pradesh' },
  '247776': { city: 'Shamli', state: 'Uttar Pradesh' },
  '247554': { city: 'Deoband', state: 'Uttar Pradesh' },
  '247001': { city: 'Saharanpur', state: 'Uttar Pradesh' },
  '251001': { city: 'Muzaffarnagar', state: 'Uttar Pradesh' },
  '251002': { city: 'Muzaffarnagar', state: 'Uttar Pradesh' },
  '251314': { city: 'Muzaffarnagar', state: 'Uttar Pradesh' },
  '201204': { city: 'Modinagar', state: 'Uttar Pradesh' },
  '201206': { city: 'Muradnagar', state: 'Uttar Pradesh' },
  '201001': { city: 'Ghaziabad', state: 'Uttar Pradesh' },
  '201002': { city: 'Ghaziabad', state: 'Uttar Pradesh' },
  '201301': { city: 'Noida', state: 'Uttar Pradesh' },
  '248001': { city: 'Dehradun', state: 'Uttarakhand' },
  '248198': { city: 'Vikasnagar', state: 'Uttarakhand' },
  '249201': { city: 'Rishikesh', state: 'Uttarakhand' },
  '249401': { city: 'Haridwar', state: 'Uttarakhand' },
  '110001': { city: 'New Delhi', state: 'Delhi' },
  '110006': { city: 'Delhi', state: 'Delhi' },
}
