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
  validateDietaryChoices,
  validateEquipmentAccess,
  validateFitnessLevel,
  validateGoal,
  validateHealthLimitations,
  validateSessionLength,
  validateTrainingDaysPerWeek,
} from "../../utils/validators";
import {
  DIETARY_NOTE_OPTIONS,
  EQUIPMENT_ACCESS_OPTIONS,
  HEALTH_LIMITATION_OPTIONS,
  hasMedicalCaution,
} from "../../utils/fitnessProfileConstants";

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
  const [healthLimitations, setHealthLimitations] = useState<string[]>([]);
  const [otherLimitations, setOtherLimitations] = useState("");
  const [equipmentAccess, setEquipmentAccess] = useState<string[]>([
    "full_gym",
  ]);
  const [otherEquipment, setOtherEquipment] = useState("");
  const [dietaryNotes, setDietaryNotes] = useState<string[]>([]);
  const [otherDietary, setOtherDietary] = useState("");

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
        const hl = Array.isArray(data.health_limitations)
          ? data.health_limitations
          : [];
        setHealthLimitations(hl);
        setOtherLimitations(data.other_limitations || "");
        const eq =
          Array.isArray(data.equipment_access) &&
          data.equipment_access.length > 0
            ? data.equipment_access
            : ["full_gym"];
        setEquipmentAccess(eq);
        setOtherEquipment(data.other_equipment || "");
        const dn = Array.isArray(data.dietary_notes) ? data.dietary_notes : [];
        setDietaryNotes(dn);
        setOtherDietary(data.other_dietary || "");
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
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
            health_limitations: [],
            other_limitations: "",
            equipment_access: ["full_gym"],
            other_equipment: "",
            dietary_notes: [],
            other_dietary: "",
            has_medical_caution: false,
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
          setHealthLimitations([]);
          setOtherLimitations("");
          setEquipmentAccess(["full_gym"]);
          setOtherEquipment("");
          setDietaryNotes([]);
          setOtherDietary("");
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

  const toggleLimitation = (code: string) => {
    setHealthLimitations((prev) => {
      if (code === "none") {
        return prev.includes("none") ? [] : ["none"];
      }
      const withoutNone = prev.filter((c) => c !== "none");
      if (withoutNone.includes(code)) {
        return withoutNone.filter((c) => c !== code);
      }
      return [...withoutNone, code];
    });
  };

  const toggleEquipment = (code: string) => {
    setEquipmentAccess((prev) => {
      if (prev.includes(code)) {
        return prev.filter((c) => c !== code);
      }
      return [...prev, code];
    });
  };

  const toggleDietary = (code: string) => {
    setDietaryNotes((prev) => {
      if (code === "none") {
        return prev.includes("none") ? [] : ["none"];
      }
      const withoutNone = prev.filter((c) => c !== "none");
      if (withoutNone.includes(code)) {
        return withoutNone.filter((c) => c !== code);
      }
      return [...withoutNone, code];
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMsg(null);
    setFormError(null);

    const errors: Record<string, string> = {};

    const goalErr = validateGoal(goal);
    if (goalErr) errors.goal = goalErr;

    const levelErr = validateFitnessLevel(fitnessLevel);
    if (levelErr) errors.fitness_level = levelErr;

    const daysErr = validateTrainingDaysPerWeek(trainingDays);
    if (daysErr) errors.training_days_per_week = daysErr;

    const lenErr = validateSessionLength(sessionLength);
    if (lenErr) errors.session_length_minutes = lenErr;

    const hlErr = validateHealthLimitations(
      healthLimitations,
      otherLimitations
    );
    if (hlErr) errors.health_limitations = hlErr;

    const eqErr = validateEquipmentAccess(equipmentAccess, otherEquipment);
    if (eqErr) errors.equipment_access = eqErr;

    const dietErr = validateDietaryChoices(dietaryNotes, otherDietary);
    if (dietErr) errors.dietary_notes = dietErr;

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField(errors);
      return;
    }

    setFieldErrors({});
    setSaving(true);

    try {
      const updated = await saveMemberFitnessProfile(memberId, {
        goal,
        fitness_level: fitnessLevel,
        training_days_per_week: Number(trainingDays),
        session_length_minutes: Number(sessionLength),
        health_limitations: healthLimitations,
        other_limitations: healthLimitations.includes("other")
          ? otherLimitations.trim()
          : "",
        equipment_access: equipmentAccess,
        other_equipment: equipmentAccess.includes("other")
          ? otherEquipment.trim()
          : "",
        dietary_notes: dietaryNotes,
        other_dietary: dietaryNotes.includes("other")
          ? otherDietary.trim()
          : "",
      });

      setProfile(updated);
      setSuccessMsg("Fitness profile saved successfully.");
    } catch (err: unknown) {
      const respData = (err as { data?: Record<string, string | string[]> })
        ?.data;
      if (respData && typeof respData === "object") {
        const serverFieldErrors: Record<string, string> = {};
        for (const [key, val] of Object.entries(respData)) {
          if (Array.isArray(val)) {
            serverFieldErrors[key] = val.join(" ");
          } else if (typeof val === "string") {
            serverFieldErrors[key] = val;
          }
        }
        setFieldErrors(serverFieldErrors);
        setFormError("Please correct the errors indicated below.");
        focusFirstInvalidField(serverFieldErrors);
      } else {
        setFormError(
          err instanceof Error
            ? err.message
            : "Failed to save fitness profile. Please check your connection."
        );
      }
    } finally {
      setSaving(false);
    }
  };

  const showCaution = hasMedicalCaution(healthLimitations);

  if (loading) {
    return (
      <Card className="bg-surface border-border p-6 text-center space-y-2">
        <Spinner size="md" />
        <p className="text-xs text-text-muted">Loading fitness profile...</p>
      </Card>
    );
  }

  if (error) {
    return <Alert variant="error">{error}</Alert>;
  }

  const measurements = profile?.latest_measurements as
    | {
        weight_kg?: number | string | null;
        height_cm?: number | string | null;
        body_fat_percentage?: number | string | null;
        lean_body_mass_kg?: number | string | null;
        resting_heart_rate?: number | string | null;
        measured_at?: string | null;
      }
    | null
    | undefined;

  return (
    <Card className="bg-surface border-border p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-border gap-2">
        <div>
          <h3 className="text-lg font-bold text-text">Fitness Profile</h3>
          <p className="text-xs text-text-muted">
            Initial fitness assessment for {memberName}. Measurements are read
            directly from the latest record.
          </p>
        </div>
        {profile?.updated_at && (
          <span className="text-xs text-text-muted">
            Last updated: {new Date(profile.updated_at).toLocaleDateString()}
          </span>
        )}
      </div>

      {successMsg && <Alert variant="success">{successMsg}</Alert>}
      {formError && <Alert variant="error">{formError}</Alert>}

      {/* Medical Caution Notice */}
      {showCaution && (
        <Alert
          variant="warning"
          className="border-warning/50 bg-warning/10 text-warning-text"
        >
          <div className="flex items-start gap-2">
            <span className="text-base">⚠️</span>
            <div>
              <p className="font-semibold text-sm">Medical Caution</p>
              <p className="text-xs">
                Confirm with the member&apos;s doctor; review plans for this
                member extra carefully.
              </p>
            </div>
          </div>
        </Alert>
      )}

      {/* Latest Trainer-Recorded Measurements (Read-Only) */}
      <div className="bg-surface-2 p-4 rounded-card border border-border space-y-2">
        <div className="flex justify-between items-center">
          <h4 className="text-xs font-semibold text-text uppercase tracking-wider">
            Latest Trainer-Recorded Measurements
          </h4>
          {measurements?.measured_at && (
            <span className="text-2xs text-text-muted">
              Measured:{" "}
              {new Date(measurements.measured_at).toLocaleDateString()}
            </span>
          )}
        </div>
        {measurements &&
        (measurements.weight_kg !== null || measurements.height_cm !== null) ? (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-2 text-center text-xs">
            <div className="bg-surface p-2 rounded border border-border">
              <span className="text-text-muted block text-2xs">Weight</span>
              <span className="font-bold text-text text-sm">
                {measurements.weight_kg ?? "—"} kg
              </span>
            </div>
            <div className="bg-surface p-2 rounded border border-border">
              <span className="text-text-muted block text-2xs">Height</span>
              <span className="font-bold text-text text-sm">
                {measurements.height_cm ?? "—"} cm
              </span>
            </div>
            <div className="bg-surface p-2 rounded border border-border">
              <span className="text-text-muted block text-2xs">Body Fat</span>
              <span className="font-bold text-text text-sm">
                {measurements.body_fat_percentage
                  ? `${measurements.body_fat_percentage}%`
                  : "—"}
              </span>
            </div>
            <div className="bg-surface p-2 rounded border border-border">
              <span className="text-text-muted block text-2xs">Lean Mass</span>
              <span className="font-bold text-text text-sm">
                {measurements.lean_body_mass_kg
                  ? `${measurements.lean_body_mass_kg} kg`
                  : "—"}
              </span>
            </div>
            <div className="bg-surface p-2 rounded border border-border">
              <span className="text-text-muted block text-2xs">Resting HR</span>
              <span className="font-bold text-text text-sm">
                {measurements.resting_heart_rate
                  ? `${measurements.resting_heart_rate} bpm`
                  : "—"}
              </span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-text-muted pt-1">
            No measurements recorded yet. Record measurements on this screen to
            populate these metrics automatically.
          </p>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-6" noValidate>
        {/* Core Profile Parameters */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            label="Primary Goal"
            htmlFor="goal"
            error={fieldErrors.goal}
            required
          >
            <select
              name="goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              className="w-full bg-surface border border-border rounded-input px-3 py-2 text-sm text-text focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">Select a goal</option>
              <option value="fat_loss">Fat Loss</option>
              <option value="muscle_gain">Muscle Gain</option>
              <option value="strength">Strength</option>
              <option value="endurance">Endurance</option>
              <option value="general_fitness">General Fitness</option>
            </select>
          </FormField>

          <FormField
            label="Fitness Level"
            htmlFor="fitness_level"
            error={fieldErrors.fitness_level}
            required
          >
            <select
              name="fitness_level"
              value={fitnessLevel}
              onChange={(e) => setFitnessLevel(e.target.value)}
              className="w-full bg-surface border border-border rounded-input px-3 py-2 text-sm text-text focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">Select a level</option>
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </FormField>

          <FormField
            label="Training Days per Week"
            htmlFor="training_days_per_week"
            error={fieldErrors.training_days_per_week}
            required
          >
            <select
              name="training_days_per_week"
              value={trainingDays}
              onChange={(e) =>
                setTrainingDays(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full bg-surface border border-border rounded-input px-3 py-2 text-sm text-text focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">Select days (2 to 6)</option>
              <option value="2">2 days / week</option>
              <option value="3">3 days / week</option>
              <option value="4">4 days / week</option>
              <option value="5">5 days / week</option>
              <option value="6">6 days / week</option>
            </select>
          </FormField>

          <FormField
            label="Session Length"
            htmlFor="session_length_minutes"
            error={fieldErrors.session_length_minutes}
            required
          >
            <select
              name="session_length_minutes"
              value={sessionLength}
              onChange={(e) =>
                setSessionLength(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full bg-surface border border-border rounded-input px-3 py-2 text-sm text-text focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">Select session length</option>
              <option value="30">30 minutes</option>
              <option value="45">45 minutes</option>
              <option value="60">60 minutes</option>
              <option value="90">90 minutes</option>
            </select>
          </FormField>
        </div>

        {/* Health Limitations & Injuries (Selectable List) */}
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-text">
            Health Limitations and Injuries{" "}
            <span className="text-error">*</span>
          </label>
          <p className="text-2xs text-text-muted">
            Select all that apply. &quot;None&quot; is exclusive.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2 pt-1">
            {HEALTH_LIMITATION_OPTIONS.map((opt) => {
              const selected = healthLimitations.includes(opt.code);
              return (
                <button
                  key={opt.code}
                  type="button"
                  onClick={() => toggleLimitation(opt.code)}
                  className={`p-2 rounded border text-xs text-left transition-colors flex items-center justify-between ${
                    selected
                      ? "bg-primary/20 border-primary text-primary font-medium"
                      : "bg-surface border-border text-text-muted hover:border-text-muted/60"
                  }`}
                >
                  <span>{opt.label}</span>
                  {selected && <span>✓</span>}
                </button>
              );
            })}
          </div>
          {fieldErrors.health_limitations && (
            <p className="text-2xs text-error mt-1">
              {fieldErrors.health_limitations}
            </p>
          )}

          {healthLimitations.includes("other") && (
            <div className="pt-2">
              <label className="block text-2xs text-text-muted mb-1">
                Other limitation details <span className="text-error">*</span>{" "}
                (max 200 characters)
              </label>
              <input
                type="text"
                name="other_limitations"
                value={otherLimitations}
                onChange={(e) => setOtherLimitations(e.target.value)}
                maxLength={200}
                placeholder="Describe other limitations or injuries"
                className="w-full bg-surface border border-border rounded-input px-3 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          )}
        </div>

        {/* Equipment Access (Selectable List) */}
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-text">
            Equipment Access <span className="text-error">*</span>
          </label>
          <p className="text-2xs text-text-muted">
            Defaults to &quot;Full gym equipment&quot;.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-1">
            {EQUIPMENT_ACCESS_OPTIONS.map((opt) => {
              const selected = equipmentAccess.includes(opt.code);
              return (
                <button
                  key={opt.code}
                  type="button"
                  onClick={() => toggleEquipment(opt.code)}
                  className={`p-2 rounded border text-xs text-left transition-colors flex items-center justify-between ${
                    selected
                      ? "bg-primary/20 border-primary text-primary font-medium"
                      : "bg-surface border-border text-text-muted hover:border-text-muted/60"
                  }`}
                >
                  <span>{opt.label}</span>
                  {selected && <span>✓</span>}
                </button>
              );
            })}
          </div>
          {fieldErrors.equipment_access && (
            <p className="text-2xs text-error mt-1">
              {fieldErrors.equipment_access}
            </p>
          )}

          {equipmentAccess.includes("other") && (
            <div className="pt-2">
              <label className="block text-2xs text-text-muted mb-1">
                Other equipment details <span className="text-error">*</span>{" "}
                (max 200 characters)
              </label>
              <input
                type="text"
                name="other_equipment"
                value={otherEquipment}
                onChange={(e) => setOtherEquipment(e.target.value)}
                maxLength={200}
                placeholder="Describe other equipment available"
                className="w-full bg-surface border border-border rounded-input px-3 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          )}
        </div>

        {/* Dietary Notes (Selectable List) */}
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-text">
            Dietary Notes <span className="text-error">*</span>
          </label>
          <p className="text-2xs text-text-muted">
            Select dietary preferences or fasting periods. &quot;No
            restrictions&quot; is exclusive.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 pt-1">
            {DIETARY_NOTE_OPTIONS.map((opt) => {
              const selected = dietaryNotes.includes(opt.code);
              return (
                <button
                  key={opt.code}
                  type="button"
                  onClick={() => toggleDietary(opt.code)}
                  className={`p-2 rounded border text-xs text-left transition-colors flex items-center justify-between ${
                    selected
                      ? "bg-primary/20 border-primary text-primary font-medium"
                      : "bg-surface border-border text-text-muted hover:border-text-muted/60"
                  }`}
                >
                  <span>{opt.label}</span>
                  {selected && <span>✓</span>}
                </button>
              );
            })}
          </div>
          {fieldErrors.dietary_notes && (
            <p className="text-2xs text-error mt-1">
              {fieldErrors.dietary_notes}
            </p>
          )}

          {dietaryNotes.includes("other") && (
            <div className="pt-2">
              <label className="block text-2xs text-text-muted mb-1">
                Other dietary details <span className="text-error">*</span> (max
                200 characters)
              </label>
              <input
                type="text"
                name="other_dietary"
                value={otherDietary}
                onChange={(e) => setOtherDietary(e.target.value)}
                maxLength={200}
                placeholder="Describe other dietary requirements or fasting"
                className="w-full bg-surface border border-border rounded-input px-3 py-1.5 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          )}
        </div>

        <div className="flex justify-end pt-2 border-t border-border">
          <Button type="submit" isLoading={saving}>
            Save Fitness Profile
          </Button>
        </div>
      </form>
    </Card>
  );
};
