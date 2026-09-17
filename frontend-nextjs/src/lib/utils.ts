import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000'

export const authHeaders = (token?: string) => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

export const formatCurrency = (amount: number) => {
  if (amount === undefined || amount === null) return '₹0.00';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR'
  }).format(amount)
}

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

export const toTitleCase = (str: string) => {
  if (!str) return '';
  return str.replace(
    /\w\S*/g,
    (txt) => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
  );
}

