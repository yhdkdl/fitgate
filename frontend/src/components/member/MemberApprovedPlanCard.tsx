import React, { useEffect, useState } from "react";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";
import {
  listMyApprovedTrainingPlans,
  type MealPatternItem,
  type TrainingPlan,
} from "../../api/trainingPlans";

export interface MemberApprovedPlanCardProps {
  hasAssignedTrainer?: boolean;
  isActiveTrainerPlan?: boolean;
}

export const MemberApprovedPlanCard: React.FC<MemberApprovedPlanCardProps> = ({
  hasAssignedTrainer = true,
  isActiveTrainerPlan = true,
}) => {
  const [loading, setLoading] = useState(true);
  const [plans, setPlans] = useState<TrainingPlan[]>([]);
  const [activeSession, setActiveSession] = useState<number>(0);

  useEffect(() => {
    let isMounted = true;
    listMyApprovedTrainingPlans()
      .then((res) => {
        if (isMounted) setPlans(res);
      })
      .catch(() => {
        if (isMounted) setPlans([]);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  if (loading) {
    return (
      <Card className="p-6 text-center bg-surface border-border">
        <Spinner size="sm" />
        <p className="text-xs text-text-muted mt-2">
          Loading your workout routine...
        </p>
      </Card>
    );
  }

  if (plans.length === 0) {
    if (!hasAssignedTrainer || !isActiveTrainerPlan) {
      return null;
    }
    return (
      <Card className="bg-surface border-border p-6 text-center space-y-2">
        <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto text-lg">
          📋
        </div>
        <h3 className="text-sm font-bold text-text uppercase tracking-wider">
          Waiting for your trainer
        </h3>
        <p className="text-xs text-text-muted max-w-sm mx-auto">
          Your trainer is preparing your personalized training and nutrition
          plan. You will receive an in-app notification once it is approved.
        </p>
      </Card>
    );
  }

  const latestPlan = plans[0];

  return (
    <Card className="bg-surface border-border p-5 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-text uppercase tracking-wider">
              This Week's Workout Plan
            </h3>
            <Badge variant="success">Trainer Approved</Badge>
          </div>
          <p className="text-xs text-text-muted mt-0.5">
            Week of{" "}
            {latestPlan.week_start_date
              ? (() => {
                  const d = new Date(latestPlan.week_start_date);
                  return isNaN(d.getTime())
                    ? String(latestPlan.week_start_date)
                    : d.toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      });
                })()
              : "Unspecified Week"}{" "}
            ·{" "}
            {latestPlan.plan_data?.training_days_per_week ||
              (Array.isArray(latestPlan.plan_data?.sessions)
                ? latestPlan.plan_data.sessions.length
                : "—")}{" "}
            days/week · Phase:{" "}
            <span className="uppercase font-semibold text-text">
              {latestPlan.plan_data?.training_phase || "General"}
            </span>
          </p>
        </div>
        <div className="text-xs text-text-muted font-medium bg-surface-2 px-2.5 py-1 rounded border border-border">
          Target Intensity:{" "}
          <span className="text-primary font-bold">
            {latestPlan.plan_data?.target_intensity?.rpe_target
              ? `RPE ${latestPlan.plan_data.target_intensity.rpe_target}`
              : "Standard RPE"}
          </span>
        </div>
      </div>

      {latestPlan.trainer_notes && (
        <div className="text-xs text-text-muted bg-primary/5 border border-primary/20 p-2.5 rounded">
          <strong className="text-primary">Trainer Note:</strong>{" "}
          {latestPlan.trainer_notes}
        </div>
      )}

      {/* Session Tabs */}
      {(() => {
        const sessions = Array.isArray(latestPlan.plan_data?.sessions)
          ? latestPlan.plan_data.sessions
          : [];
        const activeSessionPlan = sessions[activeSession];
        const exercises = Array.isArray(activeSessionPlan?.exercises)
          ? activeSessionPlan.exercises
          : [];

        return (
          <>
            <div className="flex border-b border-border gap-2 overflow-x-auto pb-1">
              {sessions.map((sess, idx) => (
                <button
                  key={sess.session_id || idx}
                  type="button"
                  onClick={() => setActiveSession(idx)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded border transition-colors whitespace-nowrap ${
                    activeSession === idx
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
                onClick={() => setActiveSession(-1)}
                className={`px-3 py-1.5 text-xs font-semibold rounded border transition-colors whitespace-nowrap ${
                  activeSession === -1
                    ? "bg-primary text-black border-primary"
                    : "bg-surface-2 text-text-muted border-border hover:text-text"
                }`}
              >
                🥗 Nutrition Guidance
              </button>
            </div>

            {/* Exercises View */}
            {activeSession >= 0 && activeSessionPlan && (
              <div className="space-y-3">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-border text-text-muted">
                        <th className="py-2 px-2">Exercise</th>
                        <th className="py-2 px-2">Target</th>
                        <th className="py-2 px-2">Sets</th>
                        <th className="py-2 px-2">Reps</th>
                        <th className="py-2 px-2">RPE</th>
                        <th className="py-2 px-2">Rest</th>
                        <th className="py-2 px-2">Notes</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {exercises.map((ex, exIdx) => (
                        <tr key={exIdx} className="hover:bg-surface-2/30">
                          <td className="py-2 px-2 font-medium text-text">
                            {ex.name || "—"}
                          </td>
                          <td className="py-2 px-2 text-text-muted">
                            {ex.target_muscle || "—"}
                          </td>
                          <td className="py-2 px-2 text-text">
                            {String(ex.sets ?? "—")}
                          </td>
                          <td className="py-2 px-2 text-text">
                            {String(ex.reps ?? "—")}
                          </td>
                          <td className="py-2 px-2 text-primary font-bold">
                            {String(ex.rpe ?? "—")}
                          </td>
                          <td className="py-2 px-2 text-text-muted">
                            {ex.rest_seconds != null
                              ? `${ex.rest_seconds}s`
                              : "—"}
                          </td>
                          <td className="py-2 px-2 text-text-muted">
                            {ex.notes || "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Nutrition View */}
            {activeSession === -1 && (
              <div className="space-y-3 text-xs">
                {(() => {
                  const nutrition =
                    latestPlan.plan_data?.nutrition ||
                    latestPlan.plan_data?.nutrition_guidance;
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
                        <div className="p-2.5 bg-primary/10 border border-primary/20 rounded text-text font-medium">
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
                          <span className="font-bold text-text block mb-1">
                            Daily Principles
                          </span>
                          <ul className="list-disc list-inside text-text-muted space-y-1">
                            {dailyPrinciples.map((pr: string, i: number) => (
                              <li key={i}>{pr}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {hydration && (
                        <div className="bg-surface-2/40 p-3 rounded border border-border">
                          <span className="font-bold text-text block mb-1">
                            Hydration
                          </span>
                          <p className="text-text-muted">{hydration}</p>
                        </div>
                      )}

                      {/* Meal patterns */}
                      {nutrition?.meal_patterns && (
                        <div className="space-y-2 pt-1">
                          <span className="font-bold text-text uppercase tracking-wider block">
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
                                    <span className="font-bold text-primary block mb-1">
                                      {item.meal || `Meal ${i + 1}`}
                                    </span>
                                    <p className="text-text-muted leading-relaxed">
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
                                    <span className="font-bold text-primary block mb-1 capitalize">
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
                                      <p className="text-text-muted">
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
          </>
        );
      })()}
    </Card>
  );
};
