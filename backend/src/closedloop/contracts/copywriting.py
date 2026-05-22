from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, model_validator


class PlanCopywriting(BaseModel):
    """Copywriting payload for a single plan card."""

    plan_name: str = Field(..., max_length=12, description="Plan display name (<= 12 chars).")
    pros_cons: list[str] = Field(
        default_factory=list,
        description="2-3 bullet points. Use '✔' for pros and '✘' for cons.",
    )
    ai_reminder: str = Field(..., description="Human-like reminder in 2-3 lines.")

    @model_validator(mode="after")
    def _validate_pros_cons(self):
        pcs = self.pros_cons or []
        if not (2 <= len(pcs) <= 3):
            raise ValueError("pros_cons must have 2-3 items")
        for s in pcs:
            if not isinstance(s, str):
                raise ValueError("pros_cons item must be a string")
            if not (s.startswith("✔") or s.startswith("✘")):
                raise ValueError("pros_cons item must start with '✔' or '✘'")
        return self


class ThreePlansCopywriting(BaseModel):
    """Copywriting payload for plan_1/2/3."""

    plan_1: Annotated[PlanCopywriting, Field(..., description="Low price decoy plan.")]
    plan_2: Annotated[PlanCopywriting, Field(..., description="Main compromise plan.")]
    plan_3: Annotated[PlanCopywriting, Field(..., description="Premium decoy plan.")]

