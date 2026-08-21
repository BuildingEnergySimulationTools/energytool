from copy import deepcopy
from io import StringIO
from pathlib import Path

import tempfile

import eppy
import pytest
from eppy.modeleditor import IDF

import energytool.base.idf_utils
from energytool.base.idf_utils import (
    get_objects_name_list,
    get_named_objects_field_values,
)
from energytool.system import HeaterSimple
from energytool.system import SystemCategories
from energytool.building import Building
from energytool.modifier import (
    set_opaque_surface_construction,
    set_external_windows,
    set_afn_surface_opening_factor,
    set_blinds_solar_transmittance,
    set_blinds_schedule,
    set_schedule_constant,
    set_system,
    set_ahu_night_ventilation,
    set_shading_geometry,
    set_shading_properties,
    set_shading_object,
    set_shade,
    set_blind,
    set_screen,
    set_complex_fenestration_state,
    update_idf_objects,
    reverse_kwargs,
)

RESOURCES_PATH = Path(__file__).parent / "resources"

try:
    IDF.setiddname(RESOURCES_PATH / "Energy+.idd")
except eppy.modeleditor.IDDAlreadySetError:
    pass

Building.set_idd(RESOURCES_PATH)


@pytest.fixture(scope="session")
def toy_building(tmp_path_factory):
    empty_idf = ""
    handle = StringIO(empty_idf)
    toy_idf = IDF(handle)
    toy_idf.idfname = None

    for toy_zone in range(4):
        toy_idf.newidfobject(key="Zone", Name=f"zone_{toy_zone}")

    # IdealLoads HVAC
    for zone in toy_idf.idfobjects["Zone"]:
        toy_idf.newidfobject(
            "ZONEHVAC:EQUIPMENTCONNECTIONS",
            Zone_Name=zone.Name,
            Zone_Conditioning_Equipment_List_Name=f"{zone.Name} Equipment",
        )
        toy_idf.newidfobject(
            "ZONEHVAC:EQUIPMENTLIST",
            Name=f"{zone.Name} Equipment",
            Zone_Equipment_1_Name=f"{zone.Name} Ideal Loads Air",
        )

        toy_idf.newidfobject(
            "ZoneHVAC:IdealLoadsAirSystem",
            Name=f"{zone.Name} Ideal Loads Air",
        )

    for _ in toy_idf.idfobjects["Zone"]:
        toy_idf.newidfobject("Lights")

    win_names = ["Ext_win_1", "Ext_win_2", "Int_win"]

    for win in win_names:
        toy_idf.newidfobject(key="WindowMaterial:SimpleGlazingSystem", Name=win)

    toy_idf.newidfobject("WindowMaterial:Shade", Name="Blinds")

    toy_idf.newidfobject(
        key="Construction",
        Name="Construction_Ext_win_1_shade",
        Outside_Layer="Blinds",
        Layer_2="Ext_win_1",
    )

    toy_idf.newidfobject(
        key="Construction",
        Name="Construction_Ext_win_1",
        Outside_Layer="Ext_win_1",
    )

    toy_idf.newidfobject(
        key="Construction",
        Name="Construction_Ext_win_2",
        Outside_Layer="Ext_win_2",
    )

    toy_idf.newidfobject(
        key="Construction",
        Name="Construction_Int_win",
        Outside_Layer="Int_win",
    )

    toy_idf.newidfobject(
        key="DESIGNSPECIFICATION:OUTDOORAIR",
        Name="zone_0_oa",
        Outdoor_Air_Method="Flow/Person",
    )

    toy_idf.newidfobject(
        key="DESIGNSPECIFICATION:OUTDOORAIR",
        Name="zone_1_oa",
        Outdoor_Air_Method="Flow/Person",
    )

    for toy_surf in range(6):
        toy_idf.newidfobject(
            "BuildingSurface:Detailed",
            Name=f"Surface_{toy_surf}",
        )

    energytool.base.idf_utils.set_named_objects_field_values(
        idf=toy_idf,
        idf_object="BuildingSurface:Detailed",
        field_name="Surface_Type",
        values=["Wall", "Wall", "Floor", "Ceiling", "Roof", "Wall"],
    )

    energytool.base.idf_utils.set_named_objects_field_values(
        idf=toy_idf,
        idf_object="BuildingSurface:Detailed",
        field_name="Outside_Boundary_Condition",
        values=["Outdoors", "Surface", "Ground", "Surface", "Outdoors", "Outdoors"],
    )

    energytool.base.idf_utils.set_named_objects_field_values(
        idf=toy_idf,
        idf_object="BuildingSurface:Detailed",
        field_name="Zone_Name",
        values=["zone_0", "Zone_1", "zone_0", "zone_2", "zone_0", "zone_3"],
    )

    for idx, sur in enumerate(["Surface_0", "Surface_1", "Surface_4", "Surface_5"]):
        toy_idf.newidfobject(
            key="FenestrationSurface:Detailed",
            Name=f"Window_{idx}",
            Building_Surface_Name=sur,
        )

    # 1 m × 1 m south-facing windows (y=5 plane), required by shading geometry tests.
    # Vertices in EnergyPlus counter-clockwise order (viewed from outside):
    #   Vertex 1 lower-left, 2 lower-right, 3 upper-right, 4 upper-left.
    # This gives: height = 1 m, width = 1 m, outward normal = (0, -1, 0).
    for window in toy_idf.idfobjects["FenestrationSurface:Detailed"]:
        window.Vertex_1_Xcoordinate = 0.0
        window.Vertex_1_Ycoordinate = 5.0
        window.Vertex_1_Zcoordinate = 0.5
        window.Vertex_2_Xcoordinate = 1.0
        window.Vertex_2_Ycoordinate = 5.0
        window.Vertex_2_Zcoordinate = 0.5
        window.Vertex_3_Xcoordinate = 1.0
        window.Vertex_3_Ycoordinate = 5.0
        window.Vertex_3_Zcoordinate = 1.5
        window.Vertex_4_Xcoordinate = 0.0
        window.Vertex_4_Ycoordinate = 5.0
        window.Vertex_4_Zcoordinate = 1.5

    energytool.base.idf_utils.set_named_objects_field_values(
        idf=toy_idf,
        idf_object="FenestrationSurface:Detailed",
        field_name="Construction_Name",
        values=[
            "Construction_Ext_win_2",
            "Construction_Int_win",
            "Construction_Ext_win_1_shade",
            "Construction_Ext_win_1",
        ],
    )

    # toy_idf.newidfobject(
    #     key="WINDOWSHADINGCONTROL",
    #     Name="zone_0_Shading_control",
    #     Zone_Name="zone_0",
    #     Shading_Type="ExteriorShade",
    #     Construction_with_Shading_Name="Construction_Ext_win_1_shade",
    #     Fenestration_Surface_1_Name="Window_1",
    # )

    toy_idf.newidfobject(
        key="WINDOWSHADINGCONTROL",
        Name="zone_0_Shading_control",
        Zone_Name="zone_0",
        Shading_Type="ExteriorShade",
        Construction_with_Shading_Name="Construction_Ext_win_2",
        Fenestration_Surface_1_Name="Window_2",
    )

    toy_idf.newidfobject(
        key="WINDOWSHADINGCONTROL",
        Name="zone_3_Shading_control",
        Zone_Name="zone_3",
        Shading_Type="ExteriorShade",
        Construction_with_Shading_Name="Construction_Ext_win_2",
        Fenestration_Surface_1_Name="Window_3",
    )

    toy_idf.newidfobject(
        key="WindowMaterial:Shade",
        Name="Blinds",
        Solar_Transmittance=0.5,
        Solar_Reflectance=0.2,
        Visible_Transmittance=0.5,
        Visible_Reflectance=0.2,
        Infrared_Hemispherical_Emissivity=0.8,
        Infrared_Transmittance=0.1,
        Thickness=0.01,
        Conductivity=0.5,
    )

    toy_idf.newidfobject(
        key="WindowShadingControl",
        Name="Control_of_blinds",
        Zone_Name="zone_1",
        Shading_Type="InteriorShade",
        Construction_with_Shading_Name="Construction_Ext_win_1_shade",
        Shading_Control_Type="OnIfScheduleAllows",
        Schedule_Name="Shading_control_winter_&_summer",
        Fenestration_Surface_1_Name="Window_1",
    )

    toy_idf.newidfobject(
        key="Schedule:Compact",
        Name="Shading_control_bis",
        Schedule_Type_Limits_Name="Fractional",
        Field_1="Through: 01 April",
        Field_2="For: AllDays",
        Field_3="Until: 24:00",
        Field_4=1.0,
        Field_5="Through:September",
        Field_6="For: AllOtherDays",
        Field_7="Until: 24:00",
        Field_8=0.0,
    )

    toy_idf.newidfobject(
        key="Schedule:Compact",
        Name="Shading_control_winter_&_summer",
        Schedule_Type_Limits_Name="Fractional",
        Field_1="Through: 01 April",
        Field_2="For: AllDays",
        Field_3="Until: 24:00",
        Field_4=0.0,
        Field_5="Through:September",
        Field_6="For: AllOtherDays",
        Field_7="Until: 24:00",
        Field_8=1.0,
    )

    toy_idf.newidfobject(
        key="ScheduleTypeLimits",
        Name="Fractional",
        Lower_Limit_Value=0,
        Upper_Limit_Value=1,
        Numeric_Type="Continuous",
    )

    toy_idf.newidfobject(
        key="AirflowNetwork:MultiZone:Surface",
        Surface_Name="Surface_0",
        Leakage_Component_Name="Airflow Network Simple Opening 8",
        WindowDoor_Opening_Factor_or_Crack_Factor=0.46,
    )

    toy_idf.newidfobject(
        key="AirflowNetwork:MultiZone:Surface",
        Surface_Name="Surface_1",
        Leakage_Component_Name="Airflow Network Simple Opening 8",
        WindowDoor_Opening_Factor_or_Crack_Factor=0.46,
    )

    # Very dirty, instantiate a Building with and idf file
    # Replace it wih toy_idf
    toy_building = Building(idf_path=RESOURCES_PATH / "test.idf")
    toy_building.idf = toy_idf

    with tempfile.NamedTemporaryFile(delete=False, suffix=".idf") as temp_file:
        temp_file_path = Path(temp_file.name)
        toy_building.idf.saveas(temp_file_path)

    return toy_building


