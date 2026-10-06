import {
  BarChart3,
  Bell,
  BookOpen,
  Calendar,
  Clock,
  CloudOff,
  FileSpreadsheet,
  FileText,
  FolderTree,
  History,
  Home,
  IndianRupee,
  Landmark,
  Layers,
  MapPin,
  Package,
  Scale,
  Shield,
  ShoppingCart,
  Tag,
  Users,
  Wallet,
  Warehouse,
  Coins,
  Receipt,
  PartyPopper,
  type LucideIcon,
} from 'lucide-react'
import type { UserPermissions } from '@/context/AuthContext'

/*
 * Every screen the app navigates to, with who may see it. The bottom tab bar and the "More" sheet both read
 * from here, so a module can't appear in one place and be missing (or wrongly visible) in the other.
 */

type Can = (module: string, action: 'create' | 'read' | 'update' | 'delete') => boolean

export interface NavContext {
  permissions: UserPermissions
  can: Can
  isAdmin: boolean
}

export type NavGroup = 'field' | 'accounts' | 'inventory' | 'reports' | 'masters' | 'admin'

export interface NavModule {
  id: string
  href: string
  label: string
  /** Short label for the tab bar */
  tabLabel?: string
  icon: LucideIcon
  group: NavGroup
  /** Extra words the More sheet's search should match */
  keywords?: string
  visible: (ctx: NavContext) => boolean
}

export const NAV_GROUP_LABELS: Record<NavGroup, string> = {
  field: 'Sales & field',
  accounts: 'Accounts',
  inventory: 'Inventory',
  reports: 'Reports & GST',
  masters: 'Masters',
  admin: 'Admin & tools',
}

const hasStockAccess = (p: UserPermissions) => p.stockScope !== 'catalog_only'
const hasVouchers = ({ permissions: p, can }: NavContext) => Boolean((p.showVouchers ?? p.showReceipts) && can('vouchers', 'read'))

export const HOME: NavModule = {
  id: 'home', href: '/', label: 'Home', icon: Home, group: 'field', visible: () => true,
}

