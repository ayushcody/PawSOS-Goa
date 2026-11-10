"""Triage one case: look at its photo, record the result, move it to TRIAGED.

Triage must never block a rescue. If the model is unavailable, gives an
unusable answer twice, or cannot see an animal, the case still moves on:
marked urgent and flagged for a person to review.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases import state_machine
from app.cases.models import Case, CaseState, Photo, Report
from app.channels import media
from app.triage.schema import TriageResult
from app.triage.service import Triager, TriageUnavailable

log = logging.getLogger(__name__)

FALLBACK_URGENCY = "high"


async def triage_case(session: Session, case: Case, triager: Triager | None) -> TriageResult | None:
    """Returns the result when triage worked, or None when a person must review."""
    result: TriageResult | None = None
    reason = "no_triager"

    if triager is not None:
        image = _first_photo(session, case)
        if image is None:
            reason = "photo_missing"
        else:
            try:
                result = await triager.triage(image)
                reason = "ok" if result.animal_visible else "no_animal_visible"
            except TriageUnavailable as error:
                reason = f"unavailable: {error}"
            except Exception:  # anything unexpected must not lose the case
                log.exception("Triage failed unexpectedly for %s", case.public_id)
                reason = "unexpected_error"

    usable = result is not None and result.animal_visible
    case.triaged_at = datetime.now(UTC)
    if usable:
        case.species = result.species
        case.injury_type = result.injury_type
        case.urgency = result.urgency
        case.aggression_risk = result.aggression_risk
        case.first_aid = result.first_aid
        case.triage_status = "ok"
    else:
        case.urgency = FALLBACK_URGENCY
        case.triage_status = "needs_review"

    state_machine.transition(
        session,
        case,
        CaseState.TRIAGED,
        actor="triage",
        data={"triage_status": case.triage_status, "urgency": case.urgency, "reason": reason},
    )
    return result if usable else None


def _first_photo(session: Session, case: Case) -> bytes | None:
    name = session.scalar(
        select(Photo.path)
        .join(Report, Photo.report_id == Report.id)
        .where(Report.case_id == case.id)
        .order_by(Photo.id)
        .limit(1)
    )
    path = media.path_for(name) if name else None
    return path.read_bytes() if path else None
