"""
Route export service: generates CSV, GPX, and KML files from optimization results.

CSV and KML are direction-aware: they can embed turn-by-turn step instructions
collected per leg via :func:`collect_route_directions`.
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from xml.dom import minidom

from app.models.schemas import DirectionStep, OptimizeResponse


def generate_csv(
    result: OptimizeResponse,
    steps_by_stop: dict[tuple[int, int], DirectionStep] | None = None,
) -> str:
    """Generate a CSV file with all vehicle routes.

    When `steps_by_stop` is provided (mapping ``(vehicle_index, stop_sequence)``
    to the direction step that arrives at that stop), ``arrive_maneuver`` and
    ``arrive_instruction`` columns are appended for each stop.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "vehicle_id",
        "stop_sequence",
        "location_id",
        "label",
        "latitude",
        "longitude",
        "distance_km",
        "time_minutes",
        "packages",
    ]
    if steps_by_stop:
        headers += ["arrive_maneuver", "arrive_instruction"]
    writer.writerow(headers)

    for vi, vehicle in enumerate(result.vehicles):
        for seq, wp in enumerate(vehicle.waypoints):
            label = ""
            if seq < len(vehicle.route_labels) and vehicle.route_labels[seq]:
                label = vehicle.route_labels[seq]
            row = [
                vehicle.vehicle_id,
                seq + 1,
                wp.get("id", ""),
                label,
                wp.get("lat", ""),
                wp.get("lon", ""),
                round(vehicle.distance_km, 3) if seq == len(vehicle.waypoints) - 1 else "",
                round(vehicle.time_minutes, 1) if seq == len(vehicle.waypoints) - 1 else "",
                vehicle.packages_delivered if seq == len(vehicle.waypoints) - 1 else "",
            ]
            if steps_by_stop:
                arriving = steps_by_stop.get((vi, seq + 1))
                row.append(arriving.maneuver if arriving else "")
                row.append(arriving.instruction if arriving else "")
            writer.writerow(row)

    # Summary row
    writer.writerow([])
    writer.writerow(
        [
            "TOTAL",
            "",
            "",
            "",
            "",
            "",
            round(result.total_distance_km, 3),
            round(result.total_time_minutes, 1),
            f"{result.assigned_count} assigned, {result.unassigned_count} unassigned",
        ]
    )

    return output.getvalue()


def generate_gpx(result: OptimizeResponse) -> str:
    """Generate a GPX 1.1 file with tracks for each vehicle."""
    gpx = ET.Element(
        "gpx",
        {
            "version": "1.1",
            "creator": "RouteForge VRP Optimizer",
            "xmlns": "http://www.topografix.com/GPX/1/1",
        },
    )

    metadata = ET.SubElement(gpx, "metadata")
    name = ET.SubElement(metadata, "name")
    name.text = f"RouteForge Optimization {result.job_id[:8]}"
    ET.SubElement(
        metadata, "desc"
    ).text = (
        f"{result.vehicles_used} vehicles, {result.assigned_count} stops, {round(result.total_distance_km, 1)} km total"
    )

    for vehicle in result.vehicles:
        for idx, wp in enumerate(vehicle.waypoints):
            wpt = ET.SubElement(
                gpx,
                "wpt",
                {
                    "lat": str(wp.get("lat", 0)),
                    "lon": str(wp.get("lon", 0)),
                },
            )
            if idx < len(vehicle.route_labels) and vehicle.route_labels[idx]:
                ET.SubElement(wpt, "name").text = vehicle.route_labels[idx]
            else:
                ET.SubElement(wpt, "name").text = f"Stop {wp.get('id', idx)}"

        # Track
        trk = ET.SubElement(gpx, "trk")
        ET.SubElement(trk, "name").text = f"Vehicle {vehicle.vehicle_id}"
        ET.SubElement(trk, "desc").text = (
            f"{round(vehicle.distance_km, 1)} km, "
            f"{round(vehicle.time_minutes, 0)} min, "
            f"{vehicle.packages_delivered} packages"
        )
        trkseg = ET.SubElement(trk, "trkseg")
        for wp in vehicle.waypoints:
            ET.SubElement(
                trkseg,
                "trkpt",
                {
                    "lat": str(wp.get("lat", 0)),
                    "lon": str(wp.get("lon", 0)),
                },
            )

    rough = ET.tostring(gpx, encoding="unicode", xml_declaration=False)
    parsed = minidom.parseString(rough)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + parsed.toprettyxml(indent="  ", encoding=None).split("\n", 1)[1]


async def collect_route_directions(
    response: OptimizeResponse,
    backend: str | None = None,
) -> dict[int, list[dict]]:
    """Fetch ordered, per-leg directions for every vehicle route.

    Returns ``{vehicle_index: [leg_result, ...]}`` where each leg_result carries
    ``steps`` (list of :class:`DirectionStep`) and ``geometry``
    (``[[lon, lat], ...]``). Leg ``i`` heads from waypoint ``i`` to ``i + 1``.
    """
    from app.services.directions import get_directions_for_leg

    legs_by_route: dict[int, list[dict]] = {}
    for vi, vehicle in enumerate(response.vehicles):
        coords = [
            (float(wp["lat"]), float(wp["lon"]))
            for wp in vehicle.waypoints
            if wp.get("lat") is not None and wp.get("lon") is not None
        ]
        route_legs: list[dict] = []
        for i in range(len(coords) - 1):
            route_legs.append(await get_directions_for_leg(coords[i], coords[i + 1], backend=backend))
        legs_by_route[vi] = route_legs
    return legs_by_route


