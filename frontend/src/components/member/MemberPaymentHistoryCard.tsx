import React, { useEffect, useState } from "react";
import {
  getMemberPaymentHistory,
  MemberPaymentHistoryItem,
} from "../../api/payments";

export const MemberPaymentHistoryCard: React.FC = () => {
  const [history, setHistory] = useState<MemberPaymentHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getMemberPaymentHistory();
        setHistory(data.results || []);
      } catch {
        setError("Could not load payment history.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <div style={{ color: "#94a3b8" }}>Loading payment history...</div>;
  }

  if (error) {
    return <div style={{ color: "#f87171" }}>{error}</div>;
  }

  if (history.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        backgroundColor: "#1e293b",
        borderRadius: "10px",
        padding: "20px",
        border: "1px solid #334155",
        marginTop: "20px",
      }}
    >
      <h3
        style={{
          fontSize: "16px",
          fontWeight: 600,
          color: "#f8fafc",
          marginTop: 0,
          marginBottom: "16px",
        }}
      >
        My Payment History & Receipts
      </h3>

      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {history.map((item) => (
          <div
            key={item.id}
            style={{
              backgroundColor: "#0f172a",
              borderRadius: "8px",
              padding: "12px 16px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              border: "1px solid #334155",
            }}
          >
            <div>
              <div
                style={{ fontWeight: 600, color: "#f8fafc", fontSize: "14px" }}
              >
                {item.plan_name || "Subscription Plan"}
              </div>
              <div
                style={{
                  fontSize: "12px",
                  color: "#94a3b8",
                  marginTop: "2px",
                }}
              >
                {new Date(item.created_at).toLocaleDateString()} • Method:{" "}
                <span style={{ textTransform: "uppercase", fontWeight: 600 }}>
                  {item.method}
                </span>
                {item.receipt_number && (
                  <span
                    style={{
                      marginLeft: "8px",
                      color: "#38bdf8",
                      fontFamily: "monospace",
                    }}
                  >
                    Receipt #{item.receipt_number}
                  </span>
                )}
              </div>
              {item.subscription_end_date && (
                <div
                  style={{
                    fontSize: "11px",
                    color: "#64748b",
                    marginTop: "2px",
                  }}
                >
                  Active until {item.subscription_end_date}
                </div>
              )}
            </div>

            <div style={{ textAlign: "right" }}>
              <div
                style={{
                  fontWeight: "bold",
                  color: "#34d399",
                  fontSize: "15px",
                }}
              >
                {item.amount_etb} {item.currency}
              </div>
              <div
                style={{
                  fontSize: "11px",
                  textTransform: "capitalize",
                  fontWeight: 600,
                  color:
                    item.status === "confirmed"
                      ? "#34d399"
                      : item.status === "pending"
                        ? "#fbbf24"
                        : "#f87171",
                  marginTop: "2px",
                }}
              >
                {item.status}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
