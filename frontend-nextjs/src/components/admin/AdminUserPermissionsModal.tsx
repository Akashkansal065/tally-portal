"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Landmark, Layers, BarChart3, Laptop, User, Shield, Ban, CheckCircle2, MapPin, Receipt, Wallet, KeyRound, Eye, EyeOff, Clock } from "lucide-react";

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
  showReceipts: boolean;
  showPayments: boolean;
  showExpenses: boolean;
  showAttendance: boolean;
  showStocks: boolean;
  showReports: boolean;
  showOrders: boolean;
  showCheckIn: boolean;
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
  onRoleChange: (userId: number, role: string) => void;
  onPermissionToggle: (userId: number, field: "showLedger" | "showStocks" | "showReports" | "showOrders" | "showCheckIn" | "showSalesLedgers" | "showPurchaseLedgers" | "showReceipts" | "showPayments" | "showExpenses" | "showAttendance", value: boolean) => void;
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

  if (!user) return null;

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
          <DialogTitle className="flex items-center gap-2 text-lg font-bold">
            <Shield className="h-5 w-5 text-primary" />
            Edit Permissions
          </DialogTitle>
          <DialogDescription>
            Configure role-based access control and scopes for <strong>{user.username}</strong>.
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
                value={user.role === "admin" ? "admin" : "sales"}
                onChange={(e) => onRoleChange(user.id, e.target.value)}
                disabled={isPending}
                className="bg-background border border-input text-foreground text-sm rounded-md px-2.5 py-1.5 focus:ring-1 focus:ring-primary focus:outline-none w-[120px] font-medium"
              >
                <option value="sales">Sales</option>
                <option value="admin">Admin</option>
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

          {/* Module 1: Show Ledger */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Landmark className={`h-4 w-4 ${user.showSalesLedgers ? "text-primary" : "text-muted-foreground"}`} />
                <Label htmlFor="sales-ledger-module" className="text-sm font-semibold cursor-pointer">Show Sales Ledgers (Debtors)</Label>
              </div>
              <Switch
                id="sales-ledger-module"
                checked={user.showSalesLedgers}
                onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showSalesLedgers", checked)}
                disabled={isPending}
              />
            </div>

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

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Receipt className={`h-4 w-4 ${user.showReceipts ? "text-primary" : "text-muted-foreground"}`} />
                <Label htmlFor="receipts-module" className="text-sm font-semibold cursor-pointer">Show Receipts (Vouchers)</Label>
              </div>
              <Switch
                id="receipts-module"
                checked={user.showReceipts}
                onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showReceipts", checked)}
                disabled={isPending}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Wallet className={`h-4 w-4 ${user.showPayments ? "text-primary" : "text-muted-foreground"}`} />
                <Label htmlFor="payments-module" className="text-sm font-semibold cursor-pointer">Show Payments (Vouchers)</Label>
              </div>
              <Switch
                id="payments-module"
                checked={user.showPayments}
                onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showPayments", checked)}
                disabled={isPending}
              />
            </div>

            {(user.showSalesLedgers || user.showPurchaseLedgers) && (
              <div className="pl-6 space-y-2">
                <Label className="text-xs font-semibold text-muted-foreground">Ledger Scope</Label>
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

          {/* Module 2: Show Stocks */}
          <div className="space-y-3 border-t pt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className={`h-4 w-4 ${user.showStocks ? "text-primary" : "text-muted-foreground"}`} />
                <Label htmlFor="stock-module" className="text-sm font-semibold cursor-pointer">Show Stocks</Label>
              </div>
              <Switch
                id="stock-module"
                checked={user.showStocks}
                onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showStocks", checked)}
                disabled={isPending}
              />
            </div>
            {user.showStocks && (
              <div className="pl-6 space-y-2">
                <select
                  value={user.stockScope || "full"}
                  onChange={(e) => onScopeChange(user.id, "stockScope", e.target.value)}
                  disabled={isPending}
                  className="w-full text-xs bg-muted/40 border border-border rounded-md px-2 py-1.5 focus:outline-none font-medium"
                >
                  <option value="full">Full Details</option>
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
            )}
          </div>

          {/* Module 3: Show Reports */}
          <div className="space-y-3 border-t pt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BarChart3 className={`h-4 w-4 ${user.showReports ? "text-primary" : "text-muted-foreground"}`} />
                <Label htmlFor="reports-module" className="text-sm font-semibold cursor-pointer">Show Reports</Label>
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

          {/* Module 4: Show Orders */}
          <div className="space-y-3 border-t pt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Laptop className={`h-4 w-4 ${user.showOrders ? "text-primary" : "text-muted-foreground"}`} />
                <Label htmlFor="orders-module" className="text-sm font-semibold cursor-pointer">Show Orders</Label>
              </div>
              <Switch
                id="orders-module"
                checked={user.showOrders}
                onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showOrders", checked)}
                disabled={isPending}
              />
            </div>
          </div>

          {/* Module 5: Show Check-In */}
          <div className="space-y-3 border-t pt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MapPin className={`h-4 w-4 ${user.showCheckIn ? "text-primary" : "text-muted-foreground"}`} />
                <Label htmlFor="checkin-module" className="text-sm font-semibold cursor-pointer">Show Check-In</Label>
              </div>
              <Switch
                id="checkin-module"
                checked={user.showCheckIn}
                onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showCheckIn", checked)}
                disabled={isPending}
              />
            </div>
          </div>

          {/* Module 6: Show Expenses */}
          <div className="space-y-3 border-t pt-4">
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
          </div>

          {/* Module 7: Show Attendance */}
          <div className="space-y-3 border-t pt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className={`h-4 w-4 ${user.showAttendance ? "text-primary" : "text-muted-foreground"}`} />
                <Label htmlFor="attendance-module" className="text-sm font-semibold cursor-pointer">Show Attendance</Label>
              </div>
              <Switch
                id="attendance-module"
                checked={user.showAttendance}
                onCheckedChange={(checked: boolean) => onPermissionToggle(user.id, "showAttendance", checked)}
                disabled={isPending}
              />
            </div>
          </div>
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
