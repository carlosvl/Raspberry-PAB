"""Match MCA race events and participant rows to ITS YOUR RACE results."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from raspberry_pab.models import Participant
from raspberry_pab.race_results.itsyourrace import ParsedIyrSession, ParsedResultRow
from raspberry_pab.race_results.names import names_match
from raspberry_pab.race_results.precision_race import ParsedRaceEvent

_VENUE_NOISE = re.compile(r"[^a-z0-9\s]", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class RaceEventCandidate:
    event: ParsedRaceEvent
    venue_score: float


@dataclass(frozen=True)
class ParticipantResultMatch:
    participant: Participant
    race_event: ParsedRaceEvent
    session: ParsedIyrSession
    row: ParsedResultRow
    match_method: str
    match_confidence: float


def normalize_venue(value: str) -> set[str]:
    cleaned = _VENUE_NOISE.sub(" ", value.lower())
    return {token for token in _WHITESPACE.sub(" ", cleaned).split() if len(token) > 2}


def venue_similarity(left: str, right: str) -> float:
    left_tokens = normalize_venue(left)
    right_tokens = normalize_venue(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    return len(overlap) / max(len(left_tokens), len(right_tokens))


def find_race_events_for_date(
    events: list[ParsedRaceEvent],
    event_date: date,
    *,
    venue_hint: str | None = None,
) -> list[RaceEventCandidate]:
    candidates = [
        event
        for event in events
        if event_date in (event.date_saturday, event.date_sunday)
    ]
    if not candidates:
        return []
    if len(candidates) == 1:
        return [RaceEventCandidate(event=candidates[0], venue_score=1.0)]
    scored = [
        RaceEventCandidate(
            event=event,
            venue_score=venue_similarity(venue_hint or event.venue_label, event.venue_label),
        )
        for event in candidates
    ]
    scored.sort(key=lambda item: item.venue_score, reverse=True)
    return scored


def sessions_for_date(
    sessions: list[ParsedIyrSession],
    event_date: date,
) -> list[ParsedIyrSession]:
    return [session for session in sessions if session.race_date == event_date]


def match_participant_in_sessions(
    participant: Participant,
    race_event: ParsedRaceEvent,
    sessions: list[ParsedIyrSession],
) -> list[ParticipantResultMatch]:
    matches: list[ParticipantResultMatch] = []
    for session in sessions:
        for row in session.rows:
            if names_match(participant.name, row.raw_name):
                matches.append(
                    ParticipantResultMatch(
                        participant=participant,
                        race_event=race_event,
                        session=session,
                        row=row,
                        match_method="date+name",
                        match_confidence=0.95,
                    )
                )
    return matches


def choose_best_match(
    matches: list[ParticipantResultMatch],
) -> ParticipantResultMatch | None:
    if len(matches) == 1:
        return matches[0]
    return None
