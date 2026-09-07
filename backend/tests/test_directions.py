"""Tests for the turn-by-turn directions service."""

from unittest.mock import patch

import pytest

from app.models.schemas import DirectionStep
from app.services import directions


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self, data):
        self.data = data

    async def get(self, *args, **kwargs):  # noqa: ARG002
        return _FakeResponse(self.data)


class _FakeClientContext:
    def __init__(self, data):
        self._client = _FakeClient(data)

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, *args):
        return None


def _patch_client(payload):
    return patch("app.services.directions.httpx.AsyncClient", return_value=_FakeClientContext(payload))


@pytest.fixture(autouse=True)
def clear_directions_cache():
    from app.services.cache import _directions_cache

    _directions_cache.clear()
    yield
    _directions_cache.clear()


def _osrm_payload():
    return {
        "code": "Ok",
        "routes": [
            {
                "geometry": {"type": "LineString", "coordinates": [[-0.1278, 51.5074], [-0.1301, 51.5089]]},
                "legs": [
                    {
                        "distance": 640.0,
                        "duration": 92.0,
                        "steps": [
                            {
                                "distance": 120.0,
                                "duration": 18.0,
                                "name": "",
                                "maneuver": {"type": "depart", "location": [-0.1278, 51.5074]},
                            },
                            {
                                "distance": 520.0,
                                "duration": 74.0,
                                "name": "Broadway",
                                "maneuver": {"type": "turn", "modifier": "left", "location": [-0.1301, 51.5089]},
                            },
                        ],
                    }
                ],
            }
        ],
    }


def _ors_payload():
    return {
        "routes": [
            {
                "geometry": {"type": "LineString", "coordinates": [[-0.1278, 51.5074], [-0.1301, 51.5089]]},
                "segments": [
                    {
                        "steps": [
                            {
                                "distance": 120.0,
                                "duration": 18.0,
                                "type": 11,
                                "instruction": "Head north on Broad St",
                                "start_location": [-0.1278, 51.5074],
                            },
                            {
                                "distance": 520.0,
                                "duration": 74.0,
                                "type": 1,
                                "instruction": "Turn right onto Broadway",
                                "start_location": [-0.1301, 51.5089],
                            },
                        ]
                    }
                ],
            }
        ]
    }


async def test_osrm_leg_parses_maneuver_steps():
    origin = (51.5074, -0.1278)
    dest = (51.5089, -0.1301)

    with _patch_client(_osrm_payload()):
        result = await directions.get_directions_for_leg(origin, dest, backend="osrm")

    assert result["source"] == "osrm"
    assert len(result["steps"]) == 2
    first, second = result["steps"]
    assert isinstance(first, DirectionStep)
    assert first.instruction == "Depart"
    assert second.instruction == "left onto Broadway"
    assert second.maneuver == "turn"
    assert second.lat == pytest.approx(dest[0])
    assert result["geometry"] == [[-0.1278, 51.5074], [-0.1301, 51.5089]]


async def test_ors_leg_parses_instruction_steps():
    origin = (51.5074, -0.1278)
    dest = (51.5089, -0.1301)

    with (
        patch.object(directions.settings, "ORS_API_KEY", "test-key"),
        _patch_client(_ors_payload()),
    ):
        result = await directions.get_directions_for_leg(origin, dest, backend="ors")

    assert result["source"] == "ors"
    assert [s.instruction for s in result["steps"]] == ["Head north on Broad St", "Turn right onto Broadway"]
    assert result["steps"][1].maneuver == 1


async def test_haversine_leg_single_step():
    origin = (51.5074, -0.1278)
    dest = (51.5089, -0.1301)

    result = await directions.get_directions_for_leg(origin, dest, backend="haversine")

    assert result["source"] == "haversine"
    assert len(result["steps"]) == 1
    step = result["steps"][0]
    assert step.instruction == "Proceed to waypoint"
    assert step.lat == pytest.approx(dest[0])
    assert step.distance_m > 0
    assert result["geometry"] == [[-0.1278, 51.5074], [-0.1301, 51.5089]]


async def test_router_failure_falls_back_to_haversine():
    origin = (51.5074, -0.1278)
    dest = (51.5089, -0.1301)

    class _DownClient(_FakeClient):
        async def get(self, *args, **kwargs):  # noqa: ARG002
            raise RuntimeError("router down")

    class _DownContext(_FakeClientContext):
        def __init__(self):
            self._client = _DownClient(None)

    with patch("app.services.directions.httpx.AsyncClient", return_value=_DownContext()):
        result = await directions.get_directions_for_leg(origin, dest, backend="osrm")

    assert result["source"] == "haversine"
    assert result["steps"][0].instruction == "Proceed to waypoint"


async def test_leg_result_is_cached():
    origin = (51.5074, -0.1278)
    dest = (51.5089, -0.1301)
    cached = {
        "steps": [{"instruction": "Cached", "distance_m": 0.0, "duration_s": 0.0, "lon": dest[1], "lat": dest[0]}],
        "geometry": [[-0.1278, 51.5074]],
        "source": "haversine",
    }

    with (
        patch("app.services.directions.cache.get_directions", return_value=cached) as mock_get,
        patch("app.services.directions.cache.set_directions") as mock_set,
    ):
        result = await directions.get_directions_for_leg(origin, dest, backend="haversine")

    mock_get.assert_called_once()
    mock_set.assert_not_called()
    assert result["source"] == "haversine"
    assert isinstance(result["steps"][0], DirectionStep)
    assert result["steps"][0].instruction == "Cached"


async def test_route_concatenates_legs():
    coords = [(51.5074, -0.1278), (51.5089, -0.1301), (51.5100, -0.1320)]

    result = await directions.get_directions_for_route(coords, backend="haversine")

    assert result["source"] == "haversine"
    assert len(result["steps"]) == 2
    assert result["steps"][0].lat == pytest.approx(coords[1][0])
    assert result["steps"][1].lat == pytest.approx(coords[2][0])
    assert result["geometry"][0] == [-0.1278, 51.5074]
    assert result["geometry"][-1] == [-0.1320, 51.5100]


async def test_route_requires_two_points():
    result = await directions.get_directions_for_route([(51.5074, -0.1278)], backend="haversine")
    assert result["steps"] == []
    assert result["geometry"] == []
