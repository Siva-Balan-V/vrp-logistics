"""
Route export service: generates CSV and GPX files from optimization results.
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from xml.dom import minidom

from app.models.schemas import OptimizeResponse


def generate_csv(result: OptimizeResponse) -> str:
    """Generate a CSV file with all vehicle routes."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
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
    )

    for vehicle in result.vehicles:
        for seq, wp in enumerate(vehicle.waypoints):
            label = ""
            if seq < len(vehicle.route_labels) and vehicle.route_labels[seq]:
                label = vehicle.route_labels[seq]
            writer.writerow(
                [
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
            )

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
        # Waypoints (named stops)
        for wp in vehicle.waypoints:
            wpt = ET.SubElement(
                gpx,
                "wpt",
                {
                    "lat": str(wp.get("lat", 0)),
                    "lon": str(wp.get("lon", 0)),
                },
            )
            idx = vehicle.waypoints.index(wp)
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
