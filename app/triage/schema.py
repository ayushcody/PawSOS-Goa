"""The exact shape we require from the vision model.

Pydantic checks every reply against this. A reply that does not fit is
rejected and asked for again (once), so nothing unchecked reaches a citizen.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Species = Literal["dog", "cat", "cow", "bird", "monkey", "snake", "other", "unclear"]
Urgency = Literal["low", "medium", "high", "critical"]
AggressionRisk = Literal["low", "medium", "high", "unknown"]

MAX_STEP_LENGTH = 200


class TriageResult(BaseModel):
    animal_visible: bool = Field(description="True only if an animal can clearly be seen.")
    species: Species
    injury_type: str = Field(
        description=(
            "A short, plain description of what is visible, such as 'visible wound on hind leg' "
            "or 'no visible injury'. Never a diagnosis."
        )
    )
    urgency: Urgency
    aggression_risk: AggressionRisk
    first_aid: list[str] = Field(
        description="Two or three short, safe steps for an untrained member of the public."
    )

    @field_validator("injury_type")
    @classmethod
    def _injury_is_short(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 160:
            raise ValueError("injury_type must be a short description")
        return value

    @field_validator("first_aid")
    @classmethod
    def _two_or_three_short_steps(cls, steps: list[str]) -> list[str]:
        steps = [s.strip() for s in steps if s.strip()]
        if not 2 <= len(steps) <= 3:
            raise ValueError("first_aid must have 2 or 3 steps")
        if any(len(s) > MAX_STEP_LENGTH for s in steps):
            raise ValueError("each first_aid step must be one short sentence")
        return steps
