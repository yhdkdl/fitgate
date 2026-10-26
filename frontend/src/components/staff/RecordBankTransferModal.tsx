import React, { useState, useEffect } from "react";
import {
  recordBankTransferPayment,
  DigitalReceipt,
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

const CHANNELS = ["CBE", "Telebirr", "Awash", "Other"];

export const RecordBankTransferModal: React.FC<Props> = ({
  isOpen,
  onClose,
  plans,
  members,
  onPaymentSuccess,
  initialMemberId,
}) => {
  const [availablePlans, setAvailablePlans] = useState<PlanOption[]>(plans || []);
  const [availableMembers, setAvailableMembers] = useState<MemberOption[]>(members || []);
  const [selectedMemberId, setSelectedMemberId] = useState<string>(
    initialMemberId || (members?.[0]?.id ?? "")
  );
  const [selectedPlanId, setSelectedPlanId] = useState<string>(plans?.[0]?.id ?? "");
  const [bankReference, setBankReference] = useState("");
  const [transferDate, setTransferDate] = useState(() => new Date().toISOString().split("T")[0]);
  const [channel, setChannel] = useState("");
  const [notes, setNotes] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmedReceipt, setConfirmedReceipt] = useState<DigitalReceipt | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    // Create client idempotency key when payment window opens, scoped per gym tenant
    const tenantPrefix = window.location.hostname.split(".")[0] || "gym";
    setIdempotencyKey(
      `bank-${tenantPrefix}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
    );

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
          if (mapped.length > 0) setSelectedPlanId((prev) => prev || mapped[0].id);
        })
        .catch(() => {});
    }

    if (members && members.length > 0) {
      setAvailableMembers(members);
      setSelectedMemberId((prev) => prev || members[0].id);
    } else {
      listGymMembers()
        .then((data) => {
          const mapped = (data || []).map((m: { id: string; full_name: string; phone?: string; email?: string }) => ({
            id: m.id,
            full_name: m.full_name,
            phone: m.phone,
            email: m.email,
          }));
          setAvailableMembers(mapped);
          if (mapped.length > 0) setSelectedMemberId((prev) => prev || mapped[0].id);
        })
        .catch(() => {});
    }

    setBankReference("");
    setTransferDate(new Date().toISOString().split("T")[0]);
    setChannel("");
    setNotes("");
    setError(null);
    setConfirmedReceipt(null);
  }, [isOpen, plans, members]);

  if (!isOpen) return null;

  const selectedPlan = availablePlans.find((p) => p.id === selectedPlanId);
  const todayStr = new Date().toISOString().split("T")[0];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMemberId) {
      setError("Please select a member.");
      return;
    }
    if (!selectedPlanId) {
      setError("Please select a membership plan.");
      return;
    }
    const trimmedRef = bankReference.trim();
    if (trimmedRef.length < 3 || trimmedRef.length > 100) {
      setError("Bank transaction reference must be between 3 and 100 characters.");
      return;
    }
    if (!transferDate) {
      setError("Transfer date is required.");
      return;
    }
    if (transferDate > todayStr) {
      setError("Transfer date cannot be in the future.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const resp = await recordBankTransferPayment({
        member_id: selectedMemberId,
        plan_id: selectedPlanId,
        bank_reference: trimmedRef,
        transfer_date: transferDate,
        channel: channel || undefined,
        notes: notes.trim() || undefined,
        idempotency_key: idempotencyKey,
      });

      setConfirmedReceipt(resp.receipt);
      if (onPaymentSuccess) {
        onPaymentSuccess(resp.receipt);
      }
    } catch (err: unknown) {
      const errorObj = err as { data?: { detail?: unknown } };
      const detail = errorObj?.data?.detail;
      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.join(", "));
      } else if (typeof detail === "object" && detail !== null) {
        setError(Object.values(detail).flat().join(", "));
      } else {
        setError("Failed to record bank-transfer payment. Please verify inputs.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.7)",
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
          border: "1px solid #334155",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)",
          maxHeight: "90vh",
          overflowY: "auto",
        }}
      >
        {confirmedReceipt ? (
          <div>
            <div style={{ textAlign: "center", marginBottom: "20px" }}>
              <div style={{ fontSize: "40px", marginBottom: "8px" }}>✅</div>
              <h3 style={{ fontSize: "20px", fontWeight: "bold", margin: 0 }}>
                Payment Confirmed & Receipt Issued
              </h3>
              <p style={{ color: "#94a3b8", fontSize: "14px", marginTop: "4px" }}>
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
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "#94a3b8" }}>Member:</span>
                <span style={{ fontWeight: 600 }}>{confirmedReceipt.member_name}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "#94a3b8" }}>Plan:</span>
                <span style={{ fontWeight: 600 }}>{confirmedReceipt.plan_name}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "#94a3b8" }}>Method:</span>
                <span style={{ textTransform: "uppercase", color: "#38bdf8", fontWeight: 600 }}>
                  Bank Transfer
                </span>
              </div>
              {confirmedReceipt.bank_reference && (
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ color: "#94a3b8" }}>Reference:</span>
                  <span style={{ fontFamily: "monospace", color: "#a78bfa", fontWeight: 600 }}>
                    {confirmedReceipt.bank_reference}
                  </span>
                </div>
              )}
              {confirmedReceipt.transfer_channel && (
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                  <span style={{ color: "#94a3b8" }}>Channel:</span>
                  <span>{confirmedReceipt.transfer_channel}</span>
                </div>
              )}
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "#94a3b8" }}>Issued By:</span>
                <span>{confirmedReceipt.issued_by_name}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ color: "#94a3b8" }}>Date:</span>
                <span>{new Date(confirmedReceipt.issued_at).toLocaleString()}</span>
              </div>
              <hr style={{ borderColor: "#334155", margin: "12px 0", borderTopWidth: "1px" }} />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "16px", fontWeight: "bold" }}>
                <span>Total Amount:</span>
                <span style={{ color: "#34d399" }}>
                  {confirmedReceipt.amount_etb} {confirmedReceipt.currency}
                </span>
              </div>
              {confirmedReceipt.notes && (
                <div style={{ marginTop: "12px", color: "#94a3b8", fontSize: "13px" }}>
                  <span style={{ fontWeight: 600 }}>Notes: </span>
                  {confirmedReceipt.notes}
                </div>
              )}
            </div>

            <div style={{ display: "flex", gap: "10px" }}>
              <button
                type="button"
                onClick={() => window.print()}
                style={{
                  flex: 1,
                  backgroundColor: "#334155",
                  color: "#f8fafc",
                  border: "none",
                  borderRadius: "6px",
                  padding: "10px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                🖨️ Print Receipt
              </button>
              <button
                type="button"
                onClick={onClose}
                style={{
                  flex: 1,
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
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
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h3 style={{ fontSize: "18px", fontWeight: "bold", margin: 0 }}>
                🏦 Record Bank Transfer Payment
              </h3>
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                style={{
                  backgroundColor: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  fontSize: "20px",
                  cursor: "pointer",
                }}
              >
                ×
              </button>
            </div>

            {error && (
              <div
                style={{
                  backgroundColor: "#7f1d1d",
                  color: "#fecaca",
                  padding: "10px 14px",
                  borderRadius: "6px",
                  fontSize: "13px",
                  marginBottom: "16px",
                }}
              >
                {error}
              </div>
            )}

            {/* Member Selection */}
            <div style={{ marginBottom: "14px" }}>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 500, color: "#cbd5e1", marginBottom: "4px" }}>
                Select Member *
              </label>
              <select
                value={selectedMemberId}
                onChange={(e) => setSelectedMemberId(e.target.value)}
                style={{
                  width: "100%",
                  backgroundColor: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  color: "#f8fafc",
                  fontSize: "14px",
                }}
              >
                {availableMembers.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.full_name} {m.phone ? `(${m.phone})` : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Plan Selection */}
            <div style={{ marginBottom: "14px" }}>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 500, color: "#cbd5e1", marginBottom: "4px" }}>
                Select Membership Plan *
              </label>
              <select
                value={selectedPlanId}
                onChange={(e) => setSelectedPlanId(e.target.value)}
                style={{
                  width: "100%",
                  backgroundColor: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  color: "#f8fafc",
                  fontSize: "14px",
                }}
              >
                {availablePlans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} - {p.price_etb} ETB ({p.duration_value} {p.duration_unit})
                  </option>
                ))}
              </select>
            </div>

            {/* Immutable Locked Plan Price */}
            {selectedPlan && (
              <div
                style={{
                  backgroundColor: "#0f172a",
                  borderRadius: "8px",
                  padding: "10px 14px",
                  marginBottom: "14px",
                  border: "1px solid #334155",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div>
                  <div style={{ fontSize: "12px", color: "#94a3b8" }}>Plan Amount (Locked)</div>
                  <div style={{ fontSize: "16px", fontWeight: "bold", color: "#34d399" }}>
                    {selectedPlan.price_etb} ETB
                  </div>
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", backgroundColor: "#1e293b", padding: "3px 6px", borderRadius: "4px" }}>
                  Locked to plan price
                </div>
              </div>
            )}

            {/* Bank Reference */}
            <div style={{ marginBottom: "14px" }}>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 500, color: "#cbd5e1", marginBottom: "4px" }}>
                Bank Transaction Reference * (3 to 100 characters)
              </label>
              <input
                type="text"
                value={bankReference}
                onChange={(e) => setBankReference(e.target.value)}
                placeholder="e.g. FT26010ABC123"
                minLength={3}
                maxLength={100}
                required
                style={{
                  width: "100%",
                  backgroundColor: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  color: "#f8fafc",
                  fontSize: "14px",
                  fontFamily: "monospace",
                }}
              />
            </div>

            {/* Transfer Date & Channel in two columns */}
            <div style={{ display: "flex", gap: "12px", marginBottom: "14px" }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: "block", fontSize: "13px", fontWeight: 500, color: "#cbd5e1", marginBottom: "4px" }}>
                  Transfer Date *
                </label>
                <input
                  type="date"
                  value={transferDate}
                  max={todayStr}
                  onChange={(e) => setTransferDate(e.target.value)}
                  required
                  style={{
                    width: "100%",
                    backgroundColor: "#0f172a",
                    border: "1px solid #475569",
                    borderRadius: "6px",
                    padding: "8px 12px",
                    color: "#f8fafc",
                    fontSize: "14px",
                  }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: "block", fontSize: "13px", fontWeight: 500, color: "#cbd5e1", marginBottom: "4px" }}>
                  Channel (Optional)
                </label>
                <select
                  value={channel}
                  onChange={(e) => setChannel(e.target.value)}
                  style={{
                    width: "100%",
                    backgroundColor: "#0f172a",
                    border: "1px solid #475569",
                    borderRadius: "6px",
                    padding: "8px 12px",
                    color: "#f8fafc",
                    fontSize: "14px",
                  }}
                >
                  <option value="">Select Channel</option>
                  {CHANNELS.map((ch) => (
                    <option key={ch} value={ch}>
                      {ch}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Optional Notes */}
            <div style={{ marginBottom: "18px" }}>
              <label style={{ display: "block", fontSize: "13px", fontWeight: 500, color: "#cbd5e1", marginBottom: "4px" }}>
                Notes (Optional, max 1000 characters)
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Optional transfer remarks"
                rows={2}
                maxLength={1000}
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

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                style={{
                  backgroundColor: "#334155",
                  color: "#f8fafc",
                  border: "none",
                  borderRadius: "6px",
                  padding: "9px 16px",
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
                  backgroundColor: "#0284c7",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  padding: "9px 18px",
                  fontWeight: 600,
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                  opacity: isSubmitting ? 0.7 : 1,
                }}
              >
                {isSubmitting ? "Recording..." : "Confirm Bank Transfer & Issue Receipt"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
