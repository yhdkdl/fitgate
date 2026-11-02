"""
Mock AI Plan Provider for FitGate.
Generates fully valid, deterministic structured training and nutrition plans
offline with zero network requests or API keys. Development and demo fallback.
"""

from typing import Any, Dict, List

from apps.trainers.ai.base import BaseAIPlanProvider
from apps.trainers.ai.schema import validate_training_plan_structure


class MockAIPlanProvider(BaseAIPlanProvider):
    """
    Produces deterministic, structured training plans tailored to member biometrics,
    weekly focus, equipment exclusions, and Ethiopian nutrition with fasting awareness.
    """

    MODEL_IDENTIFIER = "mock-ai-v1"

    def generate_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        profile = context.get("profile", {})
        plan_params = context.get("plan_parameters", {})
        training_days = profile.get("training_days_per_week", 3)
        session_length = profile.get("session_length_minutes", 60)
        excluded_equipment = set(plan_params.get("excluded_equipment", []))
        trainer_note = plan_params.get("trainer_note_for_week", "")
        focus_list = profile.get("focus_this_week") or ["no_focus"]
        dietary_notes = profile.get("dietary_notes", [])
        limitations = set(profile.get("health_limitations", []))
        intensity = plan_params.get("intensity", {})
        rpe = intensity.get("target_rpe", "7-8")
        rep_range = intensity.get("rep_range", "8-12")

        # Determine sessions based on training_days
        sessions: List[Dict[str, Any]] = []

        # Available exercise templates filtered by exclusions
        def get_safe_exercise(category: str, slot: int) -> Dict[str, Any]:
            exercises = {
                "legs": [
                    {
                        "name": "Goblet Squats with Dumbbell",
                        "req": "dumbbells",
                        "alt": "Bodyweight Tempo Air Squats",
                    },
                    {
                        "name": "Dumbbell Romanian Deadlift",
                        "req": "dumbbells",
                        "alt": "Single-Leg Glute Bridges",
                    },
                    {
                        "name": "Walking Lunges with Light Dumbbells",
                        "req": "dumbbells",
                        "alt": "Bodyweight Reverse Lunges",
                    },
                    {
                        "name": "Leg Extension Machine",
                        "req": "machines",
                        "alt": "Wall Sit Holds",
                    },
                    {
                        "name": "Standing Calf Raises",
                        "req": "bodyweight",
                        "alt": "Standing Calf Raises",
                    },
                ],
                "upper_body": [
                    {
                        "name": "Dumbbell Flat Bench Press",
                        "req": "dumbbells",
                        "alt": "Standard Floor Push-Ups",
                    },
                    {
                        "name": "Seated Cable Row",
                        "req": "cable_machine",
                        "alt": "Incline Push-Ups / Band Pull-Aparts",
                    },
                    {
                        "name": (
                            "Dumbbell Neutral-Grip Floor Press"
                            if "shoulder" in limitations
                            else "Dumbbell Overhead Shoulder Press"
                        ),
                        "req": "dumbbells",
                        "alt": (
                            "Incline Push-Ups"
                            if "shoulder" in limitations
                            else "Pike Push-Ups"
                        ),
                    },
                    {
                        "name": "Lat Pulldown on Cable Machine",
                        "req": "cable_machine",
                        "alt": "Doorframe Bodyweight Rows",
                    },
                    {
                        "name": "Dumbbell Bicep Curls",
                        "req": "dumbbells",
                        "alt": "Isometric Towel Bicep Curls",
                    },
                ],
                "core_cardio": [
                    {
                        "name": "Plank Shoulder Taps",
                        "req": "bodyweight",
                        "alt": "Forearm Plank Hold",
                    },
                    {
                        "name": "Hanging Knee Raises",
                        "req": "pull_up_bar",
                        "alt": "Lying Dead Bugs",
                    },
                    {
                        "name": "Cardio Treadmill Incline Walk",
                        "req": "cardio_machines",
                        "alt": "High Knees in Place",
                    },
                    {
                        "name": "Cable Woodchoppers",
                        "req": "cable_machine",
                        "alt": "Russian Twists",
                    },
                    {
                        "name": "Bicycle Crunches",
                        "req": "bodyweight",
                        "alt": "Bicycle Crunches",
                    },
                ],
            }

            pool = exercises.get(category, exercises["upper_body"])
            item = pool[slot % len(pool)]
            name = item["alt"] if item["req"] in excluded_equipment else item["name"]
            sets = 3 if session_length <= 45 else 4
            return {
                "name": name,
                "sets": sets,
                "reps": rep_range,
                "rpe": rpe,
                "rest_seconds": 60 if session_length <= 45 else 90,
                "notes": "Maintain controlled tempo and full range of motion.",
            }

        # Build each session
        session_names = [f"Session {chr(65 + i)}" for i in range(training_days)]
        category_rotation = [
            "upper_body",
            "legs",
            "core_cardio",
            "upper_body",
            "legs",
            "core_cardio",
        ]

        # Shift rotation if focus specified
        active_focuses = [f for f in focus_list if f != "no_focus"]
        if "legs" in active_focuses and "upper_body" in active_focuses:
            category_rotation = [
                "upper_body",
                "legs",
                "upper_body",
                "legs",
                "upper_body",
                "legs",
            ]
        elif "legs" in active_focuses:
            category_rotation = [
                "legs",
                "upper_body",
                "legs",
                "core_cardio",
                "legs",
                "upper_body",
            ]
        elif "upper_body" in active_focuses:
            category_rotation = [
                "upper_body",
                "core_cardio",
                "upper_body",
                "legs",
                "upper_body",
                "legs",
            ]
        elif "core" in active_focuses or "cardio" in active_focuses:
            category_rotation = [
                "core_cardio",
                "upper_body",
                "core_cardio",
                "legs",
                "core_cardio",
                "upper_body",
            ]
        elif "mobility" in active_focuses:
            category_rotation = [
                "core_cardio",
                "upper_body",
                "legs",
                "core_cardio",
                "upper_body",
                "legs",
            ]

        for idx, name in enumerate(session_names):
            main_cat = category_rotation[idx % len(category_rotation)]
            num_exercises = (
                4 if session_length <= 45 else (5 if session_length <= 60 else 6)
            )
            ex_list = [get_safe_exercise(main_cat, s) for s in range(num_exercises)]

            sessions.append(
                {
                    "name": name,
                    "focus": f"{main_cat.replace('_', ' ').capitalize()} Focus ({session_length} min)",
                    "exercises": ex_list,
                }
            )

        # Ethiopian Nutrition Guidance respecting fasting
        is_fasting = (
            "orthodox_fasting" in dietary_notes
            or "vegan" in dietary_notes
            or "vegetarian" in dietary_notes
        )

        if is_fasting:
            nutrition_guidance = (
                "Ethiopian fasting nutrition protocol: Rely on wholesome plant protein and complex carbohydrates. "
                "Center meals around teff injera paired with shiro wot (chickpea powder stew), misir wot (spiced red lentils), "
                "kik alicha (yellow split peas), and steamed gomen (collard greens). For hydration and recovery, consume roasted "
                "barley water (besso) with ground flaxseed. Ensure adequate water intake throughout the training day."
            )
            daily_meals = [
                {
                    "meal": "Breakfast",
                    "pattern": "Spiced oats or besso shake with flaxseed, banana, and black coffee.",
                },
                {
                    "meal": "Lunch",
                    "pattern": "1.5 teff injera with misir wot, kik alicha, and sautéed gomen.",
                },
                {
                    "meal": "Snack",
                    "pattern": "Roasted kollo (chickpeas and barley) with fresh seasonal fruit (papaya or orange).",
                },
                {
                    "meal": "Dinner",
                    "pattern": "Teff injera with creamy shiro wot, tomato timatim salata, and fosolia.",
                },
            ]
        else:
            nutrition_guidance = (
                "Standard athletic nutrition protocol emphasizing locally sourced Ethiopian whole foods. "
                "Incorporate quality proteins such as boiled eggs, grilled tilapia/asa lebleb, and lean chicken/doro with teff injera. "
                "Combine legumes (shiro, lentils) with fresh vegetable salads. Hydrate consistently before and following workouts."
            )
            daily_meals = [
                {
                    "meal": "Breakfast",
                    "pattern": "3 scrambled or boiled eggs with spiced whole wheat bread and fresh tomato salad.",
                },
                {
                    "meal": "Lunch",
                    "pattern": "1.5 teff injera with doro wot or grilled fish, accompanied by misir wot and gomen.",
                },
                {
                    "meal": "Snack",
                    "pattern": "Traditional besso drink with milk or roasted kollo mix.",
                },
                {
                    "meal": "Dinner",
                    "pattern": "Teff injera with beef tibs or shiro wot, mixed green salad with olive oil dressing.",
                },
            ]

        plan_data = {
            "sessions": sessions,
            "nutrition": {
                "guidance": nutrition_guidance,
                "meal_patterns": daily_meals,
                "dietary_notes_respected": list(dietary_notes),
            },
            "metadata": {
                "weekly_focus": focus_list,
                "trainer_note_applied": bool(trainer_note),
                "generated_by": self.MODEL_IDENTIFIER,
            },
        }

        # Validate schema before returning
        validated = validate_training_plan_structure(
            plan_data, expected_days=training_days
        )
        return {
            "plan_data": validated,
            "model_name": self.MODEL_IDENTIFIER,
        }
