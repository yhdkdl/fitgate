import React, { useCallback, useEffect, useState } from "react";
import {
  approveFreeze,
  endFreezeEarly,
  getGymFreezes,
  rejectFreeze,
  type MemberFreeze,
} from "../../api/freeze";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";

export const GymFreezesSection: React.FC = () => {
  const [freezes, setFreezes] = useState<MemberFreeze[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");

  // Rejection modal state
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [selectedFreeze, setSelectedFreeze] = useState<MemberFreeze | null>(
    null
  );
  const [rejectionReason, setRejectionReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const fetchFreezes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getGymFreezes(statusFilter || undefined);
      setFreezes(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load freeze requests."
      );
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchFreezes();
  }, [fetchFreezes]);

  const handleApprove = async (freeze: MemberFreeze) => {
    const memberName = freeze.member?.full_name || "the member";
    if (
      !window.confirm(
        `Approve freeze for ${memberName} for ${freeze.days} day(s)? This will pause their pass and extend their membership end date.`
      )
    ) {
      return;
    }

    setActionLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await approveFreeze(freeze.id);
      setSuccessMessage(res.detail || "Freeze request approved successfully.");
      await fetchFreezes();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to approve freeze request."
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleEndEarly = async (freeze: MemberFreeze) => {
    const memberName = freeze.member?.full_name || "the member";
    if (
      !window.confirm(
        `End freeze early for ${memberName}? Unused days will be returned to their subscription and freeze allowance, and their pass will become active immediately.`
      )
    ) {
      return;
    }

    setActionLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await endFreezeEarly(freeze.id);
      setSuccessMessage(res.detail || "Freeze ended early successfully.");
      await fetchFreezes();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to end freeze early."
      );
    } finally {
      setActionLoading(false);
    }
  };

  const openRejectModal = (freeze: MemberFreeze) => {
    setSelectedFreeze(freeze);
    setRejectionReason("");
    setModalError(null);
    setRejectModalOpen(true);
  };

  const handleRejectSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFreeze) return;

    const trimmed = rejectionReason.trim();
    if (trimmed.length < 5 || trimmed.length > 500) {
      setModalError(
        "Rejection explanation must be between 5 and 500 characters."
      );
      return;
    }

    setActionLoading(true);
    setModalError(null);
    try {
      const res = await rejectFreeze(selectedFreeze.id, trimmed);
      setSuccessMessage(res.detail || "Freeze request has been rejected.");
      setRejectModalOpen(false);
      setSelectedFreeze(null);
      await fetchFreezes();
    } catch (err: unknown) {
      setModalError(
        err instanceof Error ? err.message : "Failed to reject freeze request."
      );
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (status: MemberFreeze["status"]) => {
    switch (status) {
      case "approved":
        return <Badge variant="success">Approved</Badge>;
      case "rejected":
        return <Badge variant="danger">Rejected</Badge>;
      case "completed":
        return <Badge variant="secondary">Completed</Badge>;
      default:
        return <Badge variant="warning">Pending</Badge>;
    }
  };

  return (
    <Card className="bg-surface border-border p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-text">
            Membership Freeze Requests
          </h3>
          <p className="text-xs text-text-muted mt-0.5">
            Review, approve, or reject membership freeze requests from gym
            members.
          </p>
        </div>

        {/* Status filter tabs */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {[
            { label: "All", value: "" },
            { label: "Pending", value: "pending" },
            { label: "Approved", value: "approved" },
            { label: "Rejected", value: "rejected" },
            { label: "Completed", value: "completed" },
          ].map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setStatusFilter(tab.value)}
              className={`px-2.5 py-1 text-xs rounded-button transition-colors font-medium ${
                statusFilter === tab.value
                  ? "bg-primary text-white"
                  : "bg-surface-2 text-text-muted hover:text-text border border-border"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}
      {successMessage && <Alert variant="success">{successMessage}</Alert>}

      {loading ? (
        <div className="p-8 text-center flex flex-col items-center gap-2">
          <Spinner size="sm" />
          <span className="text-xs text-text-muted">
            Loading freeze requests...
          </span>
        </div>
      ) : freezes.length === 0 ? (
        <div className="p-8 text-center text-xs text-text-muted bg-surface-2/30 rounded-lg border border-border/60">
          No freeze requests found for the selected filter.
        </div>
      ) : (
        <div className="overflow-x-auto border border-border/60 rounded-lg">
          <table className="w-full text-xs text-left">
            <thead className="bg-surface-2/60 border-b border-border/60 text-text-muted">
              <tr>
                <th className="py-2.5 px-3">Member</th>
                <th className="py-2.5 px-3">Dates</th>
                <th className="py-2.5 px-3">Days</th>
                <th className="py-2.5 px-3">Reason</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Review Notes</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {freezes.map((f) => (
                <tr key={f.id} className="hover:bg-surface-2/30">
                  <td className="py-2.5 px-3 font-medium text-text">
                    <div>{f.member?.full_name || "Unknown Member"}</div>
                    {f.member?.phone && (
                      <div className="text-[11px] text-text-muted">
                        {f.member.phone}
                      </div>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-text">
                    {f.start_date} to {f.end_date}
                  </td>
                  <td className="py-2.5 px-3 font-semibold text-primary">
                    {f.days}d
                  </td>
                  <td
                    className="py-2.5 px-3 text-text max-w-[180px] truncate"
                    title={f.reason}
                  >
                    {f.reason}
                  </td>
                  <td className="py-2.5 px-3">{getStatusBadge(f.status)}</td>
                  <td className="py-2.5 px-3 text-text-muted max-w-[180px] truncate">
                    {f.status === "rejected" && f.rejection_reason ? (
                      <span className="text-danger" title={f.rejection_reason}>
                        {f.rejection_reason}
                      </span>
                    ) : f.status === "approved" && f.reviewed_at ? (
                      <span>
                        Approved {new Date(f.reviewed_at).toLocaleDateString()}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    {f.status === "pending" && (
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="primary"
                          size="sm"
                          disabled={actionLoading}
                          onClick={() => handleApprove(f)}
                          className="h-7 text-xs px-2"
                        >
                          Approve
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={actionLoading}
                          onClick={() => openRejectModal(f)}
                          className="h-7 text-xs px-2 text-danger hover:bg-danger/10"
                        >
                          Reject
                        </Button>
                      </div>
                    )}
                    {f.status === "approved" && (
                      <div className="flex items-center justify-end">
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={actionLoading}
                          onClick={() => handleEndEarly(f)}
                          className="h-7 text-xs px-2 text-warning hover:bg-warning/10"
                        >
                          End Early
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Rejection Modal with required explanation */}
      <Modal
        isOpen={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
        title="Reject Membership Freeze"
      >
        <form onSubmit={handleRejectSubmit} className="space-y-4">
          {modalError && <Alert variant="danger">{modalError}</Alert>}

          <p className="text-xs text-text-muted">
            Provide a clear explanation for rejecting the freeze request for{" "}
            <strong>{selectedFreeze?.member?.full_name || "the member"}</strong>{" "}
            ({selectedFreeze?.days} day(s)). This will be sent to the member and
            their pass will remain active.
          </p>

          <div>
            <label className="block text-xs font-medium text-text mb-1">
              Rejection Explanation (5 to 500 characters) *
            </label>
            <textarea
              required
              rows={3}
              value={rejectionReason}
              maxLength={500}
              placeholder="e.g. Freeze allowance has been exceeded or blackout period applies"
              onChange={(e) => setRejectionReason(e.target.value)}
              className="w-full px-3 py-2 bg-surface-2 border border-border rounded-input text-text text-sm focus:outline-none focus:border-primary"
            />
            <span className="text-[10px] text-text-muted">
              {rejectionReason.length}/500 characters
            </span>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              disabled={actionLoading}
              onClick={() => setRejectModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="danger" disabled={actionLoading}>
              {actionLoading ? "Rejecting..." : "Confirm Rejection"}
            </Button>
          </div>
        </form>
      </Modal>
    </Card>
  );
};
