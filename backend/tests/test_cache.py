"""Tests for cache service."""

import numpy as np

from app.services.cache import _matrix_key, get_matrix, set_matrix


def test_matrix_key_deterministic():
    """Same inputs should produce the same cache key."""
    coords = [(51.5074, -0.1278), (48.8566, 2.3522)]
    key1 = _matrix_key(coords, "haversine")
    key2 = _matrix_key(coords, "haversine")
    assert key1 == key2


def test_matrix_key_different_backends():
    """Different backends should produce different keys."""
    coords = [(51.5074, -0.1278), (48.8566, 2.3522)]
    key1 = _matrix_key(coords, "haversine")
    key2 = _matrix_key(coords, "osrm")
    assert key1 != key2


def test_matrix_key_different_coords():
    """Different coordinates should produce different keys."""
    coords1 = [(51.5074, -0.1278), (48.8566, 2.3522)]
    coords2 = [(52.5200, 13.4050), (40.7128, -74.0060)]
    key1 = _matrix_key(coords1, "haversine")
    key2 = _matrix_key(coords2, "haversine")
    assert key1 != key2


def test_lru_roundtrip():
    """Set and get should roundtrip through LRU cache."""
    coords = [(51.5074, -0.1278), (48.8566, 2.3522)]
    dist = np.array([[0.0, 343.0], [343.0, 0.0]])
    dur = np.array([[0.0, 41160.0], [41160.0, 0.0]])
    value = (dist, dur, "haversine")

    set_matrix(coords, "haversine", value)
    result = get_matrix(coords, "haversine")

    assert result is not None
    r_dist, r_dur, r_source = result
    assert np.allclose(r_dist, dist)
    assert np.allclose(r_dur, dur)
    assert r_source == "haversine"


def test_lru_miss():
    """Cache miss should return None."""
    coords = [(40.7128, -74.0060), (34.0522, -118.2437)]  # NYC to LA - different coords
    result = get_matrix(coords, "haversine")
    assert result is None


def test_lru_overwrite():
    """Setting same key should overwrite previous value."""
    coords = [(51.5074, -0.1278), (48.8566, 2.3522)]
    dist1 = np.array([[0.0, 100.0], [100.0, 0.0]])
    dist2 = np.array([[0.0, 200.0], [200.0, 0.0]])
    dur = np.zeros((2, 2))

    set_matrix(coords, "haversine", (dist1, dur, "haversine"))
    set_matrix(coords, "haversine", (dist2, dur, "osrm"))

    result = get_matrix(coords, "haversine")
    assert result is not None
    assert np.allclose(result[0], dist2)
    assert result[2] == "osrm"
