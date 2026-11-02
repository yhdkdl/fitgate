"""
LiteLLM AI Plan Provider for FitGate.
Calls Google AI Studio and OpenRouter models using an ordered fallback list.
Enforces inline fallback on timeout or schema error, lenient JSON parsing,
strict safety checks, retry on rate limits, lightweight daily diagnostic counters,
and at most one daily gym owner notice.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.trainers.ai.base import (
    AIPlanGenerationError,
    AIPlanStructureError,
    AIProviderTimeoutError,
    BaseAIPlanProvider,
)
from apps.trainers.ai.schema import (
    PlanSchemaValidationError,
    validate_training_plan_structure,
)

logger = logging.getLogger(__name__)


def build_system_prompt() -> str:
    return (
        "You are FitGate AI, an expert athletic coach and certified personal trainer. "
        "Your task is to draft a personalized 1-week training and nutrition plan based ONLY on "
        "the provided structured client profile. You MUST respond with ONLY valid JSON adhering "
        "to the requested schema. Do NOT include explanations, preambles, or markdown formatting.\n\n"
        "STRICT CONSTRAINTS:\n"
        "1. NO PERSONAL IDENTIFIERS: Never use or assume member names, phones, emails, or IDs.\n"
        "2. EXERCISE SAFETY: Strictly avoid any exercise requiring equipment in 'excluded_equipment' "
        "or violating member limitations. If the member has a shoulder limitation, strictly exclude all "
        "overhead pressing (both barbell and dumbbell) and all lateral or front raises at shoulder height "
        "(use shoulder-friendly neutral-grip presses, floor presses, or horizontal rows instead).\n"
        "3. SESSIONS: Generate exactly the requested number of sessions, named 'Session A', 'Session B', etc. "
        "When multiple focus areas are specified in 'weekly_focus' (e.g. both 'upper_body' and 'legs'), "
        "distribute sessions across ALL selected focus areas throughout the week (e.g., dedicated Upper Body sessions "
        "and dedicated Legs sessions). Never reject or drop any of the requested focus areas.\n"
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


def extract_json_payload(raw_text: str) -> str:
    """
    Strips code fences and any explanatory text before or after the JSON payload.
    """
    text = (raw_text or "").strip()
    if "```json" in text:
        parts = text.split("```json", 1)[1].split("```", 1)
        if len(parts) >= 1:
            text = parts[0].strip()
    elif "```" in text:
        parts = text.split("```", 1)[1].split("```", 1)
        if len(parts) >= 1:
            text = parts[0].strip()

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]
    return text.strip()


class LiteLLMAIPlanProvider(BaseAIPlanProvider):
    """
    Invokes Google AI Studio and OpenRouter models with ordered fallback, rate-limit retry,
    timeout handling, schema validation, and lightweight failure accounting.
    """

    def __init__(
        self,
        ordered_models: Optional[List[str]] = None,
        timeout_seconds: int = 25,
        api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
    ):
        self.gemini_api_key = gemini_api_key or getattr(
            settings, "GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", "")
        )
        self.api_key = api_key or getattr(
            settings, "OPENROUTER_API_KEY", os.environ.get("OPENROUTER_API_KEY", "")
        )
        self.timeout_seconds = timeout_seconds

        if ordered_models is not None:
            models = list(ordered_models)
        else:
            models = []
            if self.gemini_api_key:
                # Primary Google AI Studio Gemini models (fast, reliable quota)
                models.extend(
                    ["gemini/gemini-3.5-flash-lite", "gemini/gemini-3.5-flash"]
                )
            # Working OpenRouter fallback models
            models.extend(
                [
                    "openrouter/nvidia/nemotron-3.5-super-vl:free",
                    "openrouter/google/gemma-4-26b-a4b-it:free",
                ]
            )

        self.ordered_models = models

    def _invoke_gemini_direct(
        self, model_name: str, messages: List[Dict[str, str]]
    ) -> str:
        """Calls Google AI Studio REST endpoint directly using urllib."""
        clean_model = model_name.replace("gemini/", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={self.gemini_api_key}"

        combined_text = "\n\n".join(
            f"{m.get('role', 'user').upper()}:\n{m.get('content', '')}"
            for m in messages
        )
        payload = json.dumps(
            {
                "contents": [{"parts": [{"text": combined_text}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.3,
                    "maxOutputTokens": 8192,
                },
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data["candidates"][0]
                text = choice["content"]["parts"][0]["text"]
                if not text:
                    raise AIPlanStructureError("Gemini returned empty content.")
                return text.strip()
        except urllib.error.HTTPError as http_err:
            body = ""
            try:
                body = http_err.read().decode("utf-8")
            except Exception:
                pass
            if http_err.code == 429:
                raise AIPlanGenerationError(f"HTTP 429: {body}")
            raise AIPlanGenerationError(f"Gemini HTTP {http_err.code}: {body}")
        except (TimeoutError, urllib.error.URLError) as net_err:
            raise AIProviderTimeoutError(f"Gemini timed out: {net_err}")

    def _invoke_openrouter_direct(
        self, model_name: str, messages: List[Dict[str, str]]
    ) -> str:
        """Calls OpenRouter chat completions endpoint directly using urllib."""
        clean_model = model_name.replace("openrouter/", "")
        payload = json.dumps(
            {
                "model": clean_model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 4000,
                "response_format": {"type": "json_object"},
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
                data = json.loads(resp.read().decode("utf-8"))
                choice = data["choices"][0]
                content = choice["message"].get("content")
                if not content:
                    raise AIPlanStructureError("OpenRouter returned empty content.")
                return content.strip()
        except urllib.error.HTTPError as http_err:
            body = ""
            try:
                body = http_err.read().decode("utf-8")
            except Exception:
                pass
            if http_err.code == 429:
                raise AIPlanGenerationError(f"HTTP 429: {body}")
            raise AIPlanGenerationError(f"OpenRouter HTTP {http_err.code}: {body}")
        except (TimeoutError, urllib.error.URLError) as net_err:
            raise AIProviderTimeoutError(f"OpenRouter timed out: {net_err}")

    def _invoke_model(self, model: str, messages: List[Dict[str, str]]) -> str:
        """
        Invokes model via litellm if installed; falls back to direct REST endpoints.
        """
        # Try litellm if available
        try:
            import litellm

            clean_model = model
            kwargs: Dict[str, Any] = {
                "model": clean_model,
                "messages": messages,
                "timeout": self.timeout_seconds,
                "temperature": 0.3,
                "max_tokens": 4000,
            }
            if model.startswith("gemini/") and self.gemini_api_key:
                kwargs["api_key"] = self.gemini_api_key
            elif self.api_key:
                kwargs["api_key"] = self.api_key

            response = litellm.completion(**kwargs)
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()
        except Exception:
            pass

        # Native Direct REST HTTP Fallback
        if model.startswith("gemini/"):
            return self._invoke_gemini_direct(model, messages)
        return self._invoke_openrouter_direct(model, messages)

    def generate_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes plan generation with inline model fallback on failure/timeout.
        Retries once after 2 seconds on HTTP 429 rate limit.
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
        gym_id = context.get("gym_id")

        for model in self.ordered_models:
            # We attempt the model, and if it rate-limits (429), retry once after 2 seconds
            for attempt_in_model in range(2):
                try:
                    logger.info(
                        "Attempting AI plan generation using model: %s (try %d)",
                        model,
                        attempt_in_model + 1,
                    )
                    raw_text = self._invoke_model(model, messages)

                    clean_json_str = extract_json_payload(raw_text)
                    if not clean_json_str:
                        raise AIPlanStructureError(
                            "Model returned empty or non-JSON output."
                        )

                    parsed_json = json.loads(clean_json_str)
                    validated_plan = validate_training_plan_structure(
                        parsed_json, expected_days=expected_days, context=context
                    )

                    logger.info("Plan generation succeeded using model: %s", model)
                    return {
                        "plan_data": validated_plan,
                        "model_name": model,
                    }

                except Exception as exc:
                    err_str = str(exc).lower()
                    is_rate_limit = "429" in err_str or "rate" in err_str

                    # Determine failure category
                    if is_rate_limit:
                        reason = "rate_limit"
                    elif "timeout" in err_str:
                        reason = "timeout"
                    elif isinstance(
                        exc,
                        (
                            PlanSchemaValidationError,
                            AIPlanStructureError,
                            json.JSONDecodeError,
                        ),
                    ):
                        reason = "wrong_structure"
                    elif "key" in err_str or "401" in err_str or "403" in err_str:
                        reason = "key_problem"
                    else:
                        reason = "other"

                    self._record_failure_counter(gym_id, model, reason)

                    if is_rate_limit and attempt_in_model == 0:
                        logger.warning(
                            "Rate limit hit on %s. Retrying once after 2 seconds...",
                            model,
                        )
                        time.sleep(2.0)
                        continue

                    # Failed on this model
                    failed_attempts += 1
                    logger.warning(
                        "AI generation attempt %d failed on model '%s': %s",
                        failed_attempts,
                        model,
                        str(exc),
                    )
                    break

            if failed_attempts >= 3:
                break

        # If all attempts failed: send at most ONE in-app notification per gym per day
        self._notify_owner_daily_if_needed(context)
        raise AIPlanGenerationError("generation failed, try again later")

    def _record_failure_counter(
        self, gym_id: Optional[str], model: str, reason: str
    ) -> None:
        """
        Increments lightweight daily failure counter. Zero PII, zero prompts.
        """
        if not gym_id:
            return
        try:
            from apps.tenants.models import GymTenant
            from apps.trainers.models import AIDailyFailureCounter

            gym = GymTenant.objects.filter(id=gym_id).first()
            if not gym:
                return

            today = timezone.localdate()
            updated = AIDailyFailureCounter.all_objects.filter(
                gym=gym, date=today, model_name=model, failure_reason=reason
            ).update(failure_count=F("failure_count") + 1)
            if updated == 0:
                AIDailyFailureCounter.all_objects.create(
                    gym=gym,
                    date=today,
                    model_name=model,
                    failure_reason=reason,
                    failure_count=1,
                )
        except Exception as e:
            logger.warning("Could not record AI failure counter: %s", e)

    def _notify_owner_daily_if_needed(self, context: Dict[str, Any]) -> None:
        """
        Delivers at most ONE in-app notification per gym per day to the Owner on failure.
        """
        gym_id = context.get("gym_id")
        if not gym_id:
            return
        try:
            from apps.accounts.models import Notification, User
            from apps.accounts.notifications import create_notification
            from apps.tenants.models import GymTenant

            gym = GymTenant.objects.filter(id=gym_id).first()
            if not gym:
                return

            today = timezone.localdate()
            already_notified = Notification.all_objects.filter(
                gym=gym,
                created_at__date=today,
                type="ai_generation_problems_daily",
            ).exists()

            if not already_notified:
                owners = User.all_objects.filter(
                    gym=gym,
                    role=User.ROLE_OWNER,
                    is_active=True,
                )
                for owner in owners:
                    create_notification(
                        recipient=owner,
                        notification_type="ai_generation_problems_daily",
                        message="Plan generation had problems today. Trainers can retry later.",
                        gym=gym,
                    )
        except Exception as e:
            logger.warning("Could not send daily owner notification: %s", e)
