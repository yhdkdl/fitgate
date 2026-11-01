import React, { useState } from "react";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Modal } from "../ui/Modal";
import { Spinner } from "../ui/Spinner";
import {
  generateTrainingPlan,
  type PlanPrerequisites,
  type TrainingPlan,
} from "../../api/trainingPlans";
import {
  WEEKLY_FOCUS_OPTIONS,
} from "../../utils/trainingPlanConstants";

interface GeneratePlanModalProps {
  isOpen: boolean;
  onClose: () => void;
  memberId: string;
  memberName: string;
  prereqs: PlanPrerequisites;
  hasMedicalCaution?: boolean;
  onPlanGenerated: (plan: TrainingPlan) => void;
}

export const GeneratePlanModal: React.FC<GeneratePlanModalProps> = ({
  isOpen,
  onClose,
  memberId,
  memberName,
  prereqs,
  hasMedicalCaution = false,
  onPlanGenerated,
}) => {
  const [weekChoice, setWeekChoice] = useState<"this_week" | "next_week">(
    prereqs.can_generate_this_week ? "this_week" : "next_week"
  );
  const [focusSelected, setFocusSelected] = useState<string[]>(["no_focus"]);
  const [otherFocusText, setOtherFocusText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFocusToggle = (code: string) => {
    if (code === "no_focus") {
      setFocusSelected(["no_focus"]);
      setOtherFocusText("");
      return;
    }

    let updated = focusSelected.filter((c) => c !== "no_focus");
    if (updated.includes(code)) {
      updated = updated.filter((c) => c !== code);
      if (updated.length === 0) {
        updated = ["no_focus"];
      }
    } else {
      updated.push(code);
    }
    setFocusSelected(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (focusSelected.includes("other") && !otherFocusText.trim()) {
      setError("Please specify details for 'Other' weekly focus.");
      return;
    }

    setLoading(true);
    try {
      const plan = await generateTrainingPlan(memberId, {
        week_choice: weekChoice,
        focus_this_week: focusSelected,
        other_focus: focusSelected.includes("other") ? otherFocusText.trim() : undefined,
      });
      onPlanGenerated(plan);
      onClose();
    } catch (err: unknown) {
      const errObj = err as { data?: { detail?: string; message?: string }; message?: string };
      const msg =
        errObj?.data?.detail ||
        errObj?.data?.message ||
        errObj?.message ||
        "Generation failed, try again later.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Generate AI Workout Plan for ${memberName}`}>
      <form onSubmit={handleSubmit} className="space-y-4 text-text">
        {hasMedicalCaution && (
          <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded text-xs text-amber-300">
            <strong>Medical Caution:</strong> Confirm with the member's doctor; review plans for this member extra carefully.
          </div>
        )}

        {error && <Alert variant="error">{error}</Alert>}

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">
            Target Plan Week
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              disabled={!prereqs.can_generate_this_week}
              onClick={() => setWeekChoice("this_week")}
              className={`p-3 rounded border text-left text-sm transition-colors ${
                weekChoice === "this_week"
                  ? "border-primary bg-primary/10 text-primary font-bold"
                  : "border-border bg-surface text-text-muted hover:border-text-muted"
              } ${!prereqs.can_generate_this_week ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <div>This Week</div>
              <div className="text-[11px] font-normal text-text-muted">
                {prereqs.this_week_draft_count >= 3
                  ? "Weekly draft limit reached (3/3)"
                  : prereqs.has_open_draft_this_week
                  ? "Draft pending review"
                  : `Drafts used: ${prereqs.this_week_draft_count}/3`}
              </div>
            </button>

            <button
              type="button"
              disabled={!prereqs.can_generate_next_week}
              onClick={() => setWeekChoice("next_week")}
              className={`p-3 rounded border text-left text-sm transition-colors ${
                weekChoice === "next_week"
                  ? "border-primary bg-primary/10 text-primary font-bold"
                  : "border-border bg-surface text-text-muted hover:border-text-muted"
              } ${!prereqs.can_generate_next_week ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <div>Next Week</div>
              <div className="text-[11px] font-normal text-text-muted">
                {prereqs.next_week_draft_count >= 3
                  ? "Weekly draft limit reached (3/3)"
                  : prereqs.has_open_draft_next_week
                  ? "Draft pending review"
                  : `Drafts used: ${prereqs.next_week_draft_count}/3`}
              </div>
            </button>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">
            Focus For This Week (Selectable)
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {WEEKLY_FOCUS_OPTIONS.map((opt) => {
              const isChecked = focusSelected.includes(opt.code);
              return (
                <label
                  key={opt.code}
                  className={`flex items-center gap-2 p-2 rounded border cursor-pointer text-xs transition-colors ${
                    isChecked
                      ? "border-primary bg-primary/5 text-text font-medium"
                      : "border-border bg-surface text-text-muted hover:border-text-muted"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => handleFocusToggle(opt.code)}
                    className="rounded border-border text-primary focus:ring-primary h-4 w-4"
                  />
                  <span>{opt.label}</span>
                </label>
              );
            })}
          </div>
          {focusSelected.includes("other") && (
            <div className="mt-2">
              <Input
                placeholder="Specify focus (max 200 characters)..."
                maxLength={200}
                value={otherFocusText}
                onChange={(e) => setOtherFocusText(e.target.value)}
                className="text-xs"
              />
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-3 border-t border-border">
          <Button type="button" variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={
              loading ||
              (weekChoice === "this_week" && !prereqs.can_generate_this_week) ||
              (weekChoice === "next_week" && !prereqs.can_generate_next_week)
            }
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Spinner size="sm" />
                Drafting Plan with AI...
              </span>
            ) : (
              "Generate AI Workout Plan"
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