export const NAV_MODULES: NavModule[] = [
  // Sales & field
  { id: 'customers', href: '/customers', label: 'Customers', icon: Users, group: 'field', keywords: 'shops directory parties',
    visible: ({ permissions: p, can }) => Boolean(p.showCustomers && can('customers', 'read')) },
  { id: 'greetings', href: '/greetings', label: 'Greetings', icon: PartyPopper, group: 'field', keywords: 'festival wishes diwali whatsapp inactive customers',
    visible: ({ permissions: p }) => p.showReports },
  { id: 'check-in', href: '/check-in', label: 'Check-in', icon: MapPin, group: 'field', keywords: 'visit shop gps',
    visible: ({ permissions: p }) => p.showCheckIn },
  { id: 'planner', href: '/planner', label: 'Beat planner', icon: Calendar, group: 'field', keywords: 'route plan daily',
    visible: ({ permissions: p }) => p.showCheckIn },
  { id: 'visit-log', href: '/check-in/history', label: 'Visit log', icon: History, group: 'field', keywords: 'history audits check-ins',
    visible: ({ permissions: p }) => p.showCheckIn },
  { id: 'orders', href: '/temporders', label: 'Orders', icon: ShoppingCart, group: 'field', keywords: 'sales order',
    visible: ({ permissions: p }) => p.showOrders },
  { id: 'payments', href: '/payments', label: 'Payments', icon: IndianRupee, group: 'field', keywords: 'collect receipt collection',
    visible: ({ permissions: p }) => p.showPayments },
  { id: 'attendance', href: '/attendance', label: 'Attendance', icon: Clock, group: 'field', keywords: 'punch shift',
    visible: ({ permissions: p }) => p.showAttendance },
  { id: 'expenses', href: '/expenses', label: 'Expenses', icon: Wallet, group: 'field', keywords: 'claims',
    visible: ({ permissions: p }) => p.showExpenses },

  // Accounts
  { id: 'vouchers', href: '/vouchers', label: 'Vouchers', icon: FileText, group: 'accounts', keywords: 'sales purchase invoice',
    visible: hasVouchers },
  { id: 'ledgers', href: '/ledgers', label: 'Ledgers', icon: BookOpen, group: 'accounts', keywords: 'accounts statement',
    visible: ({ permissions: p, can }) => Boolean(p.showLedger || can('ledgers', 'read')) },
  { id: 'outstanding', href: '/outstanding', label: 'Outstanding', icon: Receipt, group: 'accounts', keywords: 'debtors aging reminders dues',
    visible: ({ permissions: p, can }) => Boolean(p.showPayments && can('payments', 'read')) },
  { id: 'bank-recon', href: '/bank-recon', label: 'Bank reconciliation', icon: Landmark, group: 'accounts', keywords: 'bank recon brs',
    visible: ({ can }) => can('vouchers', 'read') },

  // Inventory
  { id: 'stocks', href: '/stocks', label: 'Stock', icon: Layers, group: 'inventory', keywords: 'stock summary inventory items',
    visible: ({ permissions: p, can }) => Boolean((p.showStocks || can('stock_items', 'read')) && hasStockAccess(p)) },
  { id: 'stock-groups', href: '/masters/stock-groups', label: 'Stock groups', icon: FolderTree, group: 'inventory',
    visible: ({ permissions: p, can }) => can('stock_groups', 'read') && hasStockAccess(p) },
  { id: 'stock-categories', href: '/masters/stock-categories', label: 'Stock categories', icon: Tag, group: 'inventory',
    visible: ({ permissions: p, can }) => can('stock_categories', 'read') && hasStockAccess(p) },
  { id: 'units', href: '/masters/units', label: 'Units', icon: Scale, group: 'inventory', keywords: 'uom',
    visible: ({ permissions: p, can }) => can('units', 'read') && hasStockAccess(p) },
  { id: 'godowns', href: '/masters/godowns', label: 'Godowns', icon: Warehouse, group: 'inventory', keywords: 'warehouse location',
    visible: ({ permissions: p, can }) => can('godowns', 'read') && hasStockAccess(p) },
  { id: 'price-lists', href: '/masters/price-lists', label: 'Price lists', icon: Coins, group: 'inventory', keywords: 'rates price levels',
    visible: ({ permissions: p, can }) => can('price_lists', 'read') && hasStockAccess(p) },
  { id: 'bom', href: '/inventory/bom', label: 'BOM', icon: Package, group: 'inventory', keywords: 'bill of materials manufacturing',
    visible: ({ permissions: p, can }) => can('bom', 'read') && hasStockAccess(p) },

  // Reports & GST
  { id: 'reports', href: '/reports', label: 'Reports', icon: BarChart3, group: 'reports', keywords: 'analytics profit loss balance sheet',
    visible: ({ permissions: p }) => p.showReports },
  { id: 'gst', href: '/gst', label: 'GST returns', tabLabel: 'GST', icon: FileSpreadsheet, group: 'reports', keywords: 'gstr einvoice tax',
    visible: ({ permissions: p }) => p.showGst },

  // Accounting masters
  { id: 'ledger-groups', href: '/ledgers/groups', label: 'Account groups', icon: Layers, group: 'masters',
    visible: ({ can }) => can('ledger_groups', 'read') },
  { id: 'cost-categories', href: '/masters/cost-categories', label: 'Cost categories', icon: Layers, group: 'masters',
    visible: ({ can }) => can('cost_categories', 'read') },
  { id: 'cost-centres', href: '/masters/cost-centres', label: 'Cost centres', icon: FolderTree, group: 'masters',
    visible: ({ can }) => can('cost_centres', 'read') },
  { id: 'cost-centre-classes', href: '/masters/cost-centre-classes', label: 'Cost centre classes', icon: BookOpen, group: 'masters',
    visible: ({ can }) => can('cost_centre_classes', 'read') },
  { id: 'currencies', href: '/masters/currencies', label: 'Currencies', icon: Coins, group: 'masters',
    visible: ({ can }) => can('currencies', 'read') },
  { id: 'voucher-types', href: '/masters/voucher-types', label: 'Voucher types', icon: FileText, group: 'masters',
    visible: ({ can }) => can('voucher_types', 'read') },

  // Admin & tools
  { id: 'notifications', href: '/notifications', label: 'Notifications', icon: Bell, group: 'admin', keywords: 'alerts approvals settings push',
    visible: () => true },
  { id: 'admin', href: '/admin', label: 'Admin', icon: Shield, group: 'admin', keywords: 'users roles permissions devices sync',
    visible: ({ isAdmin }) => isAdmin },
  { id: 'sync', href: '/sync', label: 'Offline sync', icon: CloudOff, group: 'admin', keywords: 'pending queue offline',
    visible: ({ permissions: p }) => p.showCheckIn },
]

