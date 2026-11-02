import React, { useState } from "react";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";
import {
  rejectTrainingPlan,
  type TrainingPlan,
} from "../../api/trainingPlans";
import { REJECTION_REASONS_OPTIONS } from "../../utils/trainingPlanConstants";

interface RejectPlanModalProps {
  isOpen: boolean;
  onClose: () => void;
  planId: string;
  draftNumber: number;
  onPlanRejected: (newPlan: TrainingPlan) => void;
}

export const RejectPlanModal: React.FC<RejectPlanModalProps> = ({
  isOpen,
  onClose,
  planId,
  draftNumber,
  onPlanRejected,
}) => {
  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);
  const [otherReasonText, setOtherReasonText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleToggle = (code: string) => {
    if (selectedReasons.includes(code)) {
      setSelectedReasons(selectedReasons.filter((c) => c !== code));
    } else {
      setSelectedReasons([...selectedReasons, code]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (selectedReasons.length === 0) {
      setError("Please select at least one rejection reason.");
      return;
    }

    if (selectedReasons.includes("other")) {
      const trimmed = otherReasonText.trim();
      if (!trimmed || trimmed.length < 5) {
        setError("Please specify other rejection reason (5 to 200 characters).");
        return;
      }
      if (trimmed.length > 200) {
        setError("Other rejection reason cannot exceed 200 characters.");
        return;
      }
    }

    setLoading(true);
    try {
      const regeneratedPlan = await rejectTrainingPlan(planId, {
        rejection_reasons: selectedReasons,
        other_rejection_reason: selectedReasons.includes("other")
          ? otherReasonText.trim()
          : undefined,
      });
      onPlanRejected(regeneratedPlan);
      onClose();
    } catch (err: unknown) {
      const errObj = err as { data?: { detail?: string; message?: string }; message?: string };
      const rawMsg =
        errObj?.data?.detail ||
        errObj?.data?.message ||
        errObj?.message ||
        "Rejection failed. Please try again.";
      const msg =
        typeof rawMsg === "string" && (rawMsg.startsWith("<!DOCTYPE") || rawMsg.startsWith("<html"))
          ? "Generation failed, try again later."
          : rawMsg;
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Reject Draft ${draftNumber} & Regenerate`}>
      <form onSubmit={handleSubmit} className="space-y-4 text-text">
        <div className="text-xs text-text-muted">
          Select what needs adjustment. The rules engine and AI will use these reasons to generate Draft {draftNumber + 1}.
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        <div className="space-y-2">
          {REJECTION_REASONS_OPTIONS.map((opt) => {
            const isChecked = selectedReasons.includes(opt.code);
            return (
              <label
                key={opt.code}
                className={`flex items-center gap-2 p-2.5 rounded border cursor-pointer text-xs transition-colors ${isChecked
                  ? "border-primary bg-primary/5 text-text font-medium"
                  : "border-border bg-surface text-text-muted hover:border-text-muted"
                  }`}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => handleToggle(opt.code)}
                  className="rounded border-border text-primary focus:ring-primary h-4 w-4"
                />
                <span>{opt.label}</span>
              </label>
            );
          })}
        </div>

        {selectedReasons.includes("other") && (
          <div className="pt-1">
            <label className="block text-xs font-semibold text-text-muted mb-1">
              Specify Other Reason (5 to 200 characters)
            </label>
            <Input
              placeholder="e.g. Member prefers dumbbells over machines this week."
              maxLength={200}
              value={otherReasonText}
              onChange={(e) => setOtherReasonText(e.target.value)}
              className="text-xs"
            />
          </div>
        )}

        <div className="flex justify-end gap-2 pt-3 border-t border-border">
          <Button type="button" variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="danger"
            disabled={loading || selectedReasons.length === 0}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" />
                Regenerating Draft {draftNumber + 1}...
              </span>
            ) : (
              `Reject & Generate Draft ${draftNumber + 1}`
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
