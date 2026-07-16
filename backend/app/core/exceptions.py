"""Domain exceptions mapped to HTTP responses in app.main."""

from __future__ import annotations


class OnboardingError(Exception):
    """Base class for domain errors."""

    code = "onboarding_error"
    http_status = 400

    def __init__(self, message: str, *, code: str | None = None, details: object = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details


class ProviderError(OnboardingError):
    """The identity provider (AD / Entra / mock) rejected or failed an operation."""

    code = "provider_error"
    http_status = 502


class ScriptExecutionError(ProviderError):
    """A PowerShell script failed, timed out, or returned malformed output."""

    code = "script_error"


class ValidationFailed(OnboardingError):
    code = "validation_failed"
    http_status = 422


class NotFoundError(OnboardingError):
    code = "not_found"
    http_status = 404


class ConflictError(OnboardingError):
    code = "conflict"
    http_status = 409
