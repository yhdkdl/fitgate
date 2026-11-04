import React, { useEffect, useState } from "react";
import {
  getBankReceiptReviews,
  decideBankReceiptReview,
  type BankReceiptReviewItem,
} from "../../api/payments";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";

export const ReceiptReviewQueueSection: React.FC = () => {
  const [items, setItems] = useState<BankReceiptReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [selectedPhotoUrl, setSelectedPhotoUrl] = useState<string | null>(null);

  const fetchItems = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await getBankReceiptReviews();
      setItems(data);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to load receipt review items."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, []);

  const handleDecision = async (
    item: BankReceiptReviewItem,
    decision: "verified" | "declined"
  ) => {
    setDecidingId(item.id);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const resp = await decideBankReceiptReview(item.id, decision);
      setSuccessMsg(
        decision === "verified"
          ? `Receipt verified! Subscription activated for ${item.member_name}. Receipt #${resp.receipt_number || ""}`
          : `Receipt declined and reference released for ${item.member_name}.`
      );
      // Refresh queue
      await fetchItems();
    } catch (err: unknown) {
      const errorObj = err as { data?: { detail?: unknown } };
      const detail = errorObj?.data?.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : err instanceof Error
            ? err.message
            : "Failed to apply review decision.";
      setErrorMsg(msg);
      // Refresh to update if decided by someone else
      fetchItems();
    } finally {
      setDecidingId(null);
    }
  };

  return (
    <div className="space-y-6" data-testid="receipt-review-queue-section">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-4">
        <div>
          <h2 className="text-xl font-bold text-text flex items-center gap-2">
            Bank Receipt Review Queue
            {items.length > 0 && (
              <Badge variant="warning">{items.length} Pending</Badge>
            )}
          </h2>
          <p className="text-xs text-text-muted mt-1">
            Review member bank transfers that could not be verified
            automatically or had mismatched receipt details.
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={fetchItems}
          disabled={loading}
        >
          {loading ? "Refreshing..." : "Refresh Queue"}
        </Button>
      </div>

      {successMsg && <Alert variant="success">{successMsg}</Alert>}
      {errorMsg && <Alert variant="danger">{errorMsg}</Alert>}

      {loading ? (
        <Card className="p-8 flex flex-col items-center justify-center space-y-3">
          <Spinner size="md" />
          <span className="text-xs text-text-muted">
            Loading review queue...
          </span>
        </Card>
      ) : items.length === 0 ? (
        <Card className="p-8 text-center space-y-2">
          <div className="text-3xl">🎉</div>
          <h3 className="text-sm font-semibold text-text">
            No pending reviews
          </h3>
          <p className="text-xs text-text-muted max-w-sm mx-auto">
            All bank receipts have been verified or reconciled. New staff
            submissions requiring approval will appear here.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map((item) => {
            const raw = (item.receipt_verification_data ||
              {}) as Record<string, unknown>;
            const verifierAmount =
              raw.amount_etb !== undefined && raw.amount_etb !== null
                ? String(raw.amount_etb)
                : null;
            const verifierAccount = raw.account_number
              ? String(raw.account_number)
              : raw.receiver_account
                ? String(raw.receiver_account)
                : null;
            const verifierDate = raw.transaction_date
              ? String(raw.transaction_date)
              : null;
            const verifierErrorMessage = raw.error_message
              ? String(raw.error_message)
              : null;
            const isProcessing = decidingId === item.id;

            return (
              <Card
                key={item.id}
                className="p-5 space-y-4 border border-border/80 bg-surface shadow-sm"
                data-testid={`review-card-${item.id}`}
              >
                {/* Header row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/50 pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-base font-bold text-text">
                        {item.member_name}
                      </span>
                      <span className="text-xs text-text-muted">
                        ({item.member_phone || "No phone"})
                      </span>
                      {item.is_upgrade && (
                        <Badge variant="primary">Plan Upgrade</Badge>
                      )}
                    </div>
                    <p className="text-xs text-text-muted mt-0.5">
                      Submitted on {new Date(item.created_at).toLocaleString()}
                    </p>
                  </div>
                  <Badge
                    variant={
                      item.verification_outcome === "mismatch"
                        ? "danger"
                        : "warning"
                    }
                  >
                    {item.verification_outcome === "mismatch"
                      ? "Receipt Mismatch"
                      : "Could Not Check"}
                  </Badge>
                </div>

                {/* Details Comparison */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  {/* Expected Data */}
                  <div className="bg-surface-2 p-3.5 rounded-lg border border-border/60 space-y-2">
                    <span className="font-semibold text-text uppercase tracking-wider text-[10px] block">
                      Gym Plan & Transfer Record
                    </span>
                    <div className="space-y-1.5">
                      <div className="flex justify-between">
                        <span className="text-text-muted">
                          Membership Plan:
                        </span>
                        <span className="font-semibold text-text">
                          {item.plan_name}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-text-muted">
                          Expected Amount:
                        </span>
                        <span className="font-bold text-primary text-sm">
                          {item.expected_amount_etb} ETB
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-text-muted">Bank Reference:</span>
                        <code className="font-mono text-text bg-surface-3 px-1.5 py-0.5 rounded">
                          {item.bank_reference}
                        </code>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-text-muted">Bank / Channel:</span>
                        <span className="text-text uppercase font-medium">
                          {item.bank} {item.channel ? `(${item.channel})` : ""}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-text-muted">Transfer Date:</span>
                        <span className="text-text">{item.transfer_date}</span>
                      </div>
                    </div>
                  </div>

                  {/* Verifier Returned Data */}
                  <div className="bg-surface-2 p-3.5 rounded-lg border border-border/60 space-y-2">
                    <span className="font-semibold text-text uppercase tracking-wider text-[10px] block">
                      Bank Look-up Data (Cheki)
                    </span>
                    {verifierAmount || verifierAccount || verifierDate ? (
                      <div className="space-y-1.5">
                        <div className="flex justify-between">
                          <span className="text-text-muted">
                            Receipt Shows Amount:
                          </span>
                          <span
                            className={`font-bold ${verifierAmount === item.expected_amount_etb
                              ? "text-success"
                              : "text-danger"
                              }`}
                          >
                            {verifierAmount
                              ? `${verifierAmount} ETB`
                              : "Not returned"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-text-muted">
                            Receiving Account:
                          </span>
                          <span className="font-mono text-text">
                            {verifierAccount || "Not returned"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-text-muted">
                            Transaction Date:
                          </span>
                          <span className="text-text">
                            {verifierDate || "Not returned"}
                          </span>
                        </div>
                        {verifierErrorMessage && (
                          <div className="text-[11px] text-danger mt-1">
                            {verifierErrorMessage}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-text-muted italic py-2">
                        {verifierErrorMessage ||
                          "Verifier did not return receipt details (service timeout, bank format unsupported, or bank not reached)."}
                      </div>
                    )}
                  </div>
                </div>

                {/* Photo proof */}
                {item.screenshot_url && (
                  <div className="flex items-center gap-3 bg-surface-2 p-2.5 rounded-lg border border-border/60">
                    <span className="text-xs text-text-muted font-medium">
                      Uploaded Receipt Photo:
                    </span>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        setSelectedPhotoUrl(
                          item.screenshot_url ||
                          `/api/gym/payments/bank-transfers/${item.id}/screenshot/`
                        )
                      }
                    >
                      View Receipt Photo
                    </Button>
                  </div>
                )}

                {/* Decision Prompt & Action Bar */}
                <div className="border-t border-border pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-0.5">
                    <p className="text-xs font-semibold text-text">
                      Choose Verified only if your statement shows exactly{" "}
                      <span className="text-primary font-bold">
                        {item.expected_amount_etb} ETB
                      </span>{" "}
                      with this reference. If the amount is different, choose
                      Declined.
                    </p>
                    <p className="text-[11px] text-text-muted">
                      Owner and Manager statement check · Sequential receipt
                      issued upon approval
                    </p>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    <Button
                      type="button"
                      variant="danger"
                      size="sm"
                      disabled={isProcessing}
                      onClick={() => handleDecision(item, "declined")}
                    >
                      {isProcessing ? "Processing..." : "Declined"}
                    </Button>
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      disabled={isProcessing}
                      onClick={() => handleDecision(item, "verified")}
                    >
                      {isProcessing ? "Processing..." : "Verified"}
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Photo Preview Modal */}
      {selectedPhotoUrl && (
        <div
          className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50"
          onClick={() => setSelectedPhotoUrl(null)}
        >
          <div
            className="bg-surface p-4 rounded-lg max-w-2xl max-h-[90vh] overflow-auto flex flex-col gap-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center border-b border-border pb-2">
              <h3 className="text-sm font-bold text-text">
                Receipt Photo Proof
              </h3>
              <button
                type="button"
                className="text-text-muted hover:text-text font-bold text-base"
                onClick={() => setSelectedPhotoUrl(null)}
              >
                ✕
              </button>
            </div>
            <img
              src={selectedPhotoUrl}
              alt="Receipt proof"
              className="max-h-[70vh] object-contain rounded border border-border"
            />
            <div className="text-right">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setSelectedPhotoUrl(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
