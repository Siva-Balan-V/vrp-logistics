"""Tests for CSV and GPX export."""

import csv
import io
import xml.etree.ElementTree as ET

from app.models.schemas import OptimizeResponse, VehicleRoute
from app.services.export import generate_csv, generate_gpx


def _make_response():
    return OptimizeResponse(
        job_id="test-job-123",
        status="success",
        solver_time_seconds=1.5,
        total_locations=4,
        assigned_count=3,
        unassigned_count=1,
        vehicles_used=1,
        total_distance_km=12.5,
        total_time_minutes=25.0,
        vehicles=[
            VehicleRoute(
                vehicle_id=1,
                route=[0, 1, 2, 3, 0],
                route_labels=["Depot", "Stop A", "Stop B", "Stop C", "Depot"],
                distance_km=12.5,
                time_minutes=25.0,
                packages_delivered=6,
                waypoints=[
                    {"id": 0, "lat": 51.5, "lon": -0.12},
                    {"id": 1, "lat": 51.51, "lon": -0.07},
                    {"id": 2, "lat": 51.52, "lon": -0.08},
                    {"id": 3, "lat": 51.53, "lon": -0.09},
                    {"id": 0, "lat": 51.5, "lon": -0.12},
                ],
            )
        ],
        unassigned=[4],
        unassigned_labels=["Stop D"],
        matrix_source="haversine",
    )


class TestCSVExport:
    def test_csv_has_headers(self):
        result = _make_response()
        csv_content = generate_csv(result)
        reader = csv.reader(io.StringIO(csv_content))
        headers = next(reader)
        assert "vehicle_id" in headers
        assert "stop_sequence" in headers
        assert "location_id" in headers
        assert "label" in headers
        assert "latitude" in headers
        assert "longitude" in headers

    def test_csv_row_count(self):
        result = _make_response()
        csv_content = generate_csv(result)
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        # 1 header + 5 waypoints + 1 empty + 1 summary = 8 rows
        assert len(rows) == 8

    def test_csv_vehicle_id(self):
        result = _make_response()
        csv_content = generate_csv(result)
        reader = csv.reader(io.StringIO(csv_content))
        next(reader)  # skip header
        first_row = next(reader)
        assert first_row[0] == "1"  # vehicle_id

    def test_csv_summary_row(self):
        result = _make_response()
        csv_content = generate_csv(result)
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        summary = rows[-1]
        assert "TOTAL" in summary[0]
        assert "12.5" in summary[6]  # total_distance_km


class TestGPXExport:
    def test_gpx_valid_xml(self):
        result = _make_response()
        gpx_content = generate_gpx(result)
        # Remove XML declaration for parsing
        xml_content = gpx_content.split("\n", 1)[1] if gpx_content.startswith("<?xml") else gpx_content
        ET.fromstring(xml_content)

    def test_gpx_has_waypoints(self):
        result = _make_response()
        gpx_content = generate_gpx(result)
        xml_content = gpx_content.split("\n", 1)[1] if gpx_content.startswith("<?xml") else gpx_content
        root = ET.fromstring(xml_content)
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        wpts = root.findall("gpx:wpt", ns)
        assert len(wpts) == 5  # 5 waypoints (including depot at start/end)

    def test_gpx_has_track(self):
        result = _make_response()
        gpx_content = generate_gpx(result)
        xml_content = gpx_content.split("\n", 1)[1] if gpx_content.startswith("<?xml") else gpx_content
        root = ET.fromstring(xml_content)
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        trks = root.findall("gpx:trk", ns)
        assert len(trks) == 1  # 1 vehicle = 1 track

    def test_gpx_track_name(self):
        result = _make_response()
        gpx_content = generate_gpx(result)
        xml_content = gpx_content.split("\n", 1)[1] if gpx_content.startswith("<?xml") else gpx_content
        root = ET.fromstring(xml_content)
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        trk_name = root.find("gpx:trk/gpx:name", ns)
        assert trk_name.text == "Vehicle 1"

    def test_gpx_metadata(self):
        result = _make_response()
        gpx_content = generate_gpx(result)
        xml_content = gpx_content.split("\n", 1)[1] if gpx_content.startswith("<?xml") else gpx_content
        root = ET.fromstring(xml_content)
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        meta_name = root.find("gpx:metadata/gpx:name", ns)
        assert "test-job" in meta_name.text
