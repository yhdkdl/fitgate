import React, { useEffect, useState } from "react";
import {
  deactivateStaff,
  inviteStaff,
  listStaff,
  reactivateStaff,
  type InviteStaffPayload,
  type StaffMember,
  type StaffRole,
} from "../../api/staff";
import { useAuth } from "../../context/AuthContext";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";

interface StaffManagementSectionProps {
  onStaffUpdated?: () => void;
}

export const StaffManagementSection: React.FC<StaffManagementSectionProps> = ({
  onStaffUpdated,
}) => {
  const { user } = useAuth();
  const [staffList, setStaffList] = useState<StaffMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filters
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Invite modal state
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [inviteSubmitting, setInviteSubmitting] = useState(false);
  const [inviteForm, setInviteForm] = useState<InviteStaffPayload>({
    email: "",
    role: user?.role === "manager" ? "trainer" : "manager",
    full_name: "",
    phone: "",
  });
  const [inviteError, setInviteError] = useState<string | null>(null);

  // Deactivate confirmation state
  const [deactivatingId, setDeactivatingId] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  const fetchStaff = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const res = await listStaff();
      setStaffList(res);
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to load staff list.";
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStaff();
  }, []);

  const handleInviteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteError(null);

    if (!inviteForm.email.trim()) {
      setInviteError("Email is required.");
      return;
    }

    try {
      setInviteSubmitting(true);
      const res = await inviteStaff({
        email: inviteForm.email.trim(),
        role: inviteForm.role,
        full_name: inviteForm.full_name?.trim() || undefined,
        phone: inviteForm.phone?.trim() || undefined,
      });

      setSuccessMsg(
        `Staff invitation sent to ${res.user.email} as ${res.user.role}.`
      );
      setIsInviteOpen(false);
      setInviteForm({
        email: "",
        role: user?.role === "manager" ? "trainer" : "trainer",
        full_name: "",
        phone: "",
      });
      await fetchStaff();
      onStaffUpdated?.();
    } catch (err: unknown) {
      const data = (err as { data?: Record<string, unknown> })?.data;
      if (data && typeof data === "object") {
        if ("email" in data && Array.isArray(data.email)) {
          setInviteError(data.email.join(" "));
        } else if ("detail" in data && typeof data.detail === "string") {
          setInviteError(data.detail);
        } else {
          setInviteError(
            "Failed to invite staff member. Please check details."
          );
        }
      } else {
        setInviteError("Failed to invite staff member.");
      }
    } finally {
      setInviteSubmitting(false);
    }
  };

  const handleDeactivate = async (staffId: string) => {
    try {
      setActionInProgress(staffId);
      setErrorMsg(null);
      const res = await deactivateStaff(staffId);
      setSuccessMsg(`Deactivated ${res.user.email}.`);
      setDeactivatingId(null);
      await fetchStaff();
      onStaffUpdated?.();
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to deactivate staff member.";
      setErrorMsg(msg);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleReactivate = async (staffId: string) => {
    try {
      setActionInProgress(staffId);
      setErrorMsg(null);
      const res = await reactivateStaff(staffId);
      setSuccessMsg(`Reactivated ${res.user.email}.`);
      await fetchStaff();
      onStaffUpdated?.();
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Failed to reactivate staff member.";
      setErrorMsg(msg);
    } finally {
      setActionInProgress(null);
    }
  };

  // Filter staff list
  const filteredStaff = staffList.filter((member) => {
    if (roleFilter !== "all" && member.role !== roleFilter) {
      return false;
    }
    if (statusFilter === "active" && !member.is_active) {
      return false;
    }
    if (statusFilter === "deactivated" && member.is_active) {
      return false;
    }
    return true;
  });

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case "owner":
        return "primary";
      case "manager":
        return "info";
      case "trainer":
        return "success";
      case "reception":
        return "warning";
      default:
        return "default";
    }
  };

  const isOwner = user?.role === "owner";
  const isManager = user?.role === "manager";

  // Check if current user can manage a specific target staff member
  const canManageTarget = (target: StaffMember) => {
    if (target.id === user?.id) return false;
    if (target.role === "owner") return false;
    if (isOwner) return true;
    if (isManager) {
      return target.role === "trainer" || target.role === "reception";
    }
    return false;
  };

  return (
    <Card className="p-6 bg-surface border-border">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 border-b border-border pb-4">
        <div>
          <h2 className="text-xl font-bold text-text flex items-center gap-2">
            Staff Management
            <Badge variant="primary">{staffList.length}</Badge>
          </h2>
          <p className="text-xs sm:text-sm text-text-muted mt-0.5">
            Manage your gym's team. Invited staff receive a secure link to set
            their password.
          </p>
        </div>

        {(isOwner || isManager) && (
          <Button
            variant="primary"
            onClick={() => {
              setInviteError(null);
              setIsInviteOpen(true);
            }}
            className="self-start sm:self-center min-h-[44px]"
          >
            Invite Staff Member
          </Button>
        )}
      </div>

      {successMsg && (
        <Alert
          variant="success"
          className="mb-4"
          onClose={() => setSuccessMsg(null)}
        >
          {successMsg}
        </Alert>
      )}

      {errorMsg && (
        <Alert
          variant="danger"
          className="mb-4"
          onClose={() => setErrorMsg(null)}
        >
          {errorMsg}
        </Alert>
      )}

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-6 bg-surface-2 p-3 rounded-lg border border-border">
        <div className="flex items-center gap-2">
          <label
            htmlFor="staff-role-filter"
            className="text-xs font-semibold text-text-muted uppercase"
          >
            Role:
          </label>
          <select
            id="staff-role-filter"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="text-sm bg-surface border border-border rounded px-2.5 py-1.5 text-text focus:outline-none focus:border-primary min-h-[38px]"
          >
            <option value="all">All Roles</option>
            <option value="owner">Owner</option>
            <option value="manager">Manager</option>
            <option value="trainer">Trainer</option>
            <option value="reception">Reception</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label
            htmlFor="staff-status-filter"
            className="text-xs font-semibold text-text-muted uppercase"
          >
            Status:
          </label>
          <select
            id="staff-status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-sm bg-surface border border-border rounded px-2.5 py-1.5 text-text focus:outline-none focus:border-primary min-h-[38px]"
          >
            <option value="all">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="deactivated">Deactivated</option>
          </select>
        </div>

        {(roleFilter !== "all" || statusFilter !== "all") && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setRoleFilter("all");
              setStatusFilter("all");
            }}
            className="text-xs ml-auto"
          >
            Reset Filters
          </Button>
        )}
      </div>

      {/* Loading state */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-12">
          <Spinner size="lg" />
          <p className="text-sm text-text-muted mt-3">Loading staff list...</p>
        </div>
      ) : filteredStaff.length === 0 ? (
        <div className="text-center py-12 border border-dashed border-border rounded-lg bg-surface-2/30">
          <p className="text-base font-semibold text-text">No staff found</p>
          <p className="text-xs text-text-muted mt-1">
            {staffList.length === 0
              ? "No staff members have been invited yet."
              : "No staff members match the selected filters."}
          </p>
        </div>
      ) : (
        /* Responsive Table */
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-2 text-text-muted text-xs uppercase font-semibold border-b border-border">
              <tr>
                <th className="px-4 py-3">Staff Member</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3 hidden md:table-cell">Contact</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 hidden sm:table-cell">Created</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredStaff.map((member) => {
                const canManage = canManageTarget(member);
                const isDeactivatingThis = deactivatingId === member.id;
                const isBusy = actionInProgress === member.id;

                return (
                  <tr
                    key={member.id}
                    className="hover:bg-surface-2/50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-text">
                        {member.full_name || "Unnamed"}
                        {member.id === user?.id && (
                          <span className="ml-1.5 text-xs text-primary font-normal">
                            (You)
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-text-muted font-mono">
                        {member.email}
                      </div>
                    </td>

                    <td className="px-4 py-3">
                      <Badge variant={getRoleBadgeVariant(member.role)}>
                        {member.role}
                      </Badge>
                    </td>

                    <td className="px-4 py-3 hidden md:table-cell text-xs text-text-muted">
                      {member.phone || "—"}
                    </td>

                    <td className="px-4 py-3">
                      {member.is_active ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <Badge variant="danger">Deactivated</Badge>
                      )}
                    </td>

                    <td className="px-4 py-3 hidden sm:table-cell text-xs text-text-muted">
                      {new Date(member.created_at).toLocaleDateString()}
                    </td>

                    <td className="px-4 py-3 text-right">
                      {canManage ? (
                        member.is_active ? (
                          isDeactivatingThis ? (
                            <div className="flex items-center justify-end gap-1.5">
                              <span className="text-xs text-danger font-medium hidden sm:inline">
                                Deactivate?
                              </span>
                              <Button
                                variant="danger"
                                size="sm"
                                disabled={isBusy}
                                onClick={() => handleDeactivate(member.id)}
                                className="min-h-[36px]"
                              >
                                {isBusy ? "..." : "Confirm"}
                              </Button>
                              <Button
                                variant="secondary"
                                size="sm"
                                disabled={isBusy}
                                onClick={() => setDeactivatingId(null)}
                                className="min-h-[36px]"
                              >
                                Cancel
                              </Button>
                            </div>
                          ) : (
                            <Button
                              variant="secondary"
                              size="sm"
                              disabled={isBusy}
                              onClick={() => setDeactivatingId(member.id)}
                              className="text-danger hover:bg-danger/10 min-h-[36px]"
                            >
                              Deactivate
                            </Button>
                          )
                        ) : (
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={isBusy}
                            onClick={() => handleReactivate(member.id)}
                            className="text-success hover:bg-success/10 min-h-[36px]"
                          >
                            {isBusy ? "Reactivating..." : "Reactivate"}
                          </Button>
                        )
                      ) : (
                        <span className="text-xs text-text-muted italic">
                          Protected
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Invite Staff Modal */}
      {isInviteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-surface border border-border rounded-card max-w-md w-full p-6 shadow-xl relative max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-bold text-text mb-1">
              Invite New Staff Member
            </h3>
            <p className="text-xs text-text-muted mb-4">
              An invitation email with a single-use set-password link (valid for
              7 days) will be sent.
            </p>

            {inviteError && (
              <Alert variant="danger" className="mb-4">
                {inviteError}
              </Alert>
            )}

            <form onSubmit={handleInviteSubmit} className="space-y-4">
              <FormField label="Email Address *" htmlFor="staff-email">
                <Input
                  id="staff-email"
                  type="email"
                  required
                  placeholder="staff@example.com"
                  value={inviteForm.email}
                  onChange={(e) =>
                    setInviteForm((prev) => ({
                      ...prev,
                      email: e.target.value,
                    }))
                  }
                  disabled={inviteSubmitting}
                />
              </FormField>

              <FormField label="Staff Role *" htmlFor="staff-role">
                <select
                  id="staff-role"
                  value={inviteForm.role}
                  onChange={(e) =>
                    setInviteForm((prev) => ({
                      ...prev,
                      role: e.target.value as StaffRole,
                    }))
                  }
                  disabled={inviteSubmitting}
                  className="w-full bg-surface border border-border rounded-input px-3 py-2 text-sm text-text focus:outline-none focus:border-primary min-h-[44px]"
                >
                  {isOwner && <option value="manager">Manager</option>}
                  <option value="trainer">Trainer</option>
                  <option value="reception">Reception</option>
                </select>
              </FormField>

              <FormField label="Full Name" htmlFor="staff-name">
                <Input
                  id="staff-name"
                  type="text"
                  placeholder="e.g. Abebe Bikila"
                  value={inviteForm.full_name}
                  onChange={(e) =>
                    setInviteForm((prev) => ({
                      ...prev,
                      full_name: e.target.value,
                    }))
                  }
                  disabled={inviteSubmitting}
                />
              </FormField>

              <FormField label="Phone Number" htmlFor="staff-phone">
                <Input
                  id="staff-phone"
                  type="tel"
                  placeholder="e.g. +251 91 123 4567"
                  value={inviteForm.phone}
                  onChange={(e) =>
                    setInviteForm((prev) => ({
                      ...prev,
                      phone: e.target.value,
                    }))
                  }
                  disabled={inviteSubmitting}
                />
              </FormField>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-border mt-6">
                <Button
                  variant="secondary"
                  type="button"
                  onClick={() => setIsInviteOpen(false)}
                  disabled={inviteSubmitting}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  type="submit"
                  disabled={inviteSubmitting}
                >
                  {inviteSubmitting ? (
                    <div className="flex items-center gap-2">
                      <Spinner size="sm" />
                      <span>Sending...</span>
                    </div>
                  ) : (
                    "Send Invitation"
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Card>
  );
};
