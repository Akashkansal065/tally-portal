import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/** Merge conditional class names and Tailwind utilities without conflicting rules. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Resolve the backend URL for both local development and browser deployments.
 * When a local URL is used from another host, replace the loopback hostname
 * so phones on the same network can reach the developer's machine.
 */
export const API_BASE = (() => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname
    const configured = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000'
    // If accessing via loopback (localhost or 127.0.0.1), always use 127.0.0.1
    // to avoid macOS IPv6 (::1) connection refused issues when backend binds to IPv4.
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return configured.replace(/localhost|127\.0\.0\.1/, '127.0.0.1')
    }
    // Align host dynamically for local network/LAN devices (e.g. 192.168.x.x, 10.x.x.x)
    if (configured.includes('localhost') || configured.includes('127.0.0.1')) {
      return configured.replace(/localhost|127\.0\.0\.1/, hostname)
    }
    return configured
  }
  return process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000'
})()

/** Build JSON request headers and include a bearer token when one is available. */
export const authHeaders = (token?: string) => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

/** Format an amount using Indian numbering and INR currency conventions. */
export const formatCurrency = (amount: number) => {
  if (amount === undefined || amount === null) return '₹0.00';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR'
  }).format(amount)
}

/**
 * Format an API date in the Indian locale.
 * Naive ISO timestamps are treated as UTC to keep server-rendered dates stable.
 */
export const formatDate = (dateStr: string) => {
  if (!dateStr) return '';
  let s = dateStr.trim();
  if (s.includes('T') && !s.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(s)) {
    s += 'Z';
  }
  const date = new Date(s);
  if (isNaN(date.getTime())) return dateStr;
  return date.toLocaleDateString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  });
}

/** Format a timestamp in Asia/Kolkata with optional date, seconds, and casing. */
export const formatToIST = (
  dateInput: string | Date | null | undefined,
  options?: { includeSeconds?: boolean; includeDate?: boolean; uppercase?: boolean }
): string => {
  if (!dateInput) return '--';
  
  let d: Date;
  if (typeof dateInput === 'string') {
    let s = dateInput.trim();
    if (!s) return '--';
    // If ISO string has 'T' but lacks timezone offset or 'Z', treat as UTC
    if (s.includes('T') && !s.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(s)) {
      s += 'Z';
    }
    d = new Date(s);
  } else {
    d = dateInput;
  }

  if (isNaN(d.getTime())) return '--';

  const formattedTime = d.toLocaleTimeString('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    second: options?.includeSeconds ? '2-digit' : undefined,
    hour12: true,
  });

  const timePart = options?.uppercase ? formattedTime.toUpperCase() : formattedTime.toLowerCase();

  if (options?.includeDate) {
    const datePart = d.toLocaleDateString('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
    return `${datePart} • ${timePart}`;
  }

  return timePart;
};

/** Convert each word in a label to title case for UI display. */
export const toTitleCase = (str: string) => {
  if (!str) return '';
  return str.replace(
    /\w\S*/g,
    (txt) => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
  );
}
