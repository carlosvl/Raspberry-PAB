"""Orchestrate scraping, storage, and participant result matching."""

from __future__ import annotations

from datetime import date

from raspberry_pab.db import ScheduleStore
from raspberry_pab.models import (
    ParticipantResultMatchRecord,
    RaceEvent,
    RaceResultsSyncSummary,
)
from raspberry_pab.race_results.client import FetchText, RaceResultsClient
from raspberry_pab.race_results.itsyourrace import (
    ParsedIyrSession,
    build_results_url,
    build_series_landing_url,
    merge_result_pages,
    parse_category_options,
    parse_results_page_html,
    parse_results_status,
)
from raspberry_pab.race_results.matcher import (
    choose_best_match,
    find_race_events_for_date,
    match_participant_in_sessions,
    sessions_for_date,
)
from raspberry_pab.race_results.precision_race import (
    ParsedRaceEvent,
    parse_precision_race_mca_html,
)

MCA_INDEX_URL = "https://www.precisionrace.com/mca"


class RaceResultsSync:
    def __init__(
        self,
        store: ScheduleStore,
        *,
        fetch_text: FetchText | None = None,
        index_url: str = MCA_INDEX_URL,
    ) -> None:
        self._store = store
        self._index_url = index_url
        if fetch_text is None:
            client = RaceResultsClient()
            self._fetch_text = client.fetch_text
            self._owned_client = client
        else:
            self._fetch_text = fetch_text
            self._owned_client = None

    def close(self) -> None:
        if self._owned_client is not None:
            self._owned_client.close()

    def sync_index(self) -> list[RaceEvent]:
        html = self._fetch_text(self._index_url)
        parsed_events = parse_precision_race_mca_html(html, source_url=self._index_url)
        return self._store.upsert_race_events(parsed_events)

    def sync_date(self, event_date: date) -> RaceResultsSyncSummary:
        race_events = self._store.list_race_events()
        if not race_events:
            self.sync_index()
            race_events = self._store.list_race_events()
        parsed_events = [
            ParsedRaceEvent(
                season_year=event.season_year,
                race_number=event.race_number,
                venue_label=event.venue_label,
                date_saturday=event.date_saturday,
                date_sunday=event.date_sunday,
                iyr_series_id=event.iyr_series_id,
                iyr_base_url=event.iyr_base_url,
                source_url=event.source_url,
            )
            for event in race_events
            if event_date in (event.date_saturday, event.date_sunday)
        ]
        candidates = find_race_events_for_date(parsed_events, event_date)
        participants = self._store.list_participants(event_date)
        if not candidates:
            return RaceResultsSyncSummary(
                event_date=event_date,
                matched=0,
                unmatched=len(participants),
                ambiguous=0,
                sessions_synced=0,
            )
        parsed_event = candidates[0].event
        stored_event = self._store.get_race_event_by_series_id(parsed_event.iyr_series_id)
        if stored_event is None:
            raise RuntimeError(f"Race event {parsed_event.iyr_series_id} missing from store")
        sessions, sessions_synced = self._fetch_sessions_for_date(
            stored_event,
            parsed_event,
            event_date,
        )
        matched = 0
        ambiguous = 0
        unmatched = 0
        day_sessions = sessions_for_date(sessions, event_date)
        for participant in participants:
            matches = match_participant_in_sessions(participant, parsed_event, day_sessions)
            best = choose_best_match(matches)
            if best is None:
                if matches:
                    ambiguous += 1
                else:
                    unmatched += 1
                continue
            stored_session = self._store.upsert_iyr_session(
                race_event_id=stored_event.id,
                iyr_eid=best.session.eid,
                category_label=best.session.category_label,
                race_date=best.session.race_date,
                results_url=best.session.results_url,
                results_status=parse_results_status(best.session.results_status),
            )
            self._store.upsert_race_result(
                participant_id=participant.id,
                iyr_session_id=stored_session.id,
                place=best.row.place,
                bib=best.row.bib,
                team_name=best.row.team_name,
                laps=best.row.laps,
                total_time=best.row.total_time,
                total_distance=best.row.total_distance,
                raw_name=best.row.raw_name,
                match_confidence=best.match_confidence,
                match_method=best.match_method,
                result_status=parse_results_status(best.session.results_status),
            )
            matched += 1
        return RaceResultsSyncSummary(
            event_date=event_date,
            matched=matched,
            unmatched=unmatched,
            ambiguous=ambiguous,
            sessions_synced=sessions_synced,
        )

    def list_matches(self, event_date: date) -> list[ParticipantResultMatchRecord]:
        return self._store.list_participant_result_matches(event_date)

    def _fetch_sessions_for_date(
        self,
        stored_event: RaceEvent,
        parsed_event: ParsedRaceEvent,
        event_date: date,
    ) -> tuple[list[ParsedIyrSession], int]:
        landing_url = build_series_landing_url(
            base_url=parsed_event.iyr_base_url,
            series_id=parsed_event.iyr_series_id,
        )
        landing_html = self._fetch_text(landing_url)
        categories = parse_category_options(landing_html)
        sessions: list[ParsedIyrSession] = []
        synced = 0
        for category in categories:
            first_page_url = build_results_url(
                base_url=parsed_event.iyr_base_url,
                series_id=parsed_event.iyr_series_id,
                season_year=parsed_event.season_year,
                eid=category.eid,
                page=1,
            )
            first_page_html = self._fetch_text(first_page_url)
            first_page = parse_results_page_html(
                first_page_html,
                results_url=first_page_url,
                series_id=parsed_event.iyr_series_id,
                season_year=parsed_event.season_year,
                eid=category.eid,
            )
            if first_page.race_date != event_date:
                continue
            pages = [first_page]
            for page_number in range(2, first_page.page_count + 1):
                page_url = build_results_url(
                    base_url=parsed_event.iyr_base_url,
                    series_id=parsed_event.iyr_series_id,
                    season_year=parsed_event.season_year,
                    eid=category.eid,
                    page=page_number,
                )
                page_html = self._fetch_text(page_url)
                pages.append(
                    parse_results_page_html(
                        page_html,
                        results_url=page_url,
                        series_id=parsed_event.iyr_series_id,
                        season_year=parsed_event.season_year,
                        eid=category.eid,
                    )
                )
            merged = merge_result_pages(pages)
            sessions.append(merged)
            self._store.upsert_iyr_session(
                race_event_id=stored_event.id,
                iyr_eid=merged.eid,
                category_label=merged.category_label,
                race_date=merged.race_date,
                results_url=merged.results_url,
                results_status=parse_results_status(merged.results_status),
            )
            synced += 1
        return sessions, synced
