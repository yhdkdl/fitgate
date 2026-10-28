import React, { useEffect, useState } from "react";
import {
  recordBankTransferPayment,
  recordCashPayment,
  type DigitalReceipt,
} from "../../api/payments";
import { getMembershipPlans, type MembershipPlan } from "../../api/plans";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { DigitalReceiptModal } from "../ui/DigitalReceiptModal";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  member: {
    id: string;
    full_name: string;
    phone?: string;
  } | null;
  onPaymentSuccess?: (receipt: DigitalReceipt) => void;
}

const COMMON_CHANNELS = [
  "CBE",
  "Telebirr",
  "Awash Bank",
  "Dashen Bank",
  "Bank of Abyssinia",
  "Other",
];

export const RecordPaymentModal: React.FC<Props> = ({
  isOpen,
  onClose,
  member,
  onPaymentSuccess,
}) => {
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [loadingPlans, setLoadingPlans] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<"cash" | "bank_transfer">(
    "cash"
  );

  // Bank transfer fields
  const [bankReference, setBankReference] = useState("");
  const [transferDate, setTransferDate] = useState(
    () => new Date().toISOString().split("T")[0]
  );
  const [channel, setChannel] = useState("CBE");
  const [screenshotFile, setScreenshotFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");

  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<DigitalReceipt | null>(null);

  // Generate idempotency key and fetch plans when modal opens
  useEffect(() => {
    if (isOpen) {
      setIdempotencyKey(crypto.randomUUID());
      setSelectedPlanId("");
      setPaymentMethod("cash");
      setBankReference("");
      setTransferDate(new Date().toISOString().split("T")[0]);
      setChannel("CBE");
      setScreenshotFile(null);
      setNotes("");
      setError(null);
      setReceipt(null);

      setLoadingPlans(true);
      getMembershipPlans()
        .then((data) => {
          const active = (data || []).filter((p) => p.is_active);
          setPlans(active);
          if (active.length > 0) {
            setSelectedPlanId(active[0].id);
          }
        })
        .catch(() => {
          setError("Failed to load membership plans.");
        })
        .finally(() => {
          setLoadingPlans(false);
        });
    }
  }, [isOpen]);

  if (!isOpen || !member) return null;

  const selectedPlan = plans.find((p) => p.id === selectedPlanId);

  const handleScreenshotChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      setScreenshotFile(null);
      return;
    }
    const validTypes = ["image/jpeg", "image/png", "image/webp"];
    if (!validTypes.includes(file.type)) {
      setError("Screenshot must be a JPG, PNG, or WebP image.");
      e.target.value = "";
      setScreenshotFile(null);
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Screenshot file size cannot exceed 5 MB.");
      e.target.value = "";
      setScreenshotFile(null);
      return;
    }
    setError(null);
    setScreenshotFile(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPlanId) {
      setError("Please select a membership plan.");
      return;
    }

    if (paymentMethod === "bank_transfer") {
      const ref = bankReference.trim();
      if (!ref || ref.length < 3 || ref.length > 100) {
        setError("Bank reference must be between 3 and 100 characters.");
        return;
      }
      if (!transferDate) {
        setError("Transfer date is required.");
        return;
      }
      if (!screenshotFile) {
        setError("Bank transfer screenshot is required.");
        return;
      }
    }

    setSubmitting(true);
    setError(null);

    try {
      if (paymentMethod === "cash") {
        const res = await recordCashPayment({
          member_id: member.id,
          plan_id: selectedPlanId,
          notes: notes.trim() || undefined,
          idempotency_key: idempotencyKey,
        });
        setReceipt(res.receipt);
        onPaymentSuccess?.(res.receipt);
      } else {
        const res = await recordBankTransferPayment({
          member_id: member.id,
          plan_id: selectedPlanId,
          bank_reference: bankReference.trim(),
          transfer_date: transferDate,
          channel: channel.trim() || undefined,
          notes: notes.trim() || undefined,
          idempotency_key: idempotencyKey,
          screenshot: screenshotFile || undefined,
        });
        setReceipt(res.receipt);
        onPaymentSuccess?.(res.receipt);
      }
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        (err instanceof Error ? err.message : "Failed to record payment.");
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 bg-black/75 z-50 flex items-center justify-center p-4 overflow-y-auto"
        role="dialog"
        aria-modal="true"
      >
        <div className="bg-surface border border-border rounded-xl max-w-lg w-full p-6 space-y-4 my-8 text-text">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div>
              <h3 className="text-lg font-bold text-text">
                Record Member Payment
              </h3>
              <p className="text-xs text-text-muted">
                Member:{" "}
                <strong className="text-text">{member.full_name}</strong>
                {member.phone && ` (${member.phone})`}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="text-text-muted hover:text-text text-xl p-1"
            >
              ✕
            </button>
          </div>

          {error && <Alert variant="danger">{error}</Alert>}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {/* Plan Selector */}
            <FormField
              label="Select Membership Plan"
              htmlFor="payment-plan-select"
              required
            >
              {loadingPlans ? (
                <div className="flex items-center gap-2 text-xs text-text-muted py-2">
                  <Spinner size="sm" /> Loading plans...
                </div>
              ) : (
                <select
                  id="payment-plan-select"
                  value={selectedPlanId}
                  onChange={(e) => setSelectedPlanId(e.target.value)}
                  disabled={submitting}
                  className="w-full bg-surface-2 border border-border rounded-input px-3 py-2 text-sm text-text focus:outline-none focus:border-primary min-h-[44px]"
                  required
                >
                  {plans.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.duration_value} {p.duration_unit}) —{" "}
                      {Number(p.price_etb).toLocaleString()} ETB
                    </option>
                  ))}
                </select>
              )}
            </FormField>

            {/* Locked Amount Display (Item 18: Plan price stays locked) */}
            {selectedPlan && (
              <div className="bg-surface-2/60 border border-border rounded-lg p-3 flex items-center justify-between">
                <div>
                  <span className="text-xs text-text-muted block">
                    Locked Subscription Price:
                  </span>
                  <span className="text-xs font-medium text-text">
                    {selectedPlan.name} ({selectedPlan.duration_value}{" "}
                    {selectedPlan.duration_unit})
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-xl font-black text-success">
                    {Number(selectedPlan.price_etb).toLocaleString()} ETB
                  </span>
                </div>
              </div>
            )}

            {/* Payment Method Selector (Cash vs Bank Transfer) */}
            <div>
              <label className="block text-xs font-medium text-text mb-2">
                Payment Method <span className="text-danger">*</span>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setPaymentMethod("cash")}
                  className={`py-2.5 px-3 rounded-lg border text-sm font-semibold transition-colors flex items-center justify-center gap-2 min-h-[44px] ${
                    paymentMethod === "cash"
                      ? "bg-primary text-white border-primary"
                      : "bg-surface-2 text-text-muted border-border hover:text-text"
                  }`}
                >
                  💵 Cash
                </button>
                <button
                  type="button"
                  onClick={() => setPaymentMethod("bank_transfer")}
                  className={`py-2.5 px-3 rounded-lg border text-sm font-semibold transition-colors flex items-center justify-center gap-2 min-h-[44px] ${
                    paymentMethod === "bank_transfer"
                      ? "bg-primary text-white border-primary"
                      : "bg-surface-2 text-text-muted border-border hover:text-text"
                  }`}
                >
                  🏦 Bank Transfer
                </button>
              </div>
            </div>

            {/* Bank Transfer Specific Fields (Items 12 & 17) */}
            {paymentMethod === "bank_transfer" && (
              <div className="space-y-3 bg-surface-2/40 border border-border rounded-lg p-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <FormField
                    label="Bank Reference"
                    htmlFor="bt-ref"
                    required
                    helpText="3–100 characters"
                  >
                    <Input
                      id="bt-ref"
                      required
                      maxLength={100}
                      value={bankReference}
                      onChange={(e) => setBankReference(e.target.value)}
                      placeholder="e.g. FT26019XXXX"
                      className="min-h-[44px] font-mono text-xs"
                    />
                  </FormField>

                  <FormField label="Transfer Date" htmlFor="bt-date" required>
                    <Input
                      id="bt-date"
                      type="date"
                      required
                      value={transferDate}
                      onChange={(e) => setTransferDate(e.target.value)}
                      className="min-h-[44px] text-xs"
                    />
                  </FormField>
                </div>

                <FormField label="Bank / Transfer Channel" htmlFor="bt-channel">
                  <select
                    id="bt-channel"
                    value={channel}
                    onChange={(e) => setChannel(e.target.value)}
                    className="w-full bg-surface-2 border border-border rounded-input px-3 py-2 text-xs text-text focus:outline-none focus:border-primary min-h-[40px]"
                  >
                    {COMMON_CHANNELS.map((ch) => (
                      <option key={ch} value={ch}>
                        {ch}
                      </option>
                    ))}
                  </select>
                </FormField>

                <FormField
                  label="Transfer Screenshot"
                  htmlFor="bt-screenshot"
                  required
                  helpText="JPG, PNG, WebP up to 5 MB (Item 17)"
                >
                  <input
                    id="bt-screenshot"
                    type="file"
                    required
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleScreenshotChange}
                    className="w-full text-xs text-text file:mr-3 file:py-2 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-primary file:text-white hover:file:opacity-90 cursor-pointer"
                  />
                  {screenshotFile && (
                    <p className="text-[11px] text-success mt-1">
                      ✓ Selected: {screenshotFile.name} (
                      {(screenshotFile.size / 1024).toFixed(1)} KB)
                    </p>
                  )}
                </FormField>
              </div>
            )}

            {/* Optional Notes */}
            <FormField label="Notes (Optional)" htmlFor="payment-notes">
              <Input
                id="payment-notes"
                maxLength={500}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Front desk notes..."
                className="min-h-[40px] text-xs"
              />
            </FormField>

            <div className="flex justify-end gap-3 pt-3 border-t border-border">
              <Button
                type="button"
                variant="secondary"
                disabled={submitting}
                onClick={onClose}
                className="min-h-[44px]"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                disabled={submitting || !selectedPlanId}
                className="min-h-[44px]"
              >
                {submitting
                  ? "Processing..."
                  : `Confirm ${paymentMethod === "cash" ? "Cash" : "Bank Transfer"} Payment`}
              </Button>
            </div>
          </form>
        </div>
      </div>

      {/* Show Digital Receipt upon successful payment */}
      <DigitalReceiptModal
        isOpen={Boolean(receipt)}
        receipt={receipt}
        onClose={() => {
          setReceipt(null);
          onClose();
        }}
      />
    </>
  );
};