def generate_kml(
    result: OptimizeResponse,
    legs_by_route: dict[int, list[dict]] | None = None,
) -> str:
    """Generate a KML 2.2 document with a route line and per-leg placemarks.

    Each leg placemark is named after its destination stop and its description
    lists the turn-by-turn step instructions when `legs_by_route` is provided.
    """
    legs_by_route = legs_by_route or {}

    root = ET.Element("kml", {"xmlns": "http://www.opengis.net/kml/2.2"})
    doc = ET.SubElement(root, "Document")
    ET.SubElement(doc, "name").text = f"RouteForge Routes {result.job_id[:8]}"
    ET.SubElement(
        doc, "description"
    ).text = (
        f"{result.vehicles_used} vehicles, {result.assigned_count} stops, {round(result.total_distance_km, 1)} km total"
    )

    for vi, vehicle in enumerate(result.vehicles):
        waypoints = vehicle.waypoints
        labels = vehicle.route_labels or []
        legs = legs_by_route.get(vi) or []

        # Single route line for the whole vehicle
        route_pm = ET.SubElement(doc, "Placemark")
        ET.SubElement(route_pm, "name").text = f"Vehicle {vehicle.vehicle_id} route"
        ET.SubElement(route_pm, "description").text = (
            f"{len(legs)} legs, {round(vehicle.distance_km, 1)} km, "
            f"{round(vehicle.time_minutes, 0)} min, {vehicle.packages_delivered} packages"
        )
        route_ls = ET.SubElement(route_pm, "LineString")
        ET.SubElement(route_ls, "tessellate").text = "1"
        ET.SubElement(route_ls, "coordinates").text = _kml_route_coordinates(legs, waypoints)

        # Per-leg placemark with step names
        for i in range(len(waypoints) - 1):
            dest_label = ""
            if i + 1 < len(labels) and labels[i + 1]:
                dest_label = labels[i + 1]
            dest_name = dest_label or f"Stop {waypoints[i + 1].get('id', i + 1)}"

            leg = legs[i] if i < len(legs) else None
            steps = leg.get("steps", []) if leg else []
            desc_lines = [
                f"{n}. {st.instruction or 'Continue'} "
                f"[{_kml_fmt_distance(st.distance_m)} / {_kml_fmt_duration(st.duration_s)}]"
                for n, st in enumerate(steps, 1)
            ]
            if not desc_lines:
                desc_lines.append("No turn-by-turn directions available.")

            leg_pm = ET.SubElement(doc, "Placemark")
            ET.SubElement(leg_pm, "name").text = f"Leg {i + 1}: {dest_name}"
            ET.SubElement(leg_pm, "description").text = "\n".join(desc_lines)

            leg_ls = ET.SubElement(leg_pm, "LineString")
            ET.SubElement(leg_ls, "tessellate").text = "1"
            geometry = leg.get("geometry", []) if leg else []
            coords = _kml_coordinates(geometry)
            if not coords:
                coords = _kml_leg_coordinates(waypoints[i], waypoints[i + 1])
            ET.SubElement(leg_ls, "coordinates").text = coords

            ext = ET.SubElement(leg_pm, "ExtendedData")
            for key, value in (
                ("leg", i + 1),
                ("stop", waypoints[i + 1].get("id", i + 1)),
                ("destination", dest_name),
            ):
                data_el = ET.SubElement(ext, "Data", {"name": key})
                ET.SubElement(data_el, "value").text = str(value)

    return _pretty_kml(root)


# ─────────────────────────────────────────────────────────
# KML helpers
# ─────────────────────────────────────────────────────────


def _kml_coordinates(geometry: list[list[float]]) -> str:
    """Format [[lon, lat], ...] as a KML coordinates string."""
    return " ".join(f"{lon},{lat}" for lon, lat in geometry)


def _kml_route_coordinates(legs: list[dict], waypoints: list[dict]) -> str:
    """Concatenate per-leg geometries (deduplicating shared endpoints)."""
    if legs:
        coords: list[list[float]] = []
        for leg in legs:
            for pt in leg.get("geometry", []) or []:
                if coords and coords[-1] == pt:
                    continue
                coords.append(pt)
        if coords:
            return _kml_coordinates(coords)
    return " ".join(f"{wp['lon']},{wp['lat']}" for wp in waypoints)


def _kml_leg_coordinates(origin: dict, dest: dict) -> str:
    return f"{origin['lon']},{origin['lat']} {dest['lon']},{dest['lat']}"


def _kml_fmt_distance(meters) -> str:
    m = float(meters or 0)
    if m < 1000:
        return f"{round(m)} m"
    return f"{round(m / 1000, 2)} km"


def _kml_fmt_duration(seconds) -> str:
    s = float(seconds or 0)
    return f"{int(s // 60)}m {int(s % 60)}s"


def _pretty_kml(root: ET.Element) -> str:
    rough = ET.tostring(root, encoding="unicode", xml_declaration=False)
    parsed = minidom.parseString(rough)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + parsed.toprettyxml(indent="  ", encoding=None).split("\n", 1)[1]
