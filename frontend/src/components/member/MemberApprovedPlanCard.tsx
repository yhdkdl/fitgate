import React, { useEffect, useState } from "react";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";
import {
  listMyApprovedTrainingPlans,
  type TrainingPlan,
} from "../../api/trainingPlans";

export const MemberApprovedPlanCard: React.FC = () => {
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
        <p className="text-xs text-text-muted mt-2">Loading your workout routine...</p>
      </Card>
    );
  }

  if (plans.length === 0) {
    return null; // Don't clutter dashboard if no approved plan exists yet
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
            Week of {new Date(latestPlan.week_start_date).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })} · {latestPlan.plan_data.training_days_per_week} days/week · Phase: <span className="uppercase font-semibold text-text">{latestPlan.plan_data.training_phase}</span>
          </p>
        </div>
        <div className="text-xs text-text-muted font-medium bg-surface-2 px-2.5 py-1 rounded border border-border">
          Target Intensity: <span className="text-primary font-bold">RPE {latestPlan.plan_data.target_intensity.rpe_target}</span>
        </div>
      </div>

      {latestPlan.trainer_notes && (
        <div className="text-xs text-text-muted bg-primary/5 border border-primary/20 p-2.5 rounded">
          <strong className="text-primary">Trainer Note:</strong> {latestPlan.trainer_notes}
        </div>
      )}

      {/* Session Tabs */}
      <div className="flex border-b border-border gap-2 overflow-x-auto pb-1">
        {latestPlan.plan_data.sessions.map((sess, idx) => (
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
            {sess.name} ({sess.focus})
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
      {activeSession >= 0 && latestPlan.plan_data.sessions[activeSession] && (
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
                {latestPlan.plan_data.sessions[activeSession].exercises.map((ex, exIdx) => (
                  <tr key={exIdx} className="hover:bg-surface-2/30">
                    <td className="py-2 px-2 font-medium text-text">{ex.name}</td>
                    <td className="py-2 px-2 text-text-muted">{ex.target_muscle}</td>
                    <td className="py-2 px-2 text-text">{ex.sets}</td>
                    <td className="py-2 px-2 text-text">{ex.reps}</td>
                    <td className="py-2 px-2 text-primary font-bold">{ex.rpe}</td>
                    <td className="py-2 px-2 text-text-muted">{ex.rest_seconds}s</td>
                    <td className="py-2 px-2 text-text-muted">{ex.notes || "—"}</td>
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
          {latestPlan.plan_data.nutrition_guidance.fasting_compliance_note && (
            <div className="p-2.5 bg-primary/10 border border-primary/20 rounded text-text font-medium">
              {latestPlan.plan_data.nutrition_guidance.fasting_compliance_note}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="bg-surface-2/40 p-3 rounded border border-border">
              <span className="font-bold text-text block mb-1">Daily Principles</span>
              <ul className="list-disc list-inside text-text-muted space-y-1">
                {latestPlan.plan_data.nutrition_guidance.daily_principles.map((pr, i) => (
                  <li key={i}>{pr}</li>
                ))}
              </ul>
            </div>

            <div className="bg-surface-2/40 p-3 rounded border border-border">
              <span className="font-bold text-text block mb-1">Hydration</span>
              <p className="text-text-muted">{latestPlan.plan_data.nutrition_guidance.hydration_notes}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div className="bg-surface-2/40 p-3 rounded border border-border">
              <span className="font-bold text-primary block mb-1">Breakfast</span>
              <ul className="list-disc list-inside text-text-muted space-y-0.5">
                {latestPlan.plan_data.nutrition_guidance.meal_patterns.breakfast.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
            <div className="bg-surface-2/40 p-3 rounded border border-border">
              <span className="font-bold text-primary block mb-1">Lunch</span>
              <ul className="list-disc list-inside text-text-muted space-y-0.5">
                {latestPlan.plan_data.nutrition_guidance.meal_patterns.lunch.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
            <div className="bg-surface-2/40 p-3 rounded border border-border">
              <span className="font-bold text-primary block mb-1">Dinner</span>
              <ul className="list-disc list-inside text-text-muted space-y-0.5">
                {latestPlan.plan_data.nutrition_guidance.meal_patterns.dinner.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
            <div className="bg-surface-2/40 p-3 rounded border border-border">
              <span className="font-bold text-primary block mb-1">Snacks</span>
              <ul className="list-disc list-inside text-text-muted space-y-0.5">
                {latestPlan.plan_data.nutrition_guidance.meal_patterns.snacks.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};
