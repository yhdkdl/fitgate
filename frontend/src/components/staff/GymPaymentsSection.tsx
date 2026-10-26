import React, { useState, useEffect, useCallback } from "react";
import {
  getGymPayments,
  GymPaymentListResponse,
  DigitalReceipt,
  getReceiptDetail,
} from "../../api/payments";
import { RecordCashPaymentModal } from "./RecordCashPaymentModal";

export const GymPaymentsSection: React.FC = () => {
  const [paymentsData, setPaymentsData] =
    useState<GymPaymentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [methodFilter, setMethodFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [viewingReceipt, setViewingReceipt] = useState<DigitalReceipt | null>(
    null
  );
  const [receiptLoading, setReceiptLoading] = useState(false);
  const [showRecordCashModal, setShowRecordCashModal] = useState(false);

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

  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  const handleOpenReceipt = async (paymentId: string) => {
    setReceiptLoading(true);
    try {
      const receipt = await getReceiptDetail(paymentId);
      setViewingReceipt(receipt);
    } catch {
      alert("Receipt details could not be retrieved.");
    } finally {
      setReceiptLoading(false);
    }
  };

  return (
    <div style={{ padding: "16px 0" }}>
      {/* Header and Record Cash Action */}
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
            Audit payment records, confirmed receipts, and revenue totals.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowRecordCashModal(true)}
          style={{
            backgroundColor: "#2563eb",
            color: "#ffffff",
            border: "none",
            borderRadius: "6px",
            padding: "8px 16px",
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
      </div>

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
          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>
            Total from confirmed payments
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
          <div style={{ fontSize: "12px", color: "#64748b", marginTop: "4px" }}>
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
                  }}
                >
                  <td style={{ padding: "12px 16px", whiteSpace: "nowrap" }}>
                    {new Date(p.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: "12px 16px", fontWeight: 500 }}>
                    {p.member_name || "—"}
                  </td>
                  <td style={{ padding: "12px 16px" }}>{p.plan_name || "—"}</td>
                  <td style={{ padding: "12px 16px" }}>
                    <span
                      style={{
                        textTransform: "uppercase",
                        fontSize: "11px",
                        fontWeight: 600,
                        backgroundColor:
                          p.method === "cash" ? "#14532d" : "#0c4a6e",
                        color: p.method === "cash" ? "#86efac" : "#7dd3fc",
                        padding: "3px 8px",
                        borderRadius: "4px",
                      }}
                    >
                      {p.method}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", fontWeight: 600 }}>
                    {p.amount_etb} {p.currency}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
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
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    {p.receipt_number ? (
                      <button
                        type="button"
                        onClick={() => handleOpenReceipt(p.id)}
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

      {viewingReceipt && (
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
              maxWidth: "480px",
              padding: "24px",
              color: "#f8fafc",
              border: "1px solid #334155",
            }}
          >
            <div style={{ textAlign: "center", marginBottom: "16px" }}>
              <h3
                style={{
                  fontSize: "18px",
                  fontWeight: "bold",
                  margin: "0 0 4px",
                }}
              >
                Receipt #{viewingReceipt.receipt_number}
              </h3>
              <p style={{ color: "#94a3b8", fontSize: "13px", margin: 0 }}>
                {viewingReceipt.gym_name}
              </p>
            </div>
            <div
              style={{
                backgroundColor: "#0f172a",
                borderRadius: "8px",
                padding: "16px",
                fontSize: "13px",
                marginBottom: "20px",
                border: "1px solid #334155",
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
                  {viewingReceipt.member_name}
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
                <span>{viewingReceipt.plan_name}</span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                }}
              >
                <span style={{ color: "#94a3b8" }}>Amount:</span>
                <span style={{ color: "#34d399", fontWeight: "bold" }}>
                  {viewingReceipt.amount_etb} ETB
                </span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                }}
              >
                <span style={{ color: "#94a3b8" }}>Method:</span>
                <span style={{ textTransform: "uppercase" }}>
                  {viewingReceipt.payment_method}
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
                <span>{viewingReceipt.issued_by_name}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#94a3b8" }}>Date:</span>
                <span>
                  {new Date(viewingReceipt.issued_at).toLocaleString()}
                </span>
              </div>
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
                🖨️ Print
              </button>
              <button
                type="button"
                onClick={() => setViewingReceipt(null)}
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
                Close
              </button>
            </div>
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
    </div>
  );
};
