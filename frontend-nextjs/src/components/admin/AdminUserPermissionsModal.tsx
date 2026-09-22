"use client";

import { useState, useMemo, useCallback } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Landmark, Layers, BarChart3, Laptop, User, Users, Shield, Ban, CheckCircle2, MapPin, Receipt, Wallet, KeyRound, Eye, EyeOff, Clock, FileSpreadsheet, Store, ShoppingCart, FileText, IndianRupee } from "lucide-react";

const ALL_REPORT_CATEGORIES = [
  "Accounting Reports",
  "Inventory Reports",
  "Purchase Reports",
  "Outstandings",
  "Tax & Compliance",
  "Top Reports",
];

type UserItem = {
  id: number;
  username: string;
  role: string;
  showLedger: boolean;
  showSalesLedgers: boolean;
  showPurchaseLedgers: boolean;
  showVouchers?: boolean;
  showReceipts: boolean;
  showPayments: boolean;
  showExpenses: boolean;
  showAttendance: boolean;
  showStocks: boolean;
  showReports: boolean;
  showOrders: boolean;
  showCheckIn: boolean;
  showGst: boolean;
  showCustomers?: boolean;
  ledgerScope: string;
  stockScope: string;
  allowedStockGroups: string | null;
  allowedLedgerGroups: string | null;
  allowedReportCategories: string | null;
  isActive: boolean;
  createdAt: Date;
};

interface AdminUserPermissionsModalProps {
  user: UserItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isPending: boolean;
  availableLedgerGroups: string[];
  availableStockGroups: string[];
  availableRoles?: {
    role_id: number;
    name: string;
    description?: string;
    permissions?: {
      module_id: number;
      code: string;
      name: string;
      can_create: boolean;
      can_read: boolean;
      can_update: boolean;
      can_delete: boolean;
    }[];
  }[];
  onRoleChange: (userId: number, role: string) => void;
  onPermissionToggle: (userId: number, field: "showLedger" | "showStocks" | "showReports" | "showOrders" | "showCheckIn" | "showSalesLedgers" | "showPurchaseLedgers" | "showVouchers" | "showReceipts" | "showPayments" | "showExpenses" | "showAttendance" | "showGst" | "showCustomers", value: boolean) => void;
  onScopeChange: (userId: number, field: "ledgerScope" | "stockScope", value: string) => void;
  onAllowedGroupsChange: (
    userId: number,
    field: "allowedLedgerGroups" | "allowedStockGroups" | "allowedReportCategories",
    groupName: string,
    isChecked: boolean
  ) => void;
  onStatusChange: (userId: number, currentStatus: boolean) => void;
  onResetPassword: (userId: number, password: string) => Promise<{ success?: boolean; error?: string }>;
}

function GroupCheckboxes({
  groups,
  selected,
  onChange,
  disabled,
}: {
  groups: string[];
  selected: string | null;
  onChange: (group: string, checked: boolean) => void;
  disabled: boolean;
}) {
  const selectedList = selected ? selected.split(",").filter(Boolean) : [];

  return (
    <div className="mt-2 max-h-36 overflow-y-auto border border-border rounded-md p-2 bg-background/50 text-sm space-y-1 no-scrollbar">
      {groups.length === 0 && <span className="text-muted-foreground italic text-xs">No groups</span>}
      {groups.map((group) => {
        const isSelected = selectedList.includes(group);
        return (
          <label key={group} className="flex items-center gap-2 cursor-pointer py-1.5 px-2 hover:bg-muted/50 rounded transition-colors">
            <input
              type="checkbox"
              className="w-4 h-4 rounded text-primary focus:ring-primary border-border"
              checked={isSelected}
              onChange={(e) => onChange(group, e.target.checked)}
              disabled={disabled}
            />
            <span className="truncate text-xs font-medium text-foreground" title={group}>
              {group}
            </span>
          </label>
        );
      })}
    </div>
  );
}

