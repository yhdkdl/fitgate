import React, { useEffect, useState } from "react";
import {
  getMyFreezes,
  getMemberFreezeAllowance,
  requestFreeze,
  formatApiErrorMessage,
  ApiError,
  type MemberFreeze,
  type MemberFreezeAllowance,
} from "../../api/freeze";

export function getLocalDateString(d: Date = new Date()): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";

interface MemberFreezeCardProps {
  memberStatus: string;
}

export const MemberFreezeCard: React.FC<MemberFreezeCardProps> = ({ memberStatus }) => {
  const [allowance, setAllowance] = useState<MemberFreezeAllowance | null>(null);
  const [freezes, setFreezes] = useState<MemberFreeze[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal form state
  const [modalOpen, setModalOpen] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [allowanceData, freezesData] = await Promise.all([
        getMemberFreezeAllowance(),
        getMyFreezes(),
      ]);
      setAllowance(allowanceData);
      setFreezes(freezesData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load freeze allowance.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const openModal = () => {
    const today = getLocalDateString();
    const endD = new Date();
    endD.setDate(endD.getDate() + 7);
    const defaultEnd = getLocalDateString(endD);
    setStartDate(today);
    setEndDate(defaultEnd);
    setReason("");
    setFormError(null);
    setModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const trimmedReason = reason.trim();
    if (trimmedReason.length < 5 || trimmedReason.length > 500) {
      setFormError("Reason must be between 5 and 500 characters.");
      return;
    }

    if (!startDate || !endDate) {
      setFormError("Both start and end dates are required.");
      return;
    }

    if (endDate < startDate) {
      setFormError("End date must be on or after start date.");
      return;
    }

    setSubmitting(true);
    try {
      await requestFreeze({
        start_date: startDate,
        end_date: endDate,
        reason: trimmedReason,
      });
      setSuccessMessage("Freeze request submitted successfully. Awaiting staff review.");
      setModalOpen(false);
      await fetchData();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setFormError(err.message || formatApiErrorMessage(err.data, "Failed to submit freeze request."));
      } else if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("Failed to submit freeze request.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Card className="bg-surface border-border p-6 text-center space-y-2">
        <Spinner size="sm" />
        <p className="text-xs text-text-muted">Loading membership freeze options...</p>
      </Card>
    );
  }

  if (error) {
    return <Alert variant="warning">{error}</Alert>;
  }

  if (!allowance || !allowance.freeze_allowed) {
    return (
      <Card className="bg-surface border-border p-6 space-y-2">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-text-muted">
          Membership Freeze
        </h3>
        <p className="text-sm text-text-muted">
          This gym does not allow membership freezes.
        </p>
      </Card>
    );
  }

  const getStatusBadge = (status: MemberFreeze["status"]) => {
    switch (status) {
      case "approved":
        return <Badge variant="success">Approved</Badge>;
      case "rejected":
        return <Badge variant="danger">Rejected</Badge>;
      case "completed":
        return <Badge variant="secondary">Completed</Badge>;
      default:
        return <Badge variant="warning">Pending Review</Badge>;
    }
  };

  return (
    <Card className="bg-surface border-border p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-text">Membership Freeze</h3>
          <p className="text-xs text-text-muted mt-0.5">
            Temporarily pause your membership pass and extend your subscription end date.
          </p>
        </div>

        {allowance.has_active_subscription && allowance.remaining_days > 0 && memberStatus !== "suspended" && (
          <Button variant="primary" size="sm" onClick={openModal}>
            Request Freeze
          </Button>
        )}
      </div>

      {successMessage && (
        <Alert variant="success" className="text-xs">
          {successMessage}
        </Alert>
      )}

      {/* Allowance Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-surface-2/60 border border-border/60 rounded-card p-4 text-center">
          <span className="text-xs text-text-muted block font-medium">Total Allowed</span>
          <span className="text-xl font-extrabold text-text mt-1 block">
            {allowance.total_allowed} Days
          </span>
        </div>

        <div className="bg-surface-2/60 border border-border/60 rounded-card p-4 text-center">
          <span className="text-xs text-text-muted block font-medium">Used Days</span>
          <span className="text-xl font-extrabold text-text-muted mt-1 block">
            {allowance.used_days} Days
          </span>
        </div>

        <div className="bg-surface-2/60 border border-border/60 rounded-card p-4 text-center">
          <span className="text-xs text-text-muted block font-medium">Remaining Days</span>
          <span className="text-xl font-extrabold text-primary mt-1 block">
            {allowance.remaining_days} Days
          </span>
        </div>
      </div>

      {/* Request History Table */}
      <div className="space-y-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-text-muted">
          Freeze History
        </h4>
        {freezes.length === 0 ? (
          <p className="text-xs text-text-muted italic">
            You have not submitted any membership freeze requests.
          </p>
        ) : (
          <div className="overflow-x-auto border border-border/60 rounded-lg">
            <table className="w-full text-xs text-left">
              <thead className="bg-surface-2/60 border-b border-border/60 text-text-muted">
                <tr>
                  <th className="py-2.5 px-3">Start Date</th>
                  <th className="py-2.5 px-3">End Date</th>
                  <th className="py-2.5 px-3">Days</th>
                  <th className="py-2.5 px-3">Reason</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {freezes.map((f) => (
                  <tr key={f.id} className="hover:bg-surface-2/30">
                    <td className="py-2.5 px-3 font-medium text-text">{f.start_date}</td>
                    <td className="py-2.5 px-3 font-medium text-text">{f.end_date}</td>
                    <td className="py-2.5 px-3 font-semibold text-primary">{f.days}</td>
                    <td className="py-2.5 px-3 text-text max-w-[200px] truncate" title={f.reason}>
                      {f.reason}
                    </td>
                    <td className="py-2.5 px-3">{getStatusBadge(f.status)}</td>
                    <td className="py-2.5 px-3 text-text-muted">
                      {f.status === "rejected" && f.rejection_reason ? (
                        <span className="text-danger" title={f.rejection_reason}>
                          Rejected: {f.rejection_reason}
                        </span>
                      ) : f.status === "approved" && f.reviewed_at ? (
                        <span>Approved on {new Date(f.reviewed_at).toLocaleDateString()}</span>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Freeze Request Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Request Membership Freeze"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          {formError && <Alert variant="danger">{formError}</Alert>}

          <p className="text-xs text-text-muted">
            You have <strong>{allowance.remaining_days}</strong> freeze days remaining.
            Your pass will be temporarily paused during this period and your subscription
            will be extended by the approved days.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="freeze-start-date" className="block text-xs font-medium text-text mb-1">
                Start Date *
              </label>
              <input
                id="freeze-start-date"
                type="date"
                required
                value={startDate}
                min={getLocalDateString()}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-2 bg-surface-2 border border-border rounded-input text-text text-sm focus:outline-none focus:border-primary"
              />
            </div>

            <div>
              <label htmlFor="freeze-end-date" className="block text-xs font-medium text-text mb-1">
                End Date *
              </label>
              <input
                id="freeze-end-date"
                type="date"
                required
                value={endDate}
                min={startDate || getLocalDateString()}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-2 bg-surface-2 border border-border rounded-input text-text text-sm focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div>
            <label htmlFor="freeze-reason" className="block text-xs font-medium text-text mb-1">
              Reason (5 to 500 characters) *
            </label>
            <textarea
              id="freeze-reason"
              required
              rows={3}
              value={reason}
              maxLength={500}
              placeholder="e.g. Taking annual leave or travel"
              onChange={(e) => setReason(e.target.value)}
              className="w-full px-3 py-2 bg-surface-2 border border-border rounded-input text-text text-sm focus:outline-none focus:border-primary"
            />
            <span className="text-[10px] text-text-muted">
              {reason.length}/500 characters
            </span>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setModalOpen(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? "Submitting..." : "Submit Freeze Request"}
            </Button>
          </div>
        </form>
      </Modal>
    </Card>
  );
};
