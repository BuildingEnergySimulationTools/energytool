from io import StringIO
from pathlib import Path

import energytool.epluspreprocess as pr
import energytool.modifier as mo

import pytest
import eppy

from eppy.modeleditor import IDF
from energytool.building import Building
from energytool.modifier import OpaqueSurfaceModifier
from energytool.modifier import InfiltrationModifier
from energytool.modifier import EnvelopeShadesModifier
from copy import deepcopy

RESOURCES_PATH = Path(__file__).parent / "resources"

try:
    IDF.setiddname(RESOURCES_PATH / 'Energy+.idd')
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
        toy_idf.newidfobject(
            key="Zone",
            Name=f"zone_{toy_zone}"
        )

    win_names = ["Ext_win_1", "Ext_win_2", "Int_win"]

    for win in win_names:
        toy_idf.newidfobject(
            key="WindowMaterial:SimpleGlazingSystem",
            Name=win
        )

    toy_idf.newidfobject(
        "WindowMaterial:Shade", Name="Shade")

    toy_idf.newidfobject(
        key="Construction",
        Name="Construction_Ext_win_1_shade",
        Outside_Layer="Shade",
        Layer_2="Ext_win_1"
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
        Name=f"Construction_Int_win",
        Outside_Layer="Int_win",
    )

    for toy_surf in range(6):
        toy_idf.newidfobject(
            "BuildingSurface:Detailed",
            Name=f"Surface_{toy_surf}",
        )

    pr.set_objects_field_values(
        idf=toy_idf,
        idf_object="BuildingSurface:Detailed",
        field_name="Surface_Type",
        values=["Wall", "Wall", "Floor", "Ceiling", "Roof", "Wall"]
    )

    pr.set_objects_field_values(
        idf=toy_idf,
        idf_object="BuildingSurface:Detailed",
        field_name="Outside_Boundary_Condition",
        values=["Outdoors", "Surface", "Ground", "Surface", "Outdoors",
                "Outdoors"]
    )

    pr.set_objects_field_values(
        idf=toy_idf,
        idf_object="BuildingSurface:Detailed",
        field_name="Zone_Name",
        values=["zone_0", "Zone_1", "zone_0", "zone_2", "zone_0", "zone_3"]
    )

    for idx, sur in enumerate(
            ["Surface_0", "Surface_1", "Surface_4", "Surface_5"]):
        toy_idf.newidfobject(
            key="FenestrationSurface:Detailed",
            Name=f"Window_{idx}",
            Building_Surface_Name=sur
        )

    pr.set_objects_field_values(
        idf=toy_idf,
        idf_object="FenestrationSurface:Detailed",
        field_name="Construction_Name",
        values=["Construction_Ext_win_2", "Construction_Int_win",
                "Construction_Ext_win_1", "Construction_Ext_win_1"]
    )

    toy_idf.newidfobject(
        key='WINDOWSHADINGCONTROL',
        Name='zone_0_Shading_control',
        Zone_Name='zone_0',
        Shading_Type='ExteriorShade',
        Construction_with_Shading_Name='Construction_Ext_win_1_shade',
        Fenestration_Surface_1_Name='Window_2',
    )

    toy_idf.newidfobject(
        key='WINDOWSHADINGCONTROL',
        Name='zone_3_Shading_control',
        Zone_Name='zone_3',
        Shading_Type='ExteriorShade',
        Construction_with_Shading_Name='Construction_Ext_win_1_shade',
        Fenestration_Surface_1_Name='Window_3',
    )

    # Very dirty, instantiate a Building with and idf file
    # Replace it wih toy_idf
    toy_building = Building(idf_path=RESOURCES_PATH / "test.idf")
    toy_building.idf = toy_idf

    return toy_building