export function AdminUserPermissionsModal({
  user,
  open,
  onOpenChange,
  isPending,
  availableLedgerGroups,
  availableStockGroups,
  availableRoles = [],
  onRoleChange,
  onPermissionToggle,
  onScopeChange,
  onAllowedGroupsChange,
  onStatusChange,
  onResetPassword,
}: AdminUserPermissionsModalProps) {
  const [newPassword, setNewPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const activeRoleObj = useMemo(() => {
    if (!user) return null;
    return availableRoles.find(
      (r) =>
        r.name.toLowerCase() === user.role.toLowerCase() ||
        String(r.role_id) === String((user as any).role_id)
    );
  }, [availableRoles, user?.role, (user as any)?.role_id]);

  const isModuleEnabledInRole = useCallback(
    (moduleCode: string): boolean => {
      if (!user) return false;
      const roleLower = user.role.toLowerCase();
      // Admin / Superadmin / Owner bypass role restrictions
      if (roleLower === "admin" || roleLower === "superadmin" || roleLower === "owner") {
        return true;
      }
      // If roles or permissions are not yet loaded, default to true
      if (!activeRoleObj || !activeRoleObj.permissions || activeRoleObj.permissions.length === 0) {
        return true;
      }
      const perm = activeRoleObj.permissions.find(
        (p) => p.code.toLowerCase() === moduleCode.toLowerCase()
      );
      return perm ? Boolean(perm.can_read) : false;
    },
    [user, activeRoleObj]
  );

  if (!user) return null;

  const hasAnyCustomerTab =
    isModuleEnabledInRole("customers") ||
    isModuleEnabledInRole("ledger_customer") ||
    isModuleEnabledInRole("orders") ||
    isModuleEnabledInRole("visits");

  const showSupplierLedgerToggle = isModuleEnabledInRole("ledger_supplier");
  const showVouchersToggle = isModuleEnabledInRole("vouchers");
  const showPaymentsToggle = isModuleEnabledInRole("payments");
  const hasAnyAccounting = showSupplierLedgerToggle || showVouchersToggle;

  const canShowLedgerScope =
    (isModuleEnabledInRole("ledger_customer") && user.showSalesLedgers) ||
    (isModuleEnabledInRole("ledger_supplier") && user.showPurchaseLedgers);

  const showAccountingSection = hasAnyAccounting || canShowLedgerScope;

  const showExpensesToggle = isModuleEnabledInRole("expenses");
  const showAttendanceToggle = isModuleEnabledInRole("attendance");
  const showGstToggle = isModuleEnabledInRole("gst");
  const hasAnyOperations = showExpensesToggle || showAttendanceToggle || showGstToggle;

  const hasAnyConfigurableModule =
    hasAnyCustomerTab ||
    showAccountingSection ||
    showPaymentsToggle ||
    isModuleEnabledInRole("inventory") ||
    isModuleEnabledInRole("reports") ||
    hasAnyOperations;

  const handleResetClick = async () => {
    if (!newPassword) {
      toast.error("Please enter a new password");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("Password must be at least 6 characters long");
      return;
    }

    setIsResetting(true);
    try {
      const res = await onResetPassword(user.id, newPassword);
      if (res.success) {
        setNewPassword("");
      }
    } catch (err) {
      toast.error("An unexpected error occurred.");
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader className="border-b pb-4">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2 text-lg font-bold">
              <Shield className="h-5 w-5 text-primary" />
              Edit Permissions
            </DialogTitle>
            <Badge variant="outline" className="text-xs font-semibold capitalize bg-primary/5 text-primary border-primary/20">
              Role: {activeRoleObj?.name || user.role}
            </Badge>
          </div>
          <DialogDescription className="text-xs text-muted-foreground pt-1">
            Configure access overrides for <strong>{user.username}</strong>. Only modules permitted by the <strong>{activeRoleObj?.name || user.role}</strong> master role are configurable below.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* User Status / Role Row */}
          <div className="flex flex-col gap-4 bg-muted/20 p-4 rounded-lg border">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-semibold">Account Status</Label>
              <Badge
                variant={user.isActive ? "default" : "destructive"}
                className={`text-xs py-0.5 px-2.5 cursor-pointer hover:opacity-85 transition-opacity ${user.isActive ? "bg-green-500/10 text-green-600 border-green-500/20" : ""}`}
                onClick={() => onStatusChange(user.id, user.isActive)}
              >
                {user.isActive ? (
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Active
                  </span>
                ) : (
                  <span className="flex items-center gap-1">
                    <Ban className="w-3.5 h-3.5" /> Disabled
                  </span>
                )}
              </Badge>
            </div>

            <div className="flex items-center justify-between gap-4 border-t pt-3">
              <Label className="text-sm font-semibold">User Role</Label>
              <select
                value={user.role.toLowerCase()}
                onChange={(e) => onRoleChange(user.id, e.target.value)}
                disabled={isPending}
                className="bg-background border border-input text-foreground text-sm rounded-md px-2.5 py-1.5 focus:ring-1 focus:ring-primary focus:outline-none min-w-[140px] font-medium capitalize"
              >
                {availableRoles.length > 0 ? (
                  availableRoles.map((r) => (
                    <option key={r.role_id} value={r.name.toLowerCase()}>
                      {r.name}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="sales">Sales</option>
                    <option value="admin">Admin</option>
                  </>
                )}
              </select>
            </div>
          </div>

          {/* Section: Reset Password */}
          <div className="flex flex-col gap-3 bg-muted/20 p-4 rounded-lg border">
            <div className="flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-primary" />
              <Label className="text-sm font-semibold">Reset Password</Label>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <div className="relative flex-1">
                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter new password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  disabled={isResetting || isPending}
                  className="w-full px-3 py-1.5 rounded-lg border border-input bg-background text-sm focus:outline-none focus:ring-1 focus:ring-primary font-medium text-foreground pr-10 h-9"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  disabled={isResetting || isPending}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <Button
                onClick={handleResetClick}
                disabled={isResetting || isPending || !newPassword}
                size="sm"
                className="h-9"
              >
                {isResetting ? "Resetting..." : "Reset"}
              </Button>
            </div>
            <p className="text-[10px] text-muted-foreground font-medium">
              Password must be at least 6 characters long.
            </p>
          </div>

          {/* Section: Customer Profile 4 Tabs Access */}
          {hasAnyCustomerTab && (
            <div className="bg-gradient-to-br from-emerald-500/10 via-muted/20 to-primary/5 p-4 rounded-xl border border-emerald-500/25 space-y-3.5 shadow-2xs">
              <div className="flex items-center justify-between border-b border-border pb-2.5">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-emerald-500/15 text-emerald-600 flex items-center justify-center">
                    <Store className="h-4 w-4" />
                  </div>
                  <div>
                    <Label className="text-sm font-bold text-foreground block">Customer Profile Tabs</Label>
                    <p className="text-[11px] text-muted-foreground">Permissions for 360° customer profile pages</p>
                  </div>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-600 border-emerald-500/30">
                  /customers/[id]
                </Badge>
              </div>

              <div className="space-y-2.5">
                {/* Tab 1: Store & Partners */}
                {isModuleEnabledInRole("customers") && (
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-background/80 border border-border/80 hover:border-emerald-500/40 transition-colors">
                    <div className="space-y-0.5 pr-2">
                      <div className="flex items-center gap-2">
                        <Store className="h-3.5 w-3.5 text-primary shrink-0" />
                        <Label htmlFor="tab-store-toggle" className="text-xs font-bold text-foreground cursor-pointer">
                          Tab 1: Store & Partners
                        </Label>
                        <Badge variant="secondary" className="text-[9px] px-1.5 py-0 font-extrabold bg-primary/10 text-primary">Store</Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        Store details, partners/contacts, phone numbers, GPS map pin & shop photos
                      </p>
                    </div>
                    <Switch
                      id="tab-store-toggle"
                      checked={user.showCustomers !== false}
                      onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showCustomers", checked)}
                      disabled={isPending}
                    />
                  </div>
                )}

                {/* Tab 2: Ledger Statement */}
                {isModuleEnabledInRole("ledger_customer") && (
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-background/80 border border-border/80 hover:border-emerald-500/40 transition-colors">
                    <div className="space-y-0.5 pr-2">
                      <div className="flex items-center gap-2">
                        <Receipt className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                        <Label htmlFor="tab-ledger-toggle" className="text-xs font-bold text-foreground cursor-pointer">
                          Tab 2: Ledger Statement
                        </Label>
                        <Badge variant="secondary" className="text-[9px] px-1.5 py-0 font-extrabold bg-blue-500/10 text-blue-600">Ledger</Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        Debtor ledger statement, closing balance, Dr/Cr transactions & WhatsApp share
                      </p>
                    </div>
                    <Switch
                      id="tab-ledger-toggle"
                      checked={user.showSalesLedgers}
                      onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showSalesLedgers", checked)}
                      disabled={isPending}
                    />
                  </div>
                )}

                {/* Tab 3: Order History */}
                {isModuleEnabledInRole("orders") && (
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-background/80 border border-border/80 hover:border-emerald-500/40 transition-colors">
                    <div className="space-y-0.5 pr-2">
                      <div className="flex items-center gap-2">
                        <ShoppingCart className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                        <Label htmlFor="tab-orders-toggle" className="text-xs font-bold text-foreground cursor-pointer">
                          Tab 3: Order History
                        </Label>
                        <Badge variant="secondary" className="text-[9px] px-1.5 py-0 font-extrabold bg-amber-500/10 text-amber-600">Orders</Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        Sales orders placed for this customer and line-item breakdowns
                      </p>
                    </div>
                    <Switch
                      id="tab-orders-toggle"
                      checked={user.showOrders}
                      onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showOrders", checked)}
                      disabled={isPending}
                    />
                  </div>
                )}

                {/* Tab 4: Field Visits */}
                {isModuleEnabledInRole("visits") && (
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-background/80 border border-border/80 hover:border-emerald-500/40 transition-colors">
                    <div className="space-y-0.5 pr-2">
                      <div className="flex items-center gap-2">
                        <Clock className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                        <Label htmlFor="tab-visits-toggle" className="text-xs font-bold text-foreground cursor-pointer">
                          Tab 4: Field Visits
                        </Label>
                        <Badge variant="secondary" className="text-[9px] px-1.5 py-0 font-extrabold bg-emerald-500/10 text-emerald-600">Visits</Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground">
                        Salesperson shop GPS check-ins, timestamps & visit camera snapshots
                      </p>
                    </div>
                    <Switch
                      id="tab-visits-toggle"
                      checked={user.showCheckIn}
                      onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showCheckIn", checked)}
                      disabled={isPending}
                    />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Section: Accounting & Other Ledgers */}
          {showAccountingSection && (
            <div className="space-y-3 border-t pt-4">
              <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground block">
                General Accounting & Vouchers
              </Label>

              {showSupplierLedgerToggle && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Landmark className={`h-4 w-4 ${user.showPurchaseLedgers ? "text-primary" : "text-muted-foreground"}`} />
                    <Label htmlFor="purchase-ledger-module" className="text-sm font-semibold cursor-pointer">Show Purchase Ledgers (Creditors)</Label>
                  </div>
                  <Switch
                    id="purchase-ledger-module"
                    checked={user.showPurchaseLedgers}
                    onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showPurchaseLedgers", checked)}
                    disabled={isPending}
                  />
                </div>
              )}

              {showVouchersToggle && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className={`h-4 w-4 ${user.showReceipts ? "text-primary" : "text-muted-foreground"}`} />
                    <div>
                      <Label htmlFor="vouchers-module" className="text-sm font-semibold cursor-pointer block">Show Vouchers</Label>
                      <span className="text-[11px] text-muted-foreground">Access Daybook, Sales, Purchase, Receipt, Payment & Journal vouchers</span>
                    </div>
                  </div>
                  <Switch
                    id="vouchers-module"
                    checked={user.showReceipts}
                    onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showReceipts", checked)}
                    disabled={isPending}
                  />
                </div>
              )}

              {canShowLedgerScope && (
                <div className="pl-6 space-y-2 pt-1">
                  <Label className="text-xs font-semibold text-muted-foreground">Ledger Balance Scope</Label>
                  <select
                    value={user.ledgerScope || "dr_only"}
                    onChange={(e) => onScopeChange(user.id, "ledgerScope", e.target.value)}
                    disabled={isPending}
                    className="w-full text-xs bg-muted/40 border border-border rounded-md px-2 py-1.5 focus:outline-none font-medium"
                  >
                    <option value="dr_only">Dr Only (Debits)</option>
                    <option value="all">Full (Credits)</option>
                    <option value="restricted">Restricted Groups</option>
                  </select>
                  {user.ledgerScope === "restricted" && (
                    <GroupCheckboxes
                      groups={availableLedgerGroups}
                      selected={user.allowedLedgerGroups}
                      onChange={(group: string, checked: boolean) => onAllowedGroupsChange(user.id, "allowedLedgerGroups", group, checked)}
                      disabled={isPending}
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {/* Section: Payment Collection */}
          {showPaymentsToggle && (
            <div className="space-y-3 border-t pt-4">
              <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground block">
                Payment Collection
              </Label>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <IndianRupee className={`h-4 w-4 ${user.showPayments ? "text-primary" : "text-muted-foreground"}`} />
                  <div>
                    <Label htmlFor="payments-module" className="text-sm font-semibold cursor-pointer block">Show Payment Collection</Label>
                    <span className="text-[11px] text-muted-foreground">Record field customer payment collections with geocoded receipt photos</span>
                  </div>
                </div>
                <Switch
                  id="payments-module"
                  checked={user.showPayments}
                  onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showPayments", checked)}
                  disabled={isPending}
                />
              </div>
            </div>
          )}

          {/* Section: Stocks & Inventory */}
          {isModuleEnabledInRole("inventory") && (
            <div className="space-y-3 border-t pt-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Layers className={`h-4 w-4 ${user.showStocks ? "text-primary" : "text-muted-foreground"}`} />
                  <div>
                    <Label htmlFor="stock-module" className="text-sm font-semibold cursor-pointer block">Show Stocks (Valuation & Balances)</Label>
                    <span className="text-[11px] text-muted-foreground">View stock summary, closing balances, rates, and valuation</span>
                  </div>
                </div>
                <Switch
                  id="stock-module"
                  checked={user.showStocks}
                  onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showStocks", checked)}
                  disabled={isPending}
                />
              </div>
              {user.showStocks ? (
                <div className="pl-6 space-y-2">
                  <select
                    value={user.stockScope || "full"}
                    onChange={(e) => onScopeChange(user.id, "stockScope", e.target.value)}
                    disabled={isPending}
                    className="w-full text-xs bg-muted/40 border border-border rounded-md px-2 py-1.5 focus:outline-none font-medium"
                  >
                    <option value="full">Full Details (Stock Balances, Rates & Margins)</option>
                    <option value="catalog_only">Catalog Only (Order Booking only, No Stock Details)</option>
                    <option value="restricted">Restricted Groups</option>
                  </select>
                  {user.stockScope === "restricted" && (
                    <GroupCheckboxes
                      groups={availableStockGroups}
                      selected={user.allowedStockGroups}
                      onChange={(group: string, checked: boolean) => onAllowedGroupsChange(user.id, "allowedStockGroups", group, checked)}
                      disabled={isPending}
                    />
                  )}
                </div>
              ) : (
                <p className="text-[11px] text-muted-foreground pl-6">
                  Note: Order-taking users (Sales) can still search and pick products for orders without viewing stock valuation or balances.
                </p>
              )}
            </div>
          )}

          {/* Section: Reports */}
          {isModuleEnabledInRole("reports") && (
            <div className="space-y-3 border-t pt-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BarChart3 className={`h-4 w-4 ${user.showReports ? "text-primary" : "text-muted-foreground"}`} />
                  <Label htmlFor="reports-module" className="text-sm font-semibold cursor-pointer">Show Financial Reports</Label>
                </div>
                <Switch
                  id="reports-module"
                  checked={user.showReports}
                  onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showReports", checked)}
                  disabled={isPending}
                />
              </div>
              {user.showReports && (
                <div className="pl-6">
                  <GroupCheckboxes
                    groups={ALL_REPORT_CATEGORIES}
                    selected={user.allowedReportCategories}
                    onChange={(group: string, checked: boolean) => onAllowedGroupsChange(user.id, "allowedReportCategories", group, checked)}
                    disabled={isPending}
                  />
                </div>
              )}
            </div>
          )}

          {/* Section: Operations, Expenses & Compliance */}
          {hasAnyOperations && (
            <div className="space-y-3 border-t pt-4">
              <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground block">
                Operations & Compliance
              </Label>

              {showExpensesToggle && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Wallet className={`h-4 w-4 ${user.showExpenses ? "text-primary" : "text-muted-foreground"}`} />
                    <Label htmlFor="expenses-module" className="text-sm font-semibold cursor-pointer">Show Expenses</Label>
                  </div>
                  <Switch
                    id="expenses-module"
                    checked={user.showExpenses}
                    onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showExpenses", checked)}
                    disabled={isPending}
                  />
                </div>
              )}

              {showAttendanceToggle && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Clock className={`h-4 w-4 ${user.showAttendance ? "text-primary" : "text-muted-foreground"}`} />
                    <Label htmlFor="attendance-module" className="text-sm font-semibold cursor-pointer">Staff Attendance</Label>
                  </div>
                  <Switch
                    id="attendance-module"
                    checked={user.showAttendance}
                    onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showAttendance", checked)}
                    disabled={isPending}
                  />
                </div>
              )}

              {showGstToggle && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileSpreadsheet className={`h-4 w-4 ${user.showGst ? "text-primary" : "text-muted-foreground"}`} />
                    <Label htmlFor="gst-module" className="text-sm font-semibold cursor-pointer">GST Returns</Label>
                  </div>
                  <Switch
                    id="gst-module"
                    checked={user.showGst}
                    onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showGst", checked)}
                    disabled={isPending}
                  />
                </div>
              )}
            </div>
          )}

          {/* Empty state if all modules disabled in role */}
          {!hasAnyConfigurableModule && (
            <div className="p-4 rounded-xl border border-dashed border-border bg-muted/20 text-center space-y-1 my-2">
              <Shield className="h-6 w-6 text-muted-foreground mx-auto" />
              <p className="text-sm font-semibold text-foreground">No Sub-Module Overrides Available</p>
              <p className="text-xs text-muted-foreground max-w-xs mx-auto">
                All modules are currently disabled in the <strong>{activeRoleObj?.name || user.role}</strong> master role. Enable them in Roles & Permissions first.
              </p>
            </div>
          )}
        </div>

        <div className="border-t pt-4 flex justify-end">
          <Button onClick={() => onOpenChange(false)} variant="secondary">
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
