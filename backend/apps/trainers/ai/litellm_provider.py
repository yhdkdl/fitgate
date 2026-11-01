"""
LiteLLM AI Plan Provider for FitGate.
Calls OpenRouter free models via LiteLLM using an ordered fallback list.
Enforces inline fallback on timeout or schema error, 3-failure gym owner alerts,
and strict privacy compliance with zero PII.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone

from apps.trainers.ai.base import (
    AIPlanGenerationError,
    AIPlanStructureError,
    AIProviderTimeoutError,
    BaseAIPlanProvider,
)
from apps.trainers.ai.schema import (
    validate_training_plan_structure,
)

logger = logging.getLogger(__name__)


def build_system_prompt() -> str:
    return (
        "You are FitGate AI, an expert athletic coach and certified personal trainer. "
        "Your task is to draft a personalized 1-week training and nutrition plan based ONLY on "
        "the provided structured client profile. You MUST respond with ONLY valid JSON adhering "
        "to the requested schema. Do NOT include markdown code blocks (e.g. no ```json), explanations, "
        "or pleasantries.\n\n"
        "STRICT CONSTRAINTS:\n"
        "1. NO PERSONAL IDENTIFIERS: Never use or assume member names, phones, emails, or IDs.\n"
        "2. EXERCISE SAFETY: Strictly avoid any exercise requiring equipment in 'excluded_equipment' "
        "or violating member limitations. If the member has a shoulder limitation, strictly exclude all "
        "overhead pressing (both barbell and dumbbell) and all lateral or front raises at shoulder height "
        "(use shoulder-friendly neutral-grip presses, floor presses, or horizontal rows instead).\n"
        "3. SESSIONS: Generate exactly the requested number of sessions, named 'Session A', 'Session B', etc.\n"
        "4. ETHIOPIAN NUTRITION: Nutrition guidance must utilize authentic, locally accessible Ethiopian "
        "staples (e.g., teff injera, shiro, misir wot, kik alicha, gomen, shimbra [chickpeas], eggs, doro, tilapia/asa, besso). "
        "Strictly respect fasting periods (provide vegan meals when fasting is indicated).\n"
        "5. NO CALORIE PRECISION: Strictly do NOT provide numeric calorie targets or 'kcal' metrics. "
        "Focus on meal patterns, food choices, protein sources, and nutrient timing."
    )


def build_user_prompt(context: Dict[str, Any]) -> str:
    demographics = context.get("demographics", {})
    biometrics = context.get("biometrics", {})
    profile = context.get("profile", {})
    params = context.get("plan_parameters", {})
    history = context.get("history_context", {})

    prompt_dict = {
        "training_parameters": {
            "training_days_per_week": profile.get("training_days_per_week"),
            "session_length_minutes": profile.get("session_length_minutes"),
            "primary_goal": profile.get("goal"),
            "fitness_level": profile.get("fitness_level"),
            "periodization_phase": params.get("phase"),
            "prescribed_intensity": params.get("intensity"),
            "weekly_focus": profile.get("focus_this_week", ["no_focus"]),
            "other_focus_notes": profile.get("other_focus", ""),
            "trainer_note_for_week": params.get("trainer_note_for_week", ""),
        },
        "equipment_and_limitations": {
            "available_equipment": params.get("available_equipment", []),
            "excluded_equipment": params.get("excluded_equipment", []),
            "exclusion_reasons": params.get("exclusion_reasons", {}),
            "health_limitations": profile.get("health_limitations", []),
            "other_limitations": profile.get("other_limitations", ""),
            "medical_caution_flag": profile.get("has_medical_caution", False),
        },
        "nutrition_and_diet": {
            "dietary_notes": profile.get("dietary_notes", []),
            "other_dietary": profile.get("other_dietary", ""),
        },
        "demographics_and_biometrics": {
            "age": demographics.get("age"),
            "gender": demographics.get("gender"),
            "weight_kg": biometrics.get("weight_kg"),
            "height_cm": biometrics.get("height_cm"),
            "body_fat_percentage": biometrics.get("body_fat_percentage"),
            "resting_heart_rate": biometrics.get("resting_heart_rate"),
        },
        "recent_adherence": (
            {
                "attendance_rate_30d": history.get("attendance_rate"),
                "total_checkins_30d": history.get("total_checkins_30d"),
            }
            if isinstance(history, dict)
            else {"prior_plans_count": len(history) if isinstance(history, list) else 0}
        ),
        "schema_instructions": {
            "sessions": [
                {
                    "name": "Session A",
                    "focus": "string description",
                    "exercises": [
                        {
                            "name": "Exercise Name",
                            "sets": 3,
                            "reps": "8-12",
                            "rpe": "7-8",
                            "rest_seconds": 60,
                            "notes": "technique tip",
                        }
                    ],
                }
            ],
            "nutrition": {
                "guidance": "General Ethiopian whole-food nutrition guidance without calorie numbers",
                "meal_patterns": [
                    {
                        "meal": "Breakfast",
                        "pattern": "Meal description with Ethiopian ingredients",
                    },
                    {
                        "meal": "Lunch",
                        "pattern": "Meal description with Ethiopian ingredients",
                    },
                    {"meal": "Snack", "pattern": "Snack description"},
                    {
                        "meal": "Dinner",
                        "pattern": "Meal description with Ethiopian ingredients",
                    },
                ],
            },
        },
    }
    return json.dumps(prompt_dict, indent=2)


class LiteLLMAIPlanProvider(BaseAIPlanProvider):
    """
    Invokes OpenRouter models with ordered fallback, timeout handling,
    schema validation, and 3-failure gym owner alerting.
    """

    def __init__(
        self,
        ordered_models: Optional[List[str]] = None,
        timeout_seconds: int = 15,
        api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ):
        base_models = list(
            ordered_models
            or getattr(
                settings,
                "OPENROUTER_MODELS",
                [
                    "openrouter/google/gemma-4-31b-it:free",
                    "openrouter/google/gemma-4-26b-a4b-it:free",
                ],
            )
        )
        self.gemini_api_key = gemini_api_key or getattr(
            settings, "GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", "")
        )
        # If GEMINI_API_KEY is present, place Google AI Studio (Gemini Flash) FIRST in the chain
        if self.gemini_api_key:
            gemini_model = "gemini/gemini-2.0-flash"
            if gemini_model not in base_models:
                base_models.insert(0, gemini_model)

        self.ordered_models = base_models
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key or getattr(
            settings, "OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", "")
        )

    def _invoke_model(self, model: str, messages: List[Dict[str, str]]) -> str:
        """
        Invokes model via litellm if installed; falls back to direct OpenRouter HTTPS completion.
        Supports gemini/... models via Google AI Studio when GEMINI_API_KEY is configured.
        """
        if model.startswith("gemini/"):
            try:
                import litellm

                response = litellm.completion(
                    model=model,
                    messages=messages,
                    api_key=self.gemini_api_key,
                    timeout=self.timeout_seconds,
                    temperature=0.3,
                    max_tokens=3000,
                )
                content = response.choices[0].message.content
                if not content:
                    raise AIPlanStructureError("Gemini model returned empty content")
                return content.strip()
            except Exception as exc:
                if "timeout" in str(exc).lower():
                    raise AIProviderTimeoutError(f"Gemini timed out: {exc}")
                raise AIPlanGenerationError(f"Gemini call failed: {exc}")

        try:
            import litellm

            clean_model = (
                model if model.startswith("openrouter/") else f"openrouter/{model}"
            )
            kwargs: Dict[str, Any] = {
                "model": clean_model,
                "messages": messages,
                "timeout": self.timeout_seconds,
                "temperature": 0.3,
                "max_tokens": 3000,
            }
            if self.api_key:
                kwargs["api_key"] = self.api_key
            response = litellm.completion(**kwargs)
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except Exception:
            pass

        # Native HTTP fallback via OpenRouter endpoint
        import urllib.error
        import urllib.request

        clean_model = model.replace("openrouter/", "")
        payload = json.dumps(
            {
                "model": clean_model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 3000,
            }
        ).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://fitgate.app",
            "X-Title": "FitGate AI",
            "Connection": "close",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                choice = resp_json["choices"][0]
                content = choice["message"].get("content")
                if not content:
                    raise AIPlanStructureError("Model returned empty content")
                return content.strip()
        except urllib.error.HTTPError as http_err:
            error_body = ""
            try:
                error_body = http_err.read().decode("utf-8")
            except Exception:
                pass
            raise AIPlanGenerationError(
                f"OpenRouter HTTP {http_err.code}: {error_body or str(http_err)}"
            )
        except (TimeoutError, urllib.error.URLError) as net_err:
            raise AIProviderTimeoutError(f"AI provider timed out: {net_err}")

    def generate_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes plan generation with inline model fallback on failure/timeout.
        Enforces maximum 3 provider attempt failures before raising unified error.
        """
        profile = context.get("profile", {})
        expected_days = profile.get("training_days_per_week", 3)
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        failed_attempts = 0
        last_exception: Optional[Exception] = None

        for model in self.ordered_models:
            try:
                logger.info("Attempting AI plan generation using model: %s", model)
                raw_text = self._invoke_model(model, messages)

                # Clean potential markdown wrapping if present
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()

                parsed_json = json.loads(raw_text)
                validated_plan = validate_training_plan_structure(
                    parsed_json, expected_days=expected_days
                )

                logger.info("Plan generation succeeded using model: %s", model)
                return {
                    "plan_data": validated_plan,
                    "model_name": model,
                }

            except Exception as exc:
                failed_attempts += 1
                last_exception = exc
                logger.warning(
                    "AI generation attempt %d failed on model '%s': %s",
                    failed_attempts,
                    model,
                    str(exc),
                )
                if failed_attempts >= 3:
                    break

        # If loop finished or 3 attempts reached without success:
        self._notify_owner_and_log_failure(context, last_exception, failed_attempts)
        raise AIPlanGenerationError("generation failed, try again later")

    def _notify_owner_and_log_failure(
        self,
        context: Dict[str, Any],
        exception: Optional[Exception],
        attempt_count: int,
    ) -> None:
        """
        Logs critical failure and triggers owner notification alert after 3 failed provider attempts.
        """
        gym_id = context.get("gym_id")
        logger.error(
            "Three AI generation attempts failed in request for gym %s. Last error: %s",
            gym_id,
            str(exception),
        )

        try:
            from apps.accounts.models import AuditLog, User
            from apps.accounts.notifications import create_notification
            from apps.tenants.models import GymTenant

            gym = GymTenant.objects.filter(id=gym_id).first() if gym_id else None
            if gym:
                # Audit log entry for owner visibility
                AuditLog.all_objects.create(
                    gym=gym,
                    actor=None,
                    action_type="ai_plan_generation_failed",
                    affected_record_type="GymTenant",
                    affected_record_id=str(gym.id),
                    metadata={
                        "attempt_count": attempt_count,
                        "models_tried": self.ordered_models[:attempt_count],
                        "error": str(exception),
                        "timestamp": timezone.now().isoformat(),
                    },
                )

                # In-app notification for Owner & Manager
                recipients = User.all_objects.filter(
                    gym_id=gym.id,
                    role__in=[User.ROLE_OWNER, User.ROLE_MANAGER],
                    is_active=True,
                )
                for recipient in recipients:
                    create_notification(
                        recipient=recipient,
                        notification_type="ai_plan_generation_failed",
                        message="AI workout plan generation failed after 3 attempts. Please check AI provider settings.",
                        gym=gym,
                    )
        except Exception as log_err:
            logger.error(
                "Failed to write audit log or in-app notification for AI generation failure: %s",
                log_err,
            )
