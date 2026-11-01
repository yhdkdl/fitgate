"""
Schema definitions and validation for FitGate AI Training Plans.
Enforces strict JSON structure and Ethiopian nutritional constraints with zero calorie precision.
"""

from typing import Any, Dict


class PlanSchemaValidationError(Exception):
    """Raised when an AI provider returns plan data that violates the strict plan structure."""

    pass


def validate_training_plan_structure(
    plan_data: Any, expected_days: int = 3
) -> Dict[str, Any]:
    """
    Validates that plan_data conforms to the required FitGate plan structure:
    - sessions: array with length equal to training_days_per_week
      - each session has name (Session A, Session B, ...), focus, and non-empty exercises list
      - each exercise has name, sets (int), reps (str), rpe (str), rest_seconds (int), notes (str)
    - nutrition: object with guidance (str) and meal_patterns (list or str)
    - NO calorie precision (no numeric calorie targets)
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

        session_name = session.get("name", "")
        expected_name = expected_session_names[i]
        if session_name != expected_name:
            # Tolerant if starts with expected name
            if not str(session_name).startswith(expected_name):
                raise PlanSchemaValidationError(
                    f"Session {i + 1} must be named '{expected_name}', got '{session_name}'."
                )

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
            if not ex.get("name"):
                raise PlanSchemaValidationError(
                    f"Exercise {j + 1} in '{session_name}' is missing a name."
                )
            if not isinstance(ex.get("sets"), int) or ex.get("sets") < 1:
                raise PlanSchemaValidationError(
                    f"Exercise '{ex.get('name')}' sets must be an integer >= 1."
                )
            if not ex.get("reps"):
                raise PlanSchemaValidationError(
                    f"Exercise '{ex.get('name')}' must specify reps."
                )

    nutrition = plan_data.get("nutrition")
    if not isinstance(nutrition, dict):
        raise PlanSchemaValidationError("Plan must contain a 'nutrition' object.")
    if not nutrition.get("guidance"):
        raise PlanSchemaValidationError(
            "Nutrition object must contain 'guidance' text."
        )

    # Check for forbidden calorie precision (calories, kcal numbers)
    nutr_str = str(nutrition).lower()
    for forbidden in ["kcal", "calories: ", "calories :"]:
        if forbidden in nutr_str:
            raise PlanSchemaValidationError(
                f"Calorie precision '{forbidden}' is forbidden; plans must provide general meal patterns only."
            )

    return plan_data
