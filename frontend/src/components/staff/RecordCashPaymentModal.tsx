import React, { useState, useEffect } from "react";
import {
  recordCashPayment,
  DigitalReceipt,
  RecordCashPaymentResponse,
} from "../../api/payments";
import { getMembershipPlans } from "../../api/plans";
import { listGymMembers } from "../../api/members";

export interface PlanOption {
  id: string;
  name: string;
  price_etb: string | number;
  duration_value: number;
  duration_unit: string;
}

export interface MemberOption {
  id: string;
  full_name: string;
  phone?: string;
  email?: string;
}

export interface Props {
  isOpen: boolean;
  onClose: () => void;
  plans?: PlanOption[];
  members?: MemberOption[];
  onPaymentSuccess?: (receipt: DigitalReceipt) => void;
  initialMemberId?: string;
}

export const RecordCashPaymentModal: React.FC<Props> = ({
  isOpen,
  onClose,
  plans,
  members,
  onPaymentSuccess,
  initialMemberId,
}) => {
  const [availablePlans, setAvailablePlans] = useState<PlanOption[]>(
    plans || []
  );
  const [availableMembers, setAvailableMembers] = useState<MemberOption[]>(
    members || []
  );
  const [selectedMemberId, setSelectedMemberId] = useState<string>(
    initialMemberId || (members?.[0]?.id ?? "")
  );
  const [selectedPlanId, setSelectedPlanId] = useState<string>(
    plans?.[0]?.id ?? ""
  );
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmedReceipt, setConfirmedReceipt] =
    useState<DigitalReceipt | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    if (plans && plans.length > 0) {
      setAvailablePlans(plans);
      setSelectedPlanId((prev) => prev || plans[0].id);
    } else {
      getMembershipPlans()
        .then((data) => {
          const mapped = data.map((p) => ({
            id: p.id,
            name: p.name,
            price_etb: p.price_etb,
            duration_value: p.duration_value,
            duration_unit: p.duration_unit,
          }));
          setAvailablePlans(mapped);
          setSelectedPlanId((prev) => prev || (mapped[0]?.id ?? ""));
        })
        .catch(() => {});
    }

    if (members && members.length > 0) {
      setAvailableMembers(members);
      setSelectedMemberId((prev) => initialMemberId || prev || members[0].id);
    } else {
      listGymMembers()
        .then((data) => {
          const mapped = data.map((m) => ({
            id: m.id,
            full_name: m.full_name,
            phone: m.phone,
            email: m.email,
          }));
          setAvailableMembers(mapped);
          setSelectedMemberId(
            (prev) => initialMemberId || prev || (mapped[0]?.id ?? "")
          );
        })
        .catch(() => {});
    }
  }, [isOpen, plans, members, initialMemberId]);

  useEffect(() => {
    if (initialMemberId) {
      setSelectedMemberId(initialMemberId);
    }
  }, [initialMemberId]);

  if (!isOpen) return null;

  const selectedPlan = availablePlans.find((p) => p.id === selectedPlanId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMemberId || !selectedPlanId) {
      setError("Please select both a member and a plan.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    // Client idempotency key to prevent double submits
    const idempotencyKey = `cash-${selectedMemberId}-${selectedPlanId}-${Date.now()}`;

    try {
      const resp: RecordCashPaymentResponse = await recordCashPayment({
        member_id: selectedMemberId,
        plan_id: selectedPlanId,
        notes: notes.trim(),
        idempotency_key: idempotencyKey,
      });

      setConfirmedReceipt(resp.receipt);
      if (onPaymentSuccess) {
        onPaymentSuccess(resp.receipt);
      }
    } catch (err: unknown) {
      const errObj = err as {
        detail?: string;
        data?: { detail?: string };
        message?: string;
      };
      const detail =
        errObj?.data?.detail ||
        errObj?.detail ||
        errObj?.message ||
        "Failed to record cash payment. Please verify inputs.";
      setError(
        typeof detail === "object" ? JSON.stringify(detail) : String(detail)
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const handleDone = () => {
    setConfirmedReceipt(null);
    setNotes("");
    onClose();
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "16px",
      }}
    >
      <div
        style={{
          backgroundColor: "#1e293b",
          borderRadius: "12px",
          width: "100%",
          maxWidth: "520px",
          padding: "24px",
          color: "#f8fafc",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)",
          border: "1px solid #334155",
        }}
      >
        {confirmedReceipt ? (
          <div>
            <div style={{ textAlign: "center", marginBottom: "20px" }}>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "56px",
                  height: "56px",
                  borderRadius: "50%",
                  backgroundColor: "#065f46",
                  color: "#34d399",
                  fontSize: "28px",
                  marginBottom: "12px",
                }}
              >
                ✓
              </div>
              <h2
                style={{
                  fontSize: "20px",
                  fontWeight: "bold",
                  margin: "0 0 4px",
                }}
              >
                Official Digital Receipt
              </h2>
              <p
                style={{
                  color: "#94a3b8",
                  fontSize: "14px",
                  margin: 0,
                  fontFamily: "monospace",
                }}
              >
                Receipt #{confirmedReceipt.receipt_number}
              </p>
            </div>

            <div
              style={{
                backgroundColor: "#0f172a",
                borderRadius: "8px",
                padding: "16px",
                marginBottom: "20px",
                border: "1px solid #1e293b",
                fontSize: "14px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                }}
              >
                <span style={{ color: "#94a3b8" }}>Member:</span>
                <span style={{ fontWeight: 600 }}>
                  {confirmedReceipt.member_name}
                </span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                }}
              >
                <span style={{ color: "#94a3b8" }}>Plan:</span>
                <span style={{ fontWeight: 600 }}>
                  {confirmedReceipt.plan_name}
                </span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                }}
              >
                <span style={{ color: "#94a3b8" }}>Duration:</span>
                <span>{confirmedReceipt.plan_duration}</span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                }}
              >
                <span style={{ color: "#94a3b8" }}>Payment Method:</span>
                <span
                  style={{
                    textTransform: "uppercase",
                    color: "#38bdf8",
                    fontWeight: 600,
                  }}
                >
                  {confirmedReceipt.payment_method}
                </span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                }}
              >
                <span style={{ color: "#94a3b8" }}>Issued By:</span>
                <span>{confirmedReceipt.issued_by_name}</span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                }}
              >
                <span style={{ color: "#94a3b8" }}>Date & Time:</span>
                <span>
                  {new Date(confirmedReceipt.issued_at).toLocaleString()}
                </span>
              </div>
              <hr
                style={{
                  borderColor: "#334155",
                  margin: "12px 0",
                  borderTopWidth: "1px",
                }}
              />
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: "16px",
                  fontWeight: "bold",
                }}
              >
                <span>Total Amount:</span>
                <span style={{ color: "#34d399" }}>
                  {confirmedReceipt.amount_etb} {confirmedReceipt.currency}
                </span>
              </div>
              {confirmedReceipt.notes && (
                <div
                  style={{
                    marginTop: "12px",
                    color: "#94a3b8",
                    fontSize: "13px",
                  }}
                >
                  <span style={{ fontWeight: 600 }}>Notes: </span>
                  {confirmedReceipt.notes}
                </div>
              )}
            </div>

            <div style={{ display: "flex", gap: "12px" }}>
              <button
                type="button"
                onClick={handlePrint}
                style={{
                  flex: 1,
                  backgroundColor: "#334155",
                  color: "#f8fafc",
                  border: "none",
                  borderRadius: "8px",
                  padding: "10px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                🖨️ Print Receipt
              </button>
              <button
                type="button"
                onClick={handleDone}
                style={{
                  flex: 1,
                  backgroundColor: "#10b981",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "10px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "16px",
              }}
            >
              <h2
                style={{ fontSize: "18px", fontWeight: "bold", margin: 0 }}
                id="record-cash-payment-title"
              >
                Record Cash Payment
              </h2>
              <button
                type="button"
                onClick={onClose}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  fontSize: "20px",
                  cursor: "pointer",
                }}
              >
                ✕
              </button>
            </div>

            {error && (
              <div
                style={{
                  backgroundColor: "#450a0a",
                  color: "#f87171",
                  border: "1px solid #dc2626",
                  padding: "10px 14px",
                  borderRadius: "6px",
                  marginBottom: "16px",
                  fontSize: "14px",
                }}
              >
                {error}
              </div>
            )}

            {/* Member selector */}
            <div style={{ marginBottom: "16px" }}>
              <label
                style={{
                  display: "block",
                  fontSize: "14px",
                  fontWeight: 500,
                  color: "#cbd5e1",
                  marginBottom: "6px",
                }}
              >
                Select Member
              </label>
              <select
                value={selectedMemberId}
                onChange={(e) => setSelectedMemberId(e.target.value)}
                style={{
                  width: "100%",
                  backgroundColor: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  padding: "10px",
                  color: "#f8fafc",
                  fontSize: "14px",
                }}
                required
              >
                <option value="">-- Choose Member --</option>
                {availableMembers.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.full_name} {m.phone ? `(${m.phone})` : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Plan selector */}
            <div style={{ marginBottom: "16px" }}>
              <label
                style={{
                  display: "block",
                  fontSize: "14px",
                  fontWeight: 500,
                  color: "#cbd5e1",
                  marginBottom: "6px",
                }}
              >
                Membership Plan
              </label>
              <select
                value={selectedPlanId}
                onChange={(e) => setSelectedPlanId(e.target.value)}
                style={{
                  width: "100%",
                  backgroundColor: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  padding: "10px",
                  color: "#f8fafc",
                  fontSize: "14px",
                }}
                required
              >
                <option value="">-- Choose Plan --</option>
                {availablePlans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} - {p.price_etb} ETB ({p.duration_value}{" "}
                    {p.duration_unit})
                  </option>
                ))}
              </select>
            </div>

            {/* Immutable Plan Price Display */}
            {selectedPlan && (
              <div
                style={{
                  backgroundColor: "#0f172a",
                  borderRadius: "8px",
                  padding: "12px 16px",
                  marginBottom: "16px",
                  border: "1px solid #334155",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontSize: "13px", color: "#94a3b8" }}>
                    Price to Collect (Cash)
                  </div>
                  <div
                    style={{
                      fontSize: "18px",
                      fontWeight: "bold",
                      color: "#34d399",
                    }}
                  >
                    {selectedPlan.price_etb} ETB
                  </div>
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: "#64748b",
                    backgroundColor: "#1e293b",
                    padding: "4px 8px",
                    borderRadius: "4px",
                  }}
                >
                  Immutable standard price
                </div>
              </div>
            )}

            {/* Optional Notes */}
            <div style={{ marginBottom: "20px" }}>
              <label
                style={{
                  display: "block",
                  fontSize: "14px",
                  fontWeight: 500,
                  color: "#cbd5e1",
                  marginBottom: "6px",
                }}
              >
                Notes (Optional)
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Front desk receipt issued"
                rows={2}
                style={{
                  width: "100%",
                  backgroundColor: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  color: "#f8fafc",
                  fontSize: "14px",
                  resize: "vertical",
                }}
              />
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: "12px",
              }}
            >
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                style={{
                  backgroundColor: "#334155",
                  color: "#f8fafc",
                  border: "none",
                  borderRadius: "6px",
                  padding: "10px 16px",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !selectedPlan}
                style={{
                  backgroundColor: "#10b981",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  padding: "10px 20px",
                  fontWeight: 600,
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                  opacity: isSubmitting ? 0.7 : 1,
                }}
              >
                {isSubmitting
                  ? "Confirming..."
                  : "Confirm Cash & Issue Receipt"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
