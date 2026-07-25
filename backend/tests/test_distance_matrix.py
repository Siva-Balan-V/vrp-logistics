"""Tests for distance matrix service."""

import numpy as np
import pytest

from app.services.distance_matrix import build_haversine_matrix, haversine_km


def test_haversine_km_known_distance():
    """London to Paris is approximately 343 km."""
    d = haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
    assert 340 < d < 350


def test_haversine_km_same_point():
    """Distance from a point to itself should be zero."""
    d = haversine_km(51.5074, -0.1278, 51.5074, -0.1278)
    assert d == pytest.approx(0.0, abs=0.001)


def test_haversine_km_symmetry():
    """Distance A->B should equal B->A."""
    d1 = haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
    d2 = haversine_km(48.8566, 2.3522, 51.5074, -0.1278)
    assert d1 == pytest.approx(d2, rel=0.001)


def test_build_haversine_matrix_shape():
    """Matrix should be n x n."""
    coords = [(51.5074, -0.1278), (48.8566, 2.3522), (52.5200, 13.4050)]
    dist, dur = build_haversine_matrix(coords)
    assert dist.shape == (3, 3)
    assert dur.shape == (3, 3)


def test_build_haversine_matrix_diagonal_zero():
    """Diagonal of distance matrix should be zero."""
    coords = [(51.5074, -0.1278), (48.8566, 2.3522)]
    dist, _ = build_haversine_matrix(coords)
    assert dist[0, 0] == pytest.approx(0.0, abs=0.001)
    assert dist[1, 1] == pytest.approx(0.0, abs=0.001)


def test_build_haversine_matrix_symmetric():
    """Distance matrix should be symmetric."""
    coords = [(51.5074, -0.1278), (48.8566, 2.3522), (52.5200, 13.4050)]
    dist, _ = build_haversine_matrix(coords)
    assert np.allclose(dist, dist.T, atol=0.001)


def test_build_haversine_matrix_with_road_factor():
    """Matrix with road factor should be 1.35x straight-line distance."""
    coords = [(51.5074, -0.1278), (48.8566, 2.3522)]
    dist, _ = build_haversine_matrix(coords)
    straight_line = haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
    assert dist[0, 1] == pytest.approx(straight_line * 1.35, rel=0.01)


def test_build_haversine_matrix_duration():
    """Duration should be distance / speed * 3600."""
    coords = [(51.5074, -0.1278), (48.8566, 2.3522)]
    speed = 30.0
    dist, dur = build_haversine_matrix(coords, speed_kmh=speed)
    expected_dur = (dist / speed) * 3600.0
    assert np.allclose(dur, expected_dur, atol=0.001)
