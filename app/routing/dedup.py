"""Is this the same animal someone already reported?

A new case is a duplicate of an open case when it is within DEDUP_RADIUS_M,
the open case was created within DEDUP_WINDOW, and the animals look similar.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cases.models import Case, CaseState, Report
from app.sandbox import numbers as sandbox_numbers

DEDUP_RADIUS_M = 200
DEDUP_WINDOW = timedelta(hours=2)

# A case someone is still working on. Finished or merged cases are never merged into.
OPEN_STATES = [
    CaseState.NEW,
    CaseState.ROUTED,
    CaseState.ESCALATED,
    CaseState.ACCEPTED,
    CaseState.ON_SITE,
]

UNKNOWN_SPECIES = {None, "unclear", "other"}


def similar_animal(species_a: str | None, species_b: str | None) -> bool:
    """Same species, or we could not tell for one of them.

    When triage could not name the species, being in the same place at the
    same time is the stronger signal, so we treat it as a match.
    """
    if species_a in UNKNOWN_SPECIES or species_b in UNKNOWN_SPECIES:
        return True
    return species_a == species_b


def _same_audience(session: Session, case: Case):
    """Public-demo sandboxes never see each other's cases (app/sandbox).

    A sandbox report merges only into cases reported from the same sandbox; a real
    report never merges into a sandbox case.
    """
    number = session.scalar(
        select(Report.reporter_number).where(Report.case_id == case.id).limit(1)
    )
    key = sandbox_numbers.key_of(number)
    if key is not None:
        mine = select(Report.case_id).where(Report.reporter_number.like(f"{key}%"))
        return Case.id.in_(mine)
    sandboxed = select(Report.case_id).where(
        Report.case_id.is_not(None), Report.reporter_number.like(f"{sandbox_numbers.PREFIX}%")
    )
    return Case.id.not_in(sandboxed)


def _nearby(session: Session, case: Case, states: list[CaseState]):
    """Other cases in `states` within the dedup radius and time window, oldest first."""
    here = select(Case.location).where(Case.id == case.id).scalar_subquery()
    return (
        select(Case)
        .where(
            Case.id != case.id,
            Case.state.in_(states),
            Case.is_demo.is_(False),  # a real report never merges into an invented case
            Case.created_at >= datetime.now(UTC) - DEDUP_WINDOW,
            # ST_DWithin on geography measures in metres and uses the GiST index.
            func.ST_DWithin(Case.location, here, DEDUP_RADIUS_M),
            _same_audience(session, case),
        )
        .order_by(Case.created_at, Case.id)
    )


def find_duplicate(session: Session, case: Case) -> Case | None:
    """The oldest open case this one duplicates, or None."""
    for candidate in session.scalars(_nearby(session, case, OPEN_STATES)):
        if similar_animal(candidate.species, case.species):
            return candidate
    return None


def might_be_duplicate(session: Session, case: Case) -> bool:
    """Could this new, untriaged case turn out to be a duplicate? Place and time only.

    Asked before triage, so the species is not known yet: a nearby open case
    is enough. Cases still being triaged count too, because one of them may be
    open by the time this case is routed.
    """
    query = _nearby(session, case, [CaseState.REPORTED, CaseState.TRIAGED, *OPEN_STATES]).limit(1)
    return session.scalar(query) is not None
