from io import StringIO
from pathlib import Path

import eppy
import plotly.graph_objects as go
import pytest
from eppy.modeleditor import IDF

import energytool.tools as tl

RESOURCES_PATH = Path(__file__).parent / "resources"


class TestTools:
    def test_select_by_strings(self):
        test_name_list = [
            "Zone_1:control",
            "Zone_2:control",
            "control:Zone_1",
            "control:Zone_2control",
        ]

        to_test = tl.select_in_list(target_list=test_name_list, target="*")

        assert to_test == test_name_list

        to_test = tl.select_in_list(target_list=test_name_list, target="Zone_1")

        assert to_test == ["Zone_1:control", "control:Zone_1"]

        to_test = tl.select_in_list(
            target_list=test_name_list, target=["Zone_1", "Zone_2"]
        )

        assert to_test == [
            "Zone_1:control",
            "control:Zone_1",
            "Zone_2:control",
            "control:Zone_2control",
        ]

    def test_hourly_lst_from_dict(self):
        day_config = {6: 15, 18: 19, 24: 15}

        ref = [
            15,
            15,
            15,
            15,
            15,
            15,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            19,
            15,
            15,
            15,
            15,
            15,
            15,
        ]

        to_test = tl.hourly_lst_from_dict(day_config)

        assert ref == to_test

    def test_scheduler(self):
        week_day = {6: 15, 18: 19, 24: 15}
        weekend = {24: 19}
        summer = {24: -50}

        test_scheduler = tl.Scheduler(name="test", year=2009)
        test_scheduler.add_day_in_period(
            start="2009-01-01",
            end="2009-12-31",
            days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            hourly_dict=week_day,
        )

        test_scheduler.add_day_in_period(
            start="2009-01-01",
            end="2009-12-31",
            days=["Saturday", "Sunday"],
            hourly_dict=weekend,
        )

        test_scheduler.add_day_in_period(
            start="2009-04-01",
            end="2009-09-30",
            days=[
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ],
            hourly_dict=summer,
        )

        ref = [
            15.0,
            15.0,
            15.0,
            15.0,
            15.0,
            15.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            15.0,
            15.0,
            15.0,
            15.0,
            15.0,
            15.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
            19.0,
        ]

        assert ref == list(test_scheduler.series.loc["2009-01-02":"2009-01-03"])


class FakeBuilding:
    def __init__(self, idf):
        self.idf = idf


@pytest.fixture(scope="module")
def geo_building():
    try:
        IDF.setiddname(RESOURCES_PATH / "Energy+.idd")
    except eppy.modeleditor.IDDAlreadySetError:
        pass

    idf = IDF(StringIO(""))
    idf.idfname = None

    idf.newidfobject(key="Zone", Name="ConditionedZone")
    idf.newidfobject(key="Zone", Name="UnconditionedZone")
    idf.newidfobject(
        key="ZoneControl:Thermostat",
        Zone_or_ZoneList_Name="ConditionedZone",
    )

    def add_surface(obj_type, name, vertices, **attrs):
        s = idf.newidfobject(key=obj_type, Name=name)
        for k, v in attrs.items():
            setattr(s, k, v)
        s.Number_of_Vertices = len(vertices)
        for idx, (x, y, z) in enumerate(vertices, start=1):
            setattr(s, f"Vertex_{idx}_Xcoordinate", x)
            setattr(s, f"Vertex_{idx}_Ycoordinate", y)
            setattr(s, f"Vertex_{idx}_Zcoordinate", z)
        return s

    # Simple 3 m × 3 m × 3 m box — each surface at a distinct position
    add_surface(
        "BuildingSurface:Detailed", "ExtWall",
        [(0, 0, 0), (3, 0, 0), (3, 0, 3), (0, 0, 3)],
        Surface_Type="Wall",
        Outside_Boundary_Condition="Outdoors",
        Zone_Name="ConditionedZone",
    )
    add_surface(
        "BuildingSurface:Detailed", "IntWall",
        [(0, 3, 0), (0, 3, 3), (3, 3, 3), (3, 3, 0)],
        Surface_Type="Wall",
        Outside_Boundary_Condition="Surface",
        Zone_Name="ConditionedZone",
    )
    add_surface(
        "BuildingSurface:Detailed", "Roof",
        [(0, 0, 3), (3, 0, 3), (3, 3, 3), (0, 3, 3)],
        Surface_Type="Roof",
        Outside_Boundary_Condition="Outdoors",
        Zone_Name="ConditionedZone",
    )
    add_surface(
        "BuildingSurface:Detailed", "Floor",
        [(0, 0, 0), (0, 3, 0), (3, 3, 0), (3, 0, 0)],
        Surface_Type="Floor",
        Outside_Boundary_Condition="Ground",
        Zone_Name="ConditionedZone",
    )
    add_surface(
        "BuildingSurface:Detailed", "AdiabWall",
        [(0, 0, 0), (0, 0, 3), (0, 3, 3), (0, 3, 0)],
        Surface_Type="Wall",
        Outside_Boundary_Condition="Adiabatic",
        Zone_Name="UnconditionedZone",
    )
    add_surface(
        "FenestrationSurface:Detailed", "Window1",
        [(0.5, 0, 0.5), (1.5, 0, 0.5), (1.5, 0, 2.0), (0.5, 0, 2.0)],
    )
    add_surface(
        "Shading:Zone:Detailed", "Overhang1",
        [(-0.5, 0, 2.5), (2.5, 0, 2.5), (2.5, -1, 2.5), (-0.5, -1, 2.5)],
    )

    return FakeBuilding(idf)


