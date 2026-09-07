"""Tests for CSV, GPX, and KML export."""

import csv
import io
import xml.etree.ElementTree as ET

from app.models.schemas import DirectionStep, OptimizeResponse, VehicleRoute
from app.services.export import generate_csv, generate_gpx, generate_kml


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

    def test_csv_without_directions_omits_columns(self):
        result = _make_response()
        csv_content = generate_csv(result)
        reader = csv.reader(io.StringIO(csv_content))
        headers = next(reader)
        assert "arrive_maneuver" not in headers
        assert "arrive_instruction" not in headers

    def test_csv_direction_headers(self):
        result = _make_response()
        step = DirectionStep(instruction="Go left", maneuver="left", lon=-0.07, lat=51.51)
        content = generate_csv(result, {(0, 2): step})
        reader = csv.reader(io.StringIO(content))
        headers = next(reader)
        assert "arrive_maneuver" in headers
        assert "arrive_instruction" in headers

    def test_csv_direction_row_values(self):
        result = _make_response()
        step = DirectionStep(
            instruction="Turn right onto Fleet St",
            distance_m=500,
            duration_s=60,
            lon=-0.07,
            lat=51.51,
            maneuver="right",
        )
        content = generate_csv(result, {(0, 2): step})
        reader = csv.reader(io.StringIO(content))
        next(reader)  # skip header
        rows = list(reader)
        stop_row = next(r for r in rows if r[1] == "2")  # first delivery stop
        assert stop_row[9] == "right"
        assert stop_row[10] == "Turn right onto Fleet St"

    def test_csv_depot_row_has_no_direction(self):
        result = _make_response()
        step = DirectionStep(instruction="Proceed to waypoint", maneuver="depart", lon=-0.07, lat=51.51)
        content = generate_csv(result, {(0, 2): step})
        reader = csv.reader(io.StringIO(content))
        next(reader)
        rows = list(reader)
        depot_row = next(r for r in rows if r[1] == "1")
        assert depot_row[9] == ""
        assert depot_row[10] == ""


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


class TestKMLExport:
    NS = "http://www.opengis.net/kml/2.2"

    def _xml(self, content):
        body = content.split("\n", 1)[1] if content.startswith("<?xml") else content
        return ET.fromstring(body)

    def test_kml_valid_xml_and_namespace(self):
        result = _make_response()
        content = generate_kml(result)
        root = self._xml(content)
        assert root.tag == f"{{{self.NS}}}kml"

    def test_kml_has_route_and_leg_placemarks(self):
        result = _make_response()
        content = generate_kml(result)
        root = self._xml(content)
        placemarks = root.findall(f".//{{{self.NS}}}Placemark")
        # 1 vehicle route line + 4 legs
        assert len(placemarks) == 5
        assert len(root.findall(f".//{{{self.NS}}}LineString")) == 5

    def test_kml_leg_names_use_destination_label(self):
        result = _make_response()
        content = generate_kml(result)
        root = self._xml(content)
        names = [el.text for el in root.findall(f".//{{{self.NS}}}Placemark/{{{self.NS}}}name")]
        assert "Leg 1: Stop A" in names
        assert "Leg 4: Depot" in names

    def test_kml_embeds_direction_steps(self):
        result = _make_response()
        legs = {
            0: [
                {
                    "steps": [DirectionStep(instruction="Proceed to waypoint", maneuver="depart", lon=-0.12, lat=51.5)],
                    "geometry": [],
                    "source": "haversine",
                },
                {
                    "steps": [DirectionStep(instruction="Follow the road", maneuver="straight", lon=-0.08, lat=51.52)],
                    "geometry": [],
                    "source": "haversine",
                },
                {"steps": [], "geometry": [], "source": "haversine"},
                {"steps": [], "geometry": [], "source": "haversine"},
            ]
        }
        content = generate_kml(result, legs)
        root = self._xml(content)
        descriptions = [el.text or "" for el in root.findall(f".//{{{self.NS}}}Placemark/{{{self.NS}}}description")]
        assert any("Proceed to waypoint" in d for d in descriptions)
        assert any("Follow the road" in d for d in descriptions)

    def test_kml_coordinates_lon_lat_order(self):
        result = _make_response()
        legs = {
            0: [
                {"steps": [], "geometry": [[-0.12, 51.5], [-0.07, 51.51]], "source": "haversine"},
                {"steps": [], "geometry": [[-0.07, 51.51], [-0.08, 51.52]], "source": "haversine"},
                {"steps": [], "geometry": [], "source": "haversine"},
                {"steps": [], "geometry": [], "source": "haversine"},
            ]
        }
        content = generate_kml(result, legs)
        root = self._xml(content)
        coords = root.findall(f".//{{{self.NS}}}Placemark/{{{self.NS}}}LineString/{{{self.NS}}}coordinates")
        # coords[0] = full route line (concatenated, deduplicated)
        assert coords[0].text == "-0.12,51.5 -0.07,51.51 -0.08,51.52"
        # coords[1] / coords[2] = leg 1 / leg 2 line strings
        assert coords[1].text == "-0.12,51.5 -0.07,51.51"
        assert coords[2].text == "-0.07,51.51 -0.08,51.52"

    def test_kml_falls_back_to_straight_leg_coordinates(self):
        result = _make_response()
        content = generate_kml(result)
        root = self._xml(content)
        coords = root.findall(f".//{{{self.NS}}}Placemark/{{{self.NS}}}LineString/{{{self.NS}}}coordinates")
        assert coords[0].text is not None
        assert "51.5" in coords[0].text
