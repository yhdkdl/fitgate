import React, { useState, useEffect, useCallback } from "react";
import {
  getGymPayments,
  GymPaymentListResponse,
  DigitalReceipt,
  getReceiptDetail,
  getUnreconciledBankTransfers,
  reconcileBankTransfers,
  reverseBankTransfer,
  UnreconciledBankTransferItem,
} from "../../api/payments";
import { useAuth } from "../../context/AuthContext";
import { RecordCashPaymentModal } from "./RecordCashPaymentModal";
import { RecordBankTransferModal } from "./RecordBankTransferModal";
import { DigitalReceiptModal } from "../ui/DigitalReceiptModal";
import { AuthenticatedImage } from "../ui/AuthenticatedImage";

export const GymPaymentsSection: React.FC = () => {
  const { user } = useAuth();
  const isOwner = user?.role === "owner";

  const [activeTab, setActiveTab] = useState<"payments" | "unreconciled">(
    "payments"
  );
  const [paymentsData, setPaymentsData] =
    useState<GymPaymentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [methodFilter, setMethodFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [viewingReceipt, setViewingReceipt] = useState<DigitalReceipt | null>(
    null
  );
  const [viewingScreenshot, setViewingScreenshot] = useState<{
    url: string;
    reference: string;
  } | null>(null);
  const [receiptLoading, setReceiptLoading] = useState(false);
  const [showRecordCashModal, setShowRecordCashModal] = useState(false);
  const [showRecordBankModal, setShowRecordBankModal] = useState(false);

  // Unreconciled bank transfers state (Owner only)
  const [unreconciled, setUnreconciled] = useState<
    UnreconciledBankTransferItem[]
  >([]);
  const [unreconciledLoading, setUnreconciledLoading] = useState(false);
  const [unreconciledError, setUnreconciledError] = useState<string | null>(
    null
  );
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [reconciling, setReconciling] = useState(false);

  // Reversal state
  const [reversingPayment, setReversingPayment] =
    useState<UnreconciledBankTransferItem | null>(null);
  const [reversalReason, setReversalReason] = useState("");
  const [reversalLoading, setReversalLoading] = useState(false);
  const [reversalError, setReversalError] = useState<string | null>(null);

  const fetchPayments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getGymPayments({
        method: methodFilter || undefined,
        status: statusFilter || undefined,
      });
      setPaymentsData(data);
    } catch {
      setError("Failed to load payment history.");
    } finally {
      setLoading(false);
    }
  }, [methodFilter, statusFilter]);

  const fetchUnreconciled = useCallback(async () => {
    if (!isOwner) return;
    setUnreconciledLoading(true);
    setUnreconciledError(null);
    try {
      const data = await getUnreconciledBankTransfers();
      setUnreconciled(data.results || []);
      setSelectedIds([]);
    } catch {
      setUnreconciledError("Failed to load unreconciled bank transfers.");
    } finally {
      setUnreconciledLoading(false);
    }
  }, [isOwner]);

  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  useEffect(() => {
    if (activeTab === "unreconciled" && isOwner) {
      fetchUnreconciled();
    }
  }, [activeTab, isOwner, fetchUnreconciled]);

  const handleOpenReceipt = async (receiptRef: string) => {
    setReceiptLoading(true);
    try {
      const receipt = await getReceiptDetail(receiptRef);
      setViewingReceipt(receipt);
    } catch {
      alert("Receipt details could not be retrieved.");
    } finally {
      setReceiptLoading(false);
    }
  };

  const handleClearSingle = async (paymentId: string) => {
    if (
      !window.confirm(
        "Confirm that this transfer appears on your official bank statement?"
      )
    )
      return;
    setReconciling(true);
    try {
      await reconcileBankTransfers([paymentId]);
      await fetchUnreconciled();
      await fetchPayments();
    } catch (err: unknown) {
      const errorObj = err as { data?: { detail?: string } };
      alert(errorObj?.data?.detail || "Failed to reconcile transfer.");
    } finally {
      setReconciling(false);
    }
  };

  const handleClearSelected = async () => {
    if (selectedIds.length === 0) return;
    if (
      !window.confirm(
        `Clear ${selectedIds.length} selected transfer(s) against your bank statement?`
      )
    )
      return;
    setReconciling(true);
    try {
      await reconcileBankTransfers(selectedIds);
      await fetchUnreconciled();
      await fetchPayments();
    } catch (err: unknown) {
      const errorObj = err as { data?: { detail?: string } };
      alert(
        errorObj?.data?.detail || "Failed to reconcile selected transfers."
      );
    } finally {
      setReconciling(false);
    }
  };

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedIds(unreconciled.map((t) => t.id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleConfirmReversal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reversingPayment) return;
    const trimmed = reversalReason.trim();
    if (trimmed.length < 5 || trimmed.length > 500) {
      setReversalError("Reason must be between 5 and 500 characters.");
      return;
    }
    setReversalLoading(true);
    setReversalError(null);
    try {
      await reverseBankTransfer(reversingPayment.id, trimmed);
      setReversingPayment(null);
      setReversalReason("");
      await fetchUnreconciled();
      await fetchPayments();
    } catch (err: unknown) {
      const errorObj = err as { data?: { detail?: string } };
      setReversalError(
        errorObj?.data?.detail || "Failed to reverse bank transfer."
      );
    } finally {
      setReversalLoading(false);
    }
  };

  return (
    <div style={{ padding: "16px 0" }}>
      {/* Header and Payment Recording Buttons */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div>
          <h2
            style={{
              fontSize: "18px",
              fontWeight: "bold",
              margin: 0,
              color: "#f8fafc",
            }}
          >
            Gym Payments & Revenue
          </h2>
          <p style={{ fontSize: "13px", color: "#94a3b8", margin: "4px 0 0" }}>
            Audit payment records, bank transfers, confirmed receipts, and
            revenue totals.
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => setShowRecordCashModal(true)}
            style={{
              backgroundColor: "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              padding: "8px 14px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            💵 Record Cash Payment
          </button>
          <button
            type="button"
            onClick={() => setShowRecordBankModal(true)}
            style={{
              backgroundColor: "#0284c7",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              padding: "8px 14px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            🏦 Record Bank Transfer
          </button>
        </div>
      </div>

      {/* Tabs for Owner */}
      {isOwner && (
        <div
          style={{
            display: "flex",
            gap: "8px",
            borderBottom: "1px solid #334155",
            marginBottom: "16px",
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab("payments")}
            style={{
              backgroundColor: "transparent",
              border: "none",
              borderBottom:
                activeTab === "payments"
                  ? "2px solid #38bdf8"
                  : "2px solid transparent",
              color: activeTab === "payments" ? "#38bdf8" : "#94a3b8",
              padding: "8px 16px",
              fontSize: "14px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            All Payments & Revenue
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("unreconciled")}
            style={{
              backgroundColor: "transparent",
              border: "none",
              borderBottom:
                activeTab === "unreconciled"
                  ? "2px solid #38bdf8"
                  : "2px solid transparent",
              color: activeTab === "unreconciled" ? "#38bdf8" : "#94a3b8",
              padding: "8px 16px",
              fontSize: "14px",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <span>Unreconciled Bank Transfers</span>
            {unreconciled.length > 0 && (
              <span
                style={{
                  backgroundColor: "#ea580c",
                  color: "#ffffff",
                  borderRadius: "9999px",
                  padding: "1px 7px",
                  fontSize: "11px",
                  fontWeight: 700,
                }}
              >
                {unreconciled.length}
              </span>
            )}
          </button>
        </div>
      )}

      {activeTab === "unreconciled" && isOwner ? (
        <div>
          {/* Unreconciled Actions Bar */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "14px",
              backgroundColor: "#1e293b",
              padding: "12px 16px",
              borderRadius: "8px",
              border: "1px solid #334155",
            }}
          >
            <div style={{ fontSize: "13px", color: "#94a3b8" }}>
              Verify pending transfers against your bank statement. Transfers
              older than 7 days will be flagged.
            </div>
            {selectedIds.length > 0 && (
              <button
                type="button"
                onClick={handleClearSelected}
                disabled={reconciling}
                style={{
                  backgroundColor: "#059669",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  padding: "7px 14px",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: reconciling ? "not-allowed" : "pointer",
                }}
              >
                {reconciling
                  ? "Clearing..."
                  : `Clear Selected (${selectedIds.length})`}
              </button>
            )}
          </div>

          {unreconciledLoading ? (
            <div style={{ color: "#94a3b8", padding: "20px 0" }}>
              Loading unreconciled transfers...
            </div>
          ) : unreconciledError ? (
            <div style={{ color: "#f87171", padding: "20px 0" }}>
              {unreconciledError}
            </div>
          ) : unreconciled.length === 0 ? (
            <div
              style={{
                backgroundColor: "#1e293b",
                padding: "32px",
                textAlign: "center",
                borderRadius: "8px",
                color: "#94a3b8",
              }}
            >
              🎉 All bank transfers are reconciled!
            </div>
          ) : (
            <div
              style={{
                backgroundColor: "#1e293b",
                borderRadius: "8px",
                overflowX: "auto",
                border: "1px solid #334155",
              }}
            >
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "13px",
                  textAlign: "left",
                }}
              >
                <thead>
                  <tr
                    style={{
                      borderBottom: "1px solid #334155",
                      color: "#94a3b8",
                      backgroundColor: "#0f172a",
                    }}
                  >
                    <th style={{ padding: "12px 16px", width: "36px" }}>
                      <input
                        type="checkbox"
                        checked={
                          selectedIds.length === unreconciled.length &&
                          unreconciled.length > 0
                        }
                        onChange={handleSelectAll}
                      />
                    </th>
                    <th style={{ padding: "12px 16px" }}>Transfer Date</th>
                    <th style={{ padding: "12px 16px" }}>Bank Reference</th>
                    <th style={{ padding: "12px 16px" }}>Channel</th>
                    <th style={{ padding: "12px 16px" }}>Amount</th>
                    <th style={{ padding: "12px 16px" }}>Member</th>
                    <th style={{ padding: "12px 16px" }}>Confirmed By</th>
                    <th style={{ padding: "12px 16px" }}>Receipt</th>
                    <th style={{ padding: "12px 16px", textAlign: "right" }}>
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {unreconciled.map((t) => (
                    <tr
                      key={t.id}
                      style={{
                        borderBottom: "1px solid #334155",
                        color: "#f8fafc",
                      }}
                    >
                      <td style={{ padding: "12px 16px" }}>
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(t.id)}
                          onChange={() => handleToggleSelect(t.id)}
                        />
                      </td>
                      <td
                        style={{ padding: "12px 16px", whiteSpace: "nowrap" }}
                      >
                        {t.transfer_date}
                      </td>
                      <td
                        style={{
                          padding: "12px 16px",
                          fontFamily: "monospace",
                          color: "#a78bfa",
                        }}
                      >
                        <div>{t.bank_reference}</div>
                        {t.has_screenshot && (
                          <button
                            type="button"
                            onClick={() =>
                              setViewingScreenshot({
                                url:
                                  t.screenshot_url ||
                                  `/api/media/transfer-screenshots/${t.id}/`,
                                reference: t.bank_reference,
                              })
                            }
                            style={{
                              backgroundColor: "#334155",
                              color: "#38bdf8",
                              border: "1px solid #475569",
                              borderRadius: "4px",
                              padding: "2px 6px",
                              fontSize: "11px",
                              fontWeight: 600,
                              cursor: "pointer",
                              marginTop: "4px",
                              display: "inline-block",
                            }}
                          >
                            🖼️ View Screenshot
                          </button>
                        )}
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        {t.channel || "—"}
                      </td>
                      <td
                        style={{
                          padding: "12px 16px",
                          fontWeight: 600,
                          color: "#34d399",
                        }}
                      >
                        {t.amount_etb} ETB
                      </td>
                      <td style={{ padding: "12px 16px" }}>{t.member_name}</td>
                      <td style={{ padding: "12px 16px", color: "#94a3b8" }}>
                        {t.confirmed_by_name}
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        {t.receipt_number ? (
                          <button
                            type="button"
                            onClick={() =>
                              handleOpenReceipt(t.receipt_number || t.id)
                            }
                            style={{
                              background: "transparent",
                              border: "none",
                              fontFamily: "monospace",
                              color: "#38bdf8",
                              fontWeight: 600,
                              cursor: "pointer",
                              textDecoration: "underline",
                            }}
                          >
                            {t.receipt_number}
                          </button>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td
                        style={{
                          padding: "12px 16px",
                          textAlign: "right",
                          whiteSpace: "nowrap",
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => handleClearSingle(t.id)}
                          disabled={reconciling}
                          style={{
                            backgroundColor: "#059669",
                            color: "#ffffff",
                            border: "none",
                            borderRadius: "4px",
                            padding: "5px 10px",
                            fontSize: "12px",
                            fontWeight: 600,
                            cursor: "pointer",
                            marginRight: "8px",
                          }}
                        >
                          Clear
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setReversingPayment(t);
                            setReversalReason("");
                            setReversalError(null);
                          }}
                          disabled={reconciling}
                          style={{
                            backgroundColor: "#b91c1c",
                            color: "#ffffff",
                            border: "none",
                            borderRadius: "4px",
                            padding: "5px 10px",
                            fontSize: "12px",
                            fontWeight: 600,
                            cursor: "pointer",
                          }}
                        >
                          Reverse
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div>
          {/* Revenue Summary Card */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: "16px",
              marginBottom: "20px",
            }}
          >
            <div
              style={{
                backgroundColor: "#1e293b",
                borderRadius: "10px",
                padding: "20px",
                border: "1px solid #334155",
              }}
            >
              <div
                style={{
                  fontSize: "13px",
                  color: "#94a3b8",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Confirmed Revenue
              </div>
              <div
                style={{
                  fontSize: "26px",
                  fontWeight: "bold",
                  color: "#34d399",
                  marginTop: "6px",
                }}
              >
                {paymentsData
                  ? `${Number(paymentsData.total_confirmed_revenue_etb).toLocaleString()} ETB`
                  : "0 ETB"}
              </div>
              <div
                style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}
              >
                Total from confirmed, non-reversed payments
              </div>
            </div>

            <div
              style={{
                backgroundColor: "#1e293b",
                borderRadius: "10px",
                padding: "20px",
                border: "1px solid #334155",
              }}
            >
              <div
                style={{
                  fontSize: "13px",
                  color: "#94a3b8",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Transactions
              </div>
              <div
                style={{
                  fontSize: "26px",
                  fontWeight: "bold",
                  color: "#38bdf8",
                  marginTop: "6px",
                }}
              >
                {paymentsData ? paymentsData.count : 0}
              </div>
              <div
                style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}
              >
                Recorded payment records
              </div>
            </div>
          </div>

          {/* Filter Bar */}
          <div
            style={{
              display: "flex",
              gap: "12px",
              flexWrap: "wrap",
              marginBottom: "16px",
              backgroundColor: "#1e293b",
              padding: "12px 16px",
              borderRadius: "8px",
              border: "1px solid #334155",
            }}
          >
            <div>
              <label
                style={{
                  fontSize: "12px",
                  color: "#94a3b8",
                  display: "block",
                  marginBottom: "4px",
                }}
              >
                Method
              </label>
              <select
                value={methodFilter}
                onChange={(e) => setMethodFilter(e.target.value)}
                style={{
                  backgroundColor: "#0f172a",
                  color: "#f8fafc",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  padding: "6px 12px",
                  fontSize: "13px",
                }}
              >
                <option value="">All Methods</option>
                <option value="cash">Cash</option>
                <option value="chapa">Chapa</option>
                <option value="bank_transfer">Bank Transfer</option>
              </select>
            </div>

            <div>
              <label
                style={{
                  fontSize: "12px",
                  color: "#94a3b8",
                  display: "block",
                  marginBottom: "4px",
                }}
              >
                Status
              </label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  backgroundColor: "#0f172a",
                  color: "#f8fafc",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  padding: "6px 12px",
                  fontSize: "13px",
                }}
              >
                <option value="">All Statuses</option>
                <option value="confirmed">Confirmed</option>
                <option value="pending">Pending</option>
                <option value="reversed">Reversed</option>
                <option value="failed">Failed</option>
                <option value="abandoned">Abandoned</option>
              </select>
            </div>
          </div>

          {/* Table */}
          {loading ? (
            <div style={{ color: "#94a3b8", padding: "20px 0" }}>
              Loading payments...
            </div>
          ) : error ? (
            <div style={{ color: "#f87171", padding: "20px 0" }}>{error}</div>
          ) : paymentsData && paymentsData.results.length === 0 ? (
            <div
              style={{
                backgroundColor: "#1e293b",
                padding: "32px",
                textAlign: "center",
                borderRadius: "8px",
                color: "#94a3b8",
              }}
            >
              No payment transactions found.
            </div>
          ) : (
            <div
              style={{
                backgroundColor: "#1e293b",
                borderRadius: "8px",
                overflowX: "auto",
                border: "1px solid #334155",
              }}
            >
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "13px",
                  textAlign: "left",
                }}
              >
                <thead>
                  <tr
                    style={{
                      borderBottom: "1px solid #334155",
                      color: "#94a3b8",
                      backgroundColor: "#0f172a",
                    }}
                  >
                    <th style={{ padding: "12px 16px" }}>Date</th>
                    <th style={{ padding: "12px 16px" }}>Member</th>
                    <th style={{ padding: "12px 16px" }}>Plan</th>
                    <th style={{ padding: "12px 16px" }}>Method</th>
                    <th style={{ padding: "12px 16px" }}>Amount</th>
                    <th style={{ padding: "12px 16px" }}>Status</th>
                    <th style={{ padding: "12px 16px" }}>Receipt</th>
                  </tr>
                </thead>
                <tbody>
                  {paymentsData?.results.map((p) => (
                    <tr
                      key={p.id}
                      style={{
                        borderBottom: "1px solid #334155",
                        color: "#f8fafc",
                        backgroundColor:
                          p.is_reversed || p.status === "reversed"
                            ? "rgba(127, 29, 29, 0.15)"
                            : "transparent",
                      }}
                    >
                      <td
                        style={{ padding: "12px 16px", whiteSpace: "nowrap" }}
                      >
                        {new Date(p.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ padding: "12px 16px", fontWeight: 500 }}>
                        {p.member_name || "—"}
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        {p.plan_name || "—"}
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        <span
                          style={{
                            textTransform: "uppercase",
                            fontSize: "11px",
                            fontWeight: 600,
                            backgroundColor:
                              p.method === "cash"
                                ? "#14532d"
                                : p.method === "bank_transfer"
                                  ? "#4c1d95"
                                  : "#0c4a6e",
                            color:
                              p.method === "cash"
                                ? "#86efac"
                                : p.method === "bank_transfer"
                                  ? "#c4b5fd"
                                  : "#7dd3fc",
                            padding: "3px 8px",
                            borderRadius: "4px",
                          }}
                        >
                          {p.method === "bank_transfer"
                            ? "Bank Transfer"
                            : p.method}
                        </span>
                        {p.bank_reference && (
                          <div
                            style={{
                              fontSize: "11px",
                              fontFamily: "monospace",
                              color: "#a78bfa",
                              marginTop: "3px",
                            }}
                          >
                            Ref: {p.bank_reference}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "12px 16px", fontWeight: 600 }}>
                        <span
                          style={{
                            textDecoration:
                              p.is_reversed || p.status === "reversed"
                                ? "line-through"
                                : "none",
                            color:
                              p.is_reversed || p.status === "reversed"
                                ? "#94a3b8"
                                : "#f8fafc",
                          }}
                        >
                          {p.amount_etb} {p.currency}
                        </span>
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        {p.is_reversed || p.status === "reversed" ? (
                          <span
                            style={{
                              fontSize: "11px",
                              fontWeight: 700,
                              textTransform: "uppercase",
                              backgroundColor: "#7f1d1d",
                              color: "#fca5a5",
                              padding: "2px 6px",
                              borderRadius: "4px",
                            }}
                          >
                            REVERSED
                          </span>
                        ) : (
                          <span
                            style={{
                              fontSize: "11px",
                              fontWeight: 600,
                              textTransform: "capitalize",
                              color:
                                p.status === "confirmed"
                                  ? "#34d399"
                                  : p.status === "pending"
                                    ? "#fbbf24"
                                    : "#f87171",
                            }}
                          >
                            {p.status}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        {p.receipt_number ? (
                          <button
                            type="button"
                            onClick={() =>
                              handleOpenReceipt(p.receipt_number || p.id)
                            }
                            disabled={receiptLoading}
                            style={{
                              background: "transparent",
                              border: "none",
                              fontFamily: "monospace",
                              color: "#38bdf8",
                              fontWeight: 600,
                              cursor: "pointer",
                              textDecoration: "underline",
                            }}
                          >
                            {p.receipt_number}
                          </button>
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
      )}

      {/* Reusable Digital Receipt Modal (Items 3, 4, 5, 6) */}
      <DigitalReceiptModal
        isOpen={Boolean(viewingReceipt)}
        receipt={viewingReceipt}
        onClose={() => setViewingReceipt(null)}
      />

      {/* Bank Transfer Screenshot Modal (Item 17) */}
      {viewingScreenshot && (
        <div
          className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-surface border border-border rounded-xl max-w-lg w-full p-5 space-y-4 text-text">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <h3 className="font-bold text-sm text-text">
                  Transfer Screenshot
                </h3>
                <p className="text-xs text-text-muted font-mono">
                  Ref: {viewingScreenshot.reference}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setViewingScreenshot(null)}
                className="text-text-muted hover:text-text text-sm font-bold px-2 py-1"
              >
                ✕
              </button>
            </div>

            <div className="bg-bg rounded-lg p-2 border border-border flex items-center justify-center min-h-[200px]">
              <AuthenticatedImage
                src={viewingScreenshot.url}
                alt={`Bank transfer screenshot for ${viewingScreenshot.reference}`}
                className="max-h-[65vh] w-auto max-w-full rounded object-contain"
              />
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setViewingScreenshot(null)}
                className="bg-surface-2 hover:bg-border text-text text-xs font-semibold py-2 px-4 rounded-button min-h-[36px]"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reversal Modal (Owner only) */}
      {reversingPayment && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.75)",
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
              maxWidth: "500px",
              padding: "24px",
              color: "#f8fafc",
              border: "1px solid #7f1d1d",
            }}
          >
            <h3
              style={{
                fontSize: "18px",
                fontWeight: "bold",
                color: "#f87171",
                margin: "0 0 8px",
              }}
            >
              ⚠️ Reverse Bank Transfer Payment
            </h3>
            <p
              style={{
                fontSize: "13px",
                color: "#cbd5e1",
                lineHeight: "1.5",
                margin: "0 0 16px",
              }}
            >
              Reversing this transfer will restore the member's subscription to
              its exact prior state. The receipt will be preserved with a
              reversed status, and revenue will be deducted. This action is
              immutable and cannot be undone.
            </p>

            <div
              style={{
                backgroundColor: "#0f172a",
                borderRadius: "6px",
                padding: "12px",
                fontSize: "13px",
                marginBottom: "16px",
                border: "1px solid #334155",
              }}
            >
              <div>
                <strong>Member:</strong> {reversingPayment.member_name}
              </div>
              <div>
                <strong>Amount:</strong> {reversingPayment.amount_etb} ETB
              </div>
              <div>
                <strong>Reference:</strong>{" "}
                <span style={{ fontFamily: "monospace" }}>
                  {reversingPayment.bank_reference}
                </span>
              </div>
            </div>

            {reversalError && (
              <div
                style={{
                  backgroundColor: "#7f1d1d",
                  color: "#fca5a5",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  fontSize: "13px",
                  marginBottom: "14px",
                }}
              >
                {reversalError}
              </div>
            )}

            <form onSubmit={handleConfirmReversal}>
              <div style={{ marginBottom: "16px" }}>
                <label
                  style={{
                    display: "block",
                    fontSize: "13px",
                    fontWeight: 500,
                    color: "#cbd5e1",
                    marginBottom: "6px",
                  }}
                >
                  Reason for Reversal * (5 to 500 characters)
                </label>
                <textarea
                  value={reversalReason}
                  onChange={(e) => setReversalReason(e.target.value)}
                  placeholder="e.g. Bank confirmed payment bounce / fraudulent transaction reference"
                  minLength={5}
                  maxLength={500}
                  required
                  rows={3}
                  style={{
                    width: "100%",
                    backgroundColor: "#0f172a",
                    border: "1px solid #475569",
                    borderRadius: "6px",
                    padding: "8px 12px",
                    color: "#f8fafc",
                    fontSize: "13px",
                    resize: "vertical",
                  }}
                />
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: "10px",
                }}
              >
                <button
                  type="button"
                  onClick={() => setReversingPayment(null)}
                  disabled={reversalLoading}
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
                  disabled={reversalLoading || reversalReason.trim().length < 5}
                  style={{
                    backgroundColor: "#dc2626",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    padding: "9px 16px",
                    fontWeight: 600,
                    cursor: reversalLoading ? "not-allowed" : "pointer",
                    opacity: reversalLoading ? 0.7 : 1,
                  }}
                >
                  {reversalLoading ? "Reversing..." : "Confirm Reversal"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <RecordCashPaymentModal
        isOpen={showRecordCashModal}
        onClose={() => setShowRecordCashModal(false)}
        onPaymentSuccess={() => {
          setShowRecordCashModal(false);
          fetchPayments();
        }}
      />

      <RecordBankTransferModal
        isOpen={showRecordBankModal}
        onClose={() => setShowRecordBankModal(false)}
        onPaymentSuccess={() => {
          setShowRecordBankModal(false);
          fetchPayments();
          if (isOwner) fetchUnreconciled();
        }}
      />
    </div>
  );
};
