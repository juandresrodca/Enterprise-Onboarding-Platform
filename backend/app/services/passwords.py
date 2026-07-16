"""Password generation and policy validation."""

from __future__ import annotations

import secrets
import string

from app.config import PasswordPolicy

_UPPER = string.ascii_uppercase
_LOWER = string.ascii_lowercase
_DIGITS = string.digits
# Symbols chosen to avoid shell/AD-quoting foot-guns while staying complex.
_SYMBOLS = "!@#$%^&*()-_=+[]{}"
_AMBIGUOUS = set("Il1O0")


def generate_password(policy: PasswordPolicy) -> str:
    """Generate a policy-compliant password with at least one char per class."""
    length = max(policy.generated_length, policy.min_length)
    pools = []
    if policy.require_uppercase:
        pools.append(_UPPER)
    if policy.require_lowercase:
        pools.append(_LOWER)
    if policy.require_digit:
        pools.append(_DIGITS)
    if policy.require_symbol:
        pools.append(_SYMBOLS)
    if not pools:
        pools = [_LOWER + _DIGITS]

    alphabet = "".join(c for c in "".join(pools) if c not in _AMBIGUOUS)
    while True:
        chars = [secrets.choice([c for c in pool if c not in _AMBIGUOUS]) for pool in pools]
        chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
        # Fisher-Yates with a CSPRNG; random.shuffle is not cryptographically safe.
        for i in range(len(chars) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            chars[i], chars[j] = chars[j], chars[i]
        candidate = "".join(chars)
        if not validate_password(candidate, policy):
            return candidate


def validate_password(
    password: str, policy: PasswordPolicy, name_parts: list[str] | None = None
) -> list[str]:
    """Return a list of human-readable violations (empty list = compliant)."""
    problems: list[str] = []
    if len(password) < policy.min_length:
        problems.append(f"must be at least {policy.min_length} characters")
    if policy.require_uppercase and not any(c in _UPPER for c in password):
        problems.append("must contain an uppercase letter")
    if policy.require_lowercase and not any(c in _LOWER for c in password):
        problems.append("must contain a lowercase letter")
    if policy.require_digit and not any(c in _DIGITS for c in password):
        problems.append("must contain a digit")
    if policy.require_symbol and not any(not c.isalnum() for c in password):
        problems.append("must contain a symbol")
    if policy.disallow_name_parts and name_parts:
        lowered = password.lower()
        for part in name_parts:
            part = (part or "").strip().lower()
            if len(part) >= 3 and part in lowered:
                problems.append(f"must not contain the name '{part}'")
    return problems