class TestPlotIdfGeometry:
    def test_returns_figure(self, geo_building):
        fig = tl.plot_idf_geometry(geo_building)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 13

    def test_hide_surfaces(self, geo_building):
        # Only fenestration + shading groups → 2 Mesh3d + 2 outlines
        fig = tl.plot_idf_geometry(geo_building, show_building_surfaces=False)
        assert len(fig.data) == 4
        fig = tl.plot_idf_geometry(geo_building, show_fenestration_surfaces=False)
        assert len(fig.data) == 11
        fig = tl.plot_idf_geometry(geo_building, show_shading_surfaces=False)
        assert len(fig.data) == 11

    def test_surface_type_colors(self, geo_building):
        fig = tl.plot_idf_geometry(
            geo_building,
            show_fenestration_surfaces=False,
            show_shading_surfaces=False,
        )
        color_by_name = {t.name: t.color for t in fig.data if isinstance(t, go.Mesh3d)}
        assert color_by_name["External walls"] == "lightgray"
        assert color_by_name["Internal walls"] == "khaki"
        assert color_by_name["Roofs"] == "dimgray"
        assert color_by_name["Floors"] == "gray"

    def test_zone_color_mode(self, geo_building):
        # 2 zone groups + fenestration + shading → 4 Mesh3d + 7 outlines
        fig = tl.plot_idf_geometry(geo_building, color_mode="zone")
        assert len(fig.data) == 11
        mesh_names = {t.name for t in fig.data if isinstance(t, go.Mesh3d)}
        assert "ConditionedZone" in mesh_names
        assert "UnconditionedZone (adiabatic)" in mesh_names

    def test_legend_is_interactive(self, geo_building):
        fig = tl.plot_idf_geometry(geo_building)
        mesh_traces = [t for t in fig.data if isinstance(t, go.Mesh3d)]
        assert all(t.showlegend for t in mesh_traces)
        outline_traces = [
            t for t in fig.data
            if isinstance(t, go.Scatter3d) and t.mode == "lines"
        ]
        assert all(t.legendgroup is not None for t in outline_traces)

    def test_show_names_surface_type_mode(self, geo_building):
        fig_without = tl.plot_idf_geometry(geo_building, show_names=False)
        fig_with = tl.plot_idf_geometry(geo_building, show_names=True)
        fig_with.show()
        text_without = [t for t in fig_without.data if isinstance(t, go.Scatter3d) and t.mode == "text"]
        text_with = [t for t in fig_with.data if isinstance(t, go.Scatter3d) and t.mode == "text"]
        assert len(text_without) == 0
        assert len(text_with) == 7  # one label per surface (5 building + 1 fenestration + 1 shading)

    def test_show_names_zone_mode(self, geo_building):
        fig = tl.plot_idf_geometry(geo_building, color_mode="zone", show_names=True)
        text_traces = [t for t in fig.data if isinstance(t, go.Scatter3d) and t.mode == "text"]
        assert len(text_traces) == 2  # one centroid label per zone

    def test_opacity(self, geo_building):
        fig = tl.plot_idf_geometry(geo_building, opacity=0.3)
        mesh_traces = [t for t in fig.data if isinstance(t, go.Mesh3d)]
        assert all(t.opacity == 0.3 for t in mesh_traces)


