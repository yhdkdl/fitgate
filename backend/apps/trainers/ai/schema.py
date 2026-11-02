"""
Schema definitions and validation for FitGate AI Training Plans.
Enforces robust, lenient JSON structure parsing and strict safety/nutritional constraints.
"""

import json
import re
from typing import Any, Dict, Optional


class PlanSchemaValidationError(Exception):
    """Raised when an AI provider returns plan data that violates the strict plan structure."""

    pass


def validate_training_plan_structure(
    plan_data: Any, expected_days: int = 3, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Validates that plan_data conforms to the required FitGate plan structure:
    - sessions: array with length equal to training_days_per_week
      - each session has name (Session A, Session B, ...), focus, and non-empty exercises list
      - each exercise has name, sets, reps, rpe, rest_seconds, notes (lenient with type coercion)
    - nutrition: object with guidance (str) and meal_patterns (list or str)
    - strict safety: no excluded exercises or equipment; NO numeric calorie targets
    """
    if not isinstance(plan_data, dict):
        raise PlanSchemaValidationError("Plan data must be a JSON dictionary.")

    sessions = plan_data.get("sessions")
    if not isinstance(sessions, list) or len(sessions) == 0:
        raise PlanSchemaValidationError(
            "Plan must contain a non-empty list of sessions."
        )

    if len(sessions) != expected_days:
        raise PlanSchemaValidationError(
            f"Expected {expected_days} sessions for member's profile, but got {len(sessions)}."
        )

    expected_session_names = [f"Session {chr(65 + i)}" for i in range(len(sessions))]
    for i, session in enumerate(sessions):
        if not isinstance(session, dict):
            raise PlanSchemaValidationError(f"Session {i + 1} must be a dictionary.")

        session_name = str(session.get("name", "")).strip()
        expected_name = expected_session_names[i]
        if not session_name or not session_name.startswith(expected_name):
            # Normalize to expected session name
            session["name"] = expected_name
            session_name = expected_name

        if not session.get("focus") or not str(session.get("focus")).strip():
            session["focus"] = "Full Body Conditioning"

        # Coerce optional session_length_minutes if present
        if "session_length_minutes" in session:
            try:
                session["session_length_minutes"] = int(
                    re.search(r"\d+", str(session["session_length_minutes"])).group(0)
                )
            except Exception:
                session["session_length_minutes"] = 45

        exercises = session.get("exercises")
        if not isinstance(exercises, list) or len(exercises) == 0:
            raise PlanSchemaValidationError(
                f"Session '{session_name}' must contain at least one exercise."
            )

        for j, ex in enumerate(exercises):
            if not isinstance(ex, dict):
                raise PlanSchemaValidationError(
                    f"Exercise {j + 1} in '{session_name}' must be an object."
                )

            name = str(ex.get("name", "")).strip()
            if not name:
                raise PlanSchemaValidationError(
                    f"Exercise {j + 1} in '{session_name}' is missing a name."
                )
            ex["name"] = name

            # Sets: lenient parsing (accept int or string), default 3
            raw_sets = ex.get("sets")
            if isinstance(raw_sets, int) and raw_sets >= 1:
                cleaned_sets = raw_sets
            elif isinstance(raw_sets, str):
                m = re.search(r"\d+", raw_sets)
                cleaned_sets = int(m.group(0)) if m and int(m.group(0)) >= 1 else 3
            else:
                cleaned_sets = 3
            ex["sets"] = cleaned_sets

            # Reps: accept string or number, default "8-12"
            raw_reps = ex.get("reps")
            if raw_reps is not None and str(raw_reps).strip():
                ex["reps"] = str(raw_reps).strip()
            else:
                ex["reps"] = "8-12"

            # RPE: accept string or number, default "7-8"
            raw_rpe = ex.get("rpe")
            if raw_rpe is not None and str(raw_rpe).strip():
                ex["rpe"] = str(raw_rpe).strip()
            else:
                ex["rpe"] = "7-8"

            # Rest seconds: accept int or string (e.g. "60s"), default 60
            raw_rest = ex.get("rest_seconds")
            if isinstance(raw_rest, int) and raw_rest >= 0:
                cleaned_rest = raw_rest
            elif isinstance(raw_rest, str):
                m = re.search(r"\d+", raw_rest)
                cleaned_rest = int(m.group(0)) if m else 60
            else:
                cleaned_rest = 60
            ex["rest_seconds"] = cleaned_rest

            # Notes: optional string, default ""
            raw_notes = ex.get("notes")
            ex["notes"] = str(raw_notes).strip() if raw_notes is not None else ""

    # Strict Safety Exclusions: check limitations and equipment exclusions
    if context:
        profile = context.get("profile", {})
        limitations = [str(c).lower() for c in profile.get("health_limitations", [])]
        plan_params = context.get("plan_parameters", {})
        excluded_equipment = [
            str(e).lower() for e in plan_params.get("excluded_equipment", [])
        ]

        for session in sessions:
            for ex in session["exercises"]:
                ex_name_lower = ex["name"].lower()

                # Shoulder limitation exclusion
                if "shoulder" in limitations:
                    shoulder_forbidden = [
                        "overhead press",
                        "shoulder press",
                        "military press",
                        "lateral raise",
                        "front raise",
                        "arnold press",
                        "behind the neck press",
                    ]
                    for term in shoulder_forbidden:
                        if term in ex_name_lower:
                            raise PlanSchemaValidationError(
                                f"Exercise '{ex['name']}' violates member's shoulder limitation."
                            )

                # Excluded equipment check
                for eq in excluded_equipment:
                    if eq and eq in ex_name_lower:
                        raise PlanSchemaValidationError(
                            f"Exercise '{ex['name']}' requires excluded equipment: '{eq}'."
                        )

    # Nutrition section
    nutrition = plan_data.get("nutrition")
    if not isinstance(nutrition, dict):
        raise PlanSchemaValidationError("Plan must contain a 'nutrition' object.")

    guidance = str(nutrition.get("guidance", "")).strip()
    if not guidance:
        raise PlanSchemaValidationError(
            "Nutrition object must contain 'guidance' text."
        )

    # Check for forbidden calorie precision (numeric calories, kcal)
    nutr_str = json.dumps(nutrition).lower()
    if re.search(r"\b\d+\s*(?:kcal|calories|cal)\b", nutr_str) or any(
        f in nutr_str for f in ["kcal", "calories: ", "calories :"]
    ):
        raise PlanSchemaValidationError(
            "Calorie precision (e.g. numeric calories or 'kcal') is forbidden; plans must provide general meal patterns only."
        )

    return plan_data
