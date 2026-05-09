from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from pytest_mock import MockerFixture

from polarsteps_tts.application.use_cases import FetchTripCommand, FetchTripUseCase
from polarsteps_tts.domain.entities import Trip
from polarsteps_tts.domain.exceptions import TripNotFound
from polarsteps_tts.domain.ports import TripRepository
from polarsteps_tts.domain.value_objects import TripId


def _trip(trip_id: str = "42") -> Trip:
    return Trip(
        id=TripId(trip_id),
        name="Test",
        start_date=datetime(2024, 7, 15, tzinfo=UTC),
        end_date=datetime(2024, 7, 25, tzinfo=UTC),
        author_first_name="Alice",
        steps=(),
    )


class TestFetchTripUseCase:
    def test_delegates_to_repository(self, mocker: MockerFixture) -> None:
        repo = mocker.Mock(spec=TripRepository)
        repo.get_by_id.return_value = _trip("42")

        use_case = FetchTripUseCase(cast(TripRepository, repo))
        command = FetchTripCommand(TripId("42"))

        result = use_case.execute(command)

        repo.get_by_id.assert_called_once_with(TripId("42"), None)
        assert result.id == TripId("42")

    def test_passes_share_token_through(self, mocker: MockerFixture) -> None:
        repo = mocker.Mock(spec=TripRepository)
        repo.get_by_id.return_value = _trip()

        use_case = FetchTripUseCase(cast(TripRepository, repo))
        use_case.execute(FetchTripCommand(TripId("42"), share_token="tok123"))

        repo.get_by_id.assert_called_once_with(TripId("42"), "tok123")

    def test_propagates_domain_errors(self, mocker: MockerFixture) -> None:
        repo = mocker.Mock(spec=TripRepository)
        repo.get_by_id.side_effect = TripNotFound("42")

        use_case = FetchTripUseCase(cast(TripRepository, repo))

        with pytest.raises(TripNotFound):
            use_case.execute(FetchTripCommand(TripId("42")))