class TestModifier:
    def test_opaque_surface_modifier(self, toy_building):
        loc_toy = deepcopy(toy_building)

        construction_variant_dict = {
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
            ],
            "test_1_layer": [
                {
                    "Name": "Coating_2",
                    "Thickness": 0.01,
                    "Conductivity": 0.1,
                    "Density": 400,
                    "Specific_Heat": 1200,
                },
            ]
        }

        ext_walls_mod = OpaqueSurfaceModifier(
            building=loc_toy,
            name="Ext_wall_modification",
            surface_type="Wall",
            outside_boundary_condition="Outdoors",
            construction_variant_dict=construction_variant_dict
        )

        # Test general case
        ext_walls_mod.set_variant("test_base")
        material_list = loc_toy.idf.idfobjects["Material"]
        print(material_list)
        assert material_list[0]['obj'] == [
            'MATERIAL', 'Coating', 'Rough', 0.01, 0.1, 400, 1200, 0.9, 0.7,
            0.7]
        assert pr.get_objects_name_list(loc_toy.idf, "Material") == [
            'Coating', 'Laine_15cm']

        construction_list = loc_toy.idf.idfobjects["Construction"]
        assert construction_list[-1]['obj'] == [
            'CONSTRUCTION', 'test_base', 'Coating', 'Laine_15cm']

        to_test = pr.get_objects_field_values(
            idf=loc_toy.idf,
            idf_object="BuildingSurface:Detailed",
            field_name="Construction_Name"
        )
        assert to_test == ['test_base', '', '', '', '', 'test_base']

        # Test single layer construction
        ext_walls_mod.set_variant("test_1_layer")
        assert construction_list[-1]['obj'] == [
            'CONSTRUCTION', 'test_1_layer', 'Coating_2']

        # No duplication
        ext_walls_mod.set_variant("test_1_layer")
        assert pr.get_objects_name_list(loc_toy.idf, "Material") == [
            'Coating', 'Laine_15cm', 'Coating_2']

    def test_external_windows_modifier(self, toy_building):
        loc_toy = deepcopy(toy_building)

        test_win_variant_dict = {
            "Variant_1": {
                "Name": "Var_1",
                "UFactor": 1,
                "Solar_Heat_Gain_Coefficient": 0.1,
                "Visible_Transmittance": 0.1,
            },
            "Variant_2": {
                "Name": "Var_2",
                "UFactor": 2,
                "Solar_Heat_Gain_Coefficient": 0.2,
                "Visible_Transmittance": 0.2,
            }
        }

        win_test = mo.ExternalWindowsModifier(
            building=loc_toy,
            name="test",
            window_variant_dict=test_win_variant_dict
        )

        win_test.set_variant("Variant_1")

        assert win_test.windows_materials[0].fieldvalues == [
            'WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM', 'Var_1', 1, 0.1, 0.1]

        assert pr.get_objects_field_values(
            loc_toy.idf, "Construction", 'Outside_Layer') == [
                   'Shade', 'Var_1', 'Var_1', 'Int_win']

        assert pr.get_objects_field_values(
            loc_toy.idf, "Construction", 'Layer_2') == ['Var_1', '', '', '']

        win_test.set_variant("Variant_2")

        assert win_test.windows_materials[0].fieldvalues == [
            'WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM', 'Var_2', 2, 0.2, 0.2]

        assert pr.get_objects_field_values(
            loc_toy.idf, "Construction", 'Outside_Layer') == [
                   'Shade', 'Var_2', 'Var_2', 'Int_win']

        assert pr.get_objects_field_values(
            loc_toy.idf, "Construction", 'Layer_2') == ['Var_2', '', '', '']

    def test_envelope_shades_modifier(self, toy_building):
        loc_toy = deepcopy(toy_building)

        test_shade_variant_dict = {
            "Variant_1": {
                "shading": {
                    "Name": "Shading",
                    "Solar_Transmittance": 0.3
                },
            },
            "Variant_2": {
                "shading": {}
            }
        }

        mod = EnvelopeShadesModifier(
            building=loc_toy,
            name="test",
            shade_variant_dict=test_shade_variant_dict
        )

        mod.set_variant("Variant_1")
        assert [n.Name for n in mod.windows] == [
            'Window_0', 'Window_2', 'Window_3']

        for n in mod.window_constructions:
            assert n.Name in [
                "Construction_Ext_win_2", "Construction_Ext_win_1"]

        for n in mod.shaded_window_constructions:
            assert n.Name in [
                "Construction_Ext_win_1_shaded",
                "Construction_Ext_win_2_shaded"]

        test_cons = mod.building.idf.getobject(
            "Construction", "Construction_Ext_win_2_shaded")
        assert test_cons.obj == [
            'CONSTRUCTION', 'Construction_Ext_win_2_shaded', 'Shading',
            'Ext_win_2']

        assert len(mod.shading_materials) == 1
        assert mod.shading_materials[0].obj == [
            'WINDOWMATERIAL:SHADE',
            'Shading',
            0.3,
            0.5,
            0.4,
            0.5,
            0.9,
            0.0,
            0.003,
            0.1,
            0.05,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0]
        assert len(mod.shading_control) == 3
        assert mod.shading_control[0].obj == [
            'WINDOWSHADINGCONTROL',
            'zone_0_Construction_Ext_win_2_Shading_control',
            'zone_0',
            '',
            'ExteriorShade',
            'Construction_Ext_win_2_shaded',
            'OnIfScheduleAllows',
            '',
            '',
            'Yes',
            'No',
            '',
            '',
            '',
            '',
            '',
            'Group',
            'Window_0']

        mod.set_variant("Variant_2")

        test_cons = mod.building.idf.getobject(
            "Construction", "Construction_Ext_win_1")
        assert test_cons.obj == [
            'CONSTRUCTION', 'Construction_Ext_win_1', 'Ext_win_1']

        test_cons = mod.building.idf.getobject(
            "Construction", "Construction_Ext_win_2")
        assert test_cons.obj == [
            'CONSTRUCTION', 'Construction_Ext_win_2', 'Ext_win_2']

        assert mod.shaded_window_constructions == []
        assert mod.shading_materials == []
        assert mod.shading_control == []

    def test_envelope_infiltration_modifier(self, toy_building):
        loc_toy = deepcopy(toy_building)

        var = {
            "poor": {"ach": 0.1},
            "good": {"q4pa": 0.1},
            "wtf": {}
        }

        inf = InfiltrationModifier(
            building=loc_toy,
            name="test",
            infiltration_variant_dict=var)

        inf.set_variant("poor")

        assert len(inf.infiltration_objects) == 4
        assert inf.infiltration_objects[0].obj == [
            'ZONEINFILTRATION:DESIGNFLOWRATE',
            'zone_0_infiltration',
            'zone_0',
            'On 24/7',
            'AirChanges/Hour',
            '',
            '',
            '',
            0.1,
            1,
            0,
            0,
            0]
        assert inf.building.idf.getobject("Schedule:Compact", "On 24/7")