@pytest.fixture(scope="module")
def geo_building_blank_num_vertices():
    """Mimics IDF generators (e.g. Honeybee/OpenStudio) that commonly leave
    "Number of Vertices" unset, relying on EnergyPlus's own autocalculation
    rather than eppy's."""
    try:
        IDF.setiddname(RESOURCES_PATH / "Energy+.idd")
    except eppy.modeleditor.IDDAlreadySetError:
        pass

    idf = IDF(StringIO(""))
    idf.idfname = None

    idf.newidfobject(key="Zone", Name="ConditionedZone")

    def add_surface(obj_type, name, vertices, num_vertices_value, **attrs):
        s = idf.newidfobject(key=obj_type, Name=name)
        for k, v in attrs.items():
            setattr(s, k, v)
        if num_vertices_value is not None:
            s.Number_of_Vertices = num_vertices_value
        for idx, (x, y, z) in enumerate(vertices, start=1):
            setattr(s, f"Vertex_{idx}_Xcoordinate", x)
            setattr(s, f"Vertex_{idx}_Ycoordinate", y)
            setattr(s, f"Vertex_{idx}_Zcoordinate", z)
        return s

    # left at the IDD default ("autocalculate"), as when the field is never touched
    add_surface(
        "BuildingSurface:Detailed", "ExtWall",
        [(0, 0, 0), (3, 0, 0), (3, 0, 3), (0, 0, 3)],
        None,
        Surface_Type="Wall",
        Outside_Boundary_Condition="Outdoors",
        Zone_Name="ConditionedZone",
    )
    # explicitly blank, as found in some Honeybee-exported IDF text files
    add_surface(
        "Shading:Zone:Detailed", "Overhang1",
        [(-0.5, 0, 2.5), (2.5, 0, 2.5), (2.5, -1, 2.5), (-0.5, -1, 2.5)],
        "",
    )

    return FakeBuilding(idf)


class TestPlotIdfGeometryBlankNumVertices:
    def test_does_not_raise_and_infers_vertex_count(self, geo_building_blank_num_vertices):
        fig = tl.plot_idf_geometry(geo_building_blank_num_vertices)
        assert isinstance(fig, go.Figure)

        mesh_traces = [t for t in fig.data if isinstance(t, go.Mesh3d)]
        # 4 vertices per surface (wall + shading), correctly inferred despite
        # a missing/blank "Number of Vertices" field
        assert len(mesh_traces) == 2
        assert all(len(t.x) == 4 for t in mesh_traces)


@pytest.fixture(scope="module")
def geo_building_mixed_shading():
    """Honeybee/OpenStudio exports commonly represent context shading (PV
    panels, balcony railings, neighbouring building masks) as
    Shading:Building:Detailed / Shading:Site:Detailed rather than
    Shading:Zone:Detailed."""
    try:
        IDF.setiddname(RESOURCES_PATH / "Energy+.idd")
    except eppy.modeleditor.IDDAlreadySetError:
        pass

    idf = IDF(StringIO(""))
    idf.idfname = None

    def add_surface(obj_type, name, vertices):
        s = idf.newidfobject(key=obj_type, Name=name)
        s.Number_of_Vertices = len(vertices)
        for idx, (x, y, z) in enumerate(vertices, start=1):
            setattr(s, f"Vertex_{idx}_Xcoordinate", x)
            setattr(s, f"Vertex_{idx}_Ycoordinate", y)
            setattr(s, f"Vertex_{idx}_Zcoordinate", z)
        return s

    add_surface(
        "Shading:Zone:Detailed", "Overhang1",
        [(-0.5, 0, 2.5), (2.5, 0, 2.5), (2.5, -1, 2.5), (-0.5, -1, 2.5)],
    )
    add_surface(
        "Shading:Building:Detailed", "PVPanel1",
        [(0, -0.5, 1), (3, -0.5, 1), (3, -0.5, 2), (0, -0.5, 2)],
    )
    add_surface(
        "Shading:Site:Detailed", "NeighbourMask1",
        [(10, 0, 0), (10, 10, 0), (10, 10, 8), (10, 0, 8)],
    )

    return FakeBuilding(idf)


class TestPlotIdfGeometryMixedShading:
    def test_all_shading_types_are_displayed(self, geo_building_mixed_shading):
        fig = tl.plot_idf_geometry(geo_building_mixed_shading)

        shading_traces = [t for t in fig.data if isinstance(t, go.Mesh3d) and t.name == "Shading"]
        assert len(shading_traces) == 1

        names = set(shading_traces[0].text)
        assert names == {"Overhang1", "PVPanel1", "NeighbourMask1"}
        assert len(shading_traces[0].x) == 12  # 3 surfaces x 4 vertices

    def test_hide_shading_hides_all_types(self, geo_building_mixed_shading):
        fig = tl.plot_idf_geometry(geo_building_mixed_shading, show_shading_surfaces=False)
        assert not any(isinstance(t, go.Mesh3d) and t.name == "Shading" for t in fig.data)
