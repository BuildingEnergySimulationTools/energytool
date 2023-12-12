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
from energytool.building import Building
from energytool.modifier import (
    set_opaque_surface_construction,
    set_external_windows,
    set_afn_surface_opening_factor,
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

    toy_idf.newidfobject("WindowMaterial:Shade", Name="Shade")

    toy_idf.newidfobject(
        key="Construction",
        Name="Construction_Ext_win_1_shade",
        Outside_Layer="Shade",
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

    energytool.base.idf_utils.set_named_objects_field_values(
        idf=toy_idf,
        idf_object="FenestrationSurface:Detailed",
        field_name="Construction_Name",
        values=[
            "Construction_Ext_win_2",
            "Construction_Int_win",
            "Construction_Ext_win_1",
            "Construction_Ext_win_1",
        ],
    )

    toy_idf.newidfobject(
        key="WINDOWSHADINGCONTROL",
        Name="zone_0_Shading_control",
        Zone_Name="zone_0",
        Shading_Type="ExteriorShade",
        Construction_with_Shading_Name="Construction_Ext_win_1_shade",
        Fenestration_Surface_1_Name="Window_2",
    )

    toy_idf.newidfobject(
        key="WINDOWSHADINGCONTROL",
        Name="zone_3_Shading_control",
        Zone_Name="zone_3",
        Shading_Type="ExteriorShade",
        Construction_with_Shading_Name="Construction_Ext_win_1_shade",
        Fenestration_Surface_1_Name="Window_3",
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
        ) == ["Shade", "Var_1", "Var_1", "Int_win"]

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
        ) == ["Shade", "Var_2", "Var_2", "Int_win"]

        assert get_named_objects_field_values(
            loc_toy.idf, "Construction", "Layer_2"
        ) == [
            "Var_2",
            "",
            "",
            "",
        ]

        set_external_windows(loc_toy, var_0, name_filter="_0")

        assert get_objects_name_list(
            loc_toy.idf, "WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM"
        ) == ["Int_win", "Var_2", "Var_1"]

        assert get_named_objects_field_values(
            loc_toy.idf, "Construction", "Outside_Layer"
        ) == ["Shade", "Var_2", "Var_1", "Int_win"]

        assert True

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
