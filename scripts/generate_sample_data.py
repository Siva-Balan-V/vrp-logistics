#!/usr/bin/env python3
"""
Sample Data Generator for VRP Logistics Optimizer
===================================================
Generates 600 realistic delivery locations clustered around a central depot.
Uses a Gaussian Mixture Model approach to simulate real-world delivery patterns
(e.g., dense city-centre clusters, suburban areas, and outliers).

Usage:
    python generate_sample_data.py                   # → sample_data.json
    python generate_sample_data.py --n 100 --out my.json
    python generate_sample_data.py --city london
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Optional

# ─────────────────────────────────────────────
# PRESET CITY CENTRES
# ─────────────────────────────────────────────
CITIES = {
    "london":    (51.5074, -0.1278),
    "new_york":  (40.7128, -74.0060),
    "berlin":    (52.5200,  13.4050),
    "tokyo":     (35.6762, 139.6503),
    "mumbai":    (19.0760,  72.8777),
    "sydney":    (-33.8688, 151.2093),
    "paris":     (48.8566,   2.3522),
    "singapore": (1.3521,  103.8198),
}

# ─────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────

@dataclass
class DeliveryLocation:
    id: int
    lat: float
    lon: float
    demand: int
    label: str


@dataclass
class SampleDataset:
    depot: dict
    deliveries: list[dict]
    vehicles: dict
    metadata: dict


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _rand_offset(radius_km: float) -> tuple[float, float]:
    """Random offset within a circle of given radius (km)."""
    angle = random.uniform(0, 2 * math.pi)
    r = radius_km * math.sqrt(random.random())   # uniform in circle
    # 1 degree lat ≈ 111 km
    dlat = r * math.cos(angle) / 111.0
    dlon = r * math.sin(angle) / (111.0 * math.cos(math.radians(0.1)))
    return dlat, dlon


def generate_cluster(
    centre_lat: float,
    centre_lon: float,
    n: int,
    radius_km: float,
    start_id: int,
    zone_label: str,
) -> list[DeliveryLocation]:
    locs = []
    for i in range(n):
        dlat, dlon = _rand_offset(radius_km)
        locs.append(DeliveryLocation(
            id=start_id + i,
            lat=round(centre_lat + dlat, 6),
            lon=round(centre_lon + dlon, 6),
            demand=random.randint(1, 5),
            label=f"{zone_label}-{i+1:03d}",
        ))
    return locs


def generate_dataset(
    n_deliveries: int = 600,
    depot_lat: float = 51.5074,
    depot_lon: float = -0.1278,
    seed: int = 42,
    city: str = "london",
) -> SampleDataset:
    random.seed(seed)

    if city in CITIES:
        depot_lat, depot_lon = CITIES[city]

    # Cluster configuration – mimics real urban delivery patterns
    cluster_specs = [
        # (weight %, radius_km, zone_label)
        (0.30, 2.0,  "CityCore"),       # dense centre
        (0.20, 4.0,  "MidRing"),        # mid-ring
        (0.15, 6.0,  "InnerSuburb"),
        (0.15, 8.0,  "OuterSuburb"),
        (0.10, 12.0, "Peripheral"),
        (0.05, 15.0, "Outlier"),
        (0.05, 3.0,  "IndustrialPark"), # secondary cluster shifted
    ]

    deliveries: list[DeliveryLocation] = []
    current_id = 1

    for idx, (weight, radius, label) in enumerate(cluster_specs):
        count = int(n_deliveries * weight)

        # Small offset for secondary clusters
        clat = depot_lat + random.uniform(-0.03, 0.03)
        clon = depot_lon + random.uniform(-0.03, 0.03)

        cluster_locs = generate_cluster(clat, clon, count, radius, current_id, label)
        deliveries.extend(cluster_locs)
        current_id += count

    # Fill remainder
    while len(deliveries) < n_deliveries:
        dlat, dlon = _rand_offset(10.0)
        deliveries.append(DeliveryLocation(
            id=current_id,
            lat=round(depot_lat + dlat, 6),
            lon=round(depot_lon + dlon, 6),
            demand=random.randint(1, 3),
            label=f"Extra-{current_id:04d}",
        ))
        current_id += 1

    # Trim to exact count
    deliveries = deliveries[:n_deliveries]

    dataset = SampleDataset(
        depot={
            "id": 0,
            "lat": round(depot_lat, 6),
            "lon": round(depot_lon, 6),
            "demand": 0,
            "label": f"{city.title()} Depot",
        },
        deliveries=[asdict(d) for d in deliveries],
        vehicles={
            "count": 18,
            "capacity": 50,
            "max_route_duration_seconds": 9000,
            "speed_kmh": 30.0,
        },
        metadata={
            "city": city,
            "n_deliveries": len(deliveries),
            "seed": seed,
            "total_demand": sum(d.demand for d in deliveries),
            "description": (
                f"Synthetic dataset: {len(deliveries)} delivery locations around {city.title()} "
                f"with {len(cluster_specs)} spatial clusters."
            ),
        },
    )
    return dataset


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate VRP sample data")
    parser.add_argument("--n", type=int, default=600, help="Number of delivery locations")
    parser.add_argument("--city", type=str, default="london", choices=list(CITIES.keys()))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="sample_data.json")
    args = parser.parse_args()

    print(f"Generating {args.n} delivery locations around {args.city.title()} …")
    dataset = generate_dataset(
        n_deliveries=args.n,
        city=args.city,
        seed=args.seed,
    )

    with open(args.out, "w") as f:
        json.dump(
            {
                "depot": dataset.depot,
                "deliveries": dataset.deliveries,
                "vehicles": dataset.vehicles,
                "metadata": dataset.metadata,
            },
            f,
            indent=2,
        )

    print(f"✅  Saved {args.n} locations to {args.out}")
    print(f"   Depot:          {dataset.depot['label']} ({dataset.depot['lat']}, {dataset.depot['lon']})")
    print(f"   Total demand:   {dataset.metadata['total_demand']} packages")
    print(f"   Vehicles:       {dataset.vehicles['count']}")
    print(f"   Max duration:   {dataset.vehicles['max_route_duration_seconds']/3600:.1f} h per vehicle")


if __name__ == "__main__":
    main()