/*
 * The tabs between Home and More, picked from what the person works on most. Phones show the first
 * three; wider screens show more of the same list. Each list is a preference order: modules the user
 * can't open are skipped and the next one is used, and the remaining slots fall back to the general
 * order so nobody gets fewer than they could have.
 */
const TAB_PREFERENCES = {
  admin: ['customers', 'stocks', 'reports', 'vouchers', 'ledgers', 'outstanding', 'orders', 'gst'],
  field: ['customers', 'orders', 'payments', 'check-in', 'attendance', 'planner', 'expenses', 'outstanding'],
  accounts: ['vouchers', 'ledgers', 'stocks', 'reports', 'payments', 'outstanding', 'gst', 'bank-recon'],
}

/** Tabs (after Home) on phones; wider screens show up to MAX_TABS. */
export const PHONE_TAB_COUNT = 3
export const MAX_TABS = 7
const FALLBACK_ORDER = ['customers', 'vouchers', 'ledgers', 'stocks', 'orders', 'payments', 'reports', 'attendance', 'gst', 'expenses']

/*
 * Home's "Quick access" row: the next screens each role reaches for after its tabs. Modules already
 * in the tab bar are skipped, and any slots left over take the person's other screens in menu order.
 */
const QUICK_PREFERENCES = {
  admin: ['vouchers', 'ledgers', 'outstanding', 'orders', 'payments', 'gst', 'bank-recon', 'admin'],
  field: ['check-in', 'planner', 'attendance', 'expenses', 'visit-log', 'stocks', 'sync'],
  accounts: ['outstanding', 'payments', 'gst', 'bank-recon', 'customers', 'expenses', 'orders'],
}

type Persona = keyof typeof TAB_PREFERENCES

function personaOf(ctx: NavContext): Persona {
  const p = ctx.permissions
  if (ctx.isAdmin) return 'admin'
  return p.showCheckIn || (p.showOrders && p.showCustomers) ? 'field' : 'accounts'
}

function pick(available: NavModule[], order: string[], limit: number, skip: NavModule[] = []): NavModule[] {
  const byId = new Map(available.map(m => [m.id, m]))
  const picked: NavModule[] = []
  for (const candidate of [...order.map(id => byId.get(id)), ...available]) {
    if (candidate && !skip.includes(candidate) && !picked.includes(candidate)) picked.push(candidate)
    if (picked.length === limit) break
  }
  return picked
}

export function visibleModules(ctx: NavContext): NavModule[] {
  return NAV_MODULES.filter(m => m.visible(ctx))
}

export function tabModules(ctx: NavContext, count = PHONE_TAB_COUNT): NavModule[] {
  const available = visibleModules(ctx)
  const preferred = [...TAB_PREFERENCES[personaOf(ctx)], ...FALLBACK_ORDER]
  return pick(available.filter(m => preferred.includes(m.id)), preferred, count)
}

export function quickModules(ctx: NavContext, limit: number): NavModule[] {
  return pick(visibleModules(ctx), QUICK_PREFERENCES[personaOf(ctx)], limit, tabModules(ctx))
}

/** True when the current path is this module or one of its sub-pages. */
export function isActivePath(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/'
  return pathname === href || pathname.startsWith(`${href}/`)
}

/** Admin check shared by the header and the navigation (role names come from the backend as typed by admins). */
export function isAdminUser(permissions: Pick<UserPermissions, 'isAdmin'> | undefined, role: string | undefined): boolean {
  return Boolean(permissions?.isAdmin || ['admin', 'owner', 'superadmin'].includes((role ?? '').toLowerCase()))
}
