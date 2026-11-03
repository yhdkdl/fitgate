import React, { useCallback, useEffect, useState } from "react";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";
import {
  approveTrainingPlan,
  editTrainingPlan,
  getPlanPrerequisites,
  listMemberTrainingPlans,
  type MealPatternItem,
  type PlanDataStructure,
  type PlanPrerequisites,
  type TrainingPlan,
} from "../../api/trainingPlans";
import {
  REJECTION_REASONS_OPTIONS,
  WEEKLY_FOCUS_OPTIONS,
} from "../../utils/trainingPlanConstants";
import { GeneratePlanModal } from "./GeneratePlanModal";
import { RejectPlanModal } from "./RejectPlanModal";

interface TrainingPlanReviewSectionProps {
  memberId: string;
  memberName: string;
}

export const TrainingPlanReviewSection: React.FC<TrainingPlanReviewSectionProps> = ({
  memberId,
  memberName,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [prereqs, setPrereqs] = useState<PlanPrerequisites | null>(null);
  const [plans, setPlans] = useState<TrainingPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);

  const [activeSessionTab, setActiveSessionTab] = useState<number>(0);
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editedPlanData, setEditedPlanData] = useState<PlanDataStructure | null>(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const [approving, setApproving] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [prereqRes, plansRes] = await Promise.all([
        getPlanPrerequisites(memberId),
        listMemberTrainingPlans(memberId),
      ]);
      setPrereqs(prereqRes);
      setPlans(plansRes);
      setSelectedPlanId((current) => current || (plansRes.length > 0 ? plansRes[0].id : null));
    } catch (err: unknown) {
      const errObj = err as { message?: string };
      setError(errObj?.message || "Failed to load workout plans.");
    } finally {
      setLoading(false);
    }
  }, [memberId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const currentPlan = plans.find((p) => p.id === selectedPlanId) || plans[0] || null;

  useEffect(() => {
    if (currentPlan) {
      setEditedPlanData(JSON.parse(JSON.stringify(currentPlan.plan_data)));
      setIsEditing(false);
      setActiveSessionTab(0);
    }
  }, [currentPlan]);

  const handleApprove = async () => {
    if (!currentPlan) return;
    setApproving(true);
    setActionSuccess(null);
    setError(null);
    try {
      const updated = await approveTrainingPlan(currentPlan.id);
      setPlans((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setActionSuccess("Workout plan approved successfully! The member can now view their sessions.");
      const refreshedPrereqs = await getPlanPrerequisites(memberId);
      setPrereqs(refreshedPrereqs);
    } catch (err: unknown) {
      const errObj = err as { data?: { detail?: string }; message?: string };
      setError(errObj?.data?.detail || errObj?.message || "Approval failed.");
    } finally {
      setApproving(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!currentPlan || !editedPlanData) return;
    setSavingEdit(true);
    setError(null);
    setActionSuccess(null);
    try {
      const updated = await editTrainingPlan(currentPlan.id, {
        plan_data: editedPlanData,
      });
      setPlans((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
      setIsEditing(false);
      setActionSuccess("Changes saved to draft. You can now approve when ready.");
    } catch (err: unknown) {
      const errObj = err as { data?: { detail?: string }; message?: string };
      setError(errObj?.data?.detail || errObj?.message || "Failed to save edits.");
    } finally {
      setSavingEdit(false);
    }
  };

  const handlePlanGenerated = (newPlan: TrainingPlan) => {
    setPlans((prev) => [newPlan, ...prev]);
    setSelectedPlanId(newPlan.id);
    setActionSuccess(`Draft ${newPlan.draft_number} generated successfully!`);
    loadData();
  };

  const handlePlanRejected = (regeneratedPlan: TrainingPlan) => {
    setPlans((prev) => [regeneratedPlan, ...prev.map((p) => (p.id === currentPlan?.id ? { ...p, status: "rejected" as const } : p))]);
    setSelectedPlanId(regeneratedPlan.id);
    setActionSuccess(`Draft rejected. Generated Draft ${regeneratedPlan.draft_number} pending review.`);
    loadData();
  };

  if (loading) {
    return (
      <Card className="p-8 text-center bg-surface border-border">
        <Spinner size="md" />
        <p className="text-xs text-text-muted mt-2">Loading workout plans...</p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Banner & Generation Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-surface p-4 rounded-card border border-border">
        <div>
          <h3 className="text-base font-bold text-text">AI Workout Plans</h3>
          <p className="text-xs text-text-muted">
            Weekly structured workout and nutrition guidance tailored to {memberName}.
          </p>
        </div>

        <div>
          {prereqs?.eligible ? (
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={() => setIsGenerateModalOpen(true)}
              disabled={!prereqs.can_generate_this_week && !prereqs.can_generate_next_week}
            >
              Generate AI Plan
            </Button>
          ) : (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled
              title="Requirements not met"
            >
              Plan Ineligible
            </Button>
          )}
        </div>
      </div>

      {actionSuccess && <Alert variant="success">{actionSuccess}</Alert>}
      {error && <Alert variant="error">{error}</Alert>}

      {/* Ineligibility Warning if prerequisites not met */}
      {prereqs && !prereqs.eligible && prereqs.missing_requirements.length > 0 && (
        <Card className="bg-amber-500/10 border-amber-500/30 p-4 space-y-2">
          <div className="text-xs font-bold text-amber-400 uppercase tracking-wider">
            Plan Generation Requirements Missing:
          </div>
          <ul className="list-disc list-inside text-xs text-amber-200/90 space-y-1">
            {prereqs.missing_requirements.map((req, i) => (
              <li key={i}>{req}</li>
            ))}
          </ul>
        </Card>
      )}

      {/* No plans created yet */}
      {plans.length === 0 && (
        <Card className="p-10 text-center bg-surface border-border">
          <p className="text-sm font-semibold text-text">No workout plans generated yet.</p>
          <p className="text-xs text-text-muted mt-1 max-w-md mx-auto">
            Once measurements and fitness profile are recorded, click "Generate AI Plan" above to create an Ethiopian-adapted weekly routine.
          </p>
        </Card>
      )}

      {/* Active Plan View */}
      {currentPlan && (
        <div className="space-y-4">
          {/* Plan Selector & Status Header */}
          <Card className="bg-surface border-border p-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-bold text-text">
                  Week of{" "}
                  {currentPlan.week_start_date
                    ? (() => {
                        const d = new Date(currentPlan.week_start_date);
                        return isNaN(d.getTime())
                          ? String(currentPlan.week_start_date)
                          : d.toLocaleDateString(undefined, {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            });
                      })()
                    : "Unspecified Week"}
                </span>
                <Badge
                  variant={
                    currentPlan.status === "approved"
                      ? "success"
                      : currentPlan.status === "rejected"
                      ? "danger"
                      : "warning"
                  }
                >
                  {currentPlan.status === "pending_review"
                    ? "Pending Review"
                    : currentPlan.status === "approved"
                    ? "Approved"
                    : "Rejected"}
                </Badge>
                <Badge variant="neutral">Draft {currentPlan.draft_number} / 3</Badge>
                {currentPlan.was_edited && (
                  <Badge variant="primary">Edited by Trainer</Badge>
                )}
              </div>

              {/* Week switcher if multiple plans */}
              {plans.length > 1 && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-text-muted">Select Plan:</span>
                  <select
                    value={currentPlan.id}
                    onChange={(e) => setSelectedPlanId(e.target.value)}
                    className="bg-surface-2 border border-border text-text text-xs rounded px-2 py-1"
                  >
                    {plans.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.week_start_date || "Week"} (Draft {p.draft_number} - {p.status})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* Medical caution & Cautions */}
            {currentPlan.has_medical_caution && (
              <div className="p-2.5 bg-amber-500/10 border border-amber-500/30 rounded text-xs text-amber-300 font-medium">
                ⚠️ Medical Caution: Confirm with the member's doctor; review plans for this member extra carefully.
              </div>
            )}

            {/* Equipment Source Indicator */}
            <div className="bg-surface-2/60 p-2.5 rounded border border-border flex items-center justify-between text-xs">
              <span className="text-text-muted">Equipment source:</span>
              <span className="font-semibold text-text">
                {currentPlan.equipment_source || currentPlan.plan_data?.equipment_source || "member profile only"}
              </span>
            </div>

            {/* Plan Meta Information */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div className="bg-surface-2/60 p-2 rounded border border-border">
                <span className="text-text-muted block text-[10px]">Training Phase</span>
                <span className="font-semibold text-text uppercase">
                  {currentPlan.plan_data?.training_phase || "General"}
                </span>
              </div>
              <div className="bg-surface-2/60 p-2 rounded border border-border">
                <span className="text-text-muted block text-[10px]">Target Intensity</span>
                <span className="font-semibold text-primary">
                  {currentPlan.plan_data?.target_intensity?.rpe_target
                    ? `RPE ${currentPlan.plan_data.target_intensity.rpe_target}`
                    : "Standard RPE"}
                </span>
                {currentPlan.plan_data?.target_intensity?.volume_modifier && (
                  <span className="text-[10px] text-text-muted ml-1">
                    ({currentPlan.plan_data.target_intensity.volume_modifier})
                  </span>
                )}
              </div>
              <div className="bg-surface-2/60 p-2 rounded border border-border">
                <span className="text-text-muted block text-[10px]">Days / Session</span>
                <span className="font-semibold text-text">
                  {currentPlan.plan_data?.training_days_per_week ||
                    (Array.isArray(currentPlan.plan_data?.sessions)
                      ? currentPlan.plan_data.sessions.length
                      : "—")}{" "}
                  days/wk
                </span>
              </div>
              <div className="bg-surface-2/60 p-2 rounded border border-border">
                <span className="text-text-muted block text-[10px]">Source</span>
                <span
                  className="font-semibold text-text truncate block"
                  title={currentPlan.generated_by_model || "Mock AI Provider"}
                >
                  {currentPlan.generated_by_model || "Mock AI Provider"}
                </span>
              </div>
            </div>

            {/* Weekly Focus & Notes */}
            {Array.isArray(currentPlan.focus_this_week) &&
              currentPlan.focus_this_week.length > 0 && (
                <div className="text-xs text-text-muted bg-surface-2/40 p-2 rounded border border-border">
                  <strong className="text-text">Focus this week:</strong>{" "}
                  {currentPlan.focus_this_week
                    .map((code) => {
                      const match = WEEKLY_FOCUS_OPTIONS.find((opt) => opt.code === code);
                      return match ? match.label : String(code);
                    })
                    .join(", ")}
                  {currentPlan.other_focus ? ` (${currentPlan.other_focus})` : ""}
                </div>
              )}

            {currentPlan.trainer_notes && (
              <div className="text-xs text-text-muted bg-surface-2/40 p-2 rounded border border-border">
                <strong className="text-text">Trainer Note:</strong> {currentPlan.trainer_notes}
              </div>
            )}

            {/* Rejection reasons if rejected */}
            {currentPlan.status === "rejected" &&
              Array.isArray(currentPlan.rejection_reasons) &&
              currentPlan.rejection_reasons.length > 0 && (
                <div className="text-xs text-danger bg-danger/10 p-2.5 rounded border border-danger/30 space-y-1">
                  <strong className="block text-danger font-semibold">
                    Rejection Reasons:
                  </strong>
                  <ul className="list-disc list-inside space-y-0.5">
                    {currentPlan.rejection_reasons.map((reasonCode) => {
                      const match = REJECTION_REASONS_OPTIONS.find(
                        (opt) => opt.code === reasonCode
                      );
                      return (
                        <li key={reasonCode}>
                          {match ? match.label : String(reasonCode)}
                        </li>
                      );
                    })}
                  </ul>
                  {currentPlan.other_rejection_reason && (
                    <p className="text-[11px] italic text-danger/90">
                      Note: {currentPlan.other_rejection_reason}
                    </p>
                  )}
                </div>
              )}
          </Card>

          {/* Action Bar for Pending Review Draft */}
          {currentPlan.status === "pending_review" && (
            <Card className="bg-surface-2/40 border-border p-3 flex flex-wrap items-center justify-between gap-3">
              <div className="text-xs text-text-muted">
                {currentPlan.draft_number >= 3 ? (
                  <span className="font-semibold text-amber-300">
                    Draft limit reached (3/3). You must edit this draft yourself before approval.
                  </span>
                ) : (
                  <span>Review the AI-generated routine below. You can edit directly or approve.</span>
                )}
              </div>

              <div className="flex items-center gap-2">
                {!isEditing ? (
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setIsEditing(true)}
                  >
                    Edit Draft
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    onClick={handleSaveEdit}
                    disabled={savingEdit}
                  >
                    {savingEdit ? "Saving..." : "Save Edits"}
                  </Button>
                )}

                {currentPlan.draft_number < 3 ? (
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    onClick={() => setIsRejectModalOpen(true)}
                    disabled={isEditing}
                  >
                    Reject Draft
                  </Button>
                ) : (
                  <span className="text-[11px] text-text-muted italic px-2">
                    Edit this draft yourself
                  </span>
                )}

                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  onClick={handleApprove}
                  disabled={approving || isEditing}
                >
                  {approving ? "Approving..." : "Approve Plan"}
                </Button>
              </div>
            </Card>
          )}

          {/* Sessions & Nutrition Tabs */}
          {(() => {
            const sessions = Array.isArray(currentPlan.plan_data?.sessions)
              ? currentPlan.plan_data.sessions
              : [];
            const activeSession = sessions[activeSessionTab];
            const currentExercises =
              isEditing && editedPlanData?.sessions?.[activeSessionTab]?.exercises
                ? editedPlanData.sessions[activeSessionTab].exercises
                : Array.isArray(activeSession?.exercises)
                ? activeSession.exercises
                : [];

            return (
              <Card className="bg-surface border-border p-4 space-y-4">
                <div className="flex border-b border-border gap-2 overflow-x-auto pb-1">
                  {sessions.map((sess, idx) => (
                    <button
                      key={sess.session_id || idx}
                      type="button"
                      onClick={() => setActiveSessionTab(idx)}
                      className={`px-3 py-1.5 text-xs font-semibold rounded border transition-colors whitespace-nowrap ${
                        activeSessionTab === idx
                          ? "bg-primary text-black border-primary"
                          : "bg-surface-2 text-text-muted border-border hover:text-text"
                      }`}
                    >
                      {sess.name || `Session ${idx + 1}`}{" "}
                      {sess.focus ? `(${sess.focus})` : ""}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setActiveSessionTab(-1)}
                    className={`px-3 py-1.5 text-xs font-semibold rounded border transition-colors whitespace-nowrap ${
                      activeSessionTab === -1
                        ? "bg-primary text-black border-primary"
                        : "bg-surface-2 text-text-muted border-border hover:text-text"
                    }`}
                  >
                    🥗 Ethiopian Nutrition
                  </button>
                </div>

                {/* Session Exercises View */}
                {activeSessionTab >= 0 && activeSession && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold text-text uppercase tracking-wider">
                        {activeSession.name || `Session ${activeSessionTab + 1}`}:{" "}
                        <span className="text-primary">
                          {activeSession.focus || "Standard Routine"}
                        </span>
                      </h4>
                      <span className="text-[11px] text-text-muted">
                        {currentExercises.length} Exercises
                      </span>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-border text-text-muted">
                            <th className="py-2 px-2">Exercise</th>
                            <th className="py-2 px-2">Target Muscle</th>
                            <th className="py-2 px-2">Sets</th>
                            <th className="py-2 px-2">Reps</th>
                            <th className="py-2 px-2">RPE</th>
                            <th className="py-2 px-2">Rest</th>
                            <th className="py-2 px-2">Notes</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/50">
                          {currentExercises.map((ex, exIdx) => (
                            <tr key={exIdx} className="hover:bg-surface-2/30">
                              <td className="py-2 px-2 font-medium text-text">
                                {isEditing && editedPlanData ? (
                                  <input
                                    value={ex.name || ""}
                                    onChange={(e) => {
                                      const updated = { ...editedPlanData };
                                      if (
                                        updated.sessions?.[activeSessionTab]
                                          ?.exercises?.[exIdx]
                                      ) {
                                        updated.sessions[activeSessionTab].exercises[
                                          exIdx
                                        ].name = e.target.value;
                                        setEditedPlanData(updated);
                                      }
                                    }}
                                    className="bg-surface-2 border border-border rounded px-1.5 py-0.5 text-xs text-text w-full"
                                  />
                                ) : (
                                  ex.name || "—"
                                )}
                              </td>
                              <td className="py-2 px-2 text-text-muted">
                                {ex.target_muscle || "—"}
                              </td>
                              <td className="py-2 px-2 text-text">
                                {isEditing && editedPlanData ? (
                                  <input
                                    type="text"
                                    value={ex.sets ?? ""}
                                    onChange={(e) => {
                                      const updated = { ...editedPlanData };
                                      if (
                                        updated.sessions?.[activeSessionTab]
                                          ?.exercises?.[exIdx]
                                      ) {
                                        updated.sessions[activeSessionTab].exercises[
                                          exIdx
                                        ].sets = e.target.value;
                                        setEditedPlanData(updated);
                                      }
                                    }}
                                    className="bg-surface-2 border border-border rounded px-1.5 py-0.5 text-xs text-text w-16"
                                  />
                                ) : (
                                  String(ex.sets ?? "—")
                                )}
                              </td>
                              <td className="py-2 px-2 text-text">
                                {isEditing && editedPlanData ? (
                                  <input
                                    type="text"
                                    value={ex.reps ?? ""}
                                    onChange={(e) => {
                                      const updated = { ...editedPlanData };
                                      if (
                                        updated.sessions?.[activeSessionTab]
                                          ?.exercises?.[exIdx]
                                      ) {
                                        updated.sessions[activeSessionTab].exercises[
                                          exIdx
                                        ].reps = e.target.value;
                                        setEditedPlanData(updated);
                                      }
                                    }}
                                    className="bg-surface-2 border border-border rounded px-1.5 py-0.5 text-xs text-text w-24"
                                  />
                                ) : (
                                  String(ex.reps ?? "—")
                                )}
                              </td>
                              <td className="py-2 px-2 text-primary font-semibold">
                                {isEditing && editedPlanData ? (
                                  <input
                                    type="text"
                                    value={ex.rpe ?? ""}
                                    onChange={(e) => {
                                      const updated = { ...editedPlanData };
                                      if (
                                        updated.sessions?.[activeSessionTab]
                                          ?.exercises?.[exIdx]
                                      ) {
                                        updated.sessions[activeSessionTab].exercises[
                                          exIdx
                                        ].rpe = e.target.value;
                                        setEditedPlanData(updated);
                                      }
                                    }}
                                    className="bg-surface-2 border border-border rounded px-1.5 py-0.5 text-xs text-text w-16"
                                  />
                                ) : (
                                  String(ex.rpe ?? "—")
                                )}
                              </td>
                              <td className="py-2 px-2 text-text-muted">
                                {ex.rest_seconds != null ? `${ex.rest_seconds}s` : "—"}
                              </td>
                              <td className="py-2 px-2 text-text-muted">
                                {isEditing && editedPlanData ? (
                                  <input
                                    value={ex.notes || ""}
                                    onChange={(e) => {
                                      const updated = { ...editedPlanData };
                                      if (
                                        updated.sessions?.[activeSessionTab]
                                          ?.exercises?.[exIdx]
                                      ) {
                                        updated.sessions[activeSessionTab].exercises[
                                          exIdx
                                        ].notes = e.target.value;
                                        setEditedPlanData(updated);
                                      }
                                    }}
                                    className="bg-surface-2 border border-border rounded px-1.5 py-0.5 text-xs text-text w-full"
                                  />
                                ) : (
                                  ex.notes || "—"
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Nutrition Guidance Tab */}
                {activeSessionTab === -1 && (
                  <div className="space-y-4">
                    <div className="border-b border-border pb-2">
                      <h4 className="text-xs font-bold text-text uppercase tracking-wider">
                        Ethiopian Dietary & Nutrition Principles
                      </h4>
                      <p className="text-[11px] text-text-muted">
                        No strict calorie precision; focuses on wholesome Ethiopian staples respecting dietary choices & fasting.
                      </p>
                    </div>

                    {(() => {
                      const nutrition =
                        currentPlan.plan_data?.nutrition ||
                        currentPlan.plan_data?.nutrition_guidance;
                      const guidanceText =
                        typeof nutrition?.guidance === "string"
                          ? nutrition.guidance
                          : null;
                      const fastingNote =
                        nutrition?.fasting_compliance_note ||
                        (Array.isArray(nutrition?.dietary_notes_respected) &&
                        nutrition.dietary_notes_respected.length > 0
                          ? `Dietary choices respected: ${nutrition.dietary_notes_respected.join(
                              ", "
                            )}`
                          : null);
                      const dailyPrinciples = Array.isArray(
                        nutrition?.daily_principles
                      )
                        ? nutrition.daily_principles
                        : [];
                      const hydration = nutrition?.hydration_notes;

                      return (
                        <div className="space-y-3">
                          {fastingNote && (
                            <div className="p-2.5 bg-primary/10 border border-primary/30 rounded text-xs text-text font-medium">
                              {fastingNote}
                            </div>
                          )}

                          {guidanceText && (
                            <div className="bg-surface-2/40 p-3 rounded border border-border text-xs text-text-muted leading-relaxed">
                              <strong className="text-text block mb-1">
                                Nutrition Strategy:
                              </strong>
                              {guidanceText}
                            </div>
                          )}

                          {dailyPrinciples.length > 0 && (
                            <div className="bg-surface-2/40 p-3 rounded border border-border">
                              <span className="text-xs font-bold text-text block mb-1">
                                Daily Principles
                              </span>
                              <ul className="list-disc list-inside text-xs text-text-muted space-y-1">
                                {dailyPrinciples.map((pr: string, i: number) => (
                                  <li key={i}>{pr}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {hydration && (
                            <div className="bg-surface-2/40 p-3 rounded border border-border">
                              <span className="text-xs font-bold text-text block mb-1">
                                Hydration
                              </span>
                              <p className="text-xs text-text-muted">{hydration}</p>
                            </div>
                          )}

                          {/* Meal patterns */}
                          {nutrition?.meal_patterns && (
                            <div className="space-y-2 pt-1">
                              <span className="text-xs font-bold text-text uppercase tracking-wider block">
                                Suggested Meal Patterns
                              </span>
                              {Array.isArray(nutrition.meal_patterns) ? (
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                  {nutrition.meal_patterns.map(
                                    (item: MealPatternItem, i: number) => (
                                      <div
                                        key={i}
                                        className="bg-surface-2/40 p-3 rounded border border-border"
                                      >
                                        <span className="text-xs font-bold text-primary block mb-1">
                                          {item.meal || `Meal ${i + 1}`}
                                        </span>
                                        <p className="text-xs text-text-muted leading-relaxed">
                                          {item.pattern || String(item)}
                                        </p>
                                      </div>
                                    )
                                  )}
                                </div>
                              ) : typeof nutrition.meal_patterns === "object" ? (
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                  {Object.entries(nutrition.meal_patterns).map(
                                    ([mealKey, items]: [string, unknown]) => (
                                      <div
                                        key={mealKey}
                                        className="bg-surface-2/40 p-3 rounded border border-border"
                                      >
                                        <span className="text-xs font-bold text-primary block mb-1 capitalize">
                                          {mealKey} Options
                                        </span>
                                        {Array.isArray(items) ? (
                                          <ul className="list-disc list-inside text-xs text-text-muted space-y-0.5">
                                            {items.map(
                                              (it: string, idx: number) => (
                                                <li key={idx}>{it}</li>
                                              )
                                            )}
                                          </ul>
                                        ) : (
                                          <p className="text-xs text-text-muted">
                                            {String(items)}
                                          </p>
                                        )}
                                      </div>
                                    )
                                  )}
                                </div>
                              ) : null}
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                )}
              </Card>
            );
          })()}
        </div>
      )}

      {/* Generation Modal */}
      {prereqs && isGenerateModalOpen && (
        <GeneratePlanModal
          isOpen={isGenerateModalOpen}
          onClose={() => setIsGenerateModalOpen(false)}
          memberId={memberId}
          memberName={memberName}
          prereqs={prereqs}
          hasMedicalCaution={currentPlan?.has_medical_caution}
          onPlanGenerated={handlePlanGenerated}
        />
      )}

      {/* Rejection Modal */}
      {currentPlan && isRejectModalOpen && (
        <RejectPlanModal
          isOpen={isRejectModalOpen}
          onClose={() => setIsRejectModalOpen(false)}
          planId={currentPlan.id}
          draftNumber={currentPlan.draft_number}
          onPlanRejected={handlePlanRejected}
        />
      )}
    </div>
  );
};
