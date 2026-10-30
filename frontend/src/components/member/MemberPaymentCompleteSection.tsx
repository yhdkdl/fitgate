import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  getMemberPaymentStatus,
  getReceiptDetail,
  type DigitalReceipt,
  type MemberPaymentStatus,
} from "../../api/payments";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { DigitalReceiptModal } from "../ui/DigitalReceiptModal";
import { Spinner } from "../ui/Spinner";

type StatusState =
  "checking" | "confirmed" | "pending_timeout" | "failed" | "not_found";

export const MemberPaymentCompleteSection: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const reference =
    searchParams.get("tx_ref") ||
    searchParams.get("reference") ||
    searchParams.get("trxref") ||
    "";

  const [state, setState] = useState<StatusState>("checking");
  const [paymentData, setPaymentData] = useState<MemberPaymentStatus | null>(
    null
  );
  const [viewingReceipt, setViewingReceipt] = useState<DigitalReceipt | null>(
    null
  );
  const [receiptLoading, setReceiptLoading] = useState(false);
  const [receiptError, setReceiptError] = useState<string | null>(null);

  const attemptsRef = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);

  const handleOpenReceipt = async () => {
    if (!paymentData?.receipt_id) {
      setReceiptError(
        "Receipt is still being finalized. You can view it shortly in My payments."
      );
      return;
    }
    setReceiptLoading(true);
    setReceiptError(null);
    try {
      const receipt = await getReceiptDetail(paymentData.receipt_id);
      if (isMountedRef.current) {
        setViewingReceipt(receipt);
      }
    } catch {
      if (isMountedRef.current) {
        setReceiptError("Receipt details could not be retrieved at this time.");
      }
    } finally {
      if (isMountedRef.current) {
        setReceiptLoading(false);
      }
    }
  };

  useEffect(() => {
    isMountedRef.current = true;
    attemptsRef.current = 0;

    if (!reference) {
      setState("not_found");
      return;
    }

    const checkStatus = async () => {
      try {
        const res = await getMemberPaymentStatus(reference);
        if (!isMountedRef.current) return;

        setPaymentData(res);

        if (res.status === "confirmed") {
          setState("confirmed");
          if (timerRef.current) clearInterval(timerRef.current);
        } else if (res.status === "failed" || res.status === "abandoned") {
          setState("failed");
          if (timerRef.current) clearInterval(timerRef.current);
        } else {
          // Still pending
          attemptsRef.current += 1;
          if (attemptsRef.current >= 20) {
            // Approx 60 seconds (20 * 3s)
            setState("pending_timeout");
            if (timerRef.current) clearInterval(timerRef.current);
          }
        }
      } catch {
        if (!isMountedRef.current) return;
        setState("not_found");
        if (timerRef.current) clearInterval(timerRef.current);
      }
    };

    // Immediate first check
    checkStatus();

    // Poll every 3 seconds for up to ~60s
    timerRef.current = setInterval(checkStatus, 3000);

    return () => {
      isMountedRef.current = false;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [reference]);

  return (
    <div className="max-w-xl mx-auto py-8 px-4">
      <Card className="p-8 text-center bg-surface border border-border shadow-sm rounded-card">
        {state === "checking" && (
          <div className="flex flex-col items-center gap-4 py-8">
            <Spinner size="lg" />
            <h2 className="text-xl font-bold text-text">
              Checking your payment...
            </h2>
            <p className="text-sm text-text-muted max-w-sm">
              Please wait while we confirm your transaction. This will update
              automatically.
            </p>
          </div>
        )}

        {state === "confirmed" && (
          <div className="flex flex-col items-center gap-4 py-4">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center mb-2">
              <svg
                className="w-8 h-8"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-text">
              Payment confirmed. Your plan is active.
            </h2>
            {paymentData?.plan_name && (
              <p className="text-sm text-text-muted">
                Plan:{" "}
                <span className="font-semibold text-text">
                  {paymentData.plan_name}
                </span>
              </p>
            )}

            {receiptError && (
              <p className="text-xs text-amber-500 mt-1">{receiptError}</p>
            )}

            <div className="flex flex-col sm:flex-row gap-3 mt-4 w-full justify-center">
              <Button
                variant="primary"
                onClick={handleOpenReceipt}
                disabled={receiptLoading}
                className="min-h-[44px]"
              >
                {receiptLoading ? "Loading receipt..." : "View receipt"}
              </Button>
              <Button
                variant="secondary"
                onClick={() => navigate("/membership")}
                className="min-h-[44px]"
              >
                Go to My membership
              </Button>
            </div>
          </div>
        )}

        {state === "pending_timeout" && (
          <div className="flex flex-col items-center gap-4 py-4">
            <div className="w-16 h-16 rounded-full bg-amber-500/10 text-amber-500 flex items-center justify-center mb-2">
              <svg
                className="w-8 h-8"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-text">Still Confirming</h2>
            <p className="text-sm text-text-muted max-w-md leading-relaxed">
              We are still confirming your payment. This can take a minute. You
              will get a notification, and you can check My payments.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 mt-4 w-full justify-center">
              <Button
                variant="primary"
                onClick={() => navigate("/payments")}
                className="min-h-[44px]"
              >
                Check My payments
              </Button>
              <Button
                variant="secondary"
                onClick={() => navigate("/membership")}
                className="min-h-[44px]"
              >
                Go to My membership
              </Button>
            </div>
          </div>
        )}

        {state === "failed" && (
          <div className="flex flex-col items-center gap-4 py-4">
            <div className="w-16 h-16 rounded-full bg-red-500/10 text-red-500 flex items-center justify-center mb-2">
              <svg
                className="w-8 h-8"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-danger">
              The payment was not completed
            </h2>
            <p className="text-sm text-text-muted max-w-md">
              Your online payment attempt could not be processed.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 mt-4 w-full justify-center">
              <Button
                variant="primary"
                onClick={() => navigate("/membership")}
                className="min-h-[44px]"
              >
                Try again
              </Button>
              <Button
                variant="secondary"
                onClick={() => navigate("/membership")}
                className="min-h-[44px]"
              >
                Pay at the front desk (cash or bank transfer)
              </Button>
            </div>
          </div>
        )}

        {state === "not_found" && (
          <div className="flex flex-col items-center gap-4 py-4">
            <div className="w-16 h-16 rounded-full bg-surface-muted text-text-muted flex items-center justify-center mb-2">
              <svg
                className="w-8 h-8"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-text">
              We could not find this payment
            </h2>
            <p className="text-sm text-text-muted max-w-sm">
              We could not verify the details for this transaction reference.
            </p>
            <div className="mt-4 w-full flex justify-center">
              <Button
                variant="secondary"
                onClick={() => navigate("/membership")}
                className="min-h-[44px]"
              >
                Go to My membership
              </Button>
            </div>
          </div>
        )}
      </Card>

      <DigitalReceiptModal
        isOpen={!!viewingReceipt}
        onClose={() => setViewingReceipt(null)}
        receipt={viewingReceipt}
      />
    </div>
  );
};