class TestModifier:
    def test_update_idf_objects(self, toy_building):
        loc_toy = deepcopy(toy_building)

        description_update = {
            "ScheduleUpdate": {
                "Field_4": 0.5,
            }
        }

        update_idf_objects(
            model=loc_toy,
            description=description_update,
            idfobject_type="SCHEDULE:COMPACT",
            name_filter="winter",
        )

        schedule_info = loc_toy.idf.idfobjects["SCHEDULE:COMPACT"]

        assert any(
            sched.Name == "Shading_control_winter_&_summer" and sched.Field_4 == 0.5
            for sched in schedule_info
        )

    def test_set_schedule_constant(self, toy_building):
        loc_toy = deepcopy(toy_building)

        description_schedules_compact = {
            "Schedule1": {
                "Name": "Transparent_surface",
                "Schedule_Type_Limits_Name": "Fractional",
                "Hourly_Value": 1,
            },
            "Schedule2": {
                "Name": "Opaque_surface",
                "Schedule_Type_Limits_Name": "Fractional",
                "Hourly_Value": 0,
            },
        }

        set_schedule_constant(
            model=loc_toy,
            description=description_schedules_compact,
        )

        schedule_info = loc_toy.idf.idfobjects["SCHEDULE:CONSTANT"]

        assert any(
            sched.Name == "Transparent_surface" and sched.Hourly_Value == 1
            for sched in schedule_info
        )

        assert any(
            sched.Name == "Opaque_surface" and sched.Hourly_Value == 0
            for sched in schedule_info
        )

        description_update = {
            "Schedule1": {
                "Name": "Transparent_surface",
                "Schedule_Type_Limits_Name": "Fractional",
                "Hourly_Value": 0.5,
            }
        }

        set_schedule_constant(
            model=loc_toy,
            description=description_update,
        )

        assert any(
            sched.Name == "Transparent_surface" and sched.Hourly_Value == 0.5
            for sched in schedule_info
        )

    def test_set_blinds_solar_transmittance(self, toy_building):
        loc_toy = deepcopy(toy_building)

        variant_base = {"Variant_1": [{"Solar_Transmittance": 0.66}]}

        set_blinds_solar_transmittance(
            model=loc_toy, description=variant_base, name_filter="1"
        )

        shade_info = loc_toy.idf.idfobjects["WindowMaterial:Shade"]

        assert shade_info[1].fieldvalues[0:10] == [
            "WINDOWMATERIAL:SHADE",
            "Blinds",
            0.66,
            0.2,
            0.5,
            0.2,
            0.8,
            0.1,
            0.01,
            0.5,
        ]

        variant_base2 = {
            "Variant_1": [{"Solar_Transmittance": 0.66, "Solar_Reflectance": 0.12}]
        }

        set_blinds_solar_transmittance(
            model=loc_toy, description=variant_base2, name_filter="1"
        )

        assert shade_info[1].fieldvalues[0:4] == [
            "WINDOWMATERIAL:SHADE",
            "Blinds",
            0.66,
            0.12,
        ]

        variant_base3 = {"Variant_1": [{"Solar_Reflectance": 0.11}]}

        set_blinds_solar_transmittance(
            model=loc_toy, description=variant_base3, name_filter="1"
        )

        assert shade_info[1].fieldvalues[0:4] == [
            "WINDOWMATERIAL:SHADE",
            "Blinds",
            0.66,
            0.11,
        ]

    def test_set_blinds_schedule(self, toy_building):
        loc_toy = deepcopy(toy_building)

        variant_1 = {
            "Variant_1": [
                {
                    "Scenario": {
                        "Name": "Shading_control_bis",
                    },
                }
            ]
        }

        name_filter = "_2"
        set_blinds_schedule(
            model=loc_toy, description=variant_1, name_filter=name_filter
        )

        schedules = loc_toy.idf.idfobjects["WindowShadingControl"]
        for schedule in schedules:
            if name_filter in schedule.Fenestration_Surface_1_Name:
                assert schedule.Schedule_Name == "Shading_control_bis"

        variant_2 = {
            "Variant_1": [
                {
                    "Scenario": {
                        "Name": "Shading_control",
                        "Field1": "Through: 01 April",
                        "Field2": "For: AllDays",
                        "Field3": "Until: 24:00",
                        "Field4": 0.0,
                        "Field5": "Through: 30 September",
                        "Field6": "For: AllOtherDays",
                        "Field7": "Until: 24:00",
                        "Field8": 1.0,
                    },
                }
            ]
        }

        loc_toy = deepcopy(toy_building)

        set_blinds_schedule(model=loc_toy, description=variant_2, name_filter="1")

        # Check that the field values are changed
        schedule_list = loc_toy.idf.idfobjects["Schedule:Compact"]
        n = next(
            (
                index
                for index, schedule in enumerate(schedule_list)
                if schedule["Name"] == "Shading_control"
            ),
            None,
        )
        assert schedule_list[n]["Field_8"] == 1.0
        assert schedule_list[n]["Field_4"] == 0.0

        # Check that Fractional is used by Default
        assert schedule_list[n]["Schedule_Type_Limits_Name"] == "Fractional"

        variant_3 = {
            "Variant_1": [
                {
                    "Scenario": {
                        "Name": "Shading_control",
                        "Schedule_Type_Limits_Name": "Fractional1",
                        "Field1": "Through: 01 April",
                        "Field2": "For: AllDays",
                        "Field3": "Until: 24:00",
                        "Field4": 0.0,
                        "Field5": "Through: 30 September",
                        "Field6": "For: AllOtherDays",
                        "Field7": "Until: 24:00",
                        "Field8": 1.0,
                    },
                    "Limits": {
                        "Name": "Fractional1",
                        "Lower_Limit_Value": 0,
                        "Upper_Limit_Value": 1,
                        "Numeric_Type": "Continuous",
                    },
                }
            ]
        }

        loc_toy = deepcopy(toy_building)

        set_blinds_schedule(model=loc_toy, description=variant_3, name_filter="1")

        limit_list = loc_toy.idf.idfobjects["ScheduleTypeLimits"]
        # Check that Fractional1 exists
        assert any(limit["Name"] == "Fractional1" for limit in limit_list)

        # Check that original shading control has now Fractional1 as ScheduleTypeLimits
        schedule_compact_list = loc_toy.idf.idfobjects["Schedule:Compact"]
        shading_control = next(
            (
                schedule
                for schedule in schedule_compact_list
                if schedule["Name"] == "Shading_control"
            ),
            None,
        )
        assert shading_control["Schedule_Type_Limits_Name"] == "Fractional1"

    def test_opaque_surface_modifier(self, toy_building):
        loc_toy = deepcopy(toy_building)

        variant_base = {
            "test_base": [
                {
                    "Name": "Coating",
                    "Thickness": 0.01,
                    "Conductivity": 0.1,
                    "Density": 400,
                    "Specific_Heat": 1200,
                },
                {
                    "Name": "Laine_15cm",
                    "Thickness": 0.15,
                    "Conductivity": 0.032,
                    "Density": 40,
                    "Specific_Heat": 1000,
                },
            ]
        }

        variant_1 = {
            "test_1_layer": [
                {
                    "Name": "Coating_2",
                    "Thickness": 0.01,
                    "Conductivity": 0.1,
                    "Density": 400,
                    "Specific_Heat": 1200,
                },
            ],
        }

        set_opaque_surface_construction(
            model=loc_toy,
            surface_type="Wall",
            outside_boundary_condition="Outdoors",
            description=variant_base,
        )

        # Test general case
        material_list = loc_toy.idf.idfobjects["Material"]
        assert material_list[0]["obj"] == [
            "MATERIAL",
            "Coating",
            "Rough",
            0.01,
            0.1,
            400,
            1200,
            0.9,
            0.7,
            0.7,
        ]
        assert get_objects_name_list(loc_toy.idf, "Material") == [
            "Coating",
            "Laine_15cm",
        ]

        construction_list = loc_toy.idf.idfobjects["Construction"]
        assert construction_list[-1]["obj"] == [
            "CONSTRUCTION",
            "test_base",
            "Coating",
            "Laine_15cm",
        ]

        to_test = get_named_objects_field_values(
            idf=loc_toy.idf,
            idf_object="BuildingSurface:Detailed",
            field_name="Construction_Name",
        )
        assert to_test == ["test_base", "", "", "", "", "test_base"]

        # Test single layer construction
        set_opaque_surface_construction(
            model=loc_toy,
            surface_type="Wall",
            outside_boundary_condition="Outdoors",
            description=variant_1,
        )
        assert construction_list[-1]["obj"] == [
            "CONSTRUCTION",
            "test_1_layer",
            "Coating_2",
        ]

        # No duplication
        set_opaque_surface_construction(
            model=loc_toy,
            surface_type="Wall",
            outside_boundary_condition="Outdoors",
            description=variant_1,
        )
        assert energytool.base.idf_utils.get_objects_name_list(
            loc_toy.idf, "Material"
        ) == [
            "Coating",
            "Laine_15cm",
            "Coating_2",
        ]

        # Test name filter
        set_opaque_surface_construction(
            model=loc_toy,
            name_filter="_0",
            surface_type="Wall",
            outside_boundary_condition="Outdoors",
            description=variant_base,
        )

        to_test = get_named_objects_field_values(
            loc_toy.idf, "BuildingSurface:Detailed", "Construction_Name"
        )
        assert to_test == ["test_base", "", "", "", "", "test_1_layer"]

    def test_external_windows_modifier(self, toy_building):
        loc_toy = deepcopy(toy_building)
        loc_toy2 = deepcopy(toy_building)

        var_0 = {
            "Variant_1": {
                "Name": "Var_1",
                "UFactor": 1,
                "Solar_Heat_Gain_Coefficient": 0.1,
                "Visible_Transmittance": 0.1,
            },
        }

        var_1 = {
            "Variant_2": {
                "Name": "Var_2",
                "UFactor": 2,
                "Solar_Heat_Gain_Coefficient": 0.2,
                "Visible_Transmittance": 0.2,
            },
        }

        set_external_windows(loc_toy, var_0)

        assert loc_toy.idf.idfobjects["WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM"][
            -1
        ].fieldvalues == [
            "WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM",
            "Var_1",
            1,
            0.1,
            0.1,
        ]

        assert get_named_objects_field_values(
            loc_toy.idf, "Construction", "Outside_Layer"
        ) == ["Blinds", "Var_1", "Var_1", "Var_1"]

        assert get_named_objects_field_values(
            loc_toy.idf, "Construction", "Layer_2"
        ) == [
            "Var_1",
            "",
            "",
            "",
        ]

        set_external_windows(loc_toy, var_1)

        assert loc_toy.idf.idfobjects["WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM"][
            -1
        ].fieldvalues == [
            "WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM",
            "Var_2",
            2,
            0.2,
            0.2,
        ]

        assert get_named_objects_field_values(
            loc_toy.idf, "Construction", "Outside_Layer"
        ) == ["Blinds", "Var_2", "Var_2", "Var_2"]

        assert get_named_objects_field_values(
            loc_toy.idf, "Construction", "Layer_2"
        ) == [
            "Var_2",
            "",
            "",
            "",
        ]

        set_external_windows(loc_toy2, var_0, name_filter="_0")
        # test = loc_toy.idf.idfobjects["FenestrationSurface:Detailed"]
        # test2 = loc_toy.idf.idfobjects["WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM"]
        #
        # test3 = loc_toy.idf.idfobjects["CONSTRUCTION"]

        # Construction_Ext_win_2
        assert get_objects_name_list(
            loc_toy2.idf, "WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM"
        ) == ["Ext_win_1", "Int_win", "Var_1"]

        assert get_named_objects_field_values(
            loc_toy2.idf, "Construction", "Outside_Layer"
        ) == ["Blinds", "Ext_win_1", "Var_1", "Int_win"]

    def test_set_afn_surface_opening_factor(self, toy_building):
        set_afn_surface_opening_factor(
            model=toy_building,
            description={
                "opening_modif": {"WindowDoor_Opening_Factor_or_Crack_Factor": 1.0}
            },
            name_filter="_0",
        )

        afn_openings = toy_building.idf.idfobjects["AirflowNetwork:MultiZone:Surface"]
        assert [
            val.WindowDoor_Opening_Factor_or_Crack_Factor for val in afn_openings
        ] == [1.0, 0.46]

    def test_reverse_kwargs(self):
        construction_kwargs = {
            "Name": "test_construction",
            "Outside_Layer": "Layer_1",
            "Layer_2": "Layer_2",
            "Layer_3": "Layer_3",
        }

        reversed_kwargs = reverse_kwargs(construction_kwargs)

        # same number of layers
        assert reversed_kwargs == {
            "Name": "test_construction",
            "Outside_Layer": "Layer_3",
            "Layer_2": "Layer_2",
            "Layer_3": "Layer_1",
        }

        construction_kwargs = {
            "Name": "test_construction",
            "Outside_Layer": "Layer_1",
            "Layer_2": "Layer_2",
        }

        reversed_kwargs = reverse_kwargs(construction_kwargs)

        # higher number of layers
        assert reversed_kwargs == {
            "Name": "test_construction",
            "Outside_Layer": "Layer_2",
            "Layer_2": "Layer_1",
        }

        construction_kwargs = {
            "Name": "test_construction",
            "Outside_Layer": "Layer_1",
        }

        reversed_kwargs = reverse_kwargs(construction_kwargs)

        # lower number of layers
        assert reversed_kwargs == {
            "Name": "test_construction",
            "Outside_Layer": "Layer_1",
        }

    def test_set_system(self, toy_building):
        test_build = Building(idf_path=RESOURCES_PATH / "test.idf")

        # Step 1: add two heating systems manually
        heater_1 = HeaterSimple(name="simple_heater", cop=2.0)
        pac = HeaterSimple(name="PAC", cop=4.0)

        test_build.add_system(heater_1)
        test_2 = deepcopy(test_build)

        test_build.add_system(pac)

        # Check that both are present
        heating_system_names = [
            sys.name for sys in test_build.systems[SystemCategories.HEATING]
        ]
        assert "simple_heater" in heating_system_names
        assert "PAC" in heating_system_names

        # Step 2: overwrite simple_heater via set_system
        replacement_heater = HeaterSimple(name="simple_heater", cop=3.0)
        set_system(test_2, {"variant_1": replacement_heater})

        # Check that only simple_heater remains
        heating_system_names_updated = [
            sys.name for sys in test_2.systems[SystemCategories.HEATING]
        ]
        assert "simple_heater" in heating_system_names_updated
        assert "PAC" not in heating_system_names_updated

        # Optional: verify that the cop has been updated
        assert [sys.cop for sys in test_2.systems[SystemCategories.HEATING]] == [3.0]
        assert [sys.cop for sys in test_build.systems[SystemCategories.HEATING]] == [
            2.0,
            4.0,
        ]

    def test_set_ahu_night_ventilation(self, toy_building):
        set_ahu_night_ventilation(
            model=toy_building,
            description={
                "night_ventilation": {
                    "Outdoor_Air_Flow_Air_Changes_per_Hour": 4.0,
                    "Outdoor_Air_Schedule_Name": "NIGHT_VENTILATION",
                }
            },
            name_filter="zone_0",
        )

        oa_objects = toy_building.idf.idfobjects[
            "DESIGNSPECIFICATION:OUTDOORAIR"
        ]

        zone_0 = next(
            obj for obj in oa_objects
            if obj.Name == "zone_0_oa"
        )

        zone_1 = next(
            obj for obj in oa_objects
            if obj.Name == "zone_1_oa"
        )

        assert zone_0.Outdoor_Air_Method == "AirChanges/Hour"
        assert zone_0.Outdoor_Air_Flow_Air_Changes_per_Hour == 4.0
        assert zone_0.Outdoor_Air_Schedule_Name == "NIGHT_VENTILATION"
        assert zone_1.Outdoor_Air_Method == "Flow/Person"

        set_ahu_night_ventilation(
            model=toy_building,
            description={
                "night_ventilation": {
                    "Outdoor_Air_Flow_Air_Changes_per_Hour": 4.0,
                }
            },
        )

        oa_objects = toy_building.idf.idfobjects[
            "DESIGNSPECIFICATION:OUTDOORAIR"
        ]

        assert all(
            obj.Outdoor_Air_Method == "AirChanges/Hour"
            for obj in oa_objects
        )

    def test_set_shading_geometry(self, toy_building):
        # --- overhang: one surface per window ---
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "overhang", {"Depth": 0.8}, name_filter="_0")
        shading = loc.idf.idfobjects["Shading:Zone:Detailed"]
        overhang_surfaces = [s for s in shading if s.Name == "Window_0_overhang"]
        assert len(overhang_surfaces) == 1
        assert overhang_surfaces[0].Number_of_Vertices == 4
        # name_filter must exclude other windows
        assert not any(s.Name == "Window_1_overhang" for s in shading)

        # second call replaces existing surface (idempotent)
        set_shading_geometry(loc, "overhang", {"Depth": 1.0}, name_filter="_0")
        assert sum(
            1 for s in loc.idf.idfobjects["Shading:Zone:Detailed"]
            if s.Name == "Window_0_overhang"
        ) == 1

        #sidefins > left fin + right fin
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "sidefins", name_filter="_0")
        names = {s.Name for s in loc.idf.idfobjects["Shading:Zone:Detailed"]}
        assert "Window_0_left_fin" in names
        assert "Window_0_right_fin" in names

        # only right fin when Left=False
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "sidefins", {"Left": False}, name_filter="_0")
        names = {s.Name for s in loc.idf.idfobjects["Shading:Zone:Detailed"]}
        assert "Window_0_left_fin" not in names
        assert "Window_0_right_fin" in names

        # --- horizontal_louvers ---
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "horizontal_louvers", name_filter="_0")
        louvers = [
            s for s in loc.idf.idfobjects["Shading:Zone:Detailed"]
            if "Window_0_horizontal_louver" in s.Name
        ]
        assert len(louvers) == 5
        assert all(s.Number_of_Vertices == 4 for s in louvers)

        # --- vertical_louvers ---
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "vertical_louvers", name_filter="_0")
        louvers = [
            s for s in loc.idf.idfobjects["Shading:Zone:Detailed"]
            if "Window_0_vertical_louver" in s.Name
        ]
        assert len(louvers) == 4
        assert all(s.Number_of_Vertices == 4 for s in louvers)

        # --- list name_filter: Window_0 and Window_1 ---
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "overhang", name_filter=["_0", "_1"])
        overhangs = [s for s in loc.idf.idfobjects["Shading:Zone:Detailed"] if "overhang" in s.Name]
        assert {s.Name for s in overhangs} == {"Window_0_overhang", "Window_1_overhang"}

        # --- invalid type raises ValueError ---
        with pytest.raises(ValueError):
            set_shading_geometry(deepcopy(toy_building), "invalid_type")

        # --- horizontal_louvers: non-uniform Positions/Tilts override Spacing/Tilt ---
        loc = deepcopy(toy_building)
        set_shading_geometry(
            loc,
            "horizontal_louvers",
            {"Positions": [0.0, 0.5, 1.0], "Tilts": [0, 30, 45]},
            name_filter="_0",
        )
        louvers = {
            s.Name: s
            for s in loc.idf.idfobjects["Shading:Zone:Detailed"]
            if "Window_0_horizontal_louver" in s.Name
        }
        assert len(louvers) == 3
        # z_offset=0 -> top edge unchanged (z = 1.5)
        assert louvers["Window_0_horizontal_louver_0"].Vertex_1_Zcoordinate == pytest.approx(1.5)
        # z_offset=1.0 -> shifted down to the bottom edge (z = 0.5)
        assert louvers["Window_0_horizontal_louver_2"].Vertex_1_Zcoordinate == pytest.approx(0.5)

        # a scalar Tilts value applies to every louver
        loc = deepcopy(toy_building)
        set_shading_geometry(
            loc,
            "horizontal_louvers",
            {"Positions": [0.0, 0.5], "Tilts": 30},
            name_filter="_0",
        )
        louvers = [
            s for s in loc.idf.idfobjects["Shading:Zone:Detailed"]
            if "Window_0_horizontal_louver" in s.Name
        ]
        assert len(louvers) == 2

        # --- vertical_louvers: non-uniform Positions override Spacing ---
        loc = deepcopy(toy_building)
        set_shading_geometry(
            loc,
            "vertical_louvers",
            {"Positions": [0.1, 0.5, 0.9]},
            name_filter="_0",
        )
        louvers = [
            s for s in loc.idf.idfobjects["Shading:Zone:Detailed"]
            if "Window_0_vertical_louver" in s.Name
        ]
        assert len(louvers) == 3

        # --- eggcrate: crossed horizontal + vertical louvers, default params ---
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "eggcrate", name_filter="_0")
        shading = loc.idf.idfobjects["Shading:Zone:Detailed"]
        h_louvers = [s for s in shading if "Window_0_eggcrate_h" in s.Name]
        v_louvers = [s for s in shading if "Window_0_eggcrate_v" in s.Name]
        assert len(h_louvers) == 5  # same default spacing as horizontal_louvers
        assert len(v_louvers) == 4  # same default spacing as vertical_louvers
        assert not any(s.Name.startswith("Window_1_eggcrate") for s in shading)

        # replacing an eggcrate removes the previous grid (idempotent)
        set_shading_geometry(
            loc, "eggcrate", {"Spacing_H": 0.5, "Spacing_V": 0.5}, name_filter="_0"
        )
        shading = loc.idf.idfobjects["Shading:Zone:Detailed"]
        h_louvers = [s for s in shading if "Window_0_eggcrate_h" in s.Name]
        v_louvers = [s for s in shading if "Window_0_eggcrate_v" in s.Name]
        assert len(h_louvers) == 3  # arange(0, 1+1e-6, 0.5) -> 0, 0.5, 1.0
        assert len(v_louvers) == 3  # margin=0 -> arange(0, 1+1e-6, 0.5) -> 0, 0.5, 1.0

        # independent H/V depths and per-direction non-uniform positions
        loc = deepcopy(toy_building)
        set_shading_geometry(
            loc,
            "eggcrate",
            {
                "Depth_H": 0.3,
                "Depth_V": 0.6,
                "Positions_H": [0.0, 1.0],
                "Positions_V": [0.2, 0.8],
            },
            name_filter="_0",
        )
        shading = loc.idf.idfobjects["Shading:Zone:Detailed"]
        h_louvers = [s for s in shading if "Window_0_eggcrate_h" in s.Name]
        v_louvers = [s for s in shading if "Window_0_eggcrate_v" in s.Name]
        assert len(h_louvers) == 2
        assert len(v_louvers) == 2

    def test_set_shading_properties(self, toy_building):
        # setup: one overhang on Window_0
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "overhang", name_filter="_0")

        # default properties
        set_shading_properties(loc)
        refl_objs = loc.idf.idfobjects["SHADINGPROPERTY:REFLECTANCE"]
        assert len(refl_objs) == 1
        refl = refl_objs[0]
        assert refl.Shading_Surface_Name == "Window_0_overhang"
        assert refl.Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.2)
        assert refl.Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.2)
        assert refl.Fraction_of_Shading_Surface_That_Is_Glazed == pytest.approx(0.0)

        # custom reflectances
        loc2 = deepcopy(toy_building)
        set_shading_geometry(loc2, "overhang", name_filter="_0")
        set_shading_properties(loc2, description={
            "Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.6,
            "Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.55,
        })
        refl = loc2.idf.idfobjects["SHADINGPROPERTY:REFLECTANCE"][0]
        assert refl.Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.6)
        assert refl.Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.55)

        # Transmittance: creates a Schedule:Constant and assigns it
        loc3 = deepcopy(toy_building)
        set_shading_geometry(loc3, "overhang", name_filter="_0")
        set_shading_properties(loc3, description={"Transmittance": 0.3})
        shading_obj = loc3.idf.idfobjects["SHADING:ZONE:DETAILED"][0]
        sched_name = shading_obj.Transmittance_Schedule_Name
        assert sched_name != ""
        consts = loc3.idf.idfobjects["SCHEDULE:CONSTANT"]
        assert any(s.Name == sched_name and s.Hourly_Value == pytest.approx(0.3) for s in consts)

        # Transmittance_Schedule: assign existing schedule name directly
        loc4 = deepcopy(toy_building)
        set_shading_geometry(loc4, "overhang", name_filter="_0")
        set_shading_properties(loc4, description={"Transmittance_Schedule": "Shading_control_bis"})
        shading_obj = loc4.idf.idfobjects["SHADING:ZONE:DETAILED"][0]
        assert shading_obj.Transmittance_Schedule_Name == "Shading_control_bis"

        # name_filter: 4 overhangs created, properties applied only to Window_0
        loc5 = deepcopy(toy_building)
        set_shading_geometry(loc5, "overhang")  # all windows
        set_shading_properties(loc5, name_filter="Window_0")
        refl_objs = loc5.idf.idfobjects["SHADINGPROPERTY:REFLECTANCE"]
        assert len(refl_objs) == 1
        assert refl_objs[0].Shading_Surface_Name == "Window_0_overhang"

        # list name_filter
        loc6 = deepcopy(toy_building)
        set_shading_geometry(loc6, "overhang")
        set_shading_properties(loc6, name_filter=["Window_0", "Window_1"])
        refl_names = {r.Shading_Surface_Name for r in loc6.idf.idfobjects["SHADINGPROPERTY:REFLECTANCE"]}
        assert refl_names == {"Window_0_overhang", "Window_1_overhang"}

    def test_set_shading_object(self, toy_building):
        # geometry only
        loc = deepcopy(toy_building)
        set_shading_object(loc, geometry={"Type": "overhang", "Depth": 0.6}, name_filter="_0")
        shading = loc.idf.idfobjects["Shading:Zone:Detailed"]
        assert any(s.Name == "Window_0_overhang" for s in shading)
        assert not any(s.Name == "Window_1_overhang" for s in shading)

        # properties only with preset "light_concrete"
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "overhang", name_filter="_0")
        set_shading_object(loc, properties={"Preset": "light_concrete"}, name_filter="_0")
        refl = loc.idf.idfobjects["SHADINGPROPERTY:REFLECTANCE"][0]
        assert refl.Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.60)
        assert refl.Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.60)

        # preset "dark_metal" with solar reflectance override
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "overhang", name_filter="_0")
        set_shading_object(
            loc,
            properties={
                "Preset": "dark_metal",
                "Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface": 0.25,
            },
            name_filter="_0",
        )
        refl = loc.idf.idfobjects["SHADINGPROPERTY:REFLECTANCE"][0]
        # override takes precedence
        assert refl.Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.25)
        # visible from preset (dark_metal = 0.15)
        assert refl.Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.15)

        # combined geometry + properties ("vegetation" preset)
        loc = deepcopy(toy_building)
        set_shading_object(
            loc,
            geometry={"Type": "sidefins"},
            properties={"Preset": "vegetation"},
            name_filter="_0",
        )
        shading = loc.idf.idfobjects["Shading:Zone:Detailed"]
        assert any(s.Name == "Window_0_left_fin" for s in shading)
        refl_objs = loc.idf.idfobjects["SHADINGPROPERTY:REFLECTANCE"]
        assert len(refl_objs) >= 1
        for r in refl_objs:
            assert r.Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.25)
            assert r.Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.15)

        # preset "pv_panel"
        loc = deepcopy(toy_building)
        set_shading_geometry(loc, "overhang", name_filter="_0")
        set_shading_object(loc, properties={"Preset": "pv_panel"}, name_filter="_0")
        refl = loc.idf.idfobjects["SHADINGPROPERTY:REFLECTANCE"][0]
        assert refl.Diffuse_Solar_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.05)
        assert refl.Diffuse_Visible_Reflectance_of_Unglazed_Part_of_Shading_Surface == pytest.approx(0.05)

    def test_set_shade(self, toy_building):
        # default shade applied to Window_0 only
        loc = deepcopy(toy_building)
        set_shade(loc, name_filter="_0")

        shades = loc.idf.idfobjects["WINDOWMATERIAL:SHADE"]
        default_shade = next((s for s in shades if s.Name == "DEFAULT_SHADE"), None)
        assert default_shade is not None
        assert default_shade.Solar_Transmittance == pytest.approx(0.10)
        assert default_shade.Solar_Reflectance == pytest.approx(0.70)
        assert default_shade.Visible_Transmittance == pytest.approx(0.10)

        assert "DEFAULT_SHADE_CONSTRUCTION" in {c.Name for c in loc.idf.idfobjects["CONSTRUCTION"]}

        controls = loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
        ctrl = next((c for c in controls if c.Name == "Window_0_DEFAULT_SHADE_control"), None)
        assert ctrl is not None
        assert ctrl.Shading_Type == "InteriorShade"
        assert ctrl.Construction_with_Shading_Name == "DEFAULT_SHADE_CONSTRUCTION"
        assert ctrl.Shading_Control_Type == "OnIfScheduleAllows"
        # Window_1 excluded by name_filter
        assert not any(c.Name == "Window_1_DEFAULT_SHADE_control" for c in controls)

        # custom: ExteriorShade, lower transmittance, with schedule
        loc = deepcopy(toy_building)
        set_shade(
            loc,
            description={
                "Name": "MY_SHADE",
                "Solar_Transmittance": 0.05,
                "Shading_Type": "ExteriorShade",
                "Schedule": "Shading_control_bis",
            },
            name_filter="_0",
        )
        shade = next(s for s in loc.idf.idfobjects["WINDOWMATERIAL:SHADE"] if s.Name == "MY_SHADE")
        assert shade.Solar_Transmittance == pytest.approx(0.05)
        ctrl = next(
            c for c in loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
            if c.Name == "Window_0_MY_SHADE_control"
        )
        assert ctrl.Shading_Type == "ExteriorShade"
        assert ctrl.Schedule_Name == "Shading_control_bis"

        # second call with same name reuses material, does not duplicate it
        loc = deepcopy(toy_building)
        set_shade(loc)
        set_shade(loc)
        assert sum(1 for s in loc.idf.idfobjects["WINDOWMATERIAL:SHADE"] if s.Name == "DEFAULT_SHADE") == 1

        # list name_filter: Window_0 and Window_1
        loc = deepcopy(toy_building)
        set_shade(loc, name_filter=["_0", "_1"])
        controls = loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
        assert any(c.Name == "Window_0_DEFAULT_SHADE_control" for c in controls)
        assert any(c.Name == "Window_1_DEFAULT_SHADE_control" for c in controls)
        assert not any(c.Name == "Window_2_DEFAULT_SHADE_control" for c in controls)

    def test_set_blind(self, toy_building):
        # default blind on Window_0 only
        loc = deepcopy(toy_building)
        set_blind(loc, name_filter="_0")

        blinds = loc.idf.idfobjects["WINDOWMATERIAL:BLIND"]
        default_blind = next((b for b in blinds if b.Name == "DEFAULT_BLIND"), None)
        assert default_blind is not None
        assert default_blind.Slat_Width == pytest.approx(0.08)
        assert default_blind.Slat_Angle == pytest.approx(45)
        assert default_blind.Slat_Separation == pytest.approx(0.07)

        assert "DEFAULT_BLIND_CONSTRUCTION" in {c.Name for c in loc.idf.idfobjects["CONSTRUCTION"]}

        controls = loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
        ctrl = next((c for c in controls if c.Name == "Window_0_DEFAULT_BLIND_control"), None)
        assert ctrl is not None
        assert ctrl.Shading_Type == "ExteriorBlind"  # default Shading_Type
        assert ctrl.Construction_with_Shading_Name == "DEFAULT_BLIND_CONSTRUCTION"
        assert ctrl.Shading_Control_Type == "OnIfScheduleAllows"
        assert not any(c.Name == "Window_1_DEFAULT_BLIND_control" for c in controls)

        # preset "venetian_indoor": InteriorBlind, Slat_Angle=45, reflectance=0.7
        loc = deepcopy(toy_building)
        set_blind(loc, description={"Preset": "venetian_indoor", "Name": "VENETIAN"}, name_filter="_0")
        blind = next(b for b in loc.idf.idfobjects["WINDOWMATERIAL:BLIND"] if b.Name == "VENETIAN")
        assert blind.Slat_Angle == pytest.approx(45)
        assert blind.Front_Side_Slat_Beam_Solar_Reflectance == pytest.approx(0.7)
        ctrl = next(
            c for c in loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
            if c.Name == "Window_0_VENETIAN_control"
        )
        assert ctrl.Shading_Type == "InteriorBlind"

        # preset "bso_exterior": ExteriorBlind, Slat_Angle=60, reflectance=0.8
        loc = deepcopy(toy_building)
        set_blind(loc, description={"Preset": "bso_exterior", "Name": "BSO"}, name_filter="_0")
        blind = next(b for b in loc.idf.idfobjects["WINDOWMATERIAL:BLIND"] if b.Name == "BSO")
        assert blind.Slat_Angle == pytest.approx(60)
        assert blind.Front_Side_Slat_Beam_Solar_Reflectance == pytest.approx(0.8)
        ctrl = next(
            c for c in loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
            if c.Name == "Window_0_BSO_control"
        )
        assert ctrl.Shading_Type == "ExteriorBlind"

        # preset "micro_louver": BetweenGlassBlind, Slat_Angle=75, Slat_Separation=0.01
        loc = deepcopy(toy_building)
        set_blind(loc, description={"Preset": "micro_louver", "Name": "MICRO"}, name_filter="_0")
        blind = next(b for b in loc.idf.idfobjects["WINDOWMATERIAL:BLIND"] if b.Name == "MICRO")
        assert blind.Slat_Angle == pytest.approx(75)
        assert blind.Slat_Separation == pytest.approx(0.01)
        ctrl = next(
            c for c in loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
            if c.Name == "Window_0_MICRO_control"
        )
        assert ctrl.Shading_Type == "BetweenGlassBlind"

        # second call with same name reuses material, does not duplicate it
        loc = deepcopy(toy_building)
        set_blind(loc, name_filter="_0")
        set_blind(loc, name_filter="_0")
        assert sum(1 for b in loc.idf.idfobjects["WINDOWMATERIAL:BLIND"] if b.Name == "DEFAULT_BLIND") == 1

        # list name_filter: Window_0 and Window_1 only
        loc = deepcopy(toy_building)
        set_blind(loc, name_filter=["_0", "_1"])
        controls = loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
        assert any(c.Name == "Window_0_DEFAULT_BLIND_control" for c in controls)
        assert any(c.Name == "Window_1_DEFAULT_BLIND_control" for c in controls)
        assert not any(c.Name == "Window_2_DEFAULT_BLIND_control" for c in controls)

    def test_set_screen(self, toy_building):
        # default screen on Window_0 only: diameter derived from
        # Perforation_Ratio (0.30) and Pitch (0.01)
        loc = deepcopy(toy_building)
        set_screen(loc, name_filter="_0")

        screens = loc.idf.idfobjects["WINDOWMATERIAL:SCREEN"]
        default_screen = next((s for s in screens if s.Name == "DEFAULT_SCREEN"), None)
        assert default_screen is not None
        assert default_screen.Screen_Material_Spacing == pytest.approx(0.01)
        assert default_screen.Screen_Material_Diameter == pytest.approx(
            0.01 * (1 - 0.30 ** 0.5)
        )
        assert default_screen.Reflected_Beam_Transmittance_Accounting_Method == "ModelAsDiffuse"

        assert "DEFAULT_SCREEN_CONSTRUCTION" in {c.Name for c in loc.idf.idfobjects["CONSTRUCTION"]}

        controls = loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
        ctrl = next((c for c in controls if c.Name == "Window_0_DEFAULT_SCREEN_control"), None)
        assert ctrl is not None
        assert ctrl.Shading_Type == "ExteriorScreen"
        assert ctrl.Construction_with_Shading_Name == "DEFAULT_SCREEN_CONSTRUCTION"
        assert ctrl.Shading_Control_Type == "OnIfScheduleAllows"
        assert not any(c.Name == "Window_1_DEFAULT_SCREEN_control" for c in controls)

        # explicit native fields override the Perforation_Ratio/Pitch derivation
        loc = deepcopy(toy_building)
        set_screen(
            loc,
            description={
                "Name": "PERFORATED_PANEL",
                "Screen_Material_Spacing": 0.02,
                "Screen_Material_Diameter": 0.015,
                "Diffuse_Solar_Reflectance": 0.55,
                "Schedule": "Shading_control_bis",
            },
            name_filter="_0",
        )
        screen = next(s for s in loc.idf.idfobjects["WINDOWMATERIAL:SCREEN"] if s.Name == "PERFORATED_PANEL")
        assert screen.Screen_Material_Spacing == pytest.approx(0.02)
        assert screen.Screen_Material_Diameter == pytest.approx(0.015)
        assert screen.Diffuse_Solar_Reflectance == pytest.approx(0.55)
        ctrl = next(
            c for c in loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
            if c.Name == "Window_0_PERFORATED_PANEL_control"
        )
        assert ctrl.Schedule_Name == "Shading_control_bis"

        # second call with same name reuses material, does not duplicate it
        loc = deepcopy(toy_building)
        set_screen(loc)
        set_screen(loc)
        assert sum(1 for s in loc.idf.idfobjects["WINDOWMATERIAL:SCREEN"] if s.Name == "DEFAULT_SCREEN") == 1

        # list name_filter: Window_0 and Window_1 only
        loc = deepcopy(toy_building)
        set_screen(loc, name_filter=["_0", "_1"])
        controls = loc.idf.idfobjects["WINDOWSHADINGCONTROL"]
        assert any(c.Name == "Window_0_DEFAULT_SCREEN_control" for c in controls)
        assert any(c.Name == "Window_1_DEFAULT_SCREEN_control" for c in controls)
        assert not any(c.Name == "Window_2_DEFAULT_SCREEN_control" for c in controls)

    def test_set_complex_fenestration_state(self, toy_building, tmp_path):
        # one small matrix file per required BSDF matrix (2x2, arbitrary values)
        matrix_keys = [
            "Basis_Matrix",
            "Solar_Front_Transmittance",
            "Solar_Back_Reflectance",
            "Visible_Front_Transmittance",
            "Visible_Back_Transmittance",
            "Outside_Layer_Front_Absorptance",
            "Outside_Layer_Back_Absorptance",
        ]
        matrix_paths = {}
        for i, key in enumerate(matrix_keys):
            path = tmp_path / f"{key}.txt"
            path.write_text(f"{i}.0 {i}.1\n{i}.2 {i}.3\n")
            matrix_paths[key] = str(path)

        loc = deepcopy(toy_building)
        description = {
            "Name": "BSDF_TEST",
            "Outside_Layer_Name": "Ext_win_1",
            **matrix_paths,
        }

        set_complex_fenestration_state(loc, description, name_filter="Window_0")

        # one Matrix:TwoDimension per matrix key, correctly sized/filled
        matrices = {m.Name: m for m in loc.idf.idfobjects["MATRIX:TWODIMENSION"]}
        basis_matrix = matrices["BSDF_TEST_Basis_Matrix"]
        assert basis_matrix.Number_of_Rows == 2
        assert basis_matrix.Number_of_Columns == 2
        assert basis_matrix.Value_1 == pytest.approx(0.0)
        assert basis_matrix.Value_4 == pytest.approx(0.3)
        assert len(matrices) == len(matrix_keys)

        # a default ISO15099 thermal model is created
        thermal_models = loc.idf.idfobjects["WINDOWTHERMALMODEL:PARAMS"]
        default_model = next(
            (m for m in thermal_models if m.Name == "Default_CFS_Thermal_Model"), None
        )
        assert default_model is not None
        assert default_model.standard == "ISO15099"

        # the Construction:ComplexFenestrationState references the matrices
        cfs = loc.idf.idfobjects["CONSTRUCTION:COMPLEXFENESTRATIONSTATE"]
        state = next(c for c in cfs if c.Name == "BSDF_TEST")
        assert state.Basis_Matrix_Name == "BSDF_TEST_Basis_Matrix"
        assert state.Outside_Layer_Name == "Ext_win_1"
        assert state.Window_Thermal_Model == "Default_CFS_Thermal_Model"

        # only Window_0 is reassigned to the new construction
        windows = {w.Name: w for w in loc.idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]}
        assert windows["Window_0"].Construction_Name == "BSDF_TEST"
        assert windows["Window_1"].Construction_Name != "BSDF_TEST"

        # missing a required matrix key raises ValueError
        incomplete = {k: v for k, v in description.items() if k != "Solar_Front_Transmittance"}
        with pytest.raises(ValueError):
            set_complex_fenestration_state(deepcopy(toy_building), incomplete)

        # missing Outside_Layer_Name raises ValueError
        no_layer = {k: v for k, v in description.items() if k != "Outside_Layer_Name"}
        with pytest.raises(ValueError):
            set_complex_fenestration_state(deepcopy(toy_building), no_layer)

        # an explicit, existing Window_Thermal_Model name is reused as-is
        loc2 = deepcopy(toy_building)
        loc2.idf.newidfobject(
            "WindowThermalModel:Params", Name="MyThermalModel", standard="EN673Design"
        )
        set_complex_fenestration_state(
            loc2,
            {**description, "Window_Thermal_Model": "MyThermalModel"},
            name_filter="Window_0",
        )
        state2 = next(
            c for c in loc2.idf.idfobjects["CONSTRUCTION:COMPLEXFENESTRATIONSTATE"]
            if c.Name == "BSDF_TEST"
        )
        assert state2.Window_Thermal_Model == "MyThermalModel"

    def _write_bsdf_fragment(
        self,
        path,
        cfs_name="TestCFS",
        glazing_name="TestGlazing",
        glazing_transmittance=0.6,
        gas_name="TestGas",
        n_states=1,
    ):
        """
        Build a minimal but structurally realistic "WINDOW export to
        EnergyPlus (BSDF)" fragment: a glazing + a complex shade + a gas gap
        + a thermal model + a couple of small Matrix:TwoDimension objects,
        tied together by a Construction:ComplexFenestrationState - the same
        object types/relationships a real WINDOW export produces, just with
        tiny 2x2 matrices instead of a real 145x145 Klems basis.
        """
        frag = IDF(StringIO(""))
        frag.idfname = None

        frag.newidfobject(
            "WindowMaterial:Glazing",
            Name=glazing_name,
            Optical_Data_Type="BSDF",
            Solar_Transmittance_at_Normal_Incidence=glazing_transmittance,
            Thickness=0.006,
        )
        frag.newidfobject("WindowMaterial:ComplexShade", Name="TestShade")
        frag.newidfobject("WindowMaterial:Gas", Name=gas_name, Gas_Type="Air", Thickness=0.012)
        frag.newidfobject("WindowMaterial:Gap", Name="TestGap", Thickness=0.012, Gas_or_Gas_Mixture="1")
        frag.newidfobject(
            "WindowThermalModel:Params", Name="TestThermalModel", standard="ISO15099"
        )

        for i in range(n_states):
            suffix = "" if i == 0 else f"_{i}"
            matrix_names = {}
            for key in [
                "Basis", "TfSol", "RbSol", "Tfvis", "Rbvis", "fAbs", "bAbs",
            ]:
                mname = f"{cfs_name}{suffix}_{key}"
                frag.newidfobject(
                    "Matrix:TwoDimension",
                    Name=mname,
                    Number_of_Rows=2,
                    Number_of_Columns=2,
                    Value_1=0.1, Value_2=0.2, Value_3=0.3, Value_4=0.4,
                )
                matrix_names[key] = mname

            frag.newidfobject(
                "Construction:ComplexFenestrationState",
                Name=f"{cfs_name}{suffix}",
                Basis_Type="LBNLWINDOW",
                Basis_Symmetry_Type="None",
                Window_Thermal_Model="TestThermalModel",
                Basis_Matrix_Name=matrix_names["Basis"],
                Solar_Optical_Complex_Front_Transmittance_Matrix_Name=matrix_names["TfSol"],
                Solar_Optical_Complex_Back_Reflectance_Matrix_Name=matrix_names["RbSol"],
                Visible_Optical_Complex_Front_Transmittance_Matrix_Name=matrix_names["Tfvis"],
                Visible_Optical_Complex_Back_Transmittance_Matrix_Name=matrix_names["Rbvis"],
                Outside_Layer_Name="TestShade",
                Outside_Layer_Directional_Front_Absoptance_Matrix_Name=matrix_names["fAbs"],
                Outside_Layer_Directional_Back_Absoptance_Matrix_Name=matrix_names["bAbs"],
                Gap_1_Name="TestGap",
                Layer_2_Name=glazing_name,
            )

        frag.saveas(str(path))
        return path

    def test_set_complex_fenestration_state_requires_one_input(self, toy_building):
        loc = deepcopy(toy_building)
        with pytest.raises(ValueError):
            set_complex_fenestration_state(loc)
        with pytest.raises(ValueError):
            set_complex_fenestration_state(
                loc, description={"Name": "X"}, idf_fragment_path="whatever.idf"
            )

    def test_set_complex_fenestration_state_from_idf_fragment(self, toy_building, tmp_path):
        # a fragment with zero or several states is rejected
        empty_path = tmp_path / "empty.idf"
        IDF(StringIO("")).saveas(str(empty_path))
        with pytest.raises(ValueError):
            set_complex_fenestration_state(
                deepcopy(toy_building), idf_fragment_path=str(empty_path)
            )

        two_states_path = self._write_bsdf_fragment(
            tmp_path / "two_states.idf", cfs_name="TwoStates", n_states=2
        )
        with pytest.raises(ValueError):
            set_complex_fenestration_state(
                deepcopy(toy_building), idf_fragment_path=str(two_states_path)
            )

        # basic import: objects copied, window(s) reassigned
        frag_path = self._write_bsdf_fragment(tmp_path / "frag.idf")
        loc = deepcopy(toy_building)
        state_name = set_complex_fenestration_state(
            loc, idf_fragment_path=str(frag_path), name_filter="Window_0"
        )
        assert state_name == "TestCFS"
        assert {o.Name for o in loc.idf.idfobjects["WINDOWMATERIAL:GLAZING"]} == {"TestGlazing"}
        assert {o.Name for o in loc.idf.idfobjects["WINDOWMATERIAL:COMPLEXSHADE"]} == {"TestShade"}
        assert len(loc.idf.idfobjects["MATRIX:TWODIMENSION"]) == 7
        windows = {w.Name: w for w in loc.idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]}
        assert windows["Window_0"].Construction_Name == "TestCFS"
        assert windows["Window_1"].Construction_Name != "TestCFS"

        # re-importing the identical fragment is idempotent (no duplicates)
        state_name_2 = set_complex_fenestration_state(
            loc, idf_fragment_path=str(frag_path), name_filter="Window_0"
        )
        assert state_name_2 == "TestCFS"
        assert len(loc.idf.idfobjects["CONSTRUCTION:COMPLEXFENESTRATIONSTATE"]) == 1
        assert len(loc.idf.idfobjects["MATRIX:TWODIMENSION"]) == 7

        # a sub-object that already exists with IDENTICAL values is reused,
        # not duplicated, across two otherwise-different fragments
        frag_path_2 = self._write_bsdf_fragment(
            tmp_path / "frag2.idf", cfs_name="OtherCFS", glazing_name="TestGlazing",
            glazing_transmittance=0.6,  # same value as frag_path's glazing
        )
        set_complex_fenestration_state(loc, idf_fragment_path=str(frag_path_2))
        assert {o.Name for o in loc.idf.idfobjects["WINDOWMATERIAL:GLAZING"]} == {"TestGlazing"}
        assert len(loc.idf.idfobjects["CONSTRUCTION:COMPLEXFENESTRATIONSTATE"]) == 2

        # a genuine collision (same glazing name, different value) is
        # auto-renamed, and the rename propagates to whatever references it
        frag_path_3 = self._write_bsdf_fragment(
            tmp_path / "frag3.idf", cfs_name="ThirdCFS", glazing_name="TestGlazing",
            glazing_transmittance=0.15,  # different value -> forces a rename
        )
        set_complex_fenestration_state(loc, idf_fragment_path=str(frag_path_3))
        glazing_names = {o.Name for o in loc.idf.idfobjects["WINDOWMATERIAL:GLAZING"]}
        assert glazing_names == {"TestGlazing", "TestGlazing_2"}
        renamed_glazing = loc.idf.getobject("WindowMaterial:Glazing", "TestGlazing_2")
        assert renamed_glazing.Solar_Transmittance_at_Normal_Incidence == pytest.approx(0.15)
        third_cfs = loc.idf.getobject("Construction:ComplexFenestrationState", "ThirdCFS")
        assert third_cfs.Layer_2_Name == "TestGlazing_2"
        # the original, untouched by the collision
        original_glazing = loc.idf.getobject("WindowMaterial:Glazing", "TestGlazing")
        assert original_glazing.Solar_Transmittance_at_Normal_Incidence == pytest.approx(0.6)

    # def test_envelope_shades_modifier(self, toy_building):
    #     loc_toy = deepcopy(toy_building)
    #
    #     test_variant_dict = {
    #         "Variant_1": {
    #             "shading": {"Name": "Shading", "Solar_Transmittance": 0.3},
    #         },
    #         "Variant_2": {"shading": {}},
    #     }
    #
    #     mod = EnvelopeShadesModifier(
    #         building=loc_toy, name="test", variant_dict=test_variant_dict
    #     )
    #
    #     mod.set_variant("Variant_1")
    #     assert [n.Name for n in mod.windows] == ["Window_0", "Window_2", "Window_3"]
    #
    #     for n in mod.window_constructions:
    #         assert n.Name in ["Construction_Ext_win_2", "Construction_Ext_win_1"]
    #
    #     for n in mod.shaded_window_constructions:
    #         assert n.Name in [
    #             "Construction_Ext_win_1_shaded",
    #             "Construction_Ext_win_2_shaded",
    #         ]
    #
    #     test_cons = mod.building.idf.getobject(
    #         "Construction", "Construction_Ext_win_2_shaded"
    #     )
    #     assert test_cons.obj == [
    #         "CONSTRUCTION",
    #         "Construction_Ext_win_2_shaded",
    #         "Shading",
    #         "Ext_win_2",
    #     ]
    #
    #     assert len(mod.shading_materials) == 1
    #     assert mod.shading_materials[0].obj == [
    #         "WINDOWMATERIAL:SHADE",
    #         "Shading",
    #         0.3,
    #         0.5,
    #         0.4,
    #         0.5,
    #         0.9,
    #         0.0,
    #         0.003,
    #         0.1,
    #         0.05,
    #         1.0,
    #         0.0,
    #         0.0,
    #         0.0,
    #         0.0,
    #     ]
    #     assert len(mod.shading_control) == 3
    #     assert mod.shading_control[0].obj == [
    #         "WINDOWSHADINGCONTROL",
    #         "zone_0_Construction_Ext_win_2_Shading_control",
    #         "zone_0",
    #         "",
    #         "ExteriorShade",
    #         "Construction_Ext_win_2_shaded",
    #         "OnIfScheduleAllows",
    #         "",
    #         "",
    #         "Yes",
    #         "No",
    #         "",
    #         "",
    #         "",
    #         "",
    #         "",
    #         "Group",
    #         "Window_0",
    #     ]
    #
    #     mod.set_variant("Variant_2")
    #
    #     test_cons = mod.building.idf.getobject("Construction", "Construction_Ext_win_1")
    #     assert test_cons.obj == ["CONSTRUCTION", "Construction_Ext_win_1", "Ext_win_1"]
    #
    #     test_cons = mod.building.idf.getobject("Construction", "Construction_Ext_win_2")
    #     assert test_cons.obj == ["CONSTRUCTION", "Construction_Ext_win_2", "Ext_win_2"]
    #
    #     assert mod.shaded_window_constructions == []
    #     assert mod.shading_materials == []
    #     assert mod.shading_control == []
    #
    # def test_envelope_infiltration_modifier(self, toy_building):
    #     loc_toy = deepcopy(toy_building)
    #
    #     var = {"poor": {"ach": 0.1}, "good": {"q4pa": 0.1}, "wtf": {}}
    #
    #     inf = InfiltrationModifier(building=loc_toy, name="test", variant_dict=var)
    #
    #     inf.set_variant("poor")
    #
    #     assert len(inf.infiltration_objects) == 4
    #     assert inf.infiltration_objects[0].obj == [
    #         "ZONEINFILTRATION:DESIGNFLOWRATE",
    #         "zone_0_infiltration",
    #         "zone_0",
    #         "On 24/7",
    #         "AirChanges/Hour",
    #         "",
    #         "",
    #         "",
    #         0.1,
    #         1,
    #         0,
    #         0,
    #         0,
    #     ]
    #     assert inf.building.idf.getobject("Schedule:Compact", "On 24/7")
    #
    # def test_lights_modifier(self, toy_building):
    #     loc_toy = deepcopy(toy_building)
    #     var = {
    #         "poor": 10,
    #         "good": 4,
    #     }
    #     lit = LightsModifier(building=loc_toy, name="test", variant_dict=var)
    #
    #     lit.set_variant("good")
    #
    #     power_ratio_list = energytool.base.idf_utils.get_named_objects_field_values(
    #         loc_toy.idf, "Lights", "Watts_per_Zone_Floor_Area"
    #     )
    #     assert power_ratio_list == [4, 4, 4, 4]
    #
    # def test_system_modifier(self, toy_building):
    #     loc_toy = deepcopy(toy_building)
    #
    #     old_boil = st.HeaterSimple(name="Old_boiler", building=loc_toy)
    #     loc_toy.heating_system["Main_boiler"] = old_boil
    #
    #     new_boil = st.HeaterSimple(name="New_boiler", building=toy_building)
    #
    #     variant_dict = {"Variant1": new_boil}
    #
    #     system_mod = SystemModifier(
    #         building=toy_building,
    #         name="sysmod",
    #         category="heating_system",
    #         system_name="Main_boiler",
    #         variant_dict=variant_dict,
    #     )
    #
    #     system_mod.building = loc_toy
    #     system_mod.set_variant("Variant1")
    #
    #     assert loc_toy.heating_system["Main_boiler"].name == "New_boiler"
    #     assert loc_toy == loc_toy.heating_system["Main_boiler"].building
    #
    # def test_combiner(self):
    #     building = Building(idf_path=RESOURCES_PATH / "test.idf")
    #     building.heating_system = {
    #         "Main_heater": st.HeaterSimple(name="Old_boiler", building=building, cop=1)
    #     }
    #
    #     modifier_list = []
    #
    #     infiltration_variant_dict = {
    #         "good": {"q4pa": 0.5},
    #     }
    #
    #     modifier_list.append(
    #         mo.InfiltrationModifier(
    #             name="Infiltration", variant_dict=infiltration_variant_dict
    #         )
    #     )
    #
    #     boiler_variant_dict = {
    #         "PAC": st.HeaterSimple(name="PAC", cop=3, building=building)
    #     }
    #
    #     modifier_list.append(
    #         mo.SystemModifier(
    #             name="heater_modifier",
    #             category="heating_system",
    #             system_name="Main_heater",
    #             variant_dict=boiler_variant_dict,
    #         )
    #     )
    #
    #     combiner = mo.Combiner(building, modifier_list=modifier_list)
    #
    #     combiner.run(
    #         epw_file_path=RESOURCES_PATH / "Paris_2020.epw", timestep_per_hour=1
    #     )
    #
    #     to_test = combiner.get_annual_system_results()
    #
    #     assert math.floor(to_test.loc[1, "Heating"]) == math.floor(
    #         to_test.loc[0, "Heating"] / 3
    #     )
    #     assert to_test.loc[0, "Heating"] > to_test.loc[2, "Heating"]
    #     assert math.floor(to_test.loc[3, "Heating"]) == math.floor(
    #         to_test.loc[2, "Heating"] / 3
    #     )
