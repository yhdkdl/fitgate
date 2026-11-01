"""
Base AI Provider Interface for FitGate Training Plan Generation.
Defines swappable provider interface implemented by MockAIPlanProvider and LiteLLMAIPlanProvider.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class AIPlanGenerationError(Exception):
    """Base exception for all AI plan generation failures."""

    def __init__(self, message: str, code: str = "generation_failed"):
        super().__init__(message)
        self.message = message
        self.code = code


class AIProviderTimeoutError(AIPlanGenerationError):
    """Raised when an AI provider call exceeds request timeout threshold."""

    def __init__(self, message: str = "AI generation provider timed out."):
        super().__init__(message, code="provider_timeout")


class AIPlanStructureError(AIPlanGenerationError):
    """Raised when provider returns output failing schema validation."""

    def __init__(self, message: str = "Generated plan failed structure validation."):
        super().__init__(message, code="invalid_plan_structure")


class BaseAIPlanProvider(ABC):
    """Abstract interface for swappable training plan generation providers."""

    @abstractmethod
    def generate_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate structured training plan from PII-free context.

        Returns:
            dict containing:
                "plan_data": Dict[str, Any] (valid schema containing sessions and nutrition)
                "model_name": str (identifier of provider/model that produced the plan)
        """
        pass
