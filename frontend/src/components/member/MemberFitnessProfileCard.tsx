import React, { useEffect, useState } from "react";
import {
  getMemberSelfFitnessProfile,
  type FitnessProfile,
} from "../../api/fitnessProfile";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";
import {
  DIETARY_NOTE_OPTIONS,
  EQUIPMENT_ACCESS_OPTIONS,
  HEALTH_LIMITATION_OPTIONS,
} from "../../utils/fitnessProfileConstants";

export const MemberFitnessProfileCard: React.FC = () => {
  const [profile, setProfile] = useState<FitnessProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    getMemberSelfFitnessProfile()
      .then((data) => {
        if (!isMounted) return;
        setProfile(data);
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        const status = (err as { status?: number })?.status;
        if (status === 404) {
          setNotFound(true);
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
  }, []);

  if (loading) {
    return (
      <Card className="bg-surface border-border p-6 text-center space-y-2">
        <Spinner size="md" />
        <p className="text-xs text-text-muted">
          Loading your fitness profile...
        </p>
      </Card>
    );
  }

  if (error) {
    return <Alert variant="error">{error}</Alert>;
  }

  if (notFound || !profile) {
    return (
      <Card className="bg-surface border-border p-6 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">🏋️</span>
          <h3 className="text-base font-bold text-text">My Fitness Profile</h3>
        </div>
        <p className="text-xs text-text-muted">
          Your fitness profile has not been entered yet. Your assigned trainer
          will complete your profile and measurements during your first gym
          visit.
        </p>
      </Card>
    );
  }

  const formatGoal = (g: string) => {
    const map: Record<string, string> = {
      fat_loss: "Fat Loss",
      muscle_gain: "Muscle Gain",
      strength: "Strength",
      endurance: "Endurance",
      general_fitness: "General Fitness",
    };
    return map[g] || g;
  };

  const formatLevel = (l: string) => {
    const map: Record<string, string> = {
      beginner: "Beginner",
      intermediate: "Intermediate",
      advanced: "Advanced",
    };
    return map[l] || l;
  };

  const getLabel = (
    code: string,
    options: { code: string; label: string }[]
  ) => {
    const found = options.find((o) => o.code === code);
    return found ? found.label : code;
  };

  const limitations = Array.isArray(profile.health_limitations)
    ? profile.health_limitations
    : [];
  const equipment = Array.isArray(profile.equipment_access)
    ? profile.equipment_access
    : [];
  const dietary = Array.isArray(profile.dietary_notes)
    ? profile.dietary_notes
    : [];

  const metrics = profile.latest_measurements as
    | {
        weight_kg?: number | string | null;
        height_cm?: number | string | null;
        body_fat_percentage?: number | string | null;
        lean_body_mass_kg?: number | string | null;
        resting_heart_rate?: number | string | null;
      }
    | null
    | undefined;

  return (
    <Card className="bg-surface border-border p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-border gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">🏋️</span>
          <div>
            <h3 className="text-base font-bold text-text">
              My Fitness Profile
            </h3>
            <span className="text-xs text-text-muted">
              Read-only view recorded by your trainer
            </span>
          </div>
        </div>
        <Badge variant="primary">Trainer Assessed</Badge>
      </div>

      {profile.has_medical_caution && (
        <Alert
          variant="warning"
          className="border-warning/50 bg-warning/10 text-warning-text"
        >
          <div className="flex items-start gap-2">
            <span className="text-base">⚠️</span>
            <div>
              <p className="font-semibold text-xs">Medical Caution Notice</p>
              <p className="text-2xs">
                Confirm with your doctor before engaging in strenuous activity.
                Your trainer reviews plans extra carefully.
              </p>
            </div>
          </div>
        </Alert>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
        <div className="bg-surface-2 p-3 rounded-card border border-border">
          <span className="text-xs text-text-muted block">Goal</span>
          <span className="text-sm font-bold text-text capitalize">
            {formatGoal(profile.goal)}
          </span>
        </div>
        <div className="bg-surface-2 p-3 rounded-card border border-border">
          <span className="text-xs text-text-muted block">Fitness Level</span>
          <span className="text-sm font-bold text-text capitalize">
            {formatLevel(profile.fitness_level)}
          </span>
        </div>
        <div className="bg-surface-2 p-3 rounded-card border border-border">
          <span className="text-xs text-text-muted block">Training Days</span>
          <span className="text-sm font-bold text-text">
            {profile.training_days_per_week} days / week
          </span>
        </div>
        <div className="bg-surface-2 p-3 rounded-card border border-border">
          <span className="text-xs text-text-muted block">Session Length</span>
          <span className="text-sm font-bold text-text">
            {profile.session_length_minutes} minutes
          </span>
        </div>
      </div>

      {/* Latest Measurements Row */}
      {metrics &&
        (metrics.weight_kg !== null || metrics.height_cm !== null) && (
          <div className="pt-2 border-t border-border/60">
            <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
              Latest Measurements (From Trainer)
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center text-xs">
              <div className="bg-surface-2/60 p-2 rounded">
                <span className="text-text-muted block">Weight</span>
                <span className="font-bold text-text">
                  {metrics.weight_kg} kg
                </span>
              </div>
              <div className="bg-surface-2/60 p-2 rounded">
                <span className="text-text-muted block">Height</span>
                <span className="font-bold text-text">
                  {metrics.height_cm} cm
                </span>
              </div>
              <div className="bg-surface-2/60 p-2 rounded">
                <span className="text-text-muted block">Body Fat</span>
                <span className="font-bold text-text">
                  {metrics.body_fat_percentage
                    ? `${metrics.body_fat_percentage}%`
                    : "—"}
                </span>
              </div>
              <div className="bg-surface-2/60 p-2 rounded">
                <span className="text-text-muted block">Lean Mass</span>
                <span className="font-bold text-text">
                  {metrics.lean_body_mass_kg
                    ? `${metrics.lean_body_mass_kg} kg`
                    : "—"}
                </span>
              </div>
              <div className="bg-surface-2/60 p-2 rounded">
                <span className="text-text-muted block">Resting HR</span>
                <span className="font-bold text-text">
                  {metrics.resting_heart_rate
                    ? `${metrics.resting_heart_rate} bpm`
                    : "—"}
                </span>
              </div>
            </div>
          </div>
        )}

      {/* Additional Notes */}
      {(limitations.length > 0 ||
        equipment.length > 0 ||
        dietary.length > 0) && (
        <div className="space-y-3 pt-2 border-t border-border/60 text-xs">
          {limitations.length > 0 && (
            <div>
              <span className="font-bold text-text block mb-1">
                Health Limitations & Injuries:
              </span>
              <div className="flex flex-wrap gap-1">
                {limitations.map((code) => (
                  <Badge
                    key={code}
                    variant={code === "none" ? "default" : "warning"}
                  >
                    {code === "other" && profile.other_limitations
                      ? `Other: ${profile.other_limitations}`
                      : getLabel(code, HEALTH_LIMITATION_OPTIONS)}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {equipment.length > 0 && (
            <div>
              <span className="font-bold text-text block mb-1">
                Equipment Access:
              </span>
              <div className="flex flex-wrap gap-1">
                {equipment.map((code) => (
                  <Badge key={code} variant="default">
                    {code === "other" && profile.other_equipment
                      ? `Other: ${profile.other_equipment}`
                      : getLabel(code, EQUIPMENT_ACCESS_OPTIONS)}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {dietary.length > 0 && (
            <div>
              <span className="font-bold text-text block mb-1">
                Dietary Notes:
              </span>
              <div className="flex flex-wrap gap-1">
                {dietary.map((code) => (
                  <Badge key={code} variant="primary">
                    {code === "other" && profile.other_dietary
                      ? `Other: ${profile.other_dietary}`
                      : getLabel(code, DIETARY_NOTE_OPTIONS)}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
};
