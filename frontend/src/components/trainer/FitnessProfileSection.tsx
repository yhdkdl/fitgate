import React, { useEffect, useState } from "react";
import {
  getMemberFitnessProfile,
  saveMemberFitnessProfile,
  type FitnessProfile,
} from "../../api/fitnessProfile";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Spinner } from "../ui/Spinner";
import {
  focusFirstInvalidField,
  validateDietaryNotes,
  validateFitnessLevel,
  validateGoal,
  validateSessionLength,
  validateTrainingDaysPerWeek,
} from "../../utils/validators";

interface FitnessProfileSectionProps {
  memberId: string;
  memberName: string;
}

export const FitnessProfileSection: React.FC<FitnessProfileSectionProps> = ({
  memberId,
  memberName,
}) => {
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<FitnessProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Form fields
  const [goal, setGoal] = useState("");
  const [fitnessLevel, setFitnessLevel] = useState("");
  const [trainingDays, setTrainingDays] = useState<number | "">("");
  const [sessionLength, setSessionLength] = useState<number | "">("");
  const [healthLimitations, setHealthLimitations] = useState("");
  const [equipmentAccess, setEquipmentAccess] = useState("");
  const [dietaryNotes, setDietaryNotes] = useState("");

  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    setFormError(null);
    setFieldErrors({});

    getMemberFitnessProfile(memberId)
      .then((data) => {
        if (!isMounted) return;
        setProfile(data);
        setGoal(data.goal || "");
        setFitnessLevel(data.fitness_level || "");
        setTrainingDays(data.training_days_per_week ?? "");
        setSessionLength(data.session_length_minutes ?? "");
        setHealthLimitations(data.health_limitations || "");
        setEquipmentAccess(data.equipment_access || "");
        setDietaryNotes(data.dietary_notes || "");
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        // 404 is expected when no profile has been entered yet
        const status = (err as { status?: number })?.status;
        const errData = (err as { data?: { latest_measurements?: unknown } })
          ?.data;
        if (status === 404) {
          setProfile({
            member_id: memberId,
            goal: "",
            fitness_level: "",
            training_days_per_week: 3,
            session_length_minutes: 60,
            latest_measurements:
              (errData?.latest_measurements as FitnessProfile["latest_measurements"]) ??
              null,
            created_at: "",
            updated_at: "",
          } as FitnessProfile);
          setGoal("");
          setFitnessLevel("");
          setTrainingDays("");
          setSessionLength("");
          setHealthLimitations("");
          setEquipmentAccess("");
          setDietaryNotes("");
        } else {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load fitness profile."
          );
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [memberId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSuccessMsg(null);

    const errors: Record<string, string> = {};

    const goalErr = validateGoal(goal);
    if (goalErr) errors.goal = goalErr;

    const levelErr = validateFitnessLevel(fitnessLevel);
    if (levelErr) errors.fitness_level = levelErr;

    const daysErr = validateTrainingDaysPerWeek(trainingDays);
    if (daysErr) errors.training_days_per_week = daysErr;

    const lengthErr = validateSessionLength(sessionLength);
    if (lengthErr) errors.session_length_minutes = lengthErr;

    const dietErr = validateDietaryNotes(dietaryNotes);
    if (dietErr) errors.dietary_notes = dietErr;

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField(errors);
      return;
    }

    setSaving(true);
    try {
      const updated = await saveMemberFitnessProfile(memberId, {
        goal,
        fitness_level: fitnessLevel,
        training_days_per_week: Number(trainingDays),
        session_length_minutes: Number(sessionLength),
        health_limitations: healthLimitations.trim(),
        equipment_access: equipmentAccess.trim(),
        dietary_notes: dietaryNotes.trim(),
      });
      setProfile(updated);
      setSuccessMsg(`Fitness profile for ${memberName} saved successfully.`);
      setFieldErrors({});
    } catch (err: unknown) {
      const backendErrors = (
        err as { data?: Record<string, string | string[]> }
      )?.data;
      if (backendErrors && typeof backendErrors === "object") {
        const mapped: Record<string, string> = {};
        for (const [k, v] of Object.entries(backendErrors)) {
          mapped[k] = Array.isArray(v) ? v[0] : String(v);
        }
        setFieldErrors(mapped);
        setFormError("Please correct the errors indicated below.");
        focusFirstInvalidField(mapped);
      } else {
        setFormError(
          err instanceof Error ? err.message : "Failed to save fitness profile."
        );
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="bg-surface border-border p-8 text-center space-y-2">
        <Spinner size="md" />
        <p className="text-xs text-text-muted">Loading fitness profile...</p>
      </Card>
    );
  }

  if (error) {
    return <Alert variant="error">{error}</Alert>;
  }

  const latestMetrics = profile?.latest_measurements as
    | {
        weight_kg?: number | string | null;
        height_cm?: number | string | null;
        body_fat_percentage?: number | string | null;
        lean_body_mass_kg?: number | string | null;
        resting_heart_rate?: number | string | null;
        recorded_at?: string | null;
      }
    | null
    | undefined;

  const hasMeasurements = Boolean(
    latestMetrics &&
    (latestMetrics.weight_kg !== null || latestMetrics.height_cm !== null)
  );

  return (
    <div className="space-y-4">
      {/* Biometric Measurements Summary Box */}
      <div className="p-4 bg-primary/5 border border-primary/20 rounded-card space-y-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <h4 className="text-xs font-bold uppercase tracking-wider text-primary">
            Latest Trainer Measurements
          </h4>
          <span className="text-xs text-text-muted">
            Height, weight, body fat %, lean mass & resting heart rate are read
            directly from measurements and never re-typed.
          </span>
        </div>

        {hasMeasurements && latestMetrics ? (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center mt-2">
            <div className="bg-surface p-2 rounded border border-border">
              <span className="text-xs text-text-muted block">Weight</span>
              <span className="text-sm font-bold text-text">
                {latestMetrics.weight_kg !== null &&
                latestMetrics.weight_kg !== undefined
                  ? `${latestMetrics.weight_kg} kg`
                  : "—"}
              </span>
            </div>
            <div className="bg-surface p-2 rounded border border-border">
              <span className="text-xs text-text-muted block">Height</span>
              <span className="text-sm font-bold text-text">
                {latestMetrics.height_cm !== null &&
                latestMetrics.height_cm !== undefined
                  ? `${latestMetrics.height_cm} cm`
                  : "—"}
              </span>
            </div>
            <div className="bg-surface p-2 rounded border border-border">
              <span className="text-xs text-text-muted block">Body Fat</span>
              <span className="text-sm font-bold text-text">
                {latestMetrics.body_fat_percentage !== null &&
                latestMetrics.body_fat_percentage !== undefined
                  ? `${latestMetrics.body_fat_percentage}%`
                  : "—"}
              </span>
            </div>
            <div className="bg-surface p-2 rounded border border-border">
              <span className="text-xs text-text-muted block">Lean Mass</span>
              <span className="text-sm font-bold text-text">
                {latestMetrics.lean_body_mass_kg !== null &&
                latestMetrics.lean_body_mass_kg !== undefined
                  ? `${latestMetrics.lean_body_mass_kg} kg`
                  : "—"}
              </span>
            </div>
            <div className="bg-surface p-2 rounded border border-border">
              <span className="text-xs text-text-muted block">Resting HR</span>
              <span className="text-sm font-bold text-text">
                {latestMetrics.resting_heart_rate !== null &&
                latestMetrics.resting_heart_rate !== undefined
                  ? `${latestMetrics.resting_heart_rate} bpm`
                  : "—"}
              </span>
            </div>
          </div>
        ) : (
          <Alert variant="warning" className="text-xs py-2">
            No measurements recorded yet. A trainer must record measurements
            first before a training plan can be generated.
          </Alert>
        )}
      </div>

      {/* Fitness Profile Form */}
      <Card className="bg-surface border-border p-5">
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-border gap-2">
            <div>
              <h3 className="text-base font-bold text-text">
                Client Fitness Profile
              </h3>
              <p className="text-xs text-text-muted">
                Completed by the assigned trainer during the client&apos;s first
                visit.
              </p>
            </div>
            {profile?.updated_at && (
              <span className="text-xs text-text-muted">
                Last updated:{" "}
                {new Date(profile.updated_at).toLocaleDateString()}
              </span>
            )}
          </div>

          {formError && <Alert variant="error">{formError}</Alert>}
          {successMsg && <Alert variant="success">{successMsg}</Alert>}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Goal */}
            <FormField
              id="goal"
              label="Primary Goal"
              required
              error={fieldErrors.goal}
            >
              <select
                id="goal"
                value={goal}
                onChange={(e) => {
                  setGoal(e.target.value);
                  if (fieldErrors.goal) {
                    setFieldErrors((prev) => ({ ...prev, goal: "" }));
                  }
                }}
                className="w-full bg-surface-2 text-text border border-border rounded-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">Select primary goal...</option>
                <option value="fat_loss">Fat Loss</option>
                <option value="muscle_gain">Muscle Gain</option>
                <option value="strength">Strength</option>
                <option value="endurance">Endurance</option>
                <option value="general_fitness">General Fitness</option>
              </select>
            </FormField>

            {/* Fitness Level */}
            <FormField
              id="fitness_level"
              label="Fitness Level"
              required
              error={fieldErrors.fitness_level}
            >
              <select
                id="fitness_level"
                value={fitnessLevel}
                onChange={(e) => {
                  setFitnessLevel(e.target.value);
                  if (fieldErrors.fitness_level) {
                    setFieldErrors((prev) => ({ ...prev, fitness_level: "" }));
                  }
                }}
                className="w-full bg-surface-2 text-text border border-border rounded-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">Select fitness level...</option>
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </FormField>

            {/* Training Days Per Week */}
            <FormField
              id="training_days_per_week"
              label="Training Days Per Week"
              required
              error={fieldErrors.training_days_per_week}
            >
              <select
                id="training_days_per_week"
                value={trainingDays}
                onChange={(e) => {
                  setTrainingDays(
                    e.target.value === "" ? "" : Number(e.target.value)
                  );
                  if (fieldErrors.training_days_per_week) {
                    setFieldErrors((prev) => ({
                      ...prev,
                      training_days_per_week: "",
                    }));
                  }
                }}
                className="w-full bg-surface-2 text-text border border-border rounded-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">Select training days (2–6)...</option>
                <option value={2}>2 days / week</option>
                <option value={3}>3 days / week</option>
                <option value={4}>4 days / week</option>
                <option value={5}>5 days / week</option>
                <option value={6}>6 days / week</option>
              </select>
            </FormField>

            {/* Session Length */}
            <FormField
              id="session_length_minutes"
              label="Session Length"
              required
              error={fieldErrors.session_length_minutes}
            >
              <select
                id="session_length_minutes"
                value={sessionLength}
                onChange={(e) => {
                  setSessionLength(
                    e.target.value === "" ? "" : Number(e.target.value)
                  );
                  if (fieldErrors.session_length_minutes) {
                    setFieldErrors((prev) => ({
                      ...prev,
                      session_length_minutes: "",
                    }));
                  }
                }}
                className="w-full bg-surface-2 text-text border border-border rounded-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">Select session length...</option>
                <option value={30}>30 minutes</option>
                <option value={45}>45 minutes</option>
                <option value={60}>60 minutes</option>
                <option value={90}>90 minutes</option>
              </select>
            </FormField>
          </div>

          {/* Health Limitations */}
          <FormField
            id="health_limitations"
            label="Health Limitations & Injuries (Optional)"
            error={fieldErrors.health_limitations}
          >
            <textarea
              id="health_limitations"
              value={healthLimitations}
              onChange={(e) => setHealthLimitations(e.target.value)}
              placeholder="e.g. Lower back pain, left shoulder impingement, asthma"
              rows={2}
              className="w-full bg-surface-2 text-text border border-border rounded-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-y"
            />
          </FormField>

          {/* Equipment Access */}
          <FormField
            id="equipment_access"
            label="Equipment Access & Preferences (Optional)"
            error={fieldErrors.equipment_access}
          >
            <textarea
              id="equipment_access"
              value={equipmentAccess}
              onChange={(e) => setEquipmentAccess(e.target.value)}
              placeholder="e.g. Free weights, barbell, kettlebells, cable machine"
              rows={2}
              className="w-full bg-surface-2 text-text border border-border rounded-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-y"
            />
          </FormField>

          {/* Dietary Notes */}
          <FormField
            id="dietary_notes"
            label="Dietary Notes (Optional)"
            error={fieldErrors.dietary_notes}
          >
            <div className="space-y-1">
              <textarea
                id="dietary_notes"
                value={dietaryNotes}
                maxLength={1000}
                onChange={(e) => {
                  setDietaryNotes(e.target.value);
                  if (fieldErrors.dietary_notes) {
                    setFieldErrors((prev) => ({ ...prev, dietary_notes: "" }));
                  }
                }}
                placeholder="e.g. Strict vegan, peanut allergy, observes Ethiopian Orthodox fasting periods (tsom)"
                rows={3}
                className="w-full bg-surface-2 text-text border border-border rounded-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-y"
              />
              <div className="flex justify-end text-xs text-text-muted">
                {dietaryNotes.length} / 1000 characters
              </div>
            </div>
          </FormField>

          <div className="pt-2 flex justify-end">
            <Button
              type="submit"
              variant="primary"
              disabled={saving}
              className="min-h-[44px] px-6"
            >
              {saving ? <Spinner size="sm" /> : "Save Fitness Profile"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};
