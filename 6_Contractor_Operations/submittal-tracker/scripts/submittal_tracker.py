"""Deterministic submittal deadline and review-risk calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class SubmittalStatus(str, Enum):
    NOT_SUBMITTED = "not_submitted"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    REVISE_RESUBMIT = "revise_resubmit"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Submittal:
    number: str
    description: str
    required_on_site: date
    fabrication_lead_days: int
    review_days: int
    status: SubmittalStatus = SubmittalStatus.NOT_SUBMITTED
    submitted_on: date | None = None
    decided_on: date | None = None
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.number.strip() or not self.description.strip():
            raise ValueError("submittal number and description are required")
        if self.fabrication_lead_days < 0 or self.review_days < 0 or self.revision < 0:
            raise ValueError("lead, review, and revision values cannot be negative")
        if self.status in {SubmittalStatus.SUBMITTED, SubmittalStatus.UNDER_REVIEW} and self.submitted_on is None:
            raise ValueError("submitted_on is required after submission")
        if self.status in {SubmittalStatus.APPROVED, SubmittalStatus.REJECTED} and self.decided_on is None:
            raise ValueError("decided_on is required for a final decision")
        if self.submitted_on and self.decided_on and self.decided_on < self.submitted_on:
            raise ValueError("decided_on cannot precede submitted_on")

    @property
    def required_submission_date(self) -> date:
        return self.required_on_site - timedelta(days=self.fabrication_lead_days + self.review_days)


def evaluate(submittal: Submittal, as_of: date) -> dict[str, object]:
    """Evaluate timing risk without approving or transmitting a submittal."""
    required_submission = submittal.required_submission_date
    review_due = submittal.submitted_on + timedelta(days=submittal.review_days) if submittal.submitted_on else None
    reasons: list[str] = []

    if submittal.status is SubmittalStatus.APPROVED:
        risk = "complete"
    elif submittal.status in {SubmittalStatus.REJECTED, SubmittalStatus.REVISE_RESUBMIT}:
        risk = "critical" if as_of >= required_submission else "high"
        reasons.append("revision_or_replacement_required")
    elif submittal.status is SubmittalStatus.NOT_SUBMITTED and as_of > required_submission:
        risk = "critical"
        reasons.append("submission_overdue")
    elif review_due and as_of > review_due:
        risk = "critical"
        reasons.append("review_overdue")
    elif submittal.status is SubmittalStatus.NOT_SUBMITTED and (required_submission - as_of).days <= 7:
        risk = "high"
        reasons.append("submission_due_within_seven_days")
    elif review_due and (review_due - as_of).days <= 3:
        risk = "high"
        reasons.append("review_due_within_three_days")
    else:
        risk = "normal"

    if submittal.status is not SubmittalStatus.APPROVED and as_of >= submittal.required_on_site:
        risk = "critical"
        reasons.append("material_required_on_site_without_approval")
    return {
        "number": submittal.number,
        "status": submittal.status.value,
        "revision": submittal.revision,
        "required_submission_date": required_submission.isoformat(),
        "review_due": review_due.isoformat() if review_due else None,
        "required_on_site": submittal.required_on_site.isoformat(),
        "risk": risk,
        "requires_review": risk in {"high", "critical"},
        "reasons": reasons,
    }
